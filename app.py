# app.py
# Flask + SQLite backend com Estratégia PRO integrada e execução de ordens na Huobi
# Requisitos pip:
# pip install flask huobi-client apscheduler numpy

from flask import Flask, request, jsonify
import sqlite3
import os
import time
import threading
from datetime import datetime, timedelta
import math
import statistics

# Huobi SDK imports (assume huobi-client package)
try:
    from huobi.client.market import MarketClient
    from huobi.client.account import AccountClient
    from huobi.client.trade import TradeClient
    from huobi.constant import OrderType
except Exception:
    MarketClient = None
    AccountClient = None
    TradeClient = None
    OrderType = None

# -------------------------
# Config
# -------------------------
DB_FILE = os.getenv("DB_FILE", "users.db")
HUOBI_API_KEY = os.getenv("HUOBI_API_KEY")
HUOBI_API_SECRET = os.getenv("HUOBI_API_SECRET")

# How often strategy loop checks (seconds)
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", 60))  # default 60s

# initial virtual balance per user (when registering)
DEFAULT_INITIAL_BALANCE = float(os.getenv("DEFAULT_INITIAL_BALANCE", "100.0"))

# pyramid starting lot for altcoins vs btc-like can be configured per user if wanted
PIRAMIDE_MULT = 1.3
PIRAMIDE_START = 40.0  # USD

# trailing stop base factor
TRAILING_STOP_FACTOR = 0.90  # 10% below peak by default (adaptive via ATR later)

# stop time (days) to liquidate half if no +5%
STOP_TIME_DAYS = 60

# stop global percent from equity top
STOP_GLOBAL_PCT = 0.25  # 25%

# Monthly deposit
MONTHLY_DEPOSIT = 500.0

# -------------------------
# Init Huobi clients (if available)
# -------------------------
market_client = None
account_client = None
trade_client = None
huobi_account_id_cache = None

if HUOBI_API_KEY and HUOBI_API_SECRET and MarketClient is not None:
    try:
        market_client = MarketClient()
        account_client = AccountClient(api_key=HUOBI_API_KEY, secret_key=HUOBI_API_SECRET)
        trade_client = TradeClient(api_key=HUOBI_API_KEY, secret_key=HUOBI_API_SECRET)
    except Exception as e:
        print("Warning: failed to init Huobi clients:", e)
else:
    print("Huobi SDK not configured or not installed - running strategy in simulation mode.")


# -------------------------
# DB helpers
# -------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT,
            balance REAL,
            cash REAL,
            next_lot REAL,
            max_equity REAL,
            last_deposit TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            symbol TEXT,
            qty REAL,
            avg_price REAL,
            entry_time TEXT,
            trailing_stop REAL,
            last_profit_check_price REAL,
            last_checked TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT,
            symbol TEXT,
            qty REAL,
            price REAL,
            info TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()


# -------------------------
# Utility: DB CRUD
# -------------------------
def db_execute(query, params=(), fetch=False):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, params)
    if fetch:
        rows = c.fetchall()
        conn.commit()
        conn.close()
        return rows
    conn.commit()
    conn.close()
    return None

# get user record
def get_user(user_id):
    rows = db_execute("SELECT user_id, email, balance, cash, next_lot, max_equity, last_deposit FROM users WHERE user_id=?", (user_id,), fetch=True)
    if not rows:
        return None
    u = rows[0]
    return {
        "user_id": u[0],
        "email": u[1],
        "balance": float(u[2]),
        "cash": float(u[3]),
        "next_lot": float(u[4]),
        "max_equity": float(u[5]),
        "last_deposit": u[6]
    }

def create_user_db(user_id, email=None, initial_balance=DEFAULT_INITIAL_BALANCE):
    existing = get_user(user_id)
    if existing:
        return existing
    db_execute("INSERT INTO users (user_id, email, balance, cash, next_lot, max_equity, last_deposit) VALUES (?,?,?,?,?,?,?)",
               (user_id, email, initial_balance, initial_balance, PIRAMIDE_START, initial_balance, datetime.utcnow().isoformat()))
    return get_user(user_id)

def update_user_balance_and_lot(user_id, new_balance, new_cash, next_lot=None, max_equity=None):
    user = get_user(user_id)
    if not user:
        return None
    nl = next_lot if next_lot is not None else user["next_lot"]
    me = max_equity if max_equity is not None else user["max_equity"]
    db_execute("UPDATE users SET balance=?, cash=?, next_lot=?, max_equity=?, last_deposit=? WHERE user_id=?",
               (new_balance, new_cash, nl, me, user["last_deposit"], user_id))
    return get_user(user_id)

def save_history(user_id, action, symbol, qty, price, info=""):
    db_execute("INSERT INTO history (user_id, action, symbol, qty, price, info, timestamp) VALUES (?,?,?,?,?,?,?)",
               (user_id, action, symbol, qty, price, info, datetime.utcnow().isoformat()))

def get_history(user_id):
    rows = db_execute("SELECT action, symbol, qty, price, info, timestamp FROM history WHERE user_id=? ORDER BY id DESC", (user_id,), fetch=True)
    return [{"action": r[0], "symbol": r[1], "qty": r[2], "price": r[3], "info": r[4], "time": r[5]} for r in rows]

def add_position(user_id, symbol, qty, avg_price, trailing_stop):
    db_execute("INSERT INTO positions (user_id, symbol, qty, avg_price, entry_time, trailing_stop, last_profit_check_price, last_checked) VALUES (?,?,?,?,?,?,?,?)",
               (user_id, symbol, qty, avg_price, datetime.utcnow().isoformat(), trailing_stop, avg_price, datetime.utcnow().isoformat()))

def get_positions(user_id):
    rows = db_execute("SELECT id, symbol, qty, avg_price, entry_time, trailing_stop FROM positions WHERE user_id=?", (user_id,), fetch=True)
    return [{"id": r[0], "symbol": r[1], "qty": float(r[2]), "avg_price": float(r[3]), "entry_time": r[4], "trailing_stop": float(r[5])} for r in rows]

def update_position_qty_and_stop(pos_id, new_qty, new_stop):
    if new_qty <= 0:
        db_execute("DELETE FROM positions WHERE id=?", (pos_id,))
        return
    db_execute("UPDATE positions SET qty=?, trailing_stop=?, last_checked=? WHERE id=?", (new_qty, new_stop, datetime.utcnow().isoformat(), pos_id))

def delete_position(pos_id):
    db_execute("DELETE FROM positions WHERE id=?", (pos_id,))

# -------------------------
# Technical indicators helpers
# -------------------------
# candles: list of dicts with keys: timestamp, open, high, low, close, volume
def sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period

def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema_prev = values[0]
    for v in values[1:]:
        ema_prev = v * k + ema_prev * (1 - k)
    return ema_prev

def compute_sma_list(values, period):
    return [ (sum(values[i-period+1:i+1]) / period) if i+1 >= period else None for i in range(len(values)) ]

def macd_line(values, fast=12, slow=26, signal=9):
    # compute EMA fast and slow, then macd and signal
    if len(values) < slow + signal:
        return None, None
    # compute EMA arrays
    ema_fast = []
    ema_slow = []
    k_fast = 2/(fast+1)
    k_slow = 2/(slow+1)
    # seed with first value
    ema_f = values[0]
    ema_s = values[0]
    for v in values:
        ema_f = v*k_fast + ema_f*(1-k_fast)
        ema_s = v*k_slow + ema_s*(1-k_slow)
        ema_fast.append(ema_f)
        ema_slow.append(ema_s)
    macd = [f - s for f,s in zip(ema_fast, ema_slow)]
    # signal as EMA of macd
    sig = macd[0]
    for m in macd:
        sig = m*(2/(signal+1)) + sig*(1-2/(signal+1))
    hist = macd[-1] - sig
    return macd[-1], sig  # return macd last and signal

def rsi(values, period=14):
    if len(values) < period+1:
        return None
    gains = []
    losses = []
    for i in range(1, period+1):
        delta = values[-i] - values[-i-1]
        if delta > 0:
            gains.append(delta)
        else:
            losses.append(abs(delta))
    avg_gain = sum(gains)/period if gains else 0.0
    avg_loss = sum(losses)/period if losses else 0.0
    if avg_loss == 0:
        return 100
    rs = avg_gain/avg_loss
    return 100 - (100/(1+rs))

def atr(candles, period=14):
    # candles list with high, low, close
    if len(candles) < period+1:
        return None
    trs = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i-1]["close"]
        tr = max(high-low, abs(high-prev_close), abs(low-prev_close))
        trs.append(tr)
    # ATR is SMA of TRs last 'period'
    return sum(trs[-period:]) / period

# -------------------------
# Market data from Huobi
# -------------------------
def fetch_klines(symbol, period="1day", size=200):
    """
    Returns list of candles dict {timestamp, open, high, low, close, vol}
    period examples: '1min','5min','15min','30min','60min','4hour','1day','1week'
    """
    if market_client is None:
        # simulation: return synthetic candles (very rough)
        now = int(time.time())
        candles = []
        price = 50000
        for i in range(size):
            close = price + (math.sin(i/10) * 2000) + (i % 5)*10
            openp = close - (math.cos(i/8)*100)
            high = max(openp, close) + 100
            low = min(openp, close) - 100
            candles.append({
                "id": now - (size-i)*86400,
                "open": openp,
                "high": high,
                "low": low,
                "close": close,
                "vol": 10 + i
            })
            price = close
        return candles
    try:
        # huobi python SDK MarketClient has get_candlestick(symbol, period, size)
        klines = market_client.get_candlestick(symbol, period, size)
        candles = []
        for k in klines:
            candles.append({
                "id": k.id,
                "open": float(k.open),
                "high": float(k.high),
                "low": float(k.low),
                "close": float(k.close),
                "vol": float(k.vol)
            })
        return candles
    except Exception as e:
        print("Error fetching klines:", e)
        return []

# -------------------------
# Huobi order helper (real execution)
# -------------------------
def get_huobi_account_id():
    global huobi_account_id_cache
    if huobi_account_id_cache:
        return huobi_account_id_cache
    if account_client is None:
        return None
    try:
        accounts = account_client.get_accounts()
        if not accounts:
            return None
        huobi_account_id_cache = accounts[0].id
        return huobi_account_id_cache
    except Exception as e:
        print("Error getting huobi account id:", e)
        return None

def place_market_order_huobi(symbol, side, amount):
    """
    place market order on Huobi.
    amount here is quantity in base currency for market orders for some SDKs could be in quote.
    You must adapt amount/params to your integration / account type.
    """
    if trade_client is None:
        return {"status": "simulated", "message": "Huobi client not configured", "symbol": symbol, "side": side, "amount": amount}
    try:
        account_id = get_huobi_account_id()
        # Many Huobi SDKs accept create_order with order_type=OrderType.BUY_MARKET or SELL_MARKET and amount as string
        if side.lower() == "buy":
            order_id = trade_client.create_order(symbol=symbol, account_id=account_id, order_type=OrderType.BUY_MARKET, source="api", amount=str(amount))
        else:
            order_id = trade_client.create_order(symbol=symbol, account_id=account_id, order_type=OrderType.SELL_MARKET, source="api", amount=str(amount))
        return {"status": "ok", "order_id": order_id}
    except Exception as e:
        print("Error placing huobi order:", e)
        return {"status": "error", "message": str(e)}

# -------------------------
# Strategy Core
# -------------------------
def evaluate_user_strategy(user_id, symbol="btcusdt"):
    """
    Main strategy evaluator for a single user.
    - fetch candles weekly and daily
    - check conditions
    - place buys according to pyramid if conditions ok
    - check partial sells based on profit thresholds
    - trailing stop checks
    - stop-time (60 days) check: if position older than STOP_TIME_DAYS and no +5% -> sell 50%
    - stop-global handled separately within run loop (via max_equity)
    """
    user = get_user(user_id)
    if not user:
        return {"status": "error", "message": "user not found"}

    # fetch weekly candles for MACD/RSI weekly
    weekly = fetch_klines(symbol, period="1week", size=100)
    daily = fetch_klines(symbol, period="1day", size=200)

    # compute indicators
    closes_week = [c["close"] for c in weekly]
    closes_daily = [c["close"] for c in daily]

    # MM200/50 using daily
    mm200 = sma(closes_daily, 200) if len(closes_daily) >= 200 else sma(closes_daily, 50)  # fallback
    mm50 = sma(closes_daily, 50) if len(closes_daily) >= 50 else sma(closes_daily, 10)
    macd_val, macd_signal = macd_line(closes_week) if len(closes_week) >= 35 else (None, None)
    rsi_week = rsi(closes_week, period=14) if len(closes_week) >= 15 else None

    # latest price
    price = closes_daily[-1] if closes_daily else (weekly[-1]["close"] if weekly else None)
    if price is None:
        return {"status": "error", "message": "no price data"}

    # compute ATR for volatility (daily)
    atr_val = atr(daily, period=14) if len(daily) >= 15 else None

    # conditions
    cond_price_above_mm200 = (mm200 is not None and price > mm200)
    cond_mm50_gt_mm200 = (mm50 is not None and mm200 is not None and mm50 > mm200)
    cond_macd_pos = (macd_val is not None and macd_val > 0)
    cond_rsi_week = (rsi_week is not None and 50 <= rsi_week <= 70)

    can_buy = all([cond_price_above_mm200, cond_mm50_gt_mm200, cond_macd_pos, cond_rsi_week])

    actions = []

    # update equity and max_equity for stop global
    positions = get_positions(user_id)
    equity = user["cash"]  # cash is free usd for new buys
    for p in positions:
        equity += p["qty"] * price
    if equity > user["max_equity"]:
        # update max equity
        update_user_balance_and_lot(user_id, user["balance"], user["cash"], next_lot=user["next_lot"], max_equity=equity)
        user = get_user(user_id)  # refresh
    # STOP GLOBAL
    if user["max_equity"] and equity < user["max_equity"] * (1 - STOP_GLOBAL_PCT):
        # liquidate all positions
        for p in positions:
            # sell all via huobi (or simulate)
            sell_qty = p["qty"]
            huobi_resp = place_market_order_huobi(p["symbol"], "sell", sell_qty)
            user = get_user(user_id)
            user_cash = user["cash"] + sell_qty * price
            update_user_balance_and_lot(user_id, user["balance"], user_cash, next_lot=PIRAMIDE_START, max_equity=user["max_equity"])
            save_history(user_id, "stop_global_sell", p["symbol"], sell_qty, price, str(huobi_resp))
            delete_position(p["id"])
            actions.append("stop_global_liquidated")
        return {"status": "stop_global", "actions": actions}

    # BUY logic: if conditions met, try to buy next_lot USD (pirâmide)
    if can_buy:
        # fetch current user next_lot and cash
        next_lot = user["next_lot"]
        cash = user["cash"]
        # But adapt lot if RSI>75 reduce or RSI<40 increase
        adj_lot = next_lot
        if rsi_week is not None:
            if rsi_week > 75:
                adj_lot = next_lot * 0.7
            elif rsi_week < 40:
                adj_lot = next_lot * 1.2
        # also adapt by volatility: if ATR high relative to price, increase trailing and possibly reduce lot size
        if atr_val:
            atr_ratio = atr_val / price
            if atr_ratio > 0.03:  # arbitrary threshold
                # high volatility => reduce lot by 20%
                adj_lot = adj_lot * 0.8

        adj_lot = round(adj_lot, 2)
        if cash >= adj_lot and adj_lot >= 1:  # minimum 1 USD guard
            qty = adj_lot / price
            # place market buy in huobi with amount = qty or cost param depending on API (we use qty)
            huobi_resp = place_market_order_huobi(symbol, "buy", qty)
            # save position
            trailing_stop = price * TRAILING_STOP_FACTOR
            add_position(user_id, symbol, qty, price, trailing_stop)
            # deduct cash
            new_cash = cash - adj_lot
            # update next_lot
            new_next = round(next_pyramid_lot(next_lot), 2)
            update_user_balance_and_lot(user_id, user["balance"], new_cash, next_lot=new_next)
            save_history(user_id, "buy", symbol, qty, price, str(huobi_resp))
            actions.append(f"buy:{adj_lot}")
        else:
            actions.append("not_enough_cash_or_lot_too_small")

    # SELL logic: iterate positions and check profit thresholds and trailing stops
    positions = get_positions(user_id)
    for p in positions:
        buy_price = p["avg_price"]
        qty = p["qty"]
        profit_pct = (price - buy_price) / buy_price * 100
        sell_pct = sell_portion(profit_pct)
        if sell_pct > 0:
            sell_qty = qty * sell_pct
            huobi_resp = place_market_order_huobi(p["symbol"], "sell", sell_qty)
            # credit cash
            user = get_user(user_id)
            new_cash = user["cash"] + sell_qty * price
            # update DB position qty and trailing stop
            new_qty = qty - sell_qty
            # if sold entire portion, trailing_stop reset handled in update
            update_position_qty_and_stop(p["id"], new_qty, p["trailing_stop"])
            update_user_balance_and_lot(user_id, user["balance"], new_cash)
            save_history(user_id, "partial_sell", p["symbol"], sell_qty, price, str(huobi_resp))
            actions.append(f"partial_sell:{sell_qty}")

        else:
            # trailing stop update
            user = get_user(user_id)
            new_stop = p["trailing_stop"]
            if price > buy_price:
                candidate_stop = price * TRAILING_STOP_FACTOR
                if candidate_stop > new_stop:
                    new_stop = candidate_stop
            # if price below stop => sell all
            if price < new_stop:
                huobi_resp = place_market_order_huobi(p["symbol"], "sell", qty)
                user = get_user(user_id)
                new_cash = user["cash"] + qty * price
                update_user_balance_and_lot(user_id, user["balance"], new_cash)
                save_history(user_id, "trailing_stop_sell", p["symbol"], qty, price, str(huobi_resp))
                delete_position(p["id"])
                actions.append("trailing_stop_executed")
            else:
                # update trailing stop if increased
                update_position_qty_and_stop(p["id"], qty, new_stop)

        # stop time: if position older than STOP_TIME_DAYS and never reached +5% then sell 50%
        entry_time = datetime.fromisoformat(p["entry_time"])
        age_days = (datetime.utcnow() - entry_time).days
        if age_days >= STOP_TIME_DAYS:
            # check if max profit achieved since entry - for simplicity use current profit_pct
            if profit_pct < 5:
                sell_qty = p["qty"] * 0.5
                huobi_resp = place_market_order_huobi(p["symbol"], "sell", sell_qty)
                user = get_user(user_id)
                new_cash = user["cash"] + sell_qty * price
                update_user_balance_and_lot(user_id, user["balance"], new_cash)
                update_position_qty_and_stop(p["id"], p["qty"]-sell_qty, p["trailing_stop"])
                save_history(user_id, "time_stop_partial_sell", p["symbol"], sell_qty, price, str(huobi_resp))
                actions.append("time_stop_partial")

    # monthly deposit: if last_deposit more than 30 days ago, add monthly deposit to cash
    last_dep = user["last_deposit"]
    if last_dep:
        last_dt = datetime.fromisoformat(last_dep)
        if datetime.utcnow() - last_dt >= timedelta(days=30):
            # add deposit
            user = get_user(user_id)
            new_cash = user["cash"] + MONTHLY_DEPOSIT
            update_user_balance_and_lot(user_id, user["balance"], new_cash)
            db_execute("UPDATE users SET last_deposit=? WHERE user_id=?", (datetime.utcnow().isoformat(), user_id))
            save_history(user_id, "monthly_deposit", symbol, 0, 0, f"deposit {MONTHLY_DEPOSIT}")
            actions.append("monthly_deposit")

    return {"status": "ok", "actions": actions, "equity": equity, "cash": get_user(user_id)["cash"]}


# -------------------------
# Background loop (runs strategy for every user periodically)
# -------------------------
def strategy_loop():
    while True:
        try:
            # fetch all users
            rows = db_execute("SELECT user_id FROM users", fetch=True)
            user_ids = [r[0] for r in rows]
            for uid in user_ids:
                try:
                    res = evaluate_user_strategy(uid)
                    if res and res.get("actions"):
                        print(f"[{datetime.utcnow().isoformat()}] user {uid} actions: {res['actions']}")
                except Exception as e:
                    print("Error evaluating strategy for", uid, e)
        except Exception as e:
            print("Error in strategy loop:", e)
        time.sleep(CHECK_INTERVAL_SECONDS)

# start background thread
threading.Thread(target=strategy_loop, daemon=True).start()

# -------------------------
# Flask endpoints for Bubble
# -------------------------
@app.route("/register_user", methods=["POST"])
def http_register_user():
    payload = request.json or {}
    user_id = payload.get("user_id")
    email = payload.get("email")
    balance = float(payload.get("balance", DEFAULT_INITIAL_BALANCE))
    if not user_id:
        return jsonify({"status": "error", "message": "user_id required"}), 400
    u = create_user_db(user_id, email=email, initial_balance=balance)
    return jsonify({"status": "ok", "user": u})

@app.route("/balance", methods=["GET"])
def http_balance():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "user_id required"}), 400
    u = get_user(user_id)
    if not u:
        return jsonify({"status": "error", "message": "user not found"}), 404
    positions = get_positions(user_id)
    history = get_history(user_id)[:20]
    return jsonify({"status": "ok", "user": u, "positions": positions, "history": history})

@app.route("/run_strategy", methods=["POST"])
def http_run_strategy():
    payload = request.json or {}
    user_id = payload.get("user_id")
    symbol = payload.get("symbol", "btcusdt")
    if not user_id:
        return jsonify({"status": "error", "message": "user_id required"}), 400
    res = evaluate_user_strategy(user_id, symbol)
    return jsonify(res)

@app.route("/history", methods=["GET"])
def http_history():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "user_id required"}), 400
    return jsonify({"status": "ok", "history": get_history(user_id)})

# quick endpoint to force deposit (for testing)
@app.route("/deposit", methods=["POST"])
def http_deposit():
    payload = request.json or {}
    user_id = payload.get("user_id")
    amount = float(payload.get("amount", 0))
    if not user_id or amount <= 0:
        return jsonify({"status": "error", "message": "user_id and positive amount required"}), 400
    user = get_user(user_id)
    if not user:
        return jsonify({"status": "error", "message": "user not found"}), 404
    update_user_balance_and_lot(user_id, user["balance"], user["cash"] + amount)
    save_history(user_id, "manual_deposit", "", 0, 0, f"deposit {amount}")
    return jsonify({"status": "ok", "new_cash": get_user(user_id)["cash"]})

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    print("Starting Flask app with Strategy PRO. Huobi configured:", bool(trade_client))
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

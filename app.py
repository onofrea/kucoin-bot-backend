from flask import Flask, request, jsonify
import random
import datetime

app = Flask(__name__)

# Banco de dados em memória
users_data = {}

# ======================
# Funções auxiliares
# ======================

def create_user(user_id, initial_balance=100):
    """Cria usuário com saldo inicial"""
    users_data[user_id] = {
        "balance": initial_balance,
        "positions": [],
        "history": [],
        "next_lot": 40,         # valor inicial da pirâmide
        "max_equity": initial_balance  # topo histórico para stop global
    }

def get_price(symbol):
    """Simulação de preço (substituir por API HTX depois)"""
    return random.uniform(5000, 70000) if symbol == "btcusdt" else random.uniform(0.01, 10)

def strategy_conditions(price, symbol):
    """Condições de entrada da Estratégia PRO (simuladas)"""
    return {
        "trend_up": price > 20000,
        "macd_pos": True,
        "rsi_ok": 50 < random.randint(30, 80) < 70
    }

def calc_equity(user, current_price):
    """Calcula valor total (saldo + posições abertas)"""
    equity = user["balance"]
    for pos in user["positions"]:
        equity += pos["amount"] * current_price
    return equity

# ======================
# Estratégia PRO
# ======================

def run_strategy(user_id, symbol="btcusdt"):
    user = users_data.get(user_id)
    if not user:
        return {"status": "error", "message": "Usuário não encontrado"}

    price = get_price(symbol)
    cond = strategy_conditions(price, symbol)
    result_log = []

    # Atualiza topo histórico
    equity = calc_equity(user, price)
    if equity > user["max_equity"]:
        user["max_equity"] = equity

    # ---------------------
    # STOP GLOBAL
    # ---------------------
    if equity < user["max_equity"] * 0.75:  # -25% do topo
        for pos in user["positions"]:
            gain = pos["amount"] * price
            user["balance"] += gain
        user["history"].append(f"⚠️ Stop Global acionado! Tudo vendido a {price:.2f}")
        user["positions"] = []
        user["next_lot"] = 40
        return {"status": "stop", "message": "Stop global acionado"}

    # ---------------------
    # COMPRA em pirâmide
    # ---------------------
    if cond["trend_up"] and cond["macd_pos"] and cond["rsi_ok"]:
        lot = user["next_lot"]
        if user["balance"] >= lot:
            amount = lot / price
            user["positions"].append({
                "symbol": symbol,
                "amount": amount,
                "buy_price": price,
                "trailing_stop": price * 0.9,  # 10% abaixo da compra
                "date": str(datetime.datetime.now())
            })
            user["balance"] -= lot
            user["history"].append(f"✅ Compra {amount:.6f} {symbol} a {price:.2f} (lote {lot})")
            # Próximo lote = +30% do anterior
            user["next_lot"] = int(lot * 1.3)
            result_log.append(f"Compra realizada: {lot} USD")
        else:
            result_log.append("Saldo insuficiente para nova compra")

    # ---------------------
    # VENDA parcial progressiva
    # ---------------------
    new_positions = []
    for pos in user["positions"]:
        profit_pct = (price - pos["buy_price"]) / pos["buy_price"] * 100

        if profit_pct >= 40:
            sell_pct = 0.3
        elif profit_pct >= 20:
            sell_pct = 0.2
        elif profit_pct >= 10:
            sell_pct = 0.15
        elif profit_pct >= 5:
            sell_pct = 0.1
        else:
            sell_pct = 0

        if sell_pct > 0:
            sell_amount = pos["amount"] * sell_pct
            gain = sell_amount * price
            user["balance"] += gain
            pos["amount"] -= sell_amount
            user["history"].append(f"💰 Venda {sell_pct*100:.0f}% ({sell_amount:.6f}) {symbol} a {price:.2f} (+{profit_pct:.1f}%)")
            result_log.append(f"Venda parcial {sell_pct*100:.0f}%")

        # ---------------------
        # TRAILING STOP adaptativo
        # ---------------------
        if price > pos["buy_price"]:  # só ativa se houver lucro
            new_stop = price * 0.9
            if new_stop > pos["trailing_stop"]:
                pos["trailing_stop"] = new_stop

        if price < pos["trailing_stop"]:
            # stop executado
            gain = pos["amount"] * price
            user["balance"] += gain
            user["history"].append(f"⛔ Trailing Stop executado! {pos['amount']:.6f} {symbol} a {price:.2f}")
        else:
            if pos["amount"] > 0:
                new_positions.append(pos)

    user["positions"] = new_positions

    if result_log:
        return {"status": "ok", "actions": result_log, "balance": user["balance"]}
    return {"status": "hold", "message": "Nenhuma ação"}

# ======================
# Rotas Flask
# ======================

@app.route("/register_user", methods=["POST"])
def register_user():
    data = request.json
    user_id = data.get("user_id")
    initial_balance = data.get("balance", 100)
    if user_id in users_data:
        return jsonify({"status": "error", "message": "Usuário já existe"})
    create_user(user_id, initial_balance)
    return jsonify({"status": "ok", "user": user_id, "balance": initial_balance})

@app.route("/balance/<user_id>")
def balance(user_id):
    user = users_data.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "Usuário não encontrado"})
    return jsonify({
        "user": user_id,
        "balance": user["balance"],
        "positions": user["positions"]
    })

@app.route("/history/<user_id>")
def history(user_id):
    user = users_data.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "Usuário não encontrado"})
    return jsonify({"user": user_id, "history": user["history"]})

@app.route("/run_strategy/<user_id>", methods=["POST"])
def run_strategy_route(user_id):
    data = request.json or {}
    symbol = data.get("symbol", "btcusdt")
    result = run_strategy(user_id, symbol)
    return jsonify(result)

# ======================
# Start
# ======================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

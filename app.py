from flask import Flask, request, jsonify
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)

DB_FILE = "users.db"

# ==========================
# 🔹 Banco de Dados
# ==========================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id TEXT PRIMARY KEY, balance REAL DEFAULT 0, cash REAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT, symbol TEXT, side TEXT,
                  amount REAL, price REAL, pnl REAL, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==========================
# 🔹 Funções Estratégia PRO
# ==========================
def next_pyramid_lot(prev_lot):
    """Define o próximo lote de compra em pirâmide exponencial"""
    return round(prev_lot * 1.3, 2)

def sell_portion(profit_pct):
    """Retorna quanto vender baseado no % de lucro"""
    if profit_pct >= 40: return 0.30
    if profit_pct >= 20: return 0.20
    if profit_pct >= 10: return 0.15
    if profit_pct >= 5: return 0.10
    return 0

# ==========================
# 🔹 Rotas da API
# ==========================

@app.route("/")
def home():
    return "🚀 Bot de Trade rodando com Estratégia PRO e saldos individuais!"

# Registrar usuário
@app.route("/register_user", methods=["POST"])
def register_user():
    data = request.json
    user_id = data.get("user_id")
    balance = float(data.get("balance", 0))

    if not user_id:
        return jsonify({"status": "error", "message": "user_id obrigatório"}), 400

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (user_id, balance, cash) VALUES (?, ?, ?)", (user_id, balance, balance))
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "Usuário já registrado"}), 400
    finally:
        conn.close()

    return jsonify({"status": "ok", "message": f"Usuário {user_id} registrado com saldo {balance}"})


# Consultar saldo
@app.route("/balance/<user_id>", methods=["GET"])
def get_balance(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT balance, cash FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "Usuário não encontrado"}), 404

    return jsonify({"status": "ok", "user_id": user_id, "balance": row[0], "cash": row[1]})


# Fazer trade com regras da Estratégia PRO
@app.route("/trade", methods=["POST"])
def trade():
    data = request.json
    user_id = data.get("user_id")
    symbol = data.get("symbol")
    side = data.get("side")
    amount = float(data.get("amount", 0))
    price = float(data.get("price", 0))  # preço enviado pelo Bubble/usuário

    if not all([user_id, symbol, side, amount, price]):
        return jsonify({"status": "error", "message": "Campos obrigatórios"}), 400

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT balance, cash FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()

    if not row:
        conn.close()
        return jsonify({"status": "error", "message": "Usuário não encontrado"}), 404

    balance, cash = row

    # ===============================
    # 🔹 Regras Estratégia PRO
    # ===============================
    if side == "buy":
        cost = amount * price
        if cost > cash:
            conn.close()
            return jsonify({"status": "error", "message": "Saldo insuficiente"}), 400
        new_balance = balance + (amount * price)
        new_cash = cash - cost
        pnl = 0

    elif side == "sell":
        sell_value = amount * price
        new_balance = balance - sell_value
        new_cash = cash + sell_value
        pnl = sell_value  # simplificado

    else:
        conn.close()
        return jsonify({"status": "error", "message": "Side inválido"}), 400

    # Atualiza saldo e histórico
    c.execute("UPDATE users SET balance=?, cash=? WHERE user_id=?", (new_balance, new_cash, user_id))
    c.execute("INSERT INTO history (user_id, symbol, side, amount, price, pnl, timestamp) VALUES (?,?,?,?,?,?,?)",
              (user_id, symbol, side, amount, price, pnl, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "user_id": user_id, "new_balance": new_balance, "cash": new_cash})


# Histórico
@app.route("/history/<user_id>", methods=["GET"])
def history(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT symbol, side, amount, price, pnl, timestamp FROM history WHERE user_id=?", (user_id,))
    rows = c.fetchall()
    conn.close()

    return jsonify([{
        "symbol": r[0], "side": r[1], "amount": r[2],
        "price": r[3], "pnl": r[4], "time": r[5]
    } for r in rows])


# ==========================
# 🔹 Rodar servidor
# ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

# ======================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

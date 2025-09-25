import json
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

DATA_FILE = "data.json"

# 🔹 Funções utilitárias
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"balances": {}, "rules": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

data = load_data()
user_balances = data["balances"]
user_rules = data["rules"]


@app.route("/balance", methods=["GET"])
def balance_route():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "user_id obrigatório"}), 400

    saldo = user_balances.get(user_id, 0.0)
    return jsonify({"status": "ok", "user_id": user_id, "saldo": saldo})


@app.route("/reset_balance", methods=["POST"])
def reset_balance():
    req = request.json or {}
    user_id = req.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "user_id obrigatório"}), 400

    user_balances[user_id] = 100.0
    user_rules[user_id] = []
    save_data({"balances": user_balances, "rules": user_rules})

    return jsonify({"status": "ok", "user_id": user_id, "saldo": user_balances[user_id]})


@app.route("/add_rule", methods=["POST"])
def add_rule():
    req = request.json or {}
    user_id = req.get("user_id")
    symbol = req.get("symbol")
    side = req.get("side", "buy")
    target = req.get("target")
    amount = req.get("amount")

    if not user_id or not symbol or not target or not amount:
        return jsonify({"status": "error", "message": "Campos obrigatórios"}), 400

    try:
        amount_val = float(amount)
        target_val = float(target)
    except:
        return jsonify({"status": "error", "message": "Amount/Target inválido"}), 400

    if amount_val <= 0 or target_val <= 0:
        return jsonify({"status": "error", "message": "Valores devem ser > 0"}), 400

    # Inicializa saldo se não existir
    if user_id not in user_balances:
        user_balances[user_id] = 100.0
        user_rules[user_id] = []

    custo = amount_val * target_val

    if custo > user_balances[user_id]:
        return jsonify({"status": "error", "message": "Saldo insuficiente", "saldo_atual": user_balances[user_id]}), 400

    user_balances[user_id] -= custo
    rule = {"symbol": symbol, "side": side, "target": target_val, "amount": amount_val, "custo": custo}
    user_rules[user_id].append(rule)

    # 🔹 salvar no arquivo
    save_data({"balances": user_balances, "rules": user_rules})

    return jsonify({"status": "ok", "rule": rule, "saldo_restante": user_balances[user_id]})


@app.route("/rules", methods=["GET"])
def get_rules():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "user_id obrigatório"}), 400

    return jsonify({"status": "ok", "rules": user_rules.get(user_id, [])})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


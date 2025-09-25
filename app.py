from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

# -------------------------------
# CONFIGURAÇÃO DE ARQUIVOS
# -------------------------------
DATA_FILE = "data.json"

# Estrutura inicial
data = {
    "balances": {},  # {"user123": 100.0}
    "rules": {}      # {"user123": [ {rule1}, {rule2} ]}
}


# -------------------------------
# FUNÇÕES DE PERSISTÊNCIA
# -------------------------------
def load_data():
    global data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                data = json.load(f)
            except:
                data = {"balances": {}, "rules": {}}
    else:
        data = {"balances": {}, "rules": {}}


def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# -------------------------------
# ROTA: Consultar saldo
# -------------------------------
@app.route("/balance", methods=["GET"])
def balance_route():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "user_id obrigatório"}), 400

    saldo = data["balances"].get(user_id, 0.0)
    return jsonify({"status": "ok", "user_id": user_id, "saldo": saldo})


# -------------------------------
# ROTA: Resetar saldo
# -------------------------------
@app.route("/reset_balance", methods=["POST"])
def reset_balance():
    payload = request.json or {}
    user_id = payload.get("user_id")

    if not user_id:
        return jsonify({"status": "error", "message": "user_id obrigatório"}), 400

    data["balances"][user_id] = 100.0  # saldo inicial
    data["rules"][user_id] = []
    save_data()

    return jsonify({"status": "ok", "user_id": user_id, "saldo": data["balances"][user_id]})


# -------------------------------
# ROTA: Adicionar regra
# -------------------------------
@app.route("/add_rule", methods=["POST"])
def add_rule():
    payload = request.json or {}
    user_id = payload.get("user_id")
    symbol = (payload.get("symbol") or "").strip()
    side = (payload.get("side") or "buy").strip()
    target = payload.get("target")
    amount = payload.get("amount")

    if not user_id or not symbol or not target or not amount:
        return jsonify({"status": "error", "message": "Campos obrigatórios (user_id, symbol, target, amount)"}), 400

    try:
        amount_val = float(amount)
        target_val = float(target)
    except:
        return jsonify({"status": "error", "message": "Amount/Target inválido"}), 400

    if amount_val <= 0 or target_val <= 0:
        return jsonify({"status": "error", "message": "Valores devem ser maiores que 0"}), 400

    # Inicializa usuário se não existir
    if user_id not in data["balances"]:
        data["balances"][user_id] = 100.0
        data["rules"][user_id] = []

    custo = amount_val * target_val

    if custo > data["balances"][user_id]:
        return jsonify({
            "status": "error",
            "message": "Saldo insuficiente",
            "saldo_atual": data["balances"][user_id]
        }), 400

    # Desconta saldo
    data["balances"][user_id] -= custo

    # Cria regra
    rule = {
        "symbol": symbol,
        "side": side,
        "target": target_val,
        "amount": amount_val,
        "custo": custo
    }
    data["rules"][user_id].append(rule)

    save_data()

    return jsonify({
        "status": "ok",
        "user_id": user_id,
        "rule": rule,
        "saldo_restante": data["balances"][user_id]
    })


# -------------------------------
# ROTA: Listar regras
# -------------------------------
@app.route("/rules", methods=["GET"])
def get_rules():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "user_id obrigatório"}), 400

    return jsonify({
        "status": "ok",
        "user_id": user_id,
        "rules": data["rules"].get(user_id, [])
    })


# -------------------------------
# HOME
# -------------------------------
@app.route("/")
def home():
    return "🚀 API de Trade Simulada com Persistência JSON!"


# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    load_data()
    app.run(host="0.0.0.0", port=5000)


# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

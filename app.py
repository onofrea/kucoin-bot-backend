from flask import Flask, request, jsonify

app = Flask(__name__)

# -------------------------------
# DADOS EM MEMÓRIA
# -------------------------------
# Saldo por usuário
user_balances = {}   # exemplo: {"user123": 100.0}
# Regras por usuário
user_rules = {}      # exemplo: {"user123": [{"symbol": "btcusdt", "amount": 0.001, ...}]}


# -------------------------------
# ROTA: Consultar saldo
# -------------------------------
@app.route("/balance", methods=["GET"])
def balance_route():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "user_id obrigatório"}), 400

    saldo = user_balances.get(user_id, 0.0)
    return jsonify({"status": "ok", "user_id": user_id, "saldo": saldo})


# -------------------------------
# ROTA: Resetar saldo
# -------------------------------
@app.route("/reset_balance", methods=["POST"])
def reset_balance():
    data = request.json or {}
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"status": "error", "message": "user_id obrigatório"}), 400

    user_balances[user_id] = 100.0  # saldo inicial padrão
    user_rules[user_id] = []

    return jsonify({"status": "ok", "user_id": user_id, "saldo": user_balances[user_id]})


# -------------------------------
# ROTA: Adicionar regra de trade
# -------------------------------
@app.route("/add_rule", methods=["POST"])
def add_rule():
    data = request.json or {}
    user_id = data.get("user_id")
    symbol = (data.get("symbol") or "").strip()
    side = (data.get("side") or "buy").strip()
    target = data.get("target")
    amount = data.get("amount")

    if not user_id or not symbol or not target or not amount:
        return jsonify({"status": "error", "message": "Campos obrigatórios (user_id, symbol, target, amount)"}), 400

    try:
        amount_val = float(amount)
        target_val = float(target)
    except:
        return jsonify({"status": "error", "message": "Amount/Target inválido"}), 400

    if amount_val <= 0 or target_val <= 0:
        return jsonify({"status": "error", "message": "Valores devem ser maiores que 0"}), 400

    # Inicializa se não existir
    if user_id not in user_balances:
        user_balances[user_id] = 100.0
        user_rules[user_id] = []

    # Cálculo do custo
    custo = amount_val * target_val

    # Verifica saldo
    if custo > user_balances[user_id]:
        return jsonify({
            "status": "error",
            "message": "Saldo insuficiente",
            "saldo_atual": user_balances[user_id]
        }), 400

    # Desconta saldo
    user_balances[user_id] -= custo

    # Salva regra
    rule = {
        "symbol": symbol,
        "side": side,
        "target": target_val,
        "amount": amount_val,
        "custo": custo
    }
    user_rules[user_id].append(rule)

    return jsonify({
        "status": "ok",
        "user_id": user_id,
        "rule": rule,
        "saldo_restante": user_balances[user_id]
    })


# -------------------------------
# ROTA: Listar regras do usuário
# -------------------------------
@app.route("/rules", methods=["GET"])
def get_rules():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "user_id obrigatório"}), 400

    return jsonify({
        "status": "ok",
        "user_id": user_id,
        "rules": user_rules.get(user_id, [])
    })


# -------------------------------
# HOME TESTE
# -------------------------------
@app.route("/")
def home():
    return "🚀 API de Trade Simulada rodando!"


# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

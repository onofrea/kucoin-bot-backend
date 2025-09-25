from flask import Flask, request, jsonify

app = Flask(__name__)

# Lista onde as regras ficam armazenadas na memória
rules = []

@app.route("/")
def home():
    return "🚀 Servidor Huobi/KUCOIN rodando!"

@app.route("/rules", methods=["GET"])
def get_rules():
    """
    Retorna todas as regras cadastradas
    """
    return jsonify(rules)

@app.route("/add_rule", methods=["POST"])
def add_rule():
    """
    Adiciona uma nova regra de trade
    Espera receber JSON no formato:
    {
        "symbol": "btcusdt",
        "side": "buy",
        "target": 6000,
        "amount": 0.001
    }
    """
    data = request.json
    symbol = data.get("symbol")
    side = data.get("side")
    target = data.get("target")
    amount = data.get("amount")

    # 🚨 Validação: impede salvar dados inválidos
    if not symbol or not target or not amount:
        return jsonify({"status": "error", "message": "Campos obrigatórios"}), 400

    # Monta a regra
    rule = {
        "symbol": symbol,
        "side": side if side else "buy",  # padrão: buy
        "target": target,
        "amount": amount
    }

    # Salva na lista
    rules.append(rule)

    return jsonify({"status": "ok", "rule": rule}), 201

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

    return jsonify(rules)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

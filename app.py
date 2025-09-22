from flask import Flask, request, jsonify
from kucoin.client import Trade

# 🔑 Suas chaves da KuCoin (pegue em API Management na sua conta)
API_KEY = "68d1d9e754d53500017378c3"
API_SECRET = "6a4b8117-f834-40a3-9078-9b39ffe1dcef"
API_PASSPHRASE = "269826"  # KuCoin pede passphrase também

client = Trade(key=API_KEY, secret=API_SECRET, passphrase=API_PASSPHRASE)

app = Flask(__name__)

@app.route("/")
def home():
    return "🚀 Servidor KuCoin rodando!"

# 📌 Rota para criar ordem de compra ou venda
@app.route("/order", methods=["POST"])
def order():
    data = request.json
    symbol = data.get("symbol")       # Ex: BTC-USDT
    side = data.get("side")           # buy ou sell
    size = data.get("size")           # Ex: 0.001 (quantidade)

    try:
        order = client.create_market_order(
            symbol=symbol,
            side=side,
            size=size
        )
        return jsonify(order)
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

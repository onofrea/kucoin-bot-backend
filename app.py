from flask import Flask, request, jsonify
from kucoin.client import Client
import os

# 🔑 Pegando chaves do ambiente (Render → Environment Variables)
API_KEY = os.getenv("KUCOIN_API_KEY")
API_SECRET = os.getenv("KUCOIN_SECRET_KEY")
API_PASSPHRASE = os.getenv("KUCOIN_PASSPHRASE")

client = Client(API_KEY, API_SECRET, API_PASSPHRASE)

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
    port = int(os.environ.get("PORT", 5000))  # Render escolhe a porta
    app.run(host="0.0.0.0", port=port)


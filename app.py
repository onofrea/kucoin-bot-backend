from flask import Flask, request, jsonify
from binance.client import Client
import os

app = Flask(__name__)

# Pega as chaves do ambiente
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_SECRET_KEY")

client = Client(API_KEY, API_SECRET)

@app.route("/")
def home():
    return "Servidor Binance rodando!"

# 🔍 Rota de teste para ver saldo
@app.route("/test")
def test_credentials():
    try:
        account = client.get_account()
        return jsonify({"status": "ok", "balances": account["balances"]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)




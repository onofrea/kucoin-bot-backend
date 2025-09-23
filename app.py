# app.py
from flask import Flask, request, jsonify
from kucoin.client import Client
import os

app = Flask(__name__)

# pega as chaves do ambiente e remove espaços acidentais
def get_env_trim(name):
    v = os.getenv(name)
    return v.strip() if isinstance(v, str) else v

API_KEY = get_env_trim("KUCOIN_API_KEY")
API_SECRET = get_env_trim("KUCOIN_SECRET_KEY")
API_PASSPHRASE = get_env_trim("KUCOIN_PASSPHRASE")
BUBBLE_SECRET = get_env_trim("BUBBLE_SECRET")  # segredo para proteger /order

client = Client(API_KEY, API_SECRET, API_PASSPHRASE)

@app.route("/")
def home():
    return "Servidor KuCoin rodando!"

# Teste: lista contas (checa se as chaves estão corretas)
@app.route("/test")
def test_credentials():
    try:
        accounts = client.get_accounts()
        return jsonify({"status": "ok", "accounts": accounts})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# Endpoint seguro para criar ordens (recebe POST JSON)
@app.route("/order", methods=["POST"])
def order():
    # autenticação simples: Authorization: Bearer <BUBBLE_SECRET>
    auth = request.headers.get("Authorization", "")
    if not BUBBLE_SECRET or auth != f"Bearer {BUBBLE_SECRET}":
        return jsonify({"error": "unauthorized"}), 401

    data = request.json or {}
    symbol = data.get("symbol")       # ex: "BTC-USDT"
    side = data.get("side")           # "buy" ou "sell"
    size = data.get("size")           # ex: "0.001"

    if not all([symbol, side, size]):
        return jsonify({"error":"missing fields: symbol, side, size"}), 400

    try:
        # cria ordem de mercado
        order_resp = client.create_market_order(symbol=symbol, side=side, size=str(size))
        return jsonify({"status":"ok","order":order_resp})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


from flask import Flask, request, jsonify
from kucoin.client import Client
import os

app = Flask(__name__)

# pega as chaves do ambiente do Render
API_KEY = os.getenv("KUCOIN_API_KEY")
API_SECRET = os.getenv("KUCOIN_SECRET_KEY")
API_PASSPHRASE = os.getenv("KUCOIN_PASSPHRASE")

client = Client(API_KEY, API_SECRET, API_PASSPHRASE)

@app.route("/")
def home():
    return "Servidor KuCoin rodando!"

# 🔍 Rota de teste para verificar se as chaves estão corretas
@app.route("/test")
def test_credentials():
    try:
        accounts = client.get_accounts()  # ✅ trocamos aqui
        return jsonify({"status": "ok", "accounts": accounts})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



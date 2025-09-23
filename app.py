from flask import Flask, jsonify
from huobi.client.account import AccountClient
import os

app = Flask(__name__)

# Pega as chaves do ambiente
API_KEY = os.getenv("HTX_API_KEY")
API_SECRET = os.getenv("HTX_SECRET_KEY")

# Cria cliente da Huobi
account_client = AccountClient(api_key=API_KEY, secret_key=API_SECRET)

@app.route("/")
def home():
    return "Servidor HTX rodando!"

# 🔍 Teste de credenciais
@app.route("/test")
def test_credentials():
    try:
        accounts = account_client.get_accounts()
        return jsonify({"status": "ok", "accounts": [a.__dict__ for a in accounts]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

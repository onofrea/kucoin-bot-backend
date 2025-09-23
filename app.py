from flask import Flask, jsonify
from huobi.client.account import AccountClient
import os

app = Flask(__name__)

API_KEY = os.getenv("HUOBI_API_KEY")
API_SECRET = os.getenv("HUOBI_SECRET")

@app.route("/")
def home():
    return "🚀 Servidor Huobi rodando!"

@app.route("/test")
def test_credentials():
    try:
        account_client = AccountClient(api_key=API_KEY, secret_key=API_SECRET)
        accounts = account_client.get_accounts()
        return jsonify({"status": "ok", "accounts": [a.__dict__ for a in accounts]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

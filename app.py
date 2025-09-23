from flask import Flask, jsonify
from huobi import Client
import os

app = Flask(__name__)

API_KEY = os.getenv("HUOBI_API_KEY")
API_SECRET = os.getenv("HUOBI_SECRET")

@app.route("/")
def home():
    return "Servidor Huobi rodando!"

@app.route("/test")
def test_credentials():
    try:
        client = Client(API_KEY, API_SECRET)
        accounts = client.get_accounts()
        return jsonify({"status": "ok", "accounts": accounts})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


            "message": str(e)
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

from flask import Flask, jsonify
from huobi.client.account import AccountClient
import os

app = Flask(__name__)

# 🔑 Pegando as variáveis de ambiente configuradas no Render
API_KEY = os.getenv("HUOBI_API_KEY")
API_SECRET = os.getenv("HUOBI_SECRET")


@app.route("/")
def home():
    return "🚀 Servidor Huobi rodando no Render!"


# 🔍 Rota de teste para validar suas credenciais
@app

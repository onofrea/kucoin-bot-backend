from flask import Flask, jsonify, request
from huobi.client.market import MarketClient
from huobi.client.trade import TradeClient
from huobi.client.account import AccountClient
from huobi.constant import OrderType
import os
import threading
import time

app = Flask(__name__)

API_KEY = os.getenv("HUOBI_API_KEY")
API_SECRET = os.getenv("HUOBI_SECRET")

market_client = MarketClient()
account_client = AccountClient(api_key=API_KEY, secret_key=API_SECRET)
trade_client = TradeClient(api_key=API_KEY, secret_key=API_SECRET)

# Configuração inicial
rules = []  # vai guardar as regras automáticas

def bot_loop():
    while True:
        try:
            for rule in rules:
                symbol = rule["symbol"]
                price = float(market_client.get_market_trade(symbol).tick.data[0].price)

                # Verifica regra de compra
                if rule["side"] == "buy" and price <= rule["target"]:
                    trade_client.create_order(
                        symbol=symbol,
                        account_id=account_client.get_accounts()[0].id,
                        order_type=OrderType.BUY_MARKET,
                        source="api",
                        amount=str(rule["amount"])
                    )
                    print(f"✅ Compra executada de {rule['amount']} {symbol} a {price}")
                    rules.remove(rule)

                # Verifica regra de venda
                elif rule["side"] == "sell" and price >= rule["target"]:
                    trade_client.create_order(
                        symbol=symbol,
                        account_id=account_client.get_accounts()[0].id,
                        order_type=OrderType.SELL_MARKET,
                        source="api",
                        amount=str(rule["amount"])
                    )
                    print(f"✅ Venda executada de {rule['amount']} {symbol} a {price}")
                    rules.remove(rule)

        except Exception as e:
            print("Erro no loop:", e)

        time.sleep(5)  # checa a cada 5 segundos


# Inicia thread paralela
threading.Thread(target=bot_loop, daemon=True).start()


@app.route("/")
def home():
    return "🤖 Bot Automático Huobi rodando!"


@app.route("/add_rule", methods=["POST"])
def add_rule():
    """
    Exemplo de JSON:
    {
      "symbol": "btcusdt",
      "side": "buy",
      "target": 60000,
      "amount": 0.001
    }
    """
    data = request.json
    rules.append(data)
    return jsonify({"status": "ok", "rules": rules})


@app.route("/rules")
def get_rules():
    return jsonify(rules)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

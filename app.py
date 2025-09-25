from flask import Flask, request, jsonify
import os
from huobi.client.account import AccountClient

app = Flask(__name__)

# 🔑 Pega as credenciais do Render (configure nas Variáveis de Ambiente)
API_KEY = os.getenv("HUOBI_API_KEY")
API_SECRET = os.getenv("HUOBI_SECRET")

# Inicializa o cliente da Huobi
account_client = AccountClient(api_key=API_KEY, secret_key=API_SECRET)

# Lista de regras em memória
rules = []


def get_account_id():
    """Pega o primeiro account_id disponível na Huobi"""
    accounts = account_client.get_accounts()
    if not accounts:
        return None
    return accounts[0].id


def get_available_balance(currency):
    """Retorna o saldo disponível de uma moeda na Huobi"""
    try:
        account_id = get_account_id()
        if not account_id:
            return 0.0

        balances = account_client.get_balance(account_id).list

        for b in balances:
            if b.currency.lower() == currency.lower() and b.type == "trade":
                return float(b.balance)
        return 0.0
    except Exception as e:
        print("Erro ao pegar saldo:", e)
        return 0.0


@app.route("/")
def home():
    return "🚀 Servidor Huobi rodando!"


@app.route("/balance", methods=["GET"])
def balance_route():
    """
    Exemplo: /balance?currency=usdt
    """
    currency = request.args.get("currency", "usdt")
    available = get_available_balance(currency)
    return jsonify({"currency": currency, "available": available})


@app.route("/add_rule", methods=["POST"])
def add_rule():
    data = request.json or {}
    symbol = (data.get("symbol") or "").strip()
    side = (data.get("side") or "buy").strip()
    target = data.get("target")
    amount = data.get("amount")

    # 🚨 Valida campos obrigatórios
    if not symbol or not target or not amount:
        return jsonify({"status": "error", "message": "Campos obrigatórios"}), 400

    try:
        amount_val = float(amount)
        target_val = float(target)
    except Exception:
        return jsonify({"status": "error", "message": "Amount ou Target inválido"}), 400

    if amount_val <= 0 or target_val <= 0:
        return jsonify({"status": "error", "message": "Valores devem ser maiores que 0"}), 400

    # 🔎 Verifica saldo antes de aceitar regra
    symbol_lower = symbol.lower()
    if side == "buy":
        # Exemplo: BTCUSDT → quote = usdt
        if symbol_lower.endswith("usdt"):
            quote_currency = "usdt"
        else:
            return jsonify({"status": "error", "message": "Só suporta par com USDT por enquanto"}), 400

        saldo_disponivel = get_available_balance(quote_currency)
        custo_estimado = amount_val * target_val

        if custo_estimado > saldo_disponivel:
            return jsonify({
                "status": "error",
                "message": f"Saldo insuficiente. Necessário {custo_estimado} {quote_currency}, disponível {saldo_disponivel}"
            }), 400

    elif side == "sell":
        # Exemplo: BTCUSDT → base = btc
        base_currency = symbol_lower.replace("usdt", "")
        saldo_disponivel = get_available_balance(base_currency)

        if amount_val > saldo_disponivel:
            return jsonify({
                "status": "error",
                "message": f"Saldo insuficiente. Necessário {amount_val} {base_currency}, disponível {saldo_disponivel}"
            }), 400

    # ✅ Se passou nas verificações, salva a regra
    rule = {"symbol": symbol, "side": side, "target": target_val, "amount": amount_val}
    rules.append(rule)

    return jsonify({"status": "ok", "rule": rule}), 201


@app.route("/rules", methods=["GET"])
def get_rules():
    return jsonify(rules)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

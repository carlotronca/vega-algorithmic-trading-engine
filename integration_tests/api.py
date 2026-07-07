import config
from python_bitvavo_api.bitvavo import Bitvavo


# =========================
# 🔌 CLIENT BITVAVO
# =========================
client = Bitvavo({
    "APIKEY": config.API_KEY,
    "APISECRET": config.API_SECRET,
    "RESTURL": "https://api.bitvavo.com/v2",
    "ACCESSWINDOW": 10000
})


# =========================
# 📊 PREZZO MERCATO
# =========================
def get_price(market="BTC-EUR"):
    return client.tickerPrice({"market": market})


# =========================
# 💰 BALANCE ACCOUNT
# =========================
def get_balance():
    return client.balance()


# =========================
# 🛒 ORDINE MARKET
# =========================
def place_order(market="BTC-EUR", side="buy", amount="0.001"):
    return client.placeOrder({
        "market": market,
        "side": side,
        "orderType": "market",
        "amount": str(amount)
    })

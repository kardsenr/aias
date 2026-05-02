import requests
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ─── WEB SERVER FOR RENDER ─────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass

def run_server():
    HTTPServer(("0.0.0.0", 10000), Handler).serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# ─── SETTINGS ──────────────────────────────────────────────
SOSO_API_KEY   = "SOSO-51388f04096541028574f79da0e7264e"
TELEGRAM_TOKEN = "8624209931:AAGncUwPOF9x9m_YI2B63770STcKrFjOVBM"
GROQ_API_KEY   = "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"

CHAT_IDS = set()

COINS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple"
}

# ─── TELEGRAM ──────────────────────────────────────────────
def telegram_send(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

def telegram_get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 10}
    if offset:
        params["offset"] = offset
    r = requests.get(url, params=params)
    return r.json()

# ─── PRICE ─────────────────────────────────────────────────
def get_price(coin_symbol):
    coin_id = COINS.get(coin_symbol.upper())
    if not coin_id:
        return None, None, None
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        price = data[coin_id]["usd"]
        change = data[coin_id]["usd_24h_change"]
        mcap = data[coin_id]["usd_market_cap"]
        return price, change, mcap
    except Exception as e:
        print(f"Price error: {e}")
        return None, None, None

def price_message(coin_symbol):
    price, change, mcap = get_price(coin_symbol)
    if price is None:
        return f"❌ {coin_symbol} not found. Supported coins: {', '.join(COINS.keys())}"
    emoji = "📈" if change > 0 else "📉"
    sign = "+" if change > 0 else ""
    return (
        f"{emoji} <b>{coin_symbol.upper()} Live Price</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Price: <b>${price:,.2f}</b>\n"
        f"📊 24h Change: <b>{sign}{change:.2f}%</b>\n"
        f"🏦 Market Cap: ${mcap/1e9:.1f}B\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ {time.strftime('%H:%M %d/%m/%Y')}"
    )

# ─── SOSOValue API ─────────────────────────────────────────
def get_soso_news():
    url = "https://openapi.sosovalue.com/api/v1/news/featured?pageNum=1&pageSize=5"
    headers = {"x-soso-api-key": SOSO_API_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        if data.get("code") == 0:
            return data.get("data", {}).get("list", [])
    except Exception as e:
        print(f"SoSoValue error: {e}")
    return []

def get_soso_etf():
    url = "https://openapi.sosovalue.com/api/v1/etf/btc/netflow"
    headers = {"x-soso-api-key": SOSO_API_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        return r.json()
    except Exception as e:
        print(f"ETF data error: {e}")
    return {}

# ─── GROQ AI ANALYSIS ──────────────────────────────────────
def groq_analyze(news, etf_data, coin="BTC"):
    news_text = ""
    for h in news[:5]:
        content = h.get("multilanguageContent", [])
        for c in content:
            if c.get("language") == "en":
                news_text += f"- {c.get('title', '')}\n"
                break

    prompt = f"""You are a professional crypto market analyst.
Analyze the following latest crypto news and Bitcoin ETF flow data.
Generate a short and clear trading signal for {coin}.

NEWS:
{news_text if news_text else "No news available"}

ETF DATA:
{json.dumps(etf_data, indent=2)[:500] if etf_data else "No data available"}

Respond in exactly this format:
SIGNAL: [BUY / SELL / HOLD]
COIN: {coin}
CONFIDENCE: [Low / Medium / High]
REASON: [1-2 sentence explanation]
RISK WARNING: [Short warning]"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                          headers=headers, json=body, timeout=30)
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"AI analysis error: {e}"

# ─── SEND SIGNAL ───────────────────────────────────────────
def send_signal(chat_ids=None, coin="BTC"):
    if chat_ids is None:
        chat_ids = CHAT_IDS
    print(f"📡 Fetching {coin} data...")
    news = get_soso_news()
    etf_data = get_soso_etf()
    print("🤖 Groq AI analyzing...")
    analysis = groq_analyze(news, etf_data, coin)
    upper = analysis.upper()
    if "SIGNAL: BUY" in upper:
        emoji = "🟢"
    elif "SIGNAL: SELL" in upper:
        emoji = "🔴"
    else:
        emoji = "🟡"
    message = (
        f"{emoji} <b>SOSOVALUE SIGNAL BOT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{analysis}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ {time.strftime('%H:%M %d/%m/%Y')}\n"
        f"📊 Source: SoSoValue API\n"
        f"⚠️ This is not financial advice."
    )
    for chat_id in chat_ids:
        telegram_send(chat_id, message)
        print(f"✅ Signal sent → {chat_id}")

# ─── DAILY REPORT ──────────────────────────────────────────
def send_report(chat_id):
    telegram_send(chat_id, "📊 Preparing daily report, please wait...")
    price_text = ""
    for symbol in COINS:
        price, change, _ = get_price(symbol)
        if price:
            sign = "+" if change > 0 else ""
            trend = "📈" if change > 0 else "📉"
            price_text += f"{trend} <b>{symbol}:</b> ${price:,.2f} ({sign}{change:.2f}%)\n"
    news = get_soso_news()
    etf_data = get_soso_etf()
    etf_summary = ""
    if etf_data and etf_data.get("code") == 0:
        data = etf_data.get("data", {})
        etf_summary = f"Total Net Flow: ${data.get('totalNetFlow', 'N/A')}"
    news_headlines = ""
    for h in news[:3]:
        content = h.get("multilanguageContent", [])
        for c in content:
            if c.get("language") == "en":
                news_headlines += f"• {c.get('title', '')[:60]}...\n"
                break
    message = (
        f"📋 <b>DAILY CRYPTO REPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💹 <b>Prices</b>\n"
        f"{price_text if price_text else 'Data unavailable'}\n"
        f"🏦 <b>BTC ETF Data</b>\n"
        f"{etf_summary if etf_summary else 'Data unavailable'}\n\n"
        f"📰 <b>Latest News</b>\n"
        f"{news_headlines if news_headlines else 'No news available'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ {time.strftime('%H:%M %d/%m/%Y')}\n"
        f"⚠️ This is not financial advice."
    )
    telegram_send(chat_id, message)

# ─── MAIN LOOP ─────────────────────────────────────────────
def main():
    print("🚀 SoSoValue Signal Bot started!")
    print("Send /start to your bot on Telegram\n")

    offset = None
    last_signal = 0
    SIGNAL_INTERVAL = 3600

    while True:
        updates = telegram_get_updates(offset)

        for update in updates.get("result", []):
            offset = update["update_id"] + 1

            if "message" in update:
                chat_id = update["message"]["chat"]["id"]
                text = update["message"].get("text", "").strip()

                if text == "/start":
                    CHAT_IDS.add(chat_id)
                    telegram_send(chat_id,
                        "👋 <b>Welcome to SoSoValue Signal Bot!</b>\n\n"
                        "📊 AI-powered crypto signals using SoSoValue data.\n\n"
                        "<b>Commands:</b>\n"
                        "/signal — BTC signal\n"
                        "/signal ETH — ETH signal\n"
                        "/signal SOL — SOL signal\n"
                        "/price BTC — Live BTC price\n"
                        "/price ETH — Live ETH price\n"
                        "/report — Daily market report\n"
                        "/stop — Stop notifications\n\n"
                        f"💡 Supported coins: {', '.join(COINS.keys())}"
                    )
                    print(f"New user: {chat_id}")

                elif text.startswith("/signal"):
                    CHAT_IDS.add(chat_id)
                    parts = text.split()
                    coin = parts[1].upper() if len(parts) > 1 else "BTC"
                    if coin not in COINS:
                        telegram_send(chat_id, f"❌ Unsupported coin.\n💡 Options: {', '.join(COINS.keys())}")
                    else:
                        telegram_send(chat_id, f"⏳ Analyzing {coin}, please wait...")
                        send_signal({chat_id}, coin)

                elif text.startswith("/price"):
                    parts = text.split()
                    coin = parts[1].upper() if len(parts) > 1 else "BTC"
                    telegram_send(chat_id, price_message(coin))

                elif text == "/report":
                    send_report(chat_id)

                elif text == "/stop":
                    CHAT_IDS.discard(chat_id)
                    telegram_send(chat_id, "⛔ Notifications stopped. Send /start to reactivate.")

        # Hourly automatic BTC signal
        if time.time() - last_signal > SIGNAL_INTERVAL and CHAT_IDS:
            send_signal()
            last_signal = time.time()

        time.sleep(2)

if __name__ == "__main__":
    main()
    

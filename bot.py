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

# ─── CACHE (10 dakika) ─────────────────────────────────────
cache = {
    "news": [],
    "etf": {},
    "news_time": 0,
    "etf_time": 0,
}
CACHE_TTL = 600

# ─── TELEGRAM ──────────────────────────────────────────────
def telegram_send(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Telegram send error: {e}")

def telegram_get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 10}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(url, params=params, timeout=15)
        return r.json()
    except Exception as e:
        print(f"Get updates error: {e}")
        return {"result": []}

# ─── SOSOValue API WITH CACHE ──────────────────────────────
def get_soso_news():
    now = time.time()
    if cache["news"] and (now - cache["news_time"]) < CACHE_TTL:
        print("Using cached news")
        return cache["news"]
    url = "https://openapi.sosovalue.com/api/v1/news/featured?pageNum=1&pageSize=5"
    headers = {"x-soso-api-key": SOSO_API_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"News API status: {r.status_code} response: {r.text[:200]}")
        data = r.json()
        if data.get("code") == 0:
            items = data.get("data", {}).get("list", [])
            cache["news"] = items
            cache["news_time"] = now
            print(f"News fetched: {len(items)} items")
            return items
        else:
            print(f"News API error: {data.get('code')} msg: {data.get('msg')}")
    except Exception as e:
        print(f"SoSoValue news error: {e}")
    return cache["news"]

def get_soso_etf():
    now = time.time()
    if cache["etf"] and (now - cache["etf_time"]) < CACHE_TTL:
        print("Using cached ETF data")
        return cache["etf"]
    url = "https://openapi.sosovalue.com/api/v1/etf/btc/netflow"
    headers = {"x-soso-api-key": SOSO_API_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"ETF API status: {r.status_code} response: {r.text[:200]}")
        data = r.json()
        cache["etf"] = data
        cache["etf_time"] = now
        print("ETF data fetched")
        return data
    except Exception as e:
        print(f"ETF error: {e}")
    return cache["etf"]

# ─── GROQ AI ANALYSIS ──────────────────────────────────────
def groq_analyze(news, etf_data):
    news_text = ""
    for h in news[:5]:
        content = h.get("multilanguageContent", [])
        for c in content:
            if c.get("language") == "en":
                news_text += f"- {c.get('title', '')}\n"
                break

    prompt = f"""You are a professional crypto market analyst.
Analyze the following latest crypto news and Bitcoin ETF flow data.
Generate a short and clear trading signal for BTC.

NEWS:
{news_text if news_text else "No news available"}

ETF DATA:
{json.dumps(etf_data, indent=2)[:500] if etf_data else "No data available"}

Respond in exactly this format:
SIGNAL: [BUY / SELL / HOLD]
COIN: BTC
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
        print(f"Groq error: {e}")
        return f"AI analysis error: {e}"

# ─── SEND SIGNAL ───────────────────────────────────────────
def send_signal(chat_ids=None):
    if chat_ids is None:
        chat_ids = CHAT_IDS
    print("Getting BTC data...")
    news = get_soso_news()
    etf_data = get_soso_etf()
    print("Analyzing with Groq AI...")
    analysis = groq_analyze(news, etf_data)
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
        print(f"Signal sent → {chat_id}")

# ─── MAIN LOOP ─────────────────────────────────────────────
def main():
    print("SoSoValue Signal Bot started!")
    print("Pre-fetching SoSoValue data...")
    get_soso_news()
    get_soso_etf()

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
                        "📊 AI-powered BTC trading signals using SoSoValue data.\n\n"
                        "<b>Commands:</b>\n"
                        "/signal — BTC trading signal\n"
                        "/stop — Stop notifications"
                    )

                elif text == "/signal":
                    CHAT_IDS.add(chat_id)
                    telegram_send(chat_id, "⏳ Analyzing BTC, please wait...")
                    send_signal({chat_id})

                elif text == "/stop":
                    CHAT_IDS.discard(chat_id)
                    telegram_send(chat_id, "⛔ Notifications stopped. Send /start to reactivate.")

        if time.time() - last_signal > SIGNAL_INTERVAL and CHAT_IDS:
            send_signal()
            last_signal = time.time()

        time.sleep(2)

if __name__ == "__main__":
    main()
    

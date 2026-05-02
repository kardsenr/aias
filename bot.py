import requests
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ─── RENDER İÇİN WEB SERVER ────────────────────────────────
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

# ─── AYARLAR ───────────────────────────────────────────────
SOSO_API_KEY    = "SOSO-51388f04096541028574f79da0e7264e"
TELEGRAM_TOKEN  = "8624209931:AAGncUwPOF9x9m_YI2B63770STcKrFjOVBM"
GROQ_API_KEY    = "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"

CHAT_IDS = set()

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
        print(f"SoSoValue hata: {e}")
    return []

def get_soso_etf():
    url = "https://openapi.sosovalue.com/api/v1/etf/btc/netflow"
    headers = {"x-soso-api-key": SOSO_API_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        return r.json()
    except Exception as e:
        print(f"ETF veri hata: {e}")
    return {}

# ─── GROQ AI ANALİZ ────────────────────────────────────────
def groq_analiz(haberler, etf_data):
    haber_metni = ""
    for h in haberler[:5]:
        icerik = h.get("multilanguageContent", [])
        for c in icerik:
            if c.get("language") == "en":
                haber_metni += f"- {c.get('title', '')}\n"
                break

    prompt = f"""Sen bir kripto piyasa analisti asistanısın.
Aşağıdaki güncel kripto haberlerini ve Bitcoin ETF akış verisini analiz et.
Kısa ve net bir trading sinyali üret.

HABERLER:
{haber_metni if haber_metni else "Haber alınamadı"}

ETF VERİSİ:
{json.dumps(etf_data, indent=2)[:500] if etf_data else "Veri alınamadı"}

Tam olarak şu formatta yanıt ver:
SİNYAL: [AL / SAT / BEKLE]
COIN: [BTC / ETH / GENEL]
GÜVEN: [Düşük / Orta / Yüksek]
SEBEP: [1-2 cümle açıklama]
RİSK UYARISI: [Kısa uyarı]"""

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
        return f"AI analiz hatası: {e}"

# ─── SİNYAL GÖNDER ─────────────────────────────────────────
def sinyal_gonder():
    print("📡 Veri çekiliyor...")
    haberler = get_soso_news()
    etf_data = get_soso_etf()

    print("🤖 Groq AI analiz ediyor...")
    analiz = groq_analiz(haberler, etf_data)

    upper = analiz.upper()
    if "SİNYAL: AL" in upper or "SINYAL: AL" in upper:
        emoji = "🟢"
    elif "SİNYAL: SAT" in upper or "SINYAL: SAT" in upper:
        emoji = "🔴"
    else:
        emoji = "🟡"

    mesaj = (
        f"{emoji} <b>SOSOVALUE SİNYAL BOTU</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{analiz}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ {time.strftime('%H:%M %d/%m/%Y')}\n"
        f"📊 Kaynak: SoSoValue API\n"
        f"⚠️ Bu bir yatırım tavsiyesi değildir."
    )

    for chat_id in CHAT_IDS:
        telegram_send(chat_id, mesaj)
        print(f"✅ Sinyal gönderildi → {chat_id}")

# ─── ANA DÖNGÜ ─────────────────────────────────────────────
def main():
    print("🚀 SoSoValue Sinyal Botu başlatıldı!")
    print("Telegram'da botuna /start yaz\n")

    offset = None
    son_sinyal = 0
    SINYAL_ARALIGI = 3600

    while True:
        updates = telegram_get_updates(offset)

        for update in updates.get("result", []):
            offset = update["update_id"] + 1

            if "message" in update:
                chat_id = update["message"]["chat"]["id"]
                text = update["message"].get("text", "")

                if text == "/start":
                    CHAT_IDS.add(chat_id)
                    telegram_send(chat_id,
                        "👋 <b>SoSoValue Sinyal Botuna Hoş Geldin!</b>\n\n"
                        "📊 SoSoValue verileriyle saatlik sinyal gönderirim.\n\n"
                        "Komutlar:\n"
                        "/sinyal — Hemen analiz al\n"
                        "/stop — Bildirimleri durdur"
                    )
                    print(f"Yeni kullanıcı: {chat_id}")

                elif text == "/sinyal":
                    CHAT_IDS.add(chat_id)
                    telegram_send(chat_id, "⏳ Analiz yapılıyor, bekle...")
                    sinyal_gonder()

                elif text == "/stop":
                    CHAT_IDS.discard(chat_id)
                    telegram_send(chat_id, "⛔ Bildirimler durduruldu. /start ile tekrar başlatabilirsin.")

        if time.time() - son_sinyal > SINYAL_ARALIGI and CHAT_IDS:
            sinyal_gonder()
            son_sinyal = time.time()

        time.sleep(2)

if __name__ == "__main__":
    main()
    

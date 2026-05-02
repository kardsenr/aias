import os
import requests
import time
from groq import Groq
from telegram import Bot
import asyncio

# --- CONFIGURATION ---
SOSO_API_KEY = "SOSO-51388f04096541028574f79da0e7264e"
GROQ_API_KEY = "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"
TELEGRAM_TOKEN = "8624209931:AAGncUwPOF9x9m_YI2B63770STcKrFjOVBM"
CHAT_ID = "7185850425"

# Initialize Clients
groq_client = Groq(api_key=GROQ_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)

def get_soso_data(ticker):
    """
    Fetches real-time market data and AI sentiment from SoSoValue.
    """
    url = f"https://api.sosovalue.com/v1/asset/sentiment?symbol={ticker}"
    headers = {"Authorization": f"Bearer {SOSO_API_KEY}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json().get('data', {})
    except Exception as e:
        print(f"Error fetching SoSoValue data for {ticker}: {e}")
        return None

def generate_ai_analysis(ticker, data):
    """
    Generates a professional signal and reasoning using Groq (Llama 3).
    The output is strictly in English.
    """
    score = data.get('sentiment_score', 'N/A')
    market_context = data.get('analysis_summary', 'No summary available')
    
    # Force the AI to stay in English and be professional
    prompt = f"""
    Role: Senior Crypto Market Analyst
    Asset: {ticker}
    Sentiment Score: {score}/100
    Context: {market_context}

    Instruction:
    1. Determine the Signal: BUY, SELL, or HOLD.
    2. Write a 2-sentence professional reasoning in English.
    3. Tone: Serious, data-driven, institutional.
    4. Language: English Only.
    """
    
    try:
        completion = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4 # Consistent and sharp output
        )
        return completion.choices[0].message.content
    except Exception as e:
        return "HOLD\nTechnical analysis is temporarily unavailable. Please monitor market volatility."

async def send_signals():
    """
    Compiles data and sends the formatted signal to the Telegram channel.
    """
    assets = ["BTC", "ETH", "SOL"]
    current_time = time.strftime('%Y-%m-%d %H:%M')
    
    for asset in assets:
        data = get_soso_data(asset)
        if data:
            ai_output = generate_ai_analysis(asset, data)
            
            # Formatted message with Monospace font for the analysis
            message = (
                f"📊 **{asset}/USDT Market Update**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📝 **AI ANALYSIS:**\n"
                f"```\n"
                f"{ai_output}\n"
                f"```\n"
                f"⏰ *Refreshed: {current_time} UTC*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ *Disclaimer: This is not financial advice. Investing in digital assets involves significant risk. Always DYOR.*"
            )
            
            try:
                await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
                print(f"Success: Signal sent for {asset}")
            except Exception as e:
                print(f"Telegram Delivery Error: {e}")
            
            await asyncio.sleep(5) # Delay to avoid rate limits

async def main():
    print("🚀 SoSoValue & Groq Signal Bot is now LIVE...")
    while True:
        await send_signals()
        print("Cycle complete. Next update in 6 hours.")
        await asyncio.sleep(21600) # 6-hour interval

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Process terminated by user.")

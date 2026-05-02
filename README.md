# ⚡ BTC Signal Bot

Real-time Bitcoin signal bot powered by **SoSoValue API**, **Groq AI**, and deployed on **Render**.

---

## Features
| Feature | Details |
|---|---|
| 📊 BTC Signal | Rule-based score (0-100) + BUY/SELL label |
| 😱 Fear & Greed | Live index + 7-day history |
| 🔗 On-Chain | NUPL, MVRV, SOPR, Hashrate |
| 📈 Market Data | Price, volume, market cap, 52-week range |
| 🤖 AI Analysis | Groq LLaMA3 narrative for each signal |
| 📡 Auto Broadcast | Every 4 hours to your channel |

---

## Local Setup

```bash
git clone <your-repo>
cd btc_signal_bot
pip install -r requirements.txt

export TELEGRAM_TOKEN="your_token"
export SOSO_API_KEY="your_key"
export GROQ_API_KEY="your_key"
export SIGNAL_CHANNEL="@yourchannel"   # optional

python bot.py
```

---

## Deploy to Render (Free / Paid)

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "init btc signal bot"
git remote add origin https://github.com/YOURNAME/btc-signal-bot.git
git push -u origin main
```

### Step 2 — Create Render Web Service
1. Go to https://render.com → **New → Web Service**
2. Connect your GitHub repo
3. Settings:
   - **Runtime**: Python 3
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `python bot.py`
   - **Instance type**: Free (or Starter for always-on)

### Step 3 — Set Environment Variables
In Render dashboard → **Environment**:
```
TELEGRAM_TOKEN   = 8624209931:AAGncUw...
SOSO_API_KEY     = SOSO-51388f04...
GROQ_API_KEY     = gsk_DdN8kRo...
SIGNAL_CHANNEL   = @yourchannel        ← optional auto-broadcast
PORT             = 10000
```

### Step 4 — Deploy
Click **Deploy** → bot starts automatically.

> ⚠️ **Free tier** on Render spins down after 15 min idle.
> Use [UptimeRobot](https://uptimerobot.com) to ping `/health` every 5 min to keep it alive.
> Or upgrade to **Starter ($7/mo)** for always-on.

---

## Bot Commands
| Command | Description |
|---|---|
| `/start` | Welcome + menu |
| `/signal` | Full BTC signal report |
| `/market` | Price & market data |
| `/feargreed` | Fear & Greed index |
| `/onchain` | On-chain metrics |
| `/ai` | AI analysis only |

---

## Signal Logic

| Score | Label |
|---|---|
| 70–100 | 🟢🟢 STRONG BUY |
| 55–69 | 🟢 BUY |
| 45–54 | 🟡 NEUTRAL |
| 30–44 | 🔴 SELL |
| 0–29 | 🔴🔴 STRONG SELL |

Factors: Price momentum · Distance from 52w-high · Fear & Greed (contrarian) · MVRV · NUPL · SOPR

---

## Fallbacks
- SoSoValue down → **CoinGecko** (price) / **Alternative.me** (F&G)
- Groq down → graceful error message, signal still shown

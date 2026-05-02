import os
import asyncio
import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from sosovalue_client import SoSoValueClient
from groq_analyst import GroqAnalyst
from signal_engine import SignalEngine

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
SOSO_API_KEY   = os.getenv("SOSO_API_KEY", "")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")

# ── Channel / group where auto-signals are broadcast ─────────────────────────
SIGNAL_CHANNEL = os.getenv("SIGNAL_CHANNEL", "")   # e.g. @btcsignals or -100xxxxx

soso    = SoSoValueClient(SOSO_API_KEY)
groq    = GroqAnalyst(GROQ_API_KEY)
engine  = SignalEngine()

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 BTC Signal",      callback_data="signal"),
         InlineKeyboardButton("📈 Market Data",     callback_data="market")],
        [InlineKeyboardButton("😱 Fear & Greed",    callback_data="feargreed"),
         InlineKeyboardButton("🔗 On-Chain",        callback_data="onchain")],
        [InlineKeyboardButton("🤖 AI Analysis",     callback_data="ai")],
    ])

async def _send_or_edit(update: Update, text: str, keyboard=None, parse_mode="HTML"):
    kb = keyboard or _main_keyboard()
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=kb, parse_mode=parse_mode
        )
    else:
        await update.message.reply_text(
            text, reply_markup=kb, parse_mode=parse_mode
        )

# ─────────────────────────────────────────────────────────────────────────────
# Build full signal message
# ─────────────────────────────────────────────────────────────────────────────

async def build_signal_message() -> str:
    market   = await soso.get_btc_market()
    fg       = await soso.get_fear_greed()
    onchain  = await soso.get_onchain()
    signal   = engine.compute(market, fg, onchain)
    ai_text  = await groq.analyse(market, fg, onchain, signal)

    price   = market.get("price", 0)
    change  = market.get("change_24h", 0)
    vol     = market.get("volume_24h", 0)
    mktcap  = market.get("market_cap", 0)
    fg_val  = fg.get("value", 0)
    fg_lbl  = fg.get("label", "N/A")
    ath_pct = market.get("ath_pct", 0)

    nupl       = onchain.get("nupl", "N/A")
    mvrv       = onchain.get("mvrv", "N/A")
    hashrate   = onchain.get("hashrate", "N/A")
    sopr       = onchain.get("sopr", "N/A")

    sig_emoji = {"STRONG BUY": "🟢🟢", "BUY": "🟢", "NEUTRAL": "🟡",
                 "SELL": "🔴", "STRONG SELL": "🔴🔴"}.get(signal["label"], "⚪")
    chg_arrow = "🔺" if change >= 0 else "🔻"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    msg = f"""
<b>⚡ BTC SIGNAL REPORT</b>
<code>─────────────────────────</code>
🕐 <i>{now}</i>

<b>💰 PRICE</b>
  ├ Price   : <b>${price:,.2f}</b>
  ├ 24h     : {chg_arrow} <b>{change:+.2f}%</b>
  ├ Volume  : <b>${vol/1e9:.2f}B</b>
  ├ Mkt Cap : <b>${mktcap/1e12:.2f}T</b>
  └ ATH Δ   : <b>{ath_pct:+.1f}%</b>

<b>😱 FEAR & GREED</b>
  └ {_fg_bar(fg_val)}  <b>{fg_val}</b> — {fg_lbl}

<b>🔗 ON-CHAIN</b>
  ├ NUPL   : <b>{nupl}</b>
  ├ MVRV   : <b>{mvrv}</b>
  ├ SOPR   : <b>{sopr}</b>
  └ Hash   : <b>{hashrate}</b>

<b>📡 SIGNAL</b>
  {sig_emoji} <b>{signal["label"]}</b>  (score: {signal["score"]}/100)
  Confidence : <b>{signal["confidence"]}%</b>

<b>🤖 AI TAKE</b>
<i>{ai_text}</i>

<code>─────────────────────────</code>
⚠️ <i>Not financial advice. DYOR.</i>
"""
    return msg.strip()


def _fg_bar(val: int) -> str:
    filled = round(val / 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}]"

# ─────────────────────────────────────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 <b>Welcome to BTC Signal Bot</b>\n\n"
        "I combine <b>SoSoValue market data</b>, <b>on-chain metrics</b> "
        "and <b>Groq AI</b> to deliver real-time Bitcoin signals.\n\n"
        "Choose an option below 👇"
    )
    await _send_or_edit(update, text)


async def cmd_signal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.effective_message.reply_text("⏳ Fetching signal…")
    try:
        text = await build_signal_message()
        await msg.edit_text(text, parse_mode="HTML", reply_markup=_main_keyboard())
    except Exception as e:
        logger.error("signal error: %s", e)
        await msg.edit_text(f"❌ Error: {e}", reply_markup=_main_keyboard())


async def cmd_market(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.effective_message.reply_text("⏳ Loading market data…")
    try:
        d = await soso.get_btc_market()
        chg_arrow = "🔺" if d.get("change_24h", 0) >= 0 else "🔻"
        text = (
            f"<b>📈 BTC Market Snapshot</b>\n"
            f"<code>──────────────────</code>\n"
            f"💵 Price   : <b>${d.get('price',0):,.2f}</b>\n"
            f"📊 24h     : {chg_arrow} <b>{d.get('change_24h',0):+.2f}%</b>\n"
            f"📦 Volume  : <b>${d.get('volume_24h',0)/1e9:.2f}B</b>\n"
            f"🌍 Mkt Cap : <b>${d.get('market_cap',0)/1e12:.2f}T</b>\n"
            f"🏔 ATH Δ   : <b>{d.get('ath_pct',0):+.1f}%</b>\n"
            f"📅 52w H   : <b>${d.get('high_52w',0):,.0f}</b>\n"
            f"📉 52w L   : <b>${d.get('low_52w',0):,.0f}</b>"
        )
        await msg.edit_text(text, parse_mode="HTML", reply_markup=_main_keyboard())
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}", reply_markup=_main_keyboard())


async def cmd_feargreed(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.effective_message.reply_text("⏳ Loading…")
    try:
        fg = await soso.get_fear_greed()
        val = fg.get("value", 0)
        lbl = fg.get("label", "N/A")
        hist = fg.get("history", [])
        hist_lines = "\n".join(
            f"  {h['date']}: {h['value']} — {h['label']}" for h in hist[:5]
        ) or "  N/A"
        text = (
            f"<b>😱 BTC Fear & Greed Index</b>\n"
            f"<code>──────────────────────</code>\n"
            f"{_fg_bar(val)}  <b>{val}</b>\n"
            f"Status : <b>{lbl}</b>\n\n"
            f"<b>📅 Recent history:</b>\n{hist_lines}"
        )
        await msg.edit_text(text, parse_mode="HTML", reply_markup=_main_keyboard())
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}", reply_markup=_main_keyboard())


async def cmd_onchain(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.effective_message.reply_text("⏳ Loading on-chain…")
    try:
        d = await soso.get_onchain()
        text = (
            f"<b>🔗 BTC On-Chain Metrics</b>\n"
            f"<code>───────────────────</code>\n"
            f"📊 NUPL    : <b>{d.get('nupl','N/A')}</b>\n"
            f"📐 MVRV    : <b>{d.get('mvrv','N/A')}</b>\n"
            f"📉 SOPR    : <b>{d.get('sopr','N/A')}</b>\n"
            f"⛏ Hashrate: <b>{d.get('hashrate','N/A')}</b>\n"
            f"💎 LTH Sup : <b>{d.get('lth_supply','N/A')}</b>\n"
            f"📬 Addresses: <b>{d.get('active_addresses','N/A')}</b>"
        )
        await msg.edit_text(text, parse_mode="HTML", reply_markup=_main_keyboard())
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}", reply_markup=_main_keyboard())


async def cmd_ai(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.effective_message.reply_text("🤖 Asking AI…")
    try:
        market  = await soso.get_btc_market()
        fg      = await soso.get_fear_greed()
        onchain = await soso.get_onchain()
        signal  = engine.compute(market, fg, onchain)
        ai_text = await groq.analyse(market, fg, onchain, signal)
        text = (
            f"<b>🤖 Groq AI Analysis — BTC</b>\n"
            f"<code>──────────────────────</code>\n"
            f"{ai_text}"
        )
        await msg.edit_text(text, parse_mode="HTML", reply_markup=_main_keyboard())
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}", reply_markup=_main_keyboard())


# Button router
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = update.callback_query.data
    handlers = {
        "signal":    cmd_signal,
        "market":    cmd_market,
        "feargreed": cmd_feargreed,
        "onchain":   cmd_onchain,
        "ai":        cmd_ai,
    }
    if data in handlers:
        await handlers[data](update, ctx)

# ─────────────────────────────────────────────────────────────────────────────
# Scheduled broadcast
# ─────────────────────────────────────────────────────────────────────────────

async def scheduled_signal(app: Application):
    if not SIGNAL_CHANNEL:
        return
    try:
        text = await build_signal_message()
        await app.bot.send_message(
            chat_id=SIGNAL_CHANNEL, text=text, parse_mode="HTML"
        )
        logger.info("Scheduled signal sent to %s", SIGNAL_CHANNEL)
    except Exception as e:
        logger.error("Scheduled signal error: %s", e)

# ─────────────────────────────────────────────────────────────────────────────
# Keep-alive web server (Render free tier)
# ─────────────────────────────────────────────────────────────────────────────

async def run_web():
    from aiohttp import web
    async def health(_):
        return web.Response(text="OK")
    app_web = web.Application()
    app_web.router.add_get("/", health)
    app_web.router.add_get("/health", health)
    runner = web.AppRunner(app_web)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health server on port %s", port)

# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    await run_web()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("signal",    cmd_signal))
    app.add_handler(CommandHandler("market",    cmd_market))
    app.add_handler(CommandHandler("feargreed", cmd_feargreed))
    app.add_handler(CommandHandler("onchain",   cmd_onchain))
    app.add_handler(CommandHandler("ai",        cmd_ai))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Scheduler: every 4 hours
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        lambda: asyncio.create_task(scheduled_signal(app)),
        "interval", hours=4, id="auto_signal"
    )
    scheduler.start()

    logger.info("Bot starting…")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    # Keep running
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
            
        

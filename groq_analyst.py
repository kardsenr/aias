"""
Groq AI analyst — sends structured BTC data to Groq LLM
and returns a concise 3-4 sentence trading insight.
"""

import logging
from typing import Dict

from groq import AsyncGroq

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a concise, data-driven Bitcoin market analyst.
Given raw market, sentiment, and on-chain data you write a SHORT analysis
(3-4 sentences, max 120 words) in plain English.
Focus on what the data implies for BTC price in the next 24-48 hours.
Always end with a one-line risk note.
Do NOT use markdown. Do NOT repeat the raw numbers verbatim."""


class GroqAnalyst:
    def __init__(self, api_key: str):
        self._client = AsyncGroq(api_key=api_key)

    async def analyse(
        self,
        market: Dict,
        fear_greed: Dict,
        onchain: Dict,
        signal: Dict,
    ) -> str:
        price  = market.get("price", 0)
        change = market.get("change_24h", 0)
        vol    = market.get("volume_24h", 0)
        fg_val = fear_greed.get("value", 50)
        fg_lbl = fear_greed.get("label", "N/A")
        nupl   = onchain.get("nupl", "N/A")
        mvrv   = onchain.get("mvrv", "N/A")
        sopr   = onchain.get("sopr", "N/A")
        sig    = signal.get("label", "NEUTRAL")
        score  = signal.get("score", 50)

        user_msg = (
            f"BTC Price: ${price:,.2f} | 24h Change: {change:+.2f}% | "
            f"Volume: ${vol/1e9:.1f}B\n"
            f"Fear & Greed: {fg_val}/100 ({fg_lbl})\n"
            f"NUPL: {nupl} | MVRV: {mvrv} | SOPR: {sopr}\n"
            f"Signal Engine Output: {sig} (score {score}/100)\n\n"
            "Write your concise analyst take."
        )

        try:
            resp = await self._client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.45,
                max_tokens=180,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Groq API error: %s", e)
            return f"AI analysis temporarily unavailable. Signal: {sig} (score {score}/100)."

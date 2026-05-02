"""
Rule-based signal engine.
Combines price momentum, Fear & Greed, and on-chain metrics
to produce a scored BUY / SELL / NEUTRAL signal.
"""

from typing import Dict


class SignalEngine:
    """
    Score range: 0–100
      >= 70  → STRONG BUY
      55-69  → BUY
      45-54  → NEUTRAL
      30-44  → SELL
      < 30   → STRONG SELL
    """

    def compute(
        self,
        market: Dict,
        fear_greed: Dict,
        onchain: Dict,
    ) -> Dict:
        score = 50  # baseline neutral

        # ── 1. Price momentum (weight: 25 pts) ───────────────────────────
        change = market.get("change_24h", 0)
        if change > 5:
            score += 12
        elif change > 2:
            score += 6
        elif change > 0:
            score += 2
        elif change < -5:
            score -= 12
        elif change < -2:
            score -= 6
        else:
            score -= 2

        # Distance from 52-week high (bearish if far below)
        price   = market.get("price", 0)
        high52  = market.get("high_52w", price) or price
        pct_off = ((price - high52) / high52 * 100) if high52 else 0
        if pct_off > -10:
            score += 8
        elif pct_off > -25:
            score += 3
        elif pct_off < -50:
            score -= 8
        else:
            score -= 3

        # ── 2. Fear & Greed (weight: 25 pts — contrarian) ────────────────
        fg = fear_greed.get("value", 50)
        if fg <= 15:        # extreme fear → contrarian buy
            score += 15
        elif fg <= 30:
            score += 8
        elif fg <= 45:
            score += 3
        elif fg <= 55:
            score += 0
        elif fg <= 70:
            score -= 5
        elif fg <= 85:
            score -= 10
        else:               # extreme greed → contrarian sell
            score -= 15

        # ── 3. On-chain: MVRV (weight: 15 pts) ───────────────────────────
        mvrv = _to_float(onchain.get("mvrv"))
        if mvrv is not None:
            if mvrv < 1:
                score += 10   # historically undervalued
            elif mvrv < 2:
                score += 5
            elif mvrv < 3:
                score += 0
            elif mvrv < 4:
                score -= 7
            else:
                score -= 12   # historically overheated

        # ── 4. On-chain: NUPL (weight: 10 pts) ───────────────────────────
        nupl = _to_float(onchain.get("nupl"))
        if nupl is not None:
            if nupl < 0:
                score += 8    # capitulation
            elif nupl < 0.25:
                score += 4
            elif nupl < 0.5:
                score += 0
            elif nupl < 0.75:
                score -= 5
            else:
                score -= 10   # euphoria

        # ── 5. On-chain: SOPR (weight: 5 pts) ────────────────────────────
        sopr = _to_float(onchain.get("sopr"))
        if sopr is not None:
            if sopr < 0.98:
                score += 4    # spent coins at loss → fear
            elif sopr < 1.0:
                score += 2
            elif sopr < 1.02:
                score += 0
            else:
                score -= 3

        # ── Clamp ─────────────────────────────────────────────────────────
        score = max(0, min(100, score))

        # ── Label ─────────────────────────────────────────────────────────
        if score >= 70:
            label = "STRONG BUY"
            confidence = min(95, 70 + (score - 70))
        elif score >= 55:
            label = "BUY"
            confidence = 55 + (score - 55) * 2
        elif score >= 45:
            label = "NEUTRAL"
            confidence = 50
        elif score >= 30:
            label = "SELL"
            confidence = 55 + (45 - score) * 2
        else:
            label = "STRONG SELL"
            confidence = min(95, 70 + (30 - score))

        return {
            "score":      round(score),
            "label":      label,
            "confidence": round(confidence),
        }


def _to_float(val):
    if val is None or val == "N/A":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None

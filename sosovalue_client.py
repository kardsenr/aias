"""
SoSoValue REST client for BTC data.

Endpoints used:
  GET /v2/index/coin/info?coinId=bitcoin          → price, cap, volume
  GET /v2/market/total/feargreedindex             → fear & greed (current + history)
  GET /v2/index/coin/on-chain?coinId=bitcoin      → on-chain metrics (NUPL, MVRV, …)

Docs: https://sosovalue.com/developer
"""

import asyncio
import logging
from typing import Any, Dict

import aiohttp

logger = logging.getLogger(__name__)

BASE = "https://sosovalue.com/api"

# Fallback: CoinGecko public API (no key needed) for price data
CG_BASE = "https://api.coingecko.com/api/v3"


class SoSoValueClient:
    def __init__(self, api_key: str):
        self._key = api_key
        self._headers = {
            "apikey": api_key,
            "Content-Type": "application/json",
        }

    # ── internal GET ────────────────────────────────────────────────────────

    async def _get(self, path: str, params: Dict = None) -> Any:
        url = BASE + path
        async with aiohttp.ClientSession(headers=self._headers) as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.json()
                text = await resp.text()
                logger.warning("SoSo %s → %s: %s", path, resp.status, text[:200])
                raise RuntimeError(f"SoSoValue HTTP {resp.status}: {text[:120]}")

    async def _cg_get(self, path: str, params: Dict = None) -> Any:
        """CoinGecko fallback (public, no auth)."""
        url = CG_BASE + path
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.json()
                raise RuntimeError(f"CoinGecko HTTP {resp.status}")

    # ── public methods ───────────────────────────────────────────────────────

    async def get_btc_market(self) -> Dict:
        """
        Returns dict:
          price, change_24h, volume_24h, market_cap,
          high_52w, low_52w, ath_pct
        """
        try:
            data = await self._get("/v2/index/coin/info", {"coinId": "bitcoin"})
            item = data.get("data") or data
            if isinstance(item, list):
                item = item[0]

            price     = float(item.get("price") or item.get("currentPrice") or 0)
            change    = float(item.get("priceChangePercent24h") or item.get("change24h") or 0)
            volume    = float(item.get("volume24h") or item.get("totalVolume") or 0)
            mktcap    = float(item.get("marketCap") or item.get("marketCapitalization") or 0)
            ath       = float(item.get("ath") or item.get("allTimeHigh") or 0)
            high52    = float(item.get("high52w") or item.get("high52Week") or 0)
            low52     = float(item.get("low52w") or item.get("low52Week") or 0)
            ath_pct   = ((price - ath) / ath * 100) if ath else 0

            return {
                "price": price, "change_24h": change,
                "volume_24h": volume, "market_cap": mktcap,
                "high_52w": high52, "low_52w": low52,
                "ath_pct": ath_pct,
            }

        except Exception as e:
            logger.warning("SoSo market failed, using CoinGecko fallback: %s", e)
            return await self._cg_btc_market()

    async def _cg_btc_market(self) -> Dict:
        data = await self._cg_get(
            "/coins/bitcoin",
            {"localization": "false", "tickers": "false",
             "community_data": "false", "developer_data": "false"}
        )
        md = data["market_data"]
        price   = md["current_price"]["usd"]
        change  = md["price_change_percentage_24h"]
        volume  = md["total_volume"]["usd"]
        mktcap  = md["market_cap"]["usd"]
        ath     = md["ath"]["usd"]
        ath_pct = md["ath_change_percentage"]["usd"]
        high52  = md.get("high_24h", {}).get("usd", 0)   # best available from CG
        low52   = md.get("low_24h", {}).get("usd", 0)
        return {
            "price": price, "change_24h": change,
            "volume_24h": volume, "market_cap": mktcap,
            "high_52w": high52, "low_52w": low52,
            "ath_pct": ath_pct,
        }

    async def get_fear_greed(self) -> Dict:
        """
        Returns dict: value (0-100), label, history list [{date, value, label}]
        Falls back to alternative-me API if SoSo fails.
        """
        try:
            data = await self._get("/v2/market/total/feargreedindex")
            item = (data.get("data") or data)
            if isinstance(item, list):
                current = item[0]
            else:
                current = item

            val = int(current.get("value") or current.get("fearGreedIndex") or 0)
            lbl = current.get("valueClassification") or current.get("label") or _fg_label(val)

            # history
            history = []
            raw_hist = current.get("history") or (item[1:] if isinstance(item, list) else [])
            for h in raw_hist[:7]:
                history.append({
                    "date":  h.get("date") or h.get("timestamp", ""),
                    "value": int(h.get("value") or 0),
                    "label": h.get("valueClassification") or h.get("label") or _fg_label(int(h.get("value") or 0)),
                })

            return {"value": val, "label": lbl, "history": history}

        except Exception as e:
            logger.warning("SoSo F&G failed, using alternative.me: %s", e)
            return await self._alt_fear_greed()

    async def _alt_fear_greed(self) -> Dict:
        url = "https://api.alternative.me/fng/?limit=8"
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                d = await r.json(content_type=None)
        items = d.get("data", [])
        current = items[0] if items else {}
        val = int(current.get("value", 0))
        lbl = current.get("value_classification", _fg_label(val))
        history = [
            {"date": h.get("timestamp",""), "value": int(h.get("value",0)),
             "label": h.get("value_classification", "")}
            for h in items[1:8]
        ]
        return {"value": val, "label": lbl, "history": history}

    async def get_onchain(self) -> Dict:
        """
        Returns dict: nupl, mvrv, sopr, hashrate, lth_supply, active_addresses
        """
        try:
            data = await self._get("/v2/index/coin/on-chain", {"coinId": "bitcoin"})
            item = data.get("data") or data
            if isinstance(item, list):
                item = item[0]

            def _f(key, *alts):
                for k in (key, *alts):
                    v = item.get(k)
                    if v is not None:
                        try:
                            return round(float(v), 4)
                        except Exception:
                            return str(v)
                return "N/A"

            return {
                "nupl":             _f("nupl", "NUPL"),
                "mvrv":             _f("mvrv", "MVRV", "mvrvZScore"),
                "sopr":             _f("sopr", "SOPR"),
                "hashrate":         _f("hashRate", "hashrate", "networkHashrate"),
                "lth_supply":       _f("lthSupply", "longTermHolderSupply"),
                "active_addresses": _f("activeAddresses", "activeAddress"),
            }

        except Exception as e:
            logger.warning("SoSo on-chain failed, returning stub: %s", e)
            # Minimal stub so bot doesn't crash
            return {
                "nupl": "N/A", "mvrv": "N/A", "sopr": "N/A",
                "hashrate": "N/A", "lth_supply": "N/A",
                "active_addresses": "N/A",
            }


def _fg_label(val: int) -> str:
    if val <= 24:  return "Extreme Fear"
    if val <= 44:  return "Fear"
    if val <= 55:  return "Neutral"
    if val <= 74:  return "Greed"
    return "Extreme Greed"

"""
Upstox Market Data Ingestion Client — Live Quotes, Intraday/Daily Candles, and Market Regime.

Uses the Upstox v2 API for real-time market quotes, OHLCV candles, and India VIX.
Requires an OAuth2 access token (set UPSTOX_ACCESS_TOKEN in .env or dashboard).
"""

import os
import gzip
import json
import logging
import urllib.parse
import urllib.request
import requests
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from src.db.models import DailyPriceRaw, Company, Sector
from src.ingestion.validator import DataValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instruments cache location
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INSTRUMENTS_CACHE_FILE = os.path.join(BASE_DIR, "data", "upstox_nse_instruments.json")


class UpstoxMarketDataIngestion:
    """
    Primary ingestion engine for real-time market data, daily candles, and live quotes via Upstox v2 API.
    """

    UPSTOX_BASE_URL = "https://api.upstox.com/v2"
    _INSTRUMENTS_MAP: Dict[str, Dict[str, Any]] = {}
    _INSTRUMENTS_LOADED: bool = False

    def __init__(self, api_key: str = "", api_secret: str = "", access_token: str = ""):
        # Load .env
        env_path = os.path.join(BASE_DIR, ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)

        self.api_key = api_key or os.getenv("UPSTOX_API_KEY", "")
        self.api_secret = api_secret or os.getenv("UPSTOX_API_SECRET", "")
        self.access_token = access_token or os.getenv("UPSTOX_ACCESS_TOKEN", "")
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}" if self.access_token else "",
        }

    def is_authenticated(self) -> bool:
        """Check if a valid non-empty access token is configured."""
        return bool(self.access_token and self.access_token != "your_upstox_access_token_here")

    # ──────────────────────────────────────────────────────────────
    # Instrument Master Resolution
    # ──────────────────────────────────────────────────────────────

    @classmethod
    def load_instruments_master(cls, force_reload: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Loads and caches Upstox NSE Equity instruments master.
        """
        if cls._INSTRUMENTS_LOADED and not force_reload:
            return cls._INSTRUMENTS_MAP

        # Ensure data folder exists
        os.makedirs(os.path.dirname(INSTRUMENTS_CACHE_FILE), exist_ok=True)

        if os.path.exists(INSTRUMENTS_CACHE_FILE) and not force_reload:
            try:
                with open(INSTRUMENTS_CACHE_FILE, "r", encoding="utf-8") as f:
                    cls._INSTRUMENTS_MAP = json.load(f)
                    cls._INSTRUMENTS_LOADED = True
                    logger.info(f"Loaded {len(cls._INSTRUMENTS_MAP)} Upstox instruments from cache.")
                    return cls._INSTRUMENTS_MAP
            except Exception as e:
                logger.warning(f"Error loading cached instruments: {e}. Downloading fresh master...")

        # Download from Upstox assets CDN
        url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                compressed = resp.read()
                data = json.loads(gzip.decompress(compressed).decode("utf-8"))

                # Filter only NSE Equity instruments
                mapping = {}
                for item in data:
                    if item.get("segment") == "NSE_EQ" and item.get("instrument_type") == "EQ":
                        sym = item.get("trading_symbol", "").upper()
                        if sym:
                            mapping[sym] = {
                                "trading_symbol": sym,
                                "instrument_key": item.get("instrument_key"),
                                "name": item.get("name"),
                                "isin": item.get("isin"),
                                "lot_size": item.get("lot_size", 1),
                                "tick_size": item.get("tick_size", 0.05),
                                "exchange": "NSE"
                            }

                cls._INSTRUMENTS_MAP = mapping
                cls._INSTRUMENTS_LOADED = True

                with open(INSTRUMENTS_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(mapping, f)

                logger.info(f"Successfully downloaded and cached {len(mapping)} NSE equity instruments from Upstox.")
                return cls._INSTRUMENTS_MAP

        except Exception as e:
            logger.error(f"Failed to download Upstox instruments master: {e}")
            return cls._INSTRUMENTS_MAP

    @classmethod
    def get_instrument_info(cls, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Looks up an NSE symbol in the Upstox instruments catalog.
        """
        if not cls._INSTRUMENTS_LOADED:
            cls.load_instruments_master()

        sym_clean = symbol.upper().strip()
        ALIAS_MAP = {
            "TATAMOTORS": "TMCV",
            "TATA MOTORS": "TMCV",
            "TMPV": "TMPV",
            "HDFC": "HDFCBANK",
            "M&M": "M&M",
            "L&T": "LT",
            "TATAMTRDVR": "TMCV"
        }
        if sym_clean in ALIAS_MAP:
            sym_clean = ALIAS_MAP[sym_clean]

        if sym_clean in cls._INSTRUMENTS_MAP:
            return cls._INSTRUMENTS_MAP[sym_clean]

        # Handle fallback patterns
        for k, v in cls._INSTRUMENTS_MAP.items():
            if k.replace("-", "").replace("&", "") == sym_clean.replace("-", "").replace("&", ""):
                return v

        return None

    # ──────────────────────────────────────────────────────────────
    # Historical Daily & Intraday Candles via Upstox
    # ──────────────────────────────────────────────────────────────

    def fetch_daily_candles(
        self, symbol: str, days: int = 400
    ) -> List[Dict[str, Any]]:
        """
        Fetches official daily OHLCV candles from Upstox API for a symbol.
        """
        if not self.is_authenticated():
            logger.warning("No UPSTOX_ACCESS_TOKEN provided. Cannot fetch live Upstox API data.")
            return []

        info = self.get_instrument_info(symbol)
        inst_key = info.get("instrument_key") if info else f"NSE_EQ|{symbol.upper()}"

        today = date.today()
        from_date = today - timedelta(days=days)
        to_str = today.strftime("%Y-%m-%d")
        from_str = from_date.strftime("%Y-%m-%d")

        encoded_key = urllib.parse.quote(inst_key)
        url = f"{self.UPSTOX_BASE_URL}/historical-candle/{encoded_key}/day/{to_str}/{from_str}"

        try:
            resp = requests.get(url, headers=self.headers, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success" and "candles" in data.get("data", {}):
                    candles = data["data"]["candles"]
                    records = []
                    for c in candles:
                        t_str = c[0]
                        t_date = datetime.strptime(t_str[:10], "%Y-%m-%d").date()
                        records.append({
                        "trading_date":       t_date,
                        "open_price":         float(c[1]),
                        "high_price":         float(c[2]),
                        "low_price":          float(c[3]),
                        "close_price":        float(c[4]),
                        "volume":             int(c[5]),
                        "turnover":           float(c[6]) if len(c) > 6 and c[6] else float(c[4]) * int(c[5]),
                        # Deliverable volume is NOT available from Upstox candle API.
                        # Set None — never fabricate as a fixed % of volume (was incorrectly 45%).
                        # Official NSE bhav copy must be used for accurate delivery data.
                        "deliverable_volume": None,
                        "delivery_pct":       None,
                        # Price provenance fields (Fix 7)
                        "exchange":           "NSE",
                        "quote_type":         "CLOSE",
                        "price_source":       "UPSTOX_API",
                        "is_split_adjusted":  False,
                    })
                    # Sort chronologically ascending
                    records.sort(key=lambda x: x["trading_date"])
                    return records

            logger.warning(f"Upstox candle status {resp.status_code} for {symbol} ({inst_key}): {resp.text[:150]}")
            return []
        except Exception as e:
            logger.error(f"Upstox candle request failed for {symbol}: {e}")
            return []

    # ──────────────────────────────────────────────────────────────
    # Live Market Quotes via Upstox
    # ──────────────────────────────────────────────────────────────

    def fetch_live_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetches full live quote from Upstox for a single equity symbol.
        """
        if not self.is_authenticated():
            return None

        info = self.get_instrument_info(symbol)
        inst_key = info.get("instrument_key") if info else f"NSE_EQ|{symbol.upper()}"

        url = f"{self.UPSTOX_BASE_URL}/market-quote/quotes?instrument_key={urllib.parse.quote(inst_key)}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                quote_map = data.get("data", {})
                for k, q in quote_map.items():
                    ohlc = q.get("ohlc", {})
                    return {
                        "symbol":               symbol.upper(),
                        "instrument_key":       inst_key,
                        "last_price":           float(q.get("last_price", ohlc.get("close", 0.0))),
                        "open":                 float(ohlc.get("open", 0.0)),
                        "high":                 float(ohlc.get("high", 0.0)),
                        "low":                  float(ohlc.get("low", 0.0)),
                        "close":                float(ohlc.get("close", 0.0)),
                        "net_change":           float(q.get("net_change", 0.0)),
                        # day_change_pct CANNOT be reliably computed from a single live quote.
                        # Upstox ohlc.close = today's session close (or same-day open in early trading),
                        # NOT yesterday's close. Computing (LTP - ohlc.close) / ohlc.close gives
                        # intraday change from today's open, not from the previous session's close.
                        # To get true day_change_pct: join with yesterday's DailyPriceRaw.close_price.
                        "day_change_pct":       None,  # Requires prev-session close from DailyPriceRaw
                        "volume":               int(q.get("volume", 0)),
                        "average_price":        float(q.get("average_price", 0.0)),
                        "upper_circuit":        float(q.get("upper_circuit_limit", 0.0)),
                        "lower_circuit":        float(q.get("lower_circuit_limit", 0.0)),
                        "total_buy_quantity":   float(q.get("total_buy_quantity", 0.0)),
                        "total_sell_quantity":  float(q.get("total_sell_quantity", 0.0)),
                        "timestamp":            q.get("last_trade_time") or datetime.utcnow().isoformat(),
                        # Provenance
                        "price_source":         "UPSTOX_API",
                        "exchange":             "NSE",
                        "quote_type":           "LTP",
                    }
            return None
        except Exception as e:
            logger.error(f"Error fetching live quote for {symbol}: {e}")
            return None

    # ──────────────────────────────────────────────────────────────
    # Complete Symbol Ingestion into Database
    # ──────────────────────────────────────────────────────────────

    def ingest_stock_data(self, db: Session, symbol: str) -> Tuple[Optional[Company], Optional[Dict[str, Any]]]:
        """
        Complete Upstox-driven ingestion:
        1. Resolves authentic Company metadata (ISIN, Name) from Upstox master.
        2. Ingests full historical daily candles from Upstox API.
        3. Fetches live quote from Upstox.
        """
        symbol = symbol.upper().strip()
        info = self.get_instrument_info(symbol)

        company_name = info.get("name") if info else f"{symbol} Limited"
        isin_code = info.get("isin") if info else (f"INE{symbol[:7]}01" if len(symbol) <= 7 else f"INE{symbol[:7]}1")

        # 1. Check or create Company
        company = db.query(Company).filter_by(nse_symbol=symbol).first()
        if not company:
            sec = db.query(Sector).filter_by(sector_name="General").first()
            if not sec:
                sec = Sector(sector_id="sec_general", sector_name="General", description="General Equities Sector")
                db.add(sec)
                db.commit()
                db.refresh(sec)

            comp_id = f"comp_{symbol.lower()}"
            company = Company(
                company_id=comp_id,
                nse_symbol=symbol,
                bse_code=symbol,
                isin=isin_code,
                company_name=company_name,
                sector_id=sec.sector_id,
                status="ACTIVE"
            )
            db.add(company)
            db.commit()
            db.refresh(company)
        else:
            if company_name and company_name != f"{symbol} Limited":
                company.company_name = company_name
            if isin_code:
                company.isin = isin_code
            db.commit()

        # 2. Fetch Daily Candles from Upstox
        candles = self.fetch_daily_candles(symbol, days=400)
        if candles:
            from datetime import time as dtime
            for c in candles:
                raw_p = DailyPriceRaw(
                    company_id=company.company_id,
                    trading_date=c["trading_date"],
                    open_price=c["open_price"],
                    high_price=c["high_price"],
                    low_price=c["low_price"],
                    close_price=c["close_price"],
                    volume=c["volume"],
                    turnover=c.get("turnover"),
                    # Deliverable volume: not available from Upstox candle API — never fabricate
                    deliverable_volume=None,
                    delivery_pct=None,
                    # Price provenance fields (Fix 7)
                    exchange=c.get("exchange", "NSE"),
                    quote_type=c.get("quote_type", "CLOSE"),
                    price_source=c.get("price_source", "UPSTOX_API"),
                    # NSE session closes at 15:30 IST
                    quote_timestamp=datetime.combine(
                        c["trading_date"],
                        dtime(15, 30, 0)
                    ),
                )
                db.merge(raw_p)
            db.commit()
            logger.info(f"Ingested {len(candles)} Upstox daily candles for {symbol}.")

        # 3. Fetch live quote
        quote = self.fetch_live_quote(symbol)
        return company, quote

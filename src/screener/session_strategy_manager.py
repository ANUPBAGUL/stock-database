"""
Session Strategy Manager.
Decouples macro market diagnosis from live screening execution.
Caches strategy blueprints with a 60-minute TTL or on-demand refresh,
ensuring the live scanner runs in sub-second time (< 800ms).
"""

import time
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from src.mcp.market_intelligence_client import MarketIntelligenceClient
from src.llm.market_strategist import MarketStrategist
from src.llm.market_strategist_models import AdaptiveStrategyAST

logger = logging.getLogger(__name__)


class SessionStrategyManager:
    """
    In-memory session manager caching the live market intelligence and strategy AST.
    """

    _OFF_MARKET_TTL_SECONDS: float = 3600.0  # 60-Minute Off-Market Cache
    _LIVE_MARKET_TTL_SECONDS: float = 180.0   # 3-Minute Live Market Hours Cache (09:15 - 15:30 IST)
    _CACHED_STRATEGIES: Dict[str, Tuple[AdaptiveStrategyAST, str, float]] = {}
    _CACHED_MARKET_DATA: Optional[Tuple[Dict[str, Any], float]] = None
    _CLIENT = MarketIntelligenceClient()

    @classmethod
    def _get_effective_ttl(cls) -> float:
        """
        Dynamically returns 3 minutes during live NSE market hours (Mon-Fri 09:15-15:30 IST)
        to prevent stale macro telemetry, or 60 minutes outside market hours.
        """
        now_dt = datetime.now()
        # Monday is 0, Friday is 4
        if now_dt.weekday() < 5:
            # Check if between 09:15 and 15:30
            current_minute = (now_dt.hour * 60) + now_dt.minute
            market_open_minute = (9 * 60) + 15
            market_close_minute = (15 * 60) + 30
            if market_open_minute <= current_minute <= market_close_minute:
                return cls._LIVE_MARKET_TTL_SECONDS
        return cls._OFF_MARKET_TTL_SECONDS

    @classmethod
    def get_market_intelligence(cls, force_refresh: bool = False) -> Dict[str, Any]:
        """Returns cached market intelligence or fetches fresh data from NSE."""
        now = time.time()
        ttl = cls._get_effective_ttl()
        if not force_refresh and cls._CACHED_MARKET_DATA is not None:
            data, ts = cls._CACHED_MARKET_DATA
            if now - ts < ttl:
                return data

        data = cls._CLIENT.fetch_live_market_intelligence()
        cls._CACHED_MARKET_DATA = (data, now)
        return data

    @classmethod
    def get_active_strategy(
        cls,
        horizon: str = "SWING",
        user_intent: Optional[str] = None,
        force_refresh: bool = False
    ) -> Tuple[AdaptiveStrategyAST, str]:
        """
        Retrieves the active strategy blueprint in < 1ms if cached,
        or synthesizes a new one if expired or forced.
        """
        now = time.time()
        cache_key = f"{horizon.upper()}:{user_intent or 'DEFAULT'}"

        ttl = cls._get_effective_ttl()
        if not force_refresh and cache_key in cls._CACHED_STRATEGIES:
            ast, src, ts = cls._CACHED_STRATEGIES[cache_key]
            if now - ts < ttl:
                return ast, src

        market_data = cls.get_market_intelligence(force_refresh=force_refresh)
        ast, src = MarketStrategist.synthesize_strategy(market_data, horizon=horizon, user_intent=user_intent)
        cls._CACHED_STRATEGIES[cache_key] = (ast, src, now)
        return ast, src

    @classmethod
    def clear_cache(cls):
        """Clears cached session data."""
        cls._CACHED_STRATEGIES.clear()
        cls._CACHED_MARKET_DATA = None

"""
Core B: LLM CIO Copilot & Deterministic Invariant Firewall.
Orchestrates closed-world grounding, LLM reasoning, invariant verification,
and automatic failover to Core A (AlgorithmicStrategist).
"""

import os
import json
import logging
import urllib.request
from typing import Dict, Any, List, Optional, Tuple

from src.llm.market_strategist_models import MarketRegime, HorizonType, AdaptiveStrategyAST
from src.llm.algorithmic_strategist import AlgorithmicStrategist

logger = logging.getLogger(__name__)


class InvariantFirewall:
    """
    Deterministic gatekeeper that validates generated strategy parameters
    against physical market reality and sector momentum data.
    """

    @classmethod
    def validate_and_repair(
        cls,
        ast: AdaptiveStrategyAST,
        market_data: Dict[str, Any]
    ) -> Tuple[AdaptiveStrategyAST, List[str]]:
        """
        Validates the strategy against input market data.
        Returns the repaired/confirmed AST along with an audit log of warnings.
        """
        audit_log: List[str] = []
        rot = market_data.get("sector_rotation_matrix", {})
        lagging = rot.get("lagging_sectors", [])
        leading = rot.get("leading_sectors", [])

        # Invariant 1: Sector Provenance (No severely lagging sectors allowed in favored list)
        repaired_favored = []
        for s in ast.favored_sectors:
            if s in lagging and s not in leading:
                audit_log.append(f"REJECTED: '{s}' removed from favored list because it is in the Lagging RRG quadrant.")
            else:
                repaired_favored.append(s)

        if not repaired_favored:
            repaired_favored = leading[:3] if leading else ["NIFTY PHARMA", "NIFTY AUTO"]
            audit_log.append(f"REPAIRED: Injected top leading sectors: {repaired_favored}")

        ast.favored_sectors = repaired_favored

        # Invariant 2: RSI Corridors
        if ast.min_rsi >= ast.max_rsi:
            audit_log.append(f"REPAIRED: Inverted RSI bounds ({ast.min_rsi} >= {ast.max_rsi}). Reset to [52.0, 68.0].")
            ast.min_rsi = 52.0
            ast.max_rsi = 68.0
        else:
            ast.min_rsi = max(40.0, min(58.0, ast.min_rsi))
            ast.max_rsi = max(62.0, min(75.0, ast.max_rsi))

        # Invariant 3: Liquidity Floor
        if ast.min_turnover_cr < 1.0:
            audit_log.append(f"REPAIRED: Turnover floor too low ({ast.min_turnover_cr} Cr). Reset to 5.0 Cr.")
            ast.min_turnover_cr = 5.0

        # Invariant 4: Relative Volume
        ast.min_relative_volume = max(1.2, min(4.0, ast.min_relative_volume))

        # Invariant 5: Valuation Ceiling
        if ast.max_pe_ratio is not None and ast.max_pe_ratio < 15.0:
            audit_log.append(f"REPAIRED: P/E ceiling unrealistic ({ast.max_pe_ratio}x). Reset to 35.0x.")
            ast.max_pe_ratio = 35.0

        # Invariant 6: Grounded CIO Memo
        if not getattr(ast, "cio_memo", None):
            deriv = market_data.get("derivatives_positioning", {})
            breadth = market_data.get("market_breadth", {})
            vix = market_data.get("volatility_regime", {})
            spreads = market_data.get("market_dispersion_spreads", {})
            fii_pct = deriv.get("fii_index_future_long_pct", 50.0)
            coiled = market_data.get("is_coiled_spring", False)
            net_highs = breadth.get("net_new_52w_highs", 0)
            vix_val = vix.get("india_vix", 13.0)
            spread_val = spreads.get("midcap_vs_nifty_spread_pct", 0.0)
            sec_str = ", ".join(ast.favored_sectors[:3]) if ast.favored_sectors else "Leading Sectors"
            ast.cio_memo = (
                f"{ast.regime.value} active. Market breadth shows {breadth.get('advances', 0)} Adv / {breadth.get('declines', 0)} Dec "
                f"with {net_highs:+d} Net 52W Highs and Midcap alpha at {spread_val:+0.2f}%. "
                f"FII Index Futures at {fii_pct:.1f}% Long"
                f"{' (⚡ Coiled-Spring short-covering squeeze active)' if coiled else ''}. "
                f"India VIX at {vix_val:.2f}. "
                f"Deploying {ast.tactical_posture} into {sec_str} with {ast.min_relative_volume}x+ RVOL breakouts and strict ATR brackets."
            )

        return ast, audit_log


class MarketStrategist:
    """
    Unified Strategist facade.
    Attempts LLM CIO Copilot if API configured, with automatic fallback to AlgorithmicStrategist.
    """

    SYSTEM_PROMPT = """You are an elite Institutional Chief Investment Officer (CIO) for Indian Equities (NSE/BSE).
Your goal is to formulate an adaptive screening strategy conditioned on live market data and user intent.

CRITICAL ANTI-HALLUCINATION RULES:
1. CLOSED-WORLD ASSUMPTION: You possess ZERO external knowledge of today's news or prices.
   You must reason ONLY from the verified JSON context provided below.
2. ZERO STOCK TIPS: You are strictly forbidden from inventing stock symbols, corporate news, or earnings rumors.
3. CONSTRAINED AST OUTPUT: You must output ONLY a valid JSON object matching the AdaptiveStrategyAST schema.
4. RRG RESPECT: You must NEVER favor a sector categorized under 'lagging_sectors'.
5. CORRIDOR DISCIPLINE: All parameters must remain inside safe institutional boundaries.
"""

    @classmethod
    def synthesize_strategy(
        cls,
        market_data: Dict[str, Any],
        horizon: str = "SWING",
        user_intent: Optional[str] = None,
        force_algorithmic: bool = False
    ) -> Tuple[AdaptiveStrategyAST, str]:
        """
        Synthesizes the strategy AST.
        Returns (AdaptiveStrategyAST, strategist_source: "LLM_COPILOT" | "ALGORITHMIC_CORE_A")
        """
        # If algorithmic forced or no API key, execute Core A
        has_openai = bool(os.environ.get("OPENAI_API_KEY"))
        has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
        has_gemini = bool(os.environ.get("GEMINI_API_KEY"))

        if force_algorithmic or not (has_openai or has_anthropic or has_gemini):
            ast = AlgorithmicStrategist.compile_strategy(market_data, horizon, user_intent)
            repaired_ast, audit_log = InvariantFirewall.validate_and_repair(ast, market_data)
            return repaired_ast, "ALGORITHMIC_CORE_A"

        # If LLM key is present, attempt LLM Copilot synthesis
        try:
            llm_ast = cls._call_llm_copilot(market_data, horizon, user_intent)
            repaired_ast, audit_log = InvariantFirewall.validate_and_repair(llm_ast, market_data)
            if audit_log:
                logger.info(f"[MarketStrategist] Firewall applied repairs: {audit_log}")
            return repaired_ast, "LLM_COPILOT"
        except Exception as e:
            logger.warning(f"[MarketStrategist] LLM Copilot failed ({e}). Executing failover to Core A.")
            ast = AlgorithmicStrategist.compile_strategy(market_data, horizon, user_intent)
            repaired_ast, _ = InvariantFirewall.validate_and_repair(ast, market_data)
            return repaired_ast, "ALGORITHMIC_CORE_A"

    @classmethod
    def _call_gemini_copilot(
        cls,
        payload: Dict[str, Any],
        market_data: Dict[str, Any],
        horizon: str,
        user_intent: Optional[str],
        api_key: str
    ) -> AdaptiveStrategyAST:
        """Calls Google Gemini API with multi-model fallback."""
        models_to_try = [
            "gemini-flash-lite-latest",
            "models/gemini-2.5-flash",
            "gemini-flash-latest"
        ]
        prompt = f"""{cls.SYSTEM_PROMPT}

You must return ONLY a JSON object conforming to this schema:
{{
  "horizon": "{horizon.upper()}",
  "regime": "{market_data.get('overall_regime', 'SELECTIVE_ROTATION')}",
  "tactical_posture": "Detailed institutional tactical posture string",
  "user_intent_evaluated": "Evaluation of user intent if provided",
  "favored_sectors": ["Leading Sector 1", "Leading Sector 2"],
  "excluded_sectors": ["Lagging Sector 1"],
  "target_tv_industry_clusters": ["Industry 1", "Industry 2"],
  "min_rsi": 52.0,
  "max_rsi": 68.0,
  "min_relative_volume": 1.8,
  "max_debt_to_equity": 1.2,
  "max_pe_ratio": 50.0,
  "min_turnover_cr": 5.0,
  "near_52w_high_pct": 5.0
}}

Live Market Diagnostics Context:
{json.dumps(payload, indent=2)}
"""
        req_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        post_data = json.dumps(req_body).encode("utf-8")
        last_err = None

        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            if "models/" in model_name:
                url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
            try:
                req = urllib.request.Request(url, data=post_data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    if resp.status == 200:
                        res = json.loads(resp.read().decode("utf-8"))
                        text_part = res["candidates"][0]["content"]["parts"][0]["text"]
                        raw_json = json.loads(text_part)
                        base_ast = AlgorithmicStrategist.compile_strategy(market_data, horizon, user_intent)
                        raw_json["compiled_tv_predicates"] = [
                            p.dict() if hasattr(p, "dict") else p for p in base_ast.compiled_tv_predicates
                        ]
                        return AdaptiveStrategyAST(**raw_json)
            except Exception as err:
                last_err = err
                logger.warning(f"[MarketStrategist] Gemini model {model_name} failed: {err}")

        raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")

    @classmethod
    def _call_llm_copilot(
        cls,
        market_data: Dict[str, Any],
        horizon: str,
        user_intent: Optional[str]
    ) -> AdaptiveStrategyAST:
        """
        Calls available LLM API with structured output.
        Falls back to AlgorithmicStrategist if call fails.
        """
        # Lightweight JSON prompt construction
        payload = {
            "horizon": horizon,
            "user_intent": user_intent,
            "overall_regime": market_data.get("overall_regime"),
            "market_breadth": market_data.get("market_breadth"),
            "institutional_flows": market_data.get("institutional_flows_cash"),
            "sector_rotation": market_data.get("sector_rotation_matrix")
        }

        # 1. Check Gemini
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            return cls._call_gemini_copilot(payload, market_data, horizon, user_intent, gemini_key)

        # 2. Check OpenAI
        if os.environ.get("OPENAI_API_KEY"):
            from openai import OpenAI
            client = OpenAI()
            prompt = f"Analyze this live NSE market data and output the strategy AST:\n{json.dumps(payload, indent=2)}"
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": cls.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            raw_json = json.loads(resp.choices[0].message.content)
            # Merge with standard TV predicates
            base_ast = AlgorithmicStrategist.compile_strategy(market_data, horizon, user_intent)
            raw_json["compiled_tv_predicates"] = [p.dict() if hasattr(p, "dict") else p for p in base_ast.compiled_tv_predicates]
            return AdaptiveStrategyAST(**raw_json)

        raise NotImplementedError("Configured LLM provider handler not active")

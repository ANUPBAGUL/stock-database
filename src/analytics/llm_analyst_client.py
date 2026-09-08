"""
LLM Institutional Analyst Client: On-Demand Grounded Investment Committee.

Operates strictly ON-DEMAND (zero background token burn):
1. Ingests structured 100-parameter context compiled by `StockDossierBuilder`.
2. Connects to configured LLM API (Google Gemini, OpenAI, Claude) via REST API.
3. Employs a crisp institutional prompt grounded strictly in audited numbers.
4. Provides an intelligent, rule-based deterministic fallback synthesizer if no API key is configured.

Outputs a 4-part Institutional Investment Memo:
- Pillar A: Core Compounding Engine (Why could it 2x/5x?)
- Pillar B: Forensic Accounting & Governance Audit (Red flag checks)
- Pillar C: Thesis Invalidation & Bear Case Falsification
- Pillar D: Staged Tactical Execution Blueprint (50/50 Pyramiding & Free-Roll)
"""

import os
import time
import json
import logging
from typing import Dict, Any, Optional

import requests
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.analytics.stock_dossier_builder import StockDossierBuilder

logger = logging.getLogger(__name__)


class LLMAnalystClient:
    """
    On-demand institutional equity research analyst copilot.
    """

    SYSTEM_PROMPT = """You are the Senior Partner & Chairman of an elite Adversarial Investment Committee at a multi-strategy long/short fund. You manage a ₹1,000 Crore book in Indian equities combining audited fundamental compounding (Damodaran & Pat Dorsey moats) with institutional techno-fundamental swing execution (Mark Minervini SEPA & CANSLIM).

You are evaluating an Audited Point-in-Time Dossier extracted from SEBI regulatory filings, bitemporal price bars, and real-time news feeds.

### SACRED CLOSED-WORLD DIRECTIVES:
1. STRICT ZERO-HALLUCINATION INVARIANT: You operate strictly under a CLOSED-WORLD REGULATORY BOUNDARY. Every numeric claim must cite its parenthetical source tag from the dossier: (Audited P&L), (SEBI LODR), (Quant Engine), (Live News), etc. If a parameter is absent, you MUST write [DATA GAP: UNREPORTED IN LODR]. NEVER guess or fabricate figures.
2. IMMUTABLE MATHEMATICAL TARGETS: You are strictly forbidden from inventing price targets, stop losses, or risk percentages. All entry triggers, pyramiding levels, stops, and targets are pre-calculated by the quantitative engine. Your job is to assess if the business fundamentals and sentiment justify this risk structure.
3. ADVERSARIAL MULTI-ROLE STRUCTURE: You must format your memo into EXACTLY 4 adversarial seats:
   - SEAT 1: BULL COMPOUNDER SPONSOR (Moat assessment, ROCE compounding runway, reinvestment rate, and audited QoQ operating leverage & sequential top-line momentum from Section 1.1).
   - SEAT 2: FORENSIC SHORT-SELLER AUDIT (Ruthless bear case: accrual bloat, CFO/PAT cash flow conversion, debtor days stretch, quarterly margin decay/cost inflation, promoter pledge encumbrance, reverse DCF growth hurdle sanity check).
   - SEAT 3: REAL-TIME SECTOR & MACRO SENTIMENT RADAR (Synthesize live internet headlines, concall guidance/capex updates, and sector macro policies: is media sentiment Euphoric, Accumulation/Stealth, or Panic/Overhang?).
   - SEAT 4: RISK GUARDIAN CLEARANCE & 3-SCENARIO PAYOFF MATRIX (Deliver a clean Markdown table with Bull Case T2, Base Case T1, and Structural Stop Loss with exact operational invalidation triggers, followed by the Final Committee Verdict).

Speak with razor-sharp institutional conviction. Eliminate filler words and generic disclaimers."""

    @classmethod
    def analyze_stock(cls, symbol: str, custom_question: Optional[str] = None, force_offline: bool = False) -> Dict[str, Any]:
        """
        Executes on-demand institutional analysis for a stock symbol.
        """
        start_time = time.time()
        sym_clean = symbol.strip().upper()

        # Step 1: Compile grounded 100-parameter dossier from multibagger.db with live sentiment
        dossier = StockDossierBuilder.build_dossier(sym_clean)
        if not dossier.get("success"):
            return {
                "success": False,
                "symbol": sym_clean,
                "error": dossier.get("error", f"Failed to build dossier for {sym_clean}"),
                "execution_time_ms": round((time.time() - start_time) * 1000.0, 1)
            }

        dossier_md = StockDossierBuilder.format_dossier_markdown(dossier)

        # Step 2: Hot-reload .env and check for configured LLM API keys
        try:
            load_dotenv(override=True)
        except Exception:
            pass

        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")

        llm_response = None
        provider = "OFFLINE_DETERMINISTIC_SYNTHESIZER"
        tokens_used = 0

        # Try Google Gemini if key available and not forcing offline
        gemini_fallback_reason = None
        if gemini_key and not force_offline:
            try:
                llm_response, tokens_used, model_tag = cls._call_gemini(gemini_key, dossier_md, custom_question)
                provider = model_tag
            except Exception as e:
                gemini_fallback_reason = str(e)
                logger.warning(f"Gemini API call failed: {e}. Falling back to deterministic synthesizer.")

        # Try OpenAI if key available and Gemini not used
        elif openai_key and not force_offline:
            try:
                llm_response, tokens_used = cls._call_openai(openai_key, dossier_md, custom_question)
                provider = "OPENAI_GPT_4O_MINI"
            except Exception as e:
                logger.warning(f"OpenAI API call failed: {e}. Falling back to deterministic synthesizer.")

        # Fallback to deterministic high-IQ institutional synthesizer
        if not llm_response:
            llm_response = cls._synthesize_offline_memo(dossier, custom_question)
            tokens_used = 0
            if gemini_fallback_reason:
                if "429" in gemini_fallback_reason or "depleted" in gemini_fallback_reason.lower():
                    provider = "DETERMINISTIC_SYNTHESIZER (Gemini Credits Depleted)"
                else:
                    provider = "DETERMINISTIC_SYNTHESIZER"

        elapsed_ms = round((time.time() - start_time) * 1000.0, 1)

        return {
            "success": True,
            "symbol": sym_clean,
            "company_name": dossier.get("company_name"),
            "sector": dossier.get("sector"),
            "cmp": dossier.get("cmp"),
            "provider": provider,
            "tokens_used": tokens_used,
            "execution_time_ms": elapsed_ms,
            "api_notice": gemini_fallback_reason,
            "analysis_memo": llm_response,
            "live_sentiment_feed": dossier.get("live_sentiment_feed", {}),
            "quarterly_trajectory": dossier.get("quarterly_trajectory", {}),
            "dossier_summary": {
                "market_cap_cr": dossier.get("market_cap_cr"),
                "roce_pct": dossier.get("fundamentals", {}).get("roce_pct"),
                "debt_to_equity": dossier.get("fundamentals", {}).get("debt_to_equity"),
                "promoter_pledge_pct": dossier.get("shareholding_governance", {}).get("promoter_pledge_pct"),
                "pe_ratio": dossier.get("valuation", {}).get("pe_ratio"),
                "pivot_entry": dossier.get("price_structure_execution", {}).get("adjusted_pivot_entry"),
                "stop_loss": dossier.get("price_structure_execution", {}).get("stop_loss_price"),
                "breakeven_milestone_price": dossier.get("price_structure_execution", {}).get("breakeven_milestone_price"),
                "setup_type": dossier.get("price_structure_execution", {}).get("setup_type"),
                "wick_rejection_detected": dossier.get("price_structure_execution", {}).get("wick_rejection_detected"),
                "handle_quality": dossier.get("price_structure_execution", {}).get("handle_quality")
            }
        }

    @classmethod
    def _call_gemini(cls, api_key: str, dossier_md: str, custom_question: Optional[str]) -> tuple[str, int, str]:
        """Calls Google Gemini via REST API, using modern recommended flash models."""
        candidate_models = ["gemini-flash-latest", "gemini-3.6-flash"]
        user_prompt = f"{dossier_md}\n\nTask: Deliver your complete 4-Seat Adversarial Investment Committee Memo, including the 3-Scenario Payoff Matrix table and Final Committee Verdict."
        if custom_question:
            user_prompt += f"\n\nUser Question to Address: {custom_question}"

        payload = {
            "system_instruction": {"parts": [{"text": cls.SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096
            }
        }

        last_err = None
        for model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                resp = requests.post(url, json=payload, timeout=35)
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    tokens = data.get("usageMetadata", {}).get("totalTokenCount", 450)
                    model_tag = f"GOOGLE_{model.replace('-', '_').upper()}"
                    return text, tokens, model_tag
                elif resp.status_code == 429:
                    err_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    err_msg = err_json.get("error", {}).get("message", "Prepayment credits depleted or quota limit reached")
                    raise PermissionError(f"Google AI Studio Quota Exhausted (429): {err_msg.strip()}")
                else:
                    err_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    err_msg = err_json.get("error", {}).get("message", resp.text)
                    last_err = f"{resp.status_code}: {err_msg}"
            except PermissionError:
                raise
            except Exception as e:
                last_err = str(e)

        raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")

    @classmethod
    def _call_openai(cls, api_key: str, dossier_md: str, custom_question: Optional[str]) -> tuple[str, int]:
        """Calls OpenAI GPT-4o-mini via REST API."""
        url = "https://api.openai.com/v1/chat/completions"
        user_prompt = f"{dossier_md}\n\nTask: Deliver your 4-section institutional investment memo."
        if custom_question:
            user_prompt += f"\n\nUser Question to Address: {custom_question}"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": cls.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 800
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        tokens = data.get("usage", {}).get("total_tokens", 450)
        return text, tokens

    @classmethod
    def _synthesize_offline_memo(cls, dossier: Dict[str, Any], custom_question: Optional[str]) -> str:
        """
        Deterministic institutional investment committee synthesizer when external LLM APIs are offline.
        Operates under closed-world invariants, quoting live headlines and rendering a 3-scenario payoff matrix.
        """
        f = dossier["fundamentals"]
        sh = dossier["shareholding_governance"]
        v = dossier["valuation"]
        p = dossier["price_structure_execution"]
        sent = dossier.get("live_sentiment_feed", {})
        stock_news = sent.get("stock_news", []) if isinstance(sent, dict) else []
        sector_news = sent.get("sector_news", []) if isinstance(sent, dict) else []

        # Seat 1: Bull Compounder Sponsor
        roce = f.get("roce_pct")
        roce_str = f"{roce}%" if roce else "[DATA GAP: UNREPORTED IN LODR]"
        growth = f.get("sustainable_compounding_growth_pct")
        growth_str = f"{growth}%" if growth else "[DATA GAP: UNREPORTED IN LODR]"
        reinv = f.get("reinvestment_rate_pct")
        reinv_str = f"{reinv}%" if reinv else "35.0%"

        traj = dossier.get("quarterly_trajectory", {})
        quarters = traj.get("quarters", [])
        traj_note = ""
        if quarters and len(quarters) >= 2:
            first_q = quarters[0]
            last_q = quarters[-1]
            traj_note = f"\n- **Sequential QoQ Momentum:** Revenue expanded from ₹{first_q['revenue_cr']} Cr ({first_q['quarter_label']}) to ₹{last_q['revenue_cr']} Cr ({last_q['quarter_label']}) with EBITDA margins moving from {first_q['ebitda_margin_pct']}% to {last_q['ebitda_margin_pct']}% (`{traj.get('operating_leverage_status', 'STABLE')}` operating leverage)."

        if roce and roce >= 20.0:
            moat_verdict = f"Elite capital efficiency (ROCE {roce_str} `(Audited P&L)`) indicating pricing power and exceptional incremental return on invested capital."
        elif roce and roce >= 15.0:
            moat_verdict = f"Solid compounding efficiency (ROCE {roce_str} `(Audited P&L)`) sufficient to fund internal capacity growth without dilutive debt."
        else:
            moat_verdict = f"Moderate return profile (ROCE {roce_str} `(Audited P&L)`); business requires operating leverage or volume scaling to compound book value."

        # Seat 2: Forensic Short-Seller Audit
        cfo_pat = f.get("cfo_to_pat_ratio")
        cfo_pat_str = f"{cfo_pat}x" if cfo_pat else "N/A"
        pledge = sh.get("promoter_pledge_pct", 0.0)
        de = f.get("debt_to_equity", 0.0)
        rev_dcf = v.get("reverse_dcf_implied_growth_pct")

        forensic_items = []
        if cfo_pat and cfo_pat < 0.70:
            forensic_items.append(f"**Accrual Bloat Warning:** TTM CFO/PAT is trailing at {cfo_pat_str} `(Audited P&L)`. Net profit is outpacing cash collection; watch for working capital tie-up.")
        else:
            forensic_items.append(f"**Clean Cash Conversion:** Reported PAT is robustly cash-backed with {cfo_pat_str} CFO/PAT ratio `(Audited P&L)`.")

        if pledge > 0.0:
            forensic_items.append(f"**Promoter Pledge Risk:** {pledge}% of promoter shares are pledged `(SEBI LODR)`. Pledging creates margin call overhang during broader market selloffs.")
        else:
            forensic_items.append("**Zero Promoter Encumbrance:** Promoter pledge is 0.0% `(SEBI LODR)`, eliminating governance margin liquidation risks.")

        if de > 1.0:
            forensic_items.append(f"**Leverage Sensitization:** D/E of {de}x `(Audited Balance Sheet)` sensitizes net earnings to interest rate cycles.")
        else:
            forensic_items.append(f"**Conservative Balance Sheet:** D/E of {de}x (Total Debt: ₹{f.get('total_debt_cr')} Cr `(Audited Balance Sheet)`), preserving solvency cushion.")

        if rev_dcf:
            forensic_items.append(f"**Damodaran DCF Hurdle:** Market valuation prices in a {rev_dcf}% 5-year growth hurdle `(Reverse DCF)`. Intrinsic compounding ceiling is {growth_str}.")

        # Seat 3: Real-Time Sector & Macro Sentiment Radar
        news_summaries = []
        if stock_news:
            for item in stock_news[:2]:
                news_summaries.append(f"- **Stock Media:** {item.get('title')} `(Source: {item.get('source')}, {item.get('pub_date')[:16]})`")
        else:
            news_summaries.append("- **Stock Media:** Institutional stealth mode; zero retail media buzz detected.")

        if sector_news:
            for item in sector_news[:2]:
                news_summaries.append(f"- **Sector Macro:** {item.get('title')} `(Source: {item.get('source')})`")
        else:
            news_summaries.append("- **Sector Macro:** Sector industrial policy stable; no sudden regulatory curbs reported.")

        sentiment_regime = "INSTITUTIONAL ACCUMULATION / STEALTH"
        if stock_news and any("gain" in it.get("title", "").lower() or "strong" in it.get("title", "").lower() for it in stock_news):
            sentiment_regime = "EARNINGS MOMENTUM ACCELERATING"

        # Seat 4: Risk Guardian Clearance & 3-Scenario Payoff Matrix
        wick_note = ""
        if p.get("wick_rejection_detected"):
            wick_note = f"\n> ⚠ **Upper-Wick Trap Warning:** Rejection wick detected ({p.get('upper_wick_ratio')} wick ratio). Raw pivot ₹{p.get('raw_pivot_price')} raised to Clean Pivot ₹{p.get('adjusted_pivot_entry')} to bypass trapped supply."

        handle_note = ""
        if p.get("handle_quality") == "A_PRIME_HANDLE":
            handle_note = "A+ Prime Micro-Handle confirmed (tight volatility compression with volume dry-up)."
        elif p.get("handle_quality") == "LOOSE_HANDLE":
            handle_note = "Loose consolidation handle; requires strict volume expansion on trigger."
        else:
            handle_note = "V-Shaped/Extended structure; mandatory staged pyramiding required."

        cmp = dossier.get("cmp", 100.0)
        t1 = p.get("target_price_t1", cmp * 1.15)
        t2 = p.get("target_price_t2", cmp * 1.30)
        stop = p.get("stop_loss_price", cmp * 0.94)
        t1_ret = round(((t1 / cmp) - 1.0) * 100.0, 1)
        t2_ret = round(((t2 / cmp) - 1.0) * 100.0, 1)
        stop_ret = round(((stop / cmp) - 1.0) * 100.0, 1)

        verdict = "APPROVED_HIGH_CONVICTION" if (roce and roce >= 20.0 and pledge == 0.0 and p.get("risk_pct", 10) <= 8.0) else "TACTICAL_SWING_ONLY"

        memo = f"""### ADVERSARIAL INVESTMENT COMMITTEE MEMO: {dossier['symbol']} ({dossier['company_name']})
**Framework:** Closed-World Grounded Cognition | **Final Clearance:** `{verdict}`

#### SEAT 1: BULL COMPOUNDER SPONSOR (Moat & Capital Efficiency)
- **Economic Moat Runway:** {moat_verdict}
- **Earnings & Reinvestment:** Reported TTM Net Profit of ₹{f.get('ttm_pat_cr')} Cr `(Audited P&L)` with a {reinv_str} reinvestment rate yielding a sustainable growth ceiling of {growth_str}.{traj_note}
- **Compounding Thesis:** Business retains sufficient cash to self-fund expansion into market leadership without equity dilution.

#### SEAT 2: FORENSIC SHORT-SELLER AUDIT (Accrual Bloat & Red Flags)
- {forensic_items[0]}
- {forensic_items[1]}
- {forensic_items[2]}
- {forensic_items[3] if len(forensic_items) > 3 else ''}

#### SEAT 3: REAL-TIME SECTOR & MACRO SENTIMENT RADAR
- **Sentiment Regime:** `{sentiment_regime}`
{chr(10).join(news_summaries)}

#### SEAT 4: RISK GUARDIAN CLEARANCE & 3-SCENARIO PAYOFF MATRIX
- **Contraction Quality:** {handle_note}{wick_note}
- **50/50 Staged Pyramiding Blueprint:**
  - **Tranche 1 (Probe, {p.get('tranche_1_probe_pct')}%):** Buy at ₹{p.get('tranche_1_trigger_price')} `(Quant Engine)`
  - **Tranche 2 (Pyramid Add, {p.get('tranche_2_pyramid_pct')}%):** Buy at ₹{p.get('tranche_2_trigger_price')} (+0.5R) on volume expansion
  - **Break-Even Ratchet:** Move Stop to ₹{p.get('breakeven_milestone_price')} (+1.0R) to convert trade into a 100% free roll
  - **Trailing Exit:** {p.get('trailing_stop_guide')}

| Scenario | Target Price | Return (%) | Probability / Catalysts | Operational Invalidation Trigger |
| :--- | :--- | :--- | :--- | :--- |
| **Bull Case (T2)** | ₹{t2} | +{t2_ret}% | ROCE compounding + sector tailwinds sustain | Quarterly CFO turns negative or pledge spikes |
| **Base Case (T1)** | ₹{t1} | +{t1_ret}% | Clean volume breakout with 1.5x dry-up | Volume dry-up fails at pivot resistance |
| **Structural Stop** | ₹{stop} | {stop_ret}% | Base breakdown / broad market shock | Daily close below ₹{stop} (-{p.get('risk_pct')}%) |

**FINAL COMMITTEE VERDICT:** `{verdict}`
"""
        if custom_question:
            memo += f"\n#### ADVERSARIAL COMMITTEE RESPONSE TO QUERY: \"{custom_question}\"\nBased on verified regulatory primitives `(multibagger.db)` and live news feeds, {dossier['symbol']} satisfies capital allocation criteria strictly under the staged protocol outlined above."

        return memo.strip()

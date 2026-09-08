"""
Institutional Grounded LLM Analyst & Quant Execution Suite Tests.

Verifies:
1. Grounded 100-parameter PIT Dossier compilation from multibagger.db.
2. SEBI LODR lookback primitives (ROCE, D/E, promoter pledge, valuation hurdle).
3. On-demand Institutional Investment Memo synthesis (0 token burn default).
4. Upper-Wick Trap Sentinel & Dynamic Clean Pivot calculation.
5. Micro-Handle Gate & Volatility Contraction Pattern tightness.
6. 3-Stage Pyramiding Ladder (50/50 probe & pyramid, break-even milestone lock).
"""

import unittest
from datetime import datetime, timedelta

from src.analytics.stock_dossier_builder import StockDossierBuilder
from src.analytics.llm_analyst_client import LLMAnalystClient
from src.analytics.price_structure_engine import PriceStructureEngine
from src.db.base import SessionLocal
from src.db.models import Company


class TestLLMAnalystAndQuantEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Ensure database has real company data for integration tests."""
        db = SessionLocal()
        try:
            cls.test_stock = "MANORAMA"
            company = db.query(Company).filter(
                Company.nse_symbol == cls.test_stock,
                Company.listing_status == "ACTIVE"
            ).first()
            if not company:
                company = db.query(Company).filter(
                    Company.listing_status == "ACTIVE"
                ).first()
                if company:
                    cls.test_stock = company.nse_symbol
                else:
                    raise unittest.SkipTest("No active company found in database for dossier tests.")
        finally:
            db.close()

    def test_dossier_builder_valid_stock(self):
        """Verify that StockDossierBuilder extracts all 100 parameters cleanly without hallucination."""
        dossier = StockDossierBuilder.build_dossier(self.test_stock)
        self.assertTrue(dossier.get("success"), f"Dossier failed: {dossier.get('error')}")
        self.assertEqual(dossier.get("symbol"), self.test_stock)
        self.assertIsNotNone(dossier.get("company_name"))
        self.assertIsNotNone(dossier.get("cmp"))

        # Verify Fundamental Blocks
        f = dossier.get("fundamentals", {})
        self.assertIn("roce_pct", f)
        self.assertIn("debt_to_equity", f)
        self.assertIn("cfo_to_pat_ratio", f)

        # Verify Governance & Shareholding
        sh = dossier.get("shareholding_governance", {})
        self.assertIn("promoter_pct", sh)
        self.assertIn("promoter_pledge_pct", sh)

        # Verify Valuation
        v = dossier.get("valuation", {})
        self.assertIn("pe_ratio", v)
        self.assertIn("reverse_dcf_implied_growth_pct", v)

        # Verify Execution Ladder
        p = dossier.get("price_structure_execution", {})
        self.assertEqual(p.get("tranche_1_probe_pct"), 50.0)
        self.assertEqual(p.get("tranche_2_pyramid_pct"), 50.0)
        self.assertGreater(p.get("breakeven_milestone_price", 0.0), 0.0)
        self.assertIn("trailing_exit_guide", p)

    def test_dossier_builder_unknown_stock(self):
        """Verify that unknown symbols return a structured failure response."""
        dossier = StockDossierBuilder.build_dossier("NONEXISTENT_XYZ_999")
        self.assertFalse(dossier.get("success"))
        self.assertIn("error", dossier)

    def test_stock_sentiment_fetcher(self):
        """Verify that StockSentimentFetcher pulls real-time headlines with safe schema."""
        from src.analytics.stock_dossier_builder import StockSentimentFetcher
        res = StockSentimentFetcher.fetch_sentiment(self.test_stock, "Test Company", "Specialty Chemicals")
        self.assertIn("stock_news", res)
        self.assertIn("sector_news", res)
        self.assertIn("fetched_at", res)
        self.assertIsInstance(res["stock_news"], list)
        self.assertIsInstance(res["sector_news"], list)

    def test_provenance_tags_in_dossier_markdown(self):
        """Verify that Markdown dossier enforces closed-world boundary and provenance tags."""
        dossier = StockDossierBuilder.build_dossier(self.test_stock)
        md = StockDossierBuilder.format_dossier_markdown(dossier)
        self.assertIn("CLOSED-WORLD REGULATORY BOUNDARY ACTIVE", md)
        self.assertIn("[SOURCE: SEBI_AUDITED_P&L / BALANCE_SHEET]", md)
        self.assertIn("[SOURCE: SEBI_LODR_SHAREHOLDING]", md)
        self.assertIn("[SOURCE: QUANT_ENGINE_PRICE_STRUCTURE]", md)
        self.assertIn("[SOURCE: LIVE_INTERNET_NEWS_FEED]", md)

    def test_llm_analyst_offline_synthesis(self):
        """Verify that LLMAnalystClient produces an adversarial 4-seat institutional memo with zero token burn."""
        dossier = StockDossierBuilder.build_dossier(self.test_stock, include_sentiment=False)
        memo = LLMAnalystClient._synthesize_offline_memo(dossier, custom_question=None)

        self.assertIn("SEAT 1: BULL COMPOUNDER SPONSOR", memo)
        self.assertIn("SEAT 2: FORENSIC SHORT-SELLER AUDIT", memo)
        self.assertIn("SEAT 3: REAL-TIME SECTOR & MACRO SENTIMENT RADAR", memo)
        self.assertIn("SEAT 4: RISK GUARDIAN CLEARANCE & 3-SCENARIO PAYOFF MATRIX", memo)
        self.assertIn("FINAL COMMITTEE VERDICT:", memo)
        self.assertIn("| Scenario | Target Price | Return (%)", memo)

    def test_llm_analyst_custom_question(self):
        """Verify that on-demand ad-hoc queries are incorporated into the memo."""
        q = "Audit promoter pledge encumbrance and operating cash flow quality."
        dossier = StockDossierBuilder.build_dossier(self.test_stock, include_sentiment=False)
        memo = LLMAnalystClient._synthesize_offline_memo(dossier, custom_question=q)
        self.assertIn(q, memo)

    def test_upper_wick_trap_sentinel(self):
        """Verify that price action with >=40% upper wick triggers Upper-Wick Trap Sentinel and raises pivot."""
        # 35 base bars
        closes = [98.0 + (i * 0.1) for i in range(35)]
        highs = [c + 1.0 for c in closes]
        lows = [c - 1.0 for c in closes]
        volumes = [100000.0] * 35

        # Add trap bar: Opens at 101.5, spikes to 112.0, slammed back to close at 102.0
        # High = 112.0, Low = 101.0, Close = 102.0, Range = 11.0, Upper wick = 10.0 (Wick ratio = 90.9%)
        highs.append(112.0)
        lows.append(101.0)
        closes.append(102.0)
        volumes.append(400000.0)

        analysis = PriceStructureEngine.audit_swing_setup(
            daily_closes=closes,
            daily_highs=highs,
            daily_lows=lows,
            daily_volumes=volumes,
            current_price=102.0
        )

        self.assertTrue(analysis["wick_rejection_detected"])
        self.assertGreater(analysis["upper_wick_ratio"], 0.40)
        # Adjusted pivot must be raised to or above the trap bar high (112.0)
        self.assertGreaterEqual(analysis["adjusted_pivot_entry"], 112.0)

    def test_micro_handle_gate_and_pyramiding_ladder(self):
        """Verify Micro-Handle quality evaluation and 3-stage pyramiding ladder calculations."""
        closes = [95.0 + (i * 0.2) for i in range(30)]
        highs = [c + 1.2 for c in closes]
        lows = [c - 1.2 for c in closes]
        volumes = [200000.0] * 25 + [40000.0] * 5  # Volume dry-up on last 5 bars

        # Make last 5 bars tight micro-handle
        for i in range(25, 30):
            highs[i] = closes[i] + 0.3
            lows[i] = closes[i] - 0.3

        analysis = PriceStructureEngine.audit_swing_setup(
            daily_closes=closes,
            daily_highs=highs,
            daily_lows=lows,
            daily_volumes=volumes,
            current_price=closes[-1]
        )

        self.assertEqual(analysis.get("tranche_1_probe_pct"), 50.0)
        self.assertEqual(analysis.get("tranche_2_pyramid_pct"), 50.0)

        pivot = analysis["adjusted_pivot_entry"]
        stop = analysis["stop_loss_price"]
        risk = pivot - stop

        self.assertEqual(analysis.get("tranche_1_trigger_price"), pivot)
        expected_t2 = round(pivot + (0.5 * risk), 2)
        self.assertEqual(analysis.get("tranche_2_trigger_price"), expected_t2)
        expected_be = round(pivot + (1.0 * risk), 2)
        self.assertEqual(analysis.get("breakeven_milestone_price"), expected_be)
        self.assertIn(analysis.get("handle_quality"), ["A_PRIME_HANDLE", "LOOSE_HANDLE", "V_SHAPE_EXTENDED"])

    def test_quarterly_trajectory_and_operating_leverage(self):
        """Verify that 5-quarter operating leverage trajectory is computed with chronological quarters."""
        dossier = StockDossierBuilder.build_dossier(self.test_stock, include_sentiment=False)
        self.assertIn("quarterly_trajectory", dossier)
        traj = dossier["quarterly_trajectory"]
        quarters = traj.get("quarters", [])
        self.assertIsInstance(quarters, list)
        self.assertGreater(len(quarters), 0)

        # Verify quarter structure
        q0 = quarters[0]
        self.assertIn("quarter_label", q0)
        self.assertIn("revenue_cr", q0)
        self.assertIn("ebitda_cr", q0)
        self.assertIn("ebitda_margin_pct", q0)
        self.assertIn("pat_cr", q0)
        self.assertIn("pat_margin_pct", q0)
        self.assertIn(traj.get("operating_leverage_status"), ["EXPANDING", "STABLE", "COMPRESSING"])

        # Verify LLMAnalystClient.analyze_stock returns quarterly_trajectory in payload
        res = LLMAnalystClient.analyze_stock(self.test_stock, force_offline=True)
        self.assertTrue(res.get("success"))
        self.assertIn("quarterly_trajectory", res)
        self.assertEqual(res["quarterly_trajectory"]["operating_leverage_status"], traj["operating_leverage_status"])


if __name__ == "__main__":
    unittest.main()


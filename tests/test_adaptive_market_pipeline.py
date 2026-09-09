"""
Test Suite: Adaptive Market Intelligence, Dual-Core Strategist & Dynamic TV Scanner Pipeline.
Validates:
1. Live Market Intelligence Ingestion from official NSE endpoints
2. Sector Constituents & TV Industry Cluster lookups
3. Algorithmic Strategist (Core A) determinism & user intent integration
4. Invariant Firewall adversarial repairs (closed-world safety)
5. DVM Scoring calculation integrity
6. Live TradingView Dynamic Scanner execution & 2R/3R Action Card synthesis
"""

import json
import unittest
from src.mcp.market_intelligence_client import MarketIntelligenceClient
from src.mcp.sector_constituents_store import SectorConstituentsStore
from src.llm.algorithmic_strategist import AlgorithmicStrategist
from src.llm.market_strategist import InvariantFirewall, MarketStrategist
from src.llm.market_strategist_models import AdaptiveStrategyAST, HorizonType, MarketRegime
from src.analytics.dvm_scorer import DVMScorer
from src.screener.tv_dynamic_compiler import TVDynamicCompiler


class TestAdaptiveMarketPipeline(unittest.TestCase):

    def test_01_sector_constituents_store(self):
        """Verifies sector store returns verified symbols and TV clusters for all 14 sectors."""
        sectors = SectorConstituentsStore.get_all_sector_names()
        self.assertGreaterEqual(len(sectors), 10)

        auto_constituents = SectorConstituentsStore.get_index_constituents("NIFTY AUTO")
        self.assertIn("MARUTI", auto_constituents)
        self.assertIn("TATAMOTORS", auto_constituents)

        pharma_clusters = SectorConstituentsStore.get_tv_industry_clusters("NIFTY PHARMA")
        self.assertIn("Major Pharmaceuticals", pharma_clusters)

        # Symbol sector lookup
        self.assertEqual(SectorConstituentsStore.identify_sector_for_symbol("TCS"), "NIFTY IT")
        self.assertEqual(SectorConstituentsStore.identify_sector_for_symbol("CIPLA"), "NIFTY PHARMA")

    def test_02_live_market_intelligence_ingestion(self):
        """Verifies authentic live NSE market intelligence ingestion."""
        client = MarketIntelligenceClient()
        data = client.fetch_live_market_intelligence()

        # Breadth assertions
        breadth = data["market_breadth"]
        self.assertGreater(breadth["advances"], 0)
        self.assertGreater(breadth["declines"], 0)
        self.assertIn(data["overall_regime"], ["BULLISH_EXPANSION", "SELECTIVE_ROTATION", "DEFENSIVE_CONSOLIDATION", "RISK_OFF_CAPITAL_PRESERVATION"])

        # Sector RRG matrix assertions
        rot = data["sector_rotation_matrix"]
        total_sectors = len(rot["leading_sectors"]) + len(rot["improving_sectors"]) + len(rot["weakening_sectors"]) + len(rot["lagging_sectors"])
        self.assertGreaterEqual(total_sectors, 8)

        # Flow assertions
        flows = data["institutional_flows_cash"]
        self.assertIn("flow_sentiment", flows)

    def test_03_algorithmic_strategist_determinism(self):
        """Verifies Core A compiles valid Pydantic strategy AST without external calls."""
        client = MarketIntelligenceClient()
        data = client.fetch_live_market_intelligence()

        ast = AlgorithmicStrategist.compile_strategy(data, horizon="SWING", user_intent="Focus on Auto and Realty")
        self.assertEqual(ast.horizon, HorizonType.SWING)
        self.assertGreaterEqual(len(ast.favored_sectors), 1)
        self.assertGreaterEqual(len(ast.target_tv_industry_clusters), 1)
        self.assertGreater(len(ast.compiled_tv_predicates), 3)
        self.assertLess(ast.min_rsi, ast.max_rsi)

    def test_04_invariant_firewall_adversarial_repair(self):
        """Verifies Invariant Firewall catches and repairs adversarial/inverted parameters and lagging sectors."""
        mock_data = {
            "sector_rotation_matrix": {
                "leading_sectors": ["NIFTY PHARMA"],
                "lagging_sectors": ["NIFTY MEDIA", "NIFTY IT"]
            }
        }

        # Subtly adversarial AST within Pydantic bounds: favors lagging sector and inverts RSI bounds
        bad_ast = AdaptiveStrategyAST(
            horizon=HorizonType.SWING,
            regime=MarketRegime.SELECTIVE_ROTATION,
            tactical_posture="TEST",
            favored_sectors=["NIFTY MEDIA"],  # Lagging sector!
            min_rsi=65.0,                     # Inverted within Pydantic range!
            max_rsi=60.0,
            min_turnover_cr=2.0,
            max_pe_ratio=20.0
        )

        repaired, log = InvariantFirewall.validate_and_repair(bad_ast, mock_data)

        # Assert repairs were applied by the firewall
        self.assertNotIn("NIFTY MEDIA", repaired.favored_sectors)
        self.assertIn("NIFTY PHARMA", repaired.favored_sectors)
        self.assertLess(repaired.min_rsi, repaired.max_rsi)
        self.assertEqual(repaired.min_rsi, 52.0)
        self.assertEqual(repaired.max_rsi, 68.0)
        self.assertGreater(len(log), 0)

    def test_05_dvm_scorer_accuracy(self):
        """Verifies Trendlyne-style DVM calculation."""
        stock = {
            "cmp": 1000.0,
            "close": 1000.0,
            "price_52_week_high": 1020.0,  # within 2% of 52W High
            "EMA50": 950.0,
            "SMA200": 850.0,               # Stage 2 trend
            "relative_volume_10d_calc": 2.2,
            "RSI": 60.0,
            "debt_to_equity": 0.4,
            "operating_margin_ttm": 22.0,
            "price_earnings_ttm": 28.0
        }

        scores = DVMScorer.calculate_scores(stock)
        self.assertGreaterEqual(scores["durability"], 80.0)
        self.assertGreaterEqual(scores["valuation"], 70.0)
        self.assertGreaterEqual(scores["momentum"], 85.0)
        self.assertGreaterEqual(scores["composite"], 80.0)

    def test_06_live_tv_dynamic_scanner_execution(self):
        """Verifies end-to-end execution against live TradingView scanner returning 2R/3R cards."""
        client = MarketIntelligenceClient()
        data = client.fetch_live_market_intelligence()
        ast, _ = MarketStrategist.synthesize_strategy(data, horizon="SWING")

        cards = TVDynamicCompiler.execute_strategy_scan(ast, limit=5)
        self.assertGreater(len(cards), 0, "TradingView scanner must return real candidates for active market regime")

        card = cards[0]
        self.assertIsNotNone(card.symbol)
        self.assertGreater(card.cmp, 0.0)
        self.assertLess(card.stop_loss, card.entry_price)
        self.assertGreater(card.target_1, card.entry_price)
        self.assertGreater(card.target_2, card.target_1)
        self.assertAlmostEqual(card.risk_reward_ratio, 2.0, delta=0.2)
        self.assertGreaterEqual(card.dvm_composite_score, 50.0)

    def test_07_http_market_intelligence_endpoint(self):
        """Verifies launch_app.py GET /api/screener/market-intelligence contract."""
        import socket
        import http.server
        import threading
        import urllib.request
        from scripts.launch_app import WatchlistAppHandler

        s = socket.socket()
        s.bind(('', 0))
        port = s.getsockname()[1]
        s.close()

        httpd = http.server.ThreadingHTTPServer(('', port), WatchlistAppHandler)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            url = f"http://localhost:{port}/api/screener/market-intelligence?horizon=SWING&limit=5"
            with urllib.request.urlopen(url, timeout=10.0) as resp:
                self.assertEqual(resp.status, 200)
                body = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(body.get("success"))
                self.assertIn("cmmi_score", body)
                self.assertIn("overall_regime", body)
                self.assertIn("applied_filters", body)
                self.assertIn("delta_24h", body)
                self.assertIn("sieve_waterfall", body)
                self.assertIn("cards", body)
                self.assertGreater(len(body["cards"]), 0)
                self.assertIn("tradingview_watchlist_symbols", body)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()

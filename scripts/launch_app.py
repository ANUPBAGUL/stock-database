"""
Stock Watchlist & Information Maintenance Hub — HTTP Backend Server.

Port: 8060
Features:
1. Complete Upstox OAuth 2.0 Authenticator & Session Manager
2. 5-Minute Auto-Refresh Background Daemon for all watchlist stocks via Upstox API
3. Batch Text Parser for 1, 10, or 100+ stock symbols
4. 2-Tab Interactive Explorer with Live Upstox Session Status & Timer
"""

import os
import sys
import time
import json
import logging
import threading
import urllib.parse
import http.server
import socketserver
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

from src.db.base import SessionLocal
from src.db.models import Company, DailyPriceRaw, BitemporalFinancial
from src.watchlist.watchlist_manager import WatchlistManager
from src.ingestion.upstox_authenticator import UpstoxAuthenticator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = 8060
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")
AUTO_REFRESH_INTERVAL_SECONDS = 300 # 5 minutes

# Global state for refresh tracking
LAST_REFRESH_INFO = {
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "stocks_refreshed": 0,
    "status": "IDLE"
}

# Global state for operator-controlled auto-sync
AUTO_SYNC_STATE = {
    "enabled": True,
    "interval_seconds": AUTO_REFRESH_INTERVAL_SECONDS
}


class WatchlistAppHandler(http.server.SimpleHTTPRequestHandler):
    """
    HTTP Request Handler for Watchlist Hub REST APIs, Upstox Authenticator, and static dashboard.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/watchlist/all":
            self.handle_get_all_watchlist()
        elif path == "/api/watchlist/stock-detail":
            symbol = query.get("symbol", ["DIXON"])[0]
            self.handle_get_stock_detail(symbol, query)
        elif path == "/api/watchlist/refresh-all":
            self.handle_refresh_all()
        elif path == "/api/catalysts/board-meetings":
            self.handle_get_board_meetings(query)
        elif path == "/api/system/status":
            self.handle_system_status()
        elif path == "/api/system/audit-report":
            self.handle_audit_report()
        elif path == "/api/system/run-validation":
            self.handle_run_validation()
        elif path == "/api/upstox/status":
            self.handle_upstox_status()
        elif path == "/api/upstox/login-url":
            self.handle_upstox_login_url()
        elif path == "/api/upstox/callback":
            self.handle_upstox_callback(query)
        elif path == "/api/screener/presets":
            self.handle_screener_presets()
        elif path == "/api/screener/feeds":
            self.handle_screener_feeds(query)
        elif path == "/api/screener/strategic-graduations":
            self.handle_screener_strategic_graduations(query)
        elif path == "/api/analyst/dossier":
            symbol = query.get("symbol", [""])[0]
            self.handle_analyst_dossier(symbol)
        elif path == "/api/analyst/deep-dive":
            symbol = query.get("symbol", [""])[0]
            self.handle_analyst_deep_dive(symbol, query)
        elif path == "/api/intraday/live-tape":
            self.handle_intraday_live_tape()
        elif path == "/api/watchlist/auto-sync/status":
            self.send_json_response({
                "success": True,
                "enabled": AUTO_SYNC_STATE["enabled"],
                "interval_seconds": AUTO_SYNC_STATE["interval_seconds"],
                "last_refresh": LAST_REFRESH_INFO
            })
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/screener/run":
            self.handle_run_screener()
        elif path == "/api/analyst/query":
            self.handle_analyst_query()
        elif path == "/api/watchlist/parse-and-add":
            self.handle_parse_and_add()
        elif path == "/api/watchlist/refresh":
            symbol = query.get("symbol", [""])[0]
            self.handle_refresh_stock(symbol)
        elif path == "/api/watchlist/auto-sync/toggle":
            self.handle_auto_sync_toggle()
        elif path == "/api/intraday/toggle":
            self.handle_intraday_toggle()
        elif path == "/api/intraday/basket/add":
            self.handle_intraday_basket_add()
        elif path == "/api/intraday/basket/remove":
            self.handle_intraday_basket_remove()
        elif path == "/api/intraday/basket/clear":
            self.handle_intraday_basket_clear()
        elif path == "/api/upstox/exchange-code":
            self.handle_upstox_exchange_code()
        elif path == "/api/upstox/set-token":
            self.handle_upstox_set_token()
        elif path == "/api/upstox/save-credentials":
            self.handle_upstox_save_credentials()
        else:
            self.send_error(404, "Endpoint not found")

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/watchlist/remove":
            symbol = query.get("symbol", [""])[0]
            self.handle_remove_stock(symbol)
        else:
            self.send_error(404, "Endpoint not found")

    # ──────────────────────────────────────────────────────────────
    # Upstox Authenticator Endpoints
    # ──────────────────────────────────────────────────────────────

    def handle_upstox_status(self):
        """Returns current Upstox token authentication status and user profile"""
        status = UpstoxAuthenticator.get_auth_status()
        self.send_json_response({"success": True, "auth": status})

    def handle_upstox_login_url(self):
        """Returns the OAuth login URL"""
        login_url = UpstoxAuthenticator.get_login_url()
        self.send_json_response({"success": True, "login_url": login_url})

    def handle_upstox_exchange_code(self):
        """Exchanges authorization code for access token"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            req_data = json.loads(body)
            code = req_data.get("code", "")
            r_uri = req_data.get("redirect_uri")
            res = UpstoxAuthenticator.exchange_code_for_token(code, r_uri)
            self.send_json_response(res)
        except Exception as e:
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_upstox_set_token(self):
        """Manually sets and verifies an Upstox access token"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            req_data = json.loads(body)
            token = req_data.get("token", "")
            res = UpstoxAuthenticator.set_manual_token(token)
            self.send_json_response(res)
        except Exception as e:
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_upstox_save_credentials(self):
        """Saves API key and secret in .env"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            req_data = json.loads(body)
            key = req_data.get("api_key", "")
            secret = req_data.get("api_secret", "")
            r_uri = req_data.get("redirect_uri", "")
            success = UpstoxAuthenticator.save_api_credentials(key, secret, r_uri)
            self.send_json_response({"success": success, "message": "Credentials updated successfully."})
        except Exception as e:
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_upstox_callback(self, query: Dict[str, List[str]]):
        """Handles OAuth redirect from Upstox dialog"""
        code = query.get("code", [""])[0]
        if code:
            res = UpstoxAuthenticator.exchange_code_for_token(code)
            if res.get("success"):
                user_name = res.get("user_name", "Upstox User")
                html = f"""
                <!DOCTYPE html>
                <html>
                <head><title>Upstox Connected</title><style>body{{background:#080c14;color:#00ff9d;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;}}</style></head>
                <body>
                    <h2>✅ Upstox Connected Successfully!</h2>
                    <p>Welcome, <strong>{user_name}</strong>. Access token saved.</p>
                    <p>Redirecting to Hub in 2 seconds...</p>
                    <script>
                        setTimeout(() => {{ window.location.href = '/'; }}, 2000);
                    </script>
                </body>
                </html>
                """
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))
                return

        self.send_response(302)
        self.send_header("Location", "/?upstox_auth=failed")
        self.end_headers()

    # ──────────────────────────────────────────────────────────────
    # Watchlist Endpoints
    # ──────────────────────────────────────────────────────────────

    def handle_get_all_watchlist(self):
        """Returns all stocks in watchlist with full parameter suite"""
        try:
            stocks = WatchlistManager.get_all_watchlist_stocks()
            auth_status = UpstoxAuthenticator.get_auth_status()
            self.send_json_response({
                "success": True,
                "count": len(stocks),
                "stocks": stocks,
                "last_refresh": LAST_REFRESH_INFO,
                "upstox_auth": auth_status,
                "auto_sync": AUTO_SYNC_STATE
            })
        except Exception as e:
            logger.error(f"Error fetching watchlist: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_auto_sync_toggle(self):
        """Toggles scheduled 5-minute background auto-sync on or off"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            req_data = json.loads(body) if body.strip() else {}
            target_state = req_data.get("enabled")
            if target_state is None:
                AUTO_SYNC_STATE["enabled"] = not AUTO_SYNC_STATE["enabled"]
            else:
                AUTO_SYNC_STATE["enabled"] = bool(target_state)
            logger.info(f"Auto-sync toggled: enabled={AUTO_SYNC_STATE['enabled']}")
            self.send_json_response({
                "success": True,
                "enabled": AUTO_SYNC_STATE["enabled"],
                "auto_sync": AUTO_SYNC_STATE,
                "message": f"Auto-sync is now {'ENABLED' if AUTO_SYNC_STATE['enabled'] else 'PAUSED'}"
            })
        except Exception as e:
            logger.error(f"Error toggling auto-sync: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_get_stock_detail(self, symbol: str, query: Optional[Dict[str, List[str]]] = None):
        """Returns 360-degree deep parameters for a single stock"""
        db = SessionLocal()
        try:
            force_refresh = False
            if query and query.get("refresh"):
                force_refresh = query.get("refresh", ["false"])[0].lower() in ["true", "1"]

            comp = db.query(Company).filter_by(nse_symbol=symbol.upper().strip()).first()
            has_data = False
            if comp:
                p_cnt = db.query(DailyPriceRaw).filter_by(company_id=comp.company_id).count()
                q_cnt = db.query(BitemporalFinancial).filter_by(company_id=comp.company_id, period_type="QUARTERLY").count()
                has_data = (p_cnt >= 20 and q_cnt >= 4)

            fast = has_data and not force_refresh
            data = WatchlistManager.ingest_and_calculate_all_parameters(symbol, db, fast_mode=fast)
            self.send_json_response({"success": True, "stock": data})
        except Exception as e:
            logger.error(f"Error fetching stock detail for {symbol}: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)
        finally:
            db.close()

    def handle_parse_and_add(self):
        """Parses batch text input and triggers full parameter ingestion via Upstox"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            req_data = json.loads(body)
            raw_text = req_data.get("text", "") or req_data.get("raw_text", "")
            if not raw_text.strip():
                self.send_json_response({"success": False, "error": "Please provide stock names or symbols."}, status=400)
                return

            res = WatchlistManager.batch_process_stock_text(raw_text)
            self.send_json_response(res)
        except Exception as e:
            logger.error(f"Error in batch parsing: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_refresh_all(self):
        """Trigger immediate refresh of all watchlist stocks"""
        try:
            LAST_REFRESH_INFO["status"] = "REFRESHING"
            res = WatchlistManager.refresh_all_watchlist_stocks()
            LAST_REFRESH_INFO["timestamp"] = res.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            LAST_REFRESH_INFO["stocks_refreshed"] = res.get("refreshed_count", 0)
            LAST_REFRESH_INFO["status"] = "IDLE"
            self.send_json_response({"success": True, "result": res})
        except Exception as e:
            LAST_REFRESH_INFO["status"] = "ERROR"
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_refresh_stock(self, symbol: str):
        """Refreshes a specific stock or all stocks"""
        db = SessionLocal()
        try:
            if symbol:
                rec = WatchlistManager.ingest_and_calculate_all_parameters(symbol, db)
                self.send_json_response({"success": True, "refreshed_stock": rec})
            else:
                res = WatchlistManager.refresh_all_watchlist_stocks()
                self.send_json_response({"success": True, "result": res})
        except Exception as e:
            self.send_json_response({"success": False, "error": str(e)}, status=500)
        finally:
            db.close()

    def handle_remove_stock(self, symbol: str):
        """Removes/deactivates a stock from the watchlist"""
        if not symbol:
            self.send_json_response({"success": False, "error": "Symbol required"}, status=400)
            return

        db = SessionLocal()
        try:
            comp = db.query(Company).filter_by(nse_symbol=symbol.upper().strip()).first()
            if comp:
                comp.status = "INACTIVE"
                db.commit()
                self.send_json_response({"success": True, "message": f"{symbol} removed from watchlist."})
            else:
                self.send_json_response({"success": False, "error": f"Stock {symbol} not found."}, status=404)
        except Exception as e:
            self.send_json_response({"success": False, "error": str(e)}, status=500)
        finally:
            db.close()

    def handle_get_board_meetings(self, query: Dict[str, List[str]]):
        """Returns forward-looking board meetings and catalyst calendar"""
        symbol = query.get("symbol", [""])[0]
        try:
            from src.ingestion.nse_client import NseClient
            nse = NseClient()
            if symbol:
                meetings = nse.fetch_board_meetings(symbol)
            else:
                meetings = []
            self.send_json_response({"success": True, "symbol": symbol, "count": len(meetings), "meetings": meetings})
        except Exception as e:
            logger.error(f"Error fetching board meetings: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_system_status(self):
        """Returns system environment and operational stats"""
        db = SessionLocal()
        try:
            count = db.query(Company).filter_by(status="ACTIVE").count()
            auth_status = UpstoxAuthenticator.get_auth_status()
            from config.settings import settings
            db_name = settings.DATABASE_URL.split("/")[-1] if "/" in settings.DATABASE_URL else settings.DATABASE_URL
            self.send_json_response({
                "system": "Stock Watchlist & Information Maintenance Hub",
                "port": PORT,
                "environment": "PRODUCTION_SHADOW",
                "auto_refresh_interval_minutes": 5,
                "last_refresh": LAST_REFRESH_INFO,
                "upstox_auth": auth_status,
                "total_active_watchlist_stocks": count,
                "primary_data_provider": "UPSTOX_V2_API",
                "database": db_name
            })
        finally:
            db.close()

    def handle_audit_report(self):
        """Returns live longitudinal health and 8 acceptance invariants audit"""
        report_file = os.path.join(BASE_DIR, "institutional_validation_report.json")
        if os.path.exists(report_file):
            try:
                with open(report_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.send_json_response({"success": True, "report": data})
                return
            except Exception as e:
                logger.warning(f"Could not read validation report JSON: {e}")

        # Compute live if file missing
        try:
            from scripts.audit_longitudinal_dataset import LongitudinalDatasetAuditor
            audit_data = LongitudinalDatasetAuditor.run_comprehensive_audit()
            self.send_json_response({"success": True, "report": {"dataset_health": audit_data}})
        except Exception as e:
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_screener_presets(self):
        """Returns metadata for institutional screener presets"""
        presets = {
            "MULTIBAGGER_INFLECTION_PRESET": {
                "name": "Multibagger Asymmetric Inflection",
                "horizon": "3-5 Years",
                "description": "High Incremental ROIIC (>25%), High Reinvestment Rate (>60%), and Positive Expectations Asymmetry",
                "filters": {"min_roce_pct": 15.0, "min_sales_growth_3y_pct": 12.0, "max_debt_to_equity": 1.0}
            },
            "SWING_VCP_BREAKOUT_PRESET": {
                "name": "Swing Trading VCP Breakout",
                "horizon": "2-4 Weeks",
                "description": "Weinstein Stage 2 Uptrend, Volatility Contraction Pattern (VCP), and 1:2.3+ Risk/Reward Setup",
                "filters": {"min_roce_pct": 12.0, "near_52w_high_pct": 20.0, "require_stage_2_uptrend": True}
            },
            "MICROCAP_COMPOUNDER_PRESET": {
                "name": "Microcap Hidden Compounder",
                "horizon": "2-4 Years",
                "description": "Market Cap ₹250-₹3,000 Cr, Low/Zero Debt, Accelerating CFO conversion, Zero Pledge",
                "filters": {"min_market_cap_cr": 150.0, "max_market_cap_cr": 3000.0, "min_roce_pct": 18.0, "max_debt_to_equity": 0.5}
            },
            "INTRADAY_MOMENTUM_SCALP_PRESET": {
                "name": "Intraday Momentum Scalp Radar",
                "horizon": "1 Day",
                "description": "Large Cap / Liquid Midcaps with Relative Volume > 2.5x and ATR Range Expansion",
                "filters": {"min_market_cap_cr": 1500.0, "min_daily_turnover_cr": 5.0}
            }
        }
        self.send_json_response({"success": True, "presets": presets})

    def handle_screener_feeds(self, query: Dict[str, List[str]]):
        """Returns active segregated feeds for Long-Term, Swing, and Intraday setups"""
        from src.screener.screener_service import ScreenerService
        preset = query.get("preset", ["MULTIBAGGER_INFLECTION_PRESET"])[0]
        mode = query.get("mode", ["LIVE_CLOUD"])[0]
        response = ScreenerService.run_preset_screen(preset, mode=mode)
        self.send_json_response(response.model_dump())

    def handle_screener_strategic_graduations(self, query: Dict[str, List[str]]):
        """Returns strategic watchlist candidates with graduation telemetry and active alerts"""
        from src.screener.screener_service import ScreenerService
        from src.screener.screener_models import ScreenerFilterRequest
        try:
            mode = query.get("mode", ["LIVE_CLOUD"])[0]
            req = ScreenerFilterRequest(mode=mode, preset="MULTIBAGGER_INFLECTION_PRESET", limit=30)
            res = ScreenerService.run_screen(req)
            strat_feed = res.strategic_watchlist_feed or [c for c in res.candidates if c.business_potential_score >= 70.0]
            grad_candidates = [
                {
                    "symbol": c.symbol,
                    "company_name": c.company_name,
                    "cmp": c.cmp,
                    "business_potential_score": c.business_potential_score,
                    "expectations_asymmetry_gap_pct": c.expectations_asymmetry_gap_pct,
                    "entry_quality_score": c.entry_quality_score,
                    "tape_confirmation_score": c.tape_confirmation_score,
                    "graduation_status": c.graduation_status,
                    "graduation_readiness_pct": c.graduation_readiness_pct,
                    "graduation_trigger": c.graduation_trigger,
                    "graduation_target_pivot": c.graduation_target_pivot
                }
                for c in strat_feed
            ]
            grad_candidates.sort(key=lambda x: x["graduation_readiness_pct"], reverse=True)
            self.send_json_response({
                "success": True,
                "total_monitored": len(grad_candidates),
                "ready_count": sum(1 for c in grad_candidates if (c.get("graduation_readiness_pct") or 0.0) >= 85.0),
                "candidates": grad_candidates
            })
        except Exception as e:
            logger.error(f"Error handling strategic graduations: {e}", exc_info=True)
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_run_screener(self):
        """Runs on-demand screener with custom filter parameters"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            from src.screener.screener_models import ScreenerFilterRequest
            from src.screener.screener_service import ScreenerService
            req_dict = json.loads(body) if body else {}
            req = ScreenerFilterRequest(**req_dict)
            response = ScreenerService.run_screen(req)
            self.send_json_response(response.model_dump())
        except Exception as e:
            logger.error(f"Error handling screener run: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    # ──────────────────────────────────────────────────────────────
    # Institutional Analyst & LLM Copilot Endpoints (Strictly On-Demand)
    # ──────────────────────────────────────────────────────────────

    def handle_analyst_dossier(self, symbol: str):
        """Returns the structured 100-parameter Point-in-Time research dossier for a stock."""
        try:
            from src.analytics.stock_dossier_builder import StockDossierBuilder
            if not symbol:
                self.send_json_response({"success": False, "error": "Symbol query parameter is required"}, status=400)
                return
            dossier = StockDossierBuilder.build_dossier(symbol)
            status_code = 200 if dossier.get("success") else 404
            self.send_json_response(dossier, status=status_code)
        except Exception as e:
            logger.error(f"Error compiling dossier for {symbol}: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_analyst_deep_dive(self, symbol: str, query: Dict[str, List[str]]):
        """Generates an on-demand institutional investment memo for a stock."""
        try:
            from src.analytics.llm_analyst_client import LLMAnalystClient
            if not symbol:
                self.send_json_response({"success": False, "error": "Symbol query parameter is required"}, status=400)
                return
            custom_q = query.get("question", [None])[0]
            res = LLMAnalystClient.analyze_stock(symbol, custom_question=custom_q)
            status_code = 200 if res.get("success") else 404
            self.send_json_response(res, status=status_code)
        except Exception as e:
            logger.error(f"Error generating analyst deep dive for {symbol}: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_analyst_query(self):
        """Handles custom ad-hoc interactive research questions for a stock."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            from src.analytics.llm_analyst_client import LLMAnalystClient
            req_data = json.loads(body) if body else {}
            symbol = req_data.get("symbol", "")
            question = req_data.get("question", "")
            if not symbol:
                self.send_json_response({"success": False, "error": "Symbol is required in payload"}, status=400)
                return
            res = LLMAnalystClient.analyze_stock(symbol, custom_question=question)
            status_code = 200 if res.get("success") else 400
            self.send_json_response(res, status=status_code)
        except Exception as e:
            logger.error(f"Error handling analyst query: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_intraday_toggle(self):
        """Toggles the live intraday microstructure radar on or off"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            from src.analytics.intraday_focus_manager import IntradayFocusManager
            mgr = IntradayFocusManager()
            req_data = json.loads(body) if body.strip() else {}
            target_armed = req_data.get("armed")
            is_armed = mgr.toggle(target_armed)
            self.send_json_response({"success": True, "is_armed": is_armed, "state": mgr.get_state()})
        except Exception as e:
            logger.error(f"Error toggling intraday radar: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_intraday_basket_add(self):
        """Adds a stock to the active intraday focus basket (max 8)"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            from src.analytics.intraday_focus_manager import IntradayFocusManager
            mgr = IntradayFocusManager()
            req_data = json.loads(body) if body.strip() else {}
            symbol = req_data.get("symbol", "")
            if not symbol:
                self.send_json_response({"success": False, "error": "Symbol is required"}, status=400)
                return
            basket = mgr.add_to_basket(symbol)
            self.send_json_response({"success": True, "symbol": symbol.upper(), "basket": basket, "state": mgr.get_state()})
        except Exception as e:
            logger.error(f"Error adding to intraday basket: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_intraday_basket_remove(self):
        """Removes a stock from the active intraday focus basket"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            from src.analytics.intraday_focus_manager import IntradayFocusManager
            mgr = IntradayFocusManager()
            req_data = json.loads(body) if body.strip() else {}
            symbol = req_data.get("symbol", "")
            if not symbol:
                self.send_json_response({"success": False, "error": "Symbol is required"}, status=400)
                return
            basket = mgr.remove_from_basket(symbol)
            self.send_json_response({"success": True, "symbol": symbol.upper(), "basket": basket, "state": mgr.get_state()})
        except Exception as e:
            logger.error(f"Error removing from intraday basket: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_intraday_basket_clear(self):
        """Clears all stocks from the active intraday focus basket"""
        try:
            from src.analytics.intraday_focus_manager import IntradayFocusManager
            mgr = IntradayFocusManager()
            basket = mgr.clear_basket()
            self.send_json_response({"success": True, "basket": basket, "state": mgr.get_state()})
        except Exception as e:
            logger.error(f"Error clearing intraday basket: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_intraday_live_tape(self):
        """Returns the real-time live tape state and microstructure snapshots"""
        try:
            from src.analytics.intraday_focus_manager import IntradayFocusManager
            mgr = IntradayFocusManager()
            self.send_json_response({"success": True, **mgr.get_state()})
        except Exception as e:
            logger.error(f"Error fetching intraday live tape: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_run_validation(self):
        """Executes full institutional validation suite and returns results"""
        try:
            from scripts.run_institutional_validation import execute_institutional_campaign
            report = execute_institutional_campaign()
            self.send_json_response({"success": True, "report": report})
        except Exception as e:
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def send_json_response(self, data: Any, status: int = 200):
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2, default=str).encode("utf-8"))
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.debug(f"Client disconnected while writing response: {e}")

    def do_OPTIONS(self):
        try:
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.debug(f"Client disconnected on OPTIONS: {e}")


def _auto_refresh_background_worker():
    """
    Background worker that executes every 5 minutes (300 seconds) to update
    all active watchlist stocks from the Upstox API during regular market hours.
    """
    from src.analytics.intraday_focus_manager import is_indian_market_open
    logger.info("Starting 5-Minute Upstox Auto-Refresh Background Worker...")
    time.sleep(10)
    
    while True:
        try:
            if not AUTO_SYNC_STATE.get("enabled", True):
                LAST_REFRESH_INFO["status"] = "PAUSED (MANUAL_ONLY)"
                time.sleep(2)
                continue

            if is_indian_market_open():
                logger.info("Executing scheduled 5-minute Upstox data refresh cycle...")
                LAST_REFRESH_INFO["status"] = "REFRESHING"
                res = WatchlistManager.refresh_all_watchlist_stocks()
                LAST_REFRESH_INFO["timestamp"] = res.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                LAST_REFRESH_INFO["stocks_refreshed"] = res.get("refreshed_count", 0)
                LAST_REFRESH_INFO["status"] = "IDLE"
                logger.info(f"5-Minute Upstox Auto-Refresh completed. {res.get('refreshed_count', 0)} stocks updated.")
            else:
                LAST_REFRESH_INFO["status"] = "IDLE (MARKET_CLOSED)"
                logger.debug("Indian markets currently closed (09:15-15:30 IST weekdays). Background refresh idling.")
        except Exception as e:
            LAST_REFRESH_INFO["status"] = "ERROR"
            logger.error(f"Error in 5-minute auto-refresh cycle: {e}")

        # Sleep responsive to auto_sync toggling
        for _ in range(AUTO_REFRESH_INTERVAL_SECONDS):
            if not AUTO_SYNC_STATE.get("enabled", True):
                break
            time.sleep(1)


def run_server():
    refresh_thread = threading.Thread(target=_auto_refresh_background_worker, daemon=True)
    refresh_thread.start()

    # Use ThreadingHTTPServer for concurrent non-blocking HTTP requests
    server_address = ("", PORT)
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    httpd = http.server.ThreadingHTTPServer(server_address, WatchlistAppHandler)
    httpd.daemon_threads = True

    print(f"=======================================================================")
    print(f"  STOCK WATCHLIST & INFORMATION HUB LIVE AT http://localhost:{PORT}  ")
    print(f"  [Upstox Authenticator]: Ready at /api/upstox/status & /api/upstox/login-url")
    print(f"  [Auto-Refresh Engine]: Active (Updating Upstox data every 5 minutes) ")
    print(f"  [Concurrency Mode]: Multi-Threaded HTTP Server Active               ")
    print(f"=======================================================================")
    while True:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
            break
        except Exception as e:
            logger.error(f"HTTP Server loop exception: {e}")
            time.sleep(1)
    httpd.server_close()


if __name__ == "__main__":
    run_server()

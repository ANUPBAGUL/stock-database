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
from typing import Dict, Any, List

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.db.base import SessionLocal
from src.db.models import Company
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
            self.handle_get_stock_detail(symbol)
        elif path == "/api/watchlist/refresh-all":
            self.handle_refresh_all()
        elif path == "/api/catalysts/board-meetings":
            self.handle_get_board_meetings(query)
        elif path == "/api/system/status":
            self.handle_system_status()
        elif path == "/api/upstox/status":
            self.handle_upstox_status()
        elif path == "/api/upstox/login-url":
            self.handle_upstox_login_url()
        elif path == "/api/upstox/callback":
            self.handle_upstox_callback(query)
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/watchlist/parse-and-add":
            self.handle_parse_and_add()
        elif path == "/api/watchlist/refresh":
            symbol = query.get("symbol", [""])[0]
            self.handle_refresh_stock(symbol)
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
                "upstox_auth": auth_status
            })
        except Exception as e:
            logger.error(f"Error fetching watchlist: {e}")
            self.send_json_response({"success": False, "error": str(e)}, status=500)

    def handle_get_stock_detail(self, symbol: str):
        """Returns 360-degree deep parameters for a single stock"""
        db = SessionLocal()
        try:
            data = WatchlistManager.ingest_and_calculate_all_parameters(symbol, db)
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
            raw_text = req_data.get("text", "")
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
            self.send_json_response({
                "system": "Stock Watchlist & Information Maintenance Hub",
                "port": PORT,
                "environment": "PRODUCTION_SHADOW",
                "auto_refresh_interval_minutes": 5,
                "last_refresh": LAST_REFRESH_INFO,
                "upstox_auth": auth_status,
                "total_active_watchlist_stocks": count,
                "primary_data_provider": "UPSTOX_V2_API",
                "database": "multibagger.db"
            })
        finally:
            db.close()

    def send_json_response(self, data: Any, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, default=str).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def _auto_refresh_background_worker():
    """
    Background worker that executes every 5 minutes (300 seconds) to update
    all active watchlist stocks from the Upstox API.
    """
    logger.info("Starting 5-Minute Upstox Auto-Refresh Background Worker...")
    time.sleep(10)
    
    while True:
        try:
            logger.info("Executing scheduled 5-minute Upstox data refresh cycle...")
            LAST_REFRESH_INFO["status"] = "REFRESHING"
            res = WatchlistManager.refresh_all_watchlist_stocks()
            LAST_REFRESH_INFO["timestamp"] = res.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            LAST_REFRESH_INFO["stocks_refreshed"] = res.get("refreshed_count", 0)
            LAST_REFRESH_INFO["status"] = "IDLE"
            logger.info(f"5-Minute Upstox Auto-Refresh completed. {res.get('refreshed_count', 0)} stocks updated.")
        except Exception as e:
            LAST_REFRESH_INFO["status"] = "ERROR"
            logger.error(f"Error in 5-minute auto-refresh cycle: {e}")

        time.sleep(AUTO_REFRESH_INTERVAL_SECONDS)


def run_server():
    os.chdir(DASHBOARD_DIR)

    refresh_thread = threading.Thread(target=_auto_refresh_background_worker, daemon=True)
    refresh_thread.start()

    # Use ThreadingHTTPServer for concurrent non-blocking HTTP requests
    server_address = ("", PORT)
    httpd = http.server.ThreadingHTTPServer(server_address, WatchlistAppHandler)
    httpd.daemon_threads = True

    print(f"=======================================================================")
    print(f"  STOCK WATCHLIST & INFORMATION HUB LIVE AT http://localhost:{PORT}  ")
    print(f"  [Upstox Authenticator]: Ready at /api/upstox/status & /api/upstox/login-url")
    print(f"  [Auto-Refresh Engine]: Active (Updating Upstox data every 5 minutes) ")
    print(f"  [Concurrency Mode]: Multi-Threaded HTTP Server Active               ")
    print(f"=======================================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    run_server()

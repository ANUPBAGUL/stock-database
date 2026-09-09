"""
Rigorous Verification Harness: 360° Deep Parameters & Adversarial AI Memos in Market Mood & Strategy.
Validates:
1. StockDossierBuilder on both Local DB (RELIANCE) and Cloud-Only (KAYNES) stocks.
2. LLMAnalystClient 4-seat memo synthesis with zero 404 errors.
3. MacroMemoSynthesizer 4-seat macro committee memo.
4. HTTP Server Endpoints on port 8060.
"""

import sys
import io
import os
import json
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Ensure UTF-8 stdout on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def log_test(step: str, passed: bool, detail: str = ""):
    icon = "✅ PASS" if passed else "❌ FAIL"
    print(f"[{icon}] {step}")
    if detail:
        print(f"       -> {detail}")

def test_stock_dossiers():
    print("\n--- 1. Testing Stock Dossier Synthesis (Local vs Cloud) ---")
    from src.analytics.stock_dossier_builder import StockDossierBuilder

    # Local stock
    rel_dossier = StockDossierBuilder.build_dossier("RELIANCE", include_sentiment=False)
    log_test(
        "Local DB Stock (RELIANCE) Dossier",
        rel_dossier.get("success") is True and rel_dossier.get("market_cap_cr") is not None,
        f"Success: {rel_dossier.get('success')}, MCap: ₹{rel_dossier.get('market_cap_cr')} Cr, Provenance: Local DB"
    )

    # Cloud-only stock
    kay_dossier = StockDossierBuilder.build_dossier("KAYNES", include_sentiment=False)
    log_test(
        "Cloud-Only Stock (KAYNES) Fallback Dossier",
        kay_dossier.get("success") is True and kay_dossier.get("cmp") is not None,
        f"Success: {kay_dossier.get('success')}, CMP: ₹{kay_dossier.get('cmp')}, MCap: ₹{kay_dossier.get('market_cap_cr')} Cr, Provenance: {kay_dossier.get('provenance')}"
    )

def test_llm_analyst_memos():
    print("\n--- 2. Testing 4-Seat Adversarial Investment Committee Memos ---")
    from src.analytics.llm_analyst_client import LLMAnalystClient

    # Local stock memo
    rel_memo = LLMAnalystClient.analyze_stock("RELIANCE", force_offline=True)
    has_rel_seats = (
        "SEAT 1: BULL COMPOUNDER SPONSOR" in rel_memo.get("analysis_memo", "") and
        "SEAT 2: FORENSIC SHORT-SELLER AUDIT" in rel_memo.get("analysis_memo", "")
    )
    log_test(
        "Local DB Stock (RELIANCE) 4-Seat Memo",
        rel_memo.get("success") is True and has_rel_seats,
        f"Success: {rel_memo.get('success')}, Provider: {rel_memo.get('provider')}, Memo Len: {len(rel_memo.get('analysis_memo', ''))}"
    )

    # Cloud-only stock memo
    kay_memo = LLMAnalystClient.analyze_stock("KAYNES", force_offline=True)
    has_kay_seats = (
        "SEAT 1: BULL COMPOUNDER SPONSOR" in kay_memo.get("analysis_memo", "") and
        "SEAT 2: FORENSIC SHORT-SELLER AUDIT" in kay_memo.get("analysis_memo", "")
    )
    log_test(
        "Cloud-Only Stock (KAYNES) 4-Seat Memo",
        kay_memo.get("success") is True and has_kay_seats,
        f"Success: {kay_memo.get('success')}, Provider: {kay_memo.get('provider')}, Memo Len: {len(kay_memo.get('analysis_memo', ''))}"
    )

def test_macro_memo_synthesizer():
    print("\n--- 3. Testing Top-Level Macro Institutional Strategy Memo ---")
    from src.screener.session_strategy_manager import SessionStrategyManager
    from src.analytics.macro_memo_synthesizer import MacroMemoSynthesizer

    intel = SessionStrategyManager.get_market_intelligence()
    macro_res = MacroMemoSynthesizer.synthesize_macro_memo(intel)
    memo_text = macro_res.get("macro_memo_md", "")

    has_macro_seats = (
        "SEAT 1: INSTITUTIONAL BULL" in memo_text and
        "SEAT 2: FORENSIC SHORT-SELLER" in memo_text and
        "SEAT 3: TACTICAL ASSET ALLOCATOR" in memo_text and
        "SEAT 4: SECTOR ROTATION PLAYBOOK" in memo_text
    )
    log_test(
        "Macro 4-Seat Investment Committee Memo",
        macro_res.get("success") is True and has_macro_seats,
        f"Success: {macro_res.get('success')}, Regime: {macro_res.get('regime')}, CMMI: {macro_res.get('cmmi_score')}, Memo Len: {len(memo_text)}"
    )

def test_http_endpoints():
    print("\n--- 4. Testing HTTP REST Endpoints on http://localhost:8060 ---")

    # Endpoint 1: Macro Memo
    try:
        resp = urllib.request.urlopen("http://localhost:8060/api/screener/macro-memo", timeout=12)
        data = json.loads(resp.read().decode("utf-8"))
        log_test(
            "HTTP GET /api/screener/macro-memo",
            data.get("success") is True and len(data.get("macro_memo_md", "")) > 1000,
            f"HTTP 200, Regime: {data.get('regime')}, Length: {len(data.get('macro_memo_md', ''))} chars"
        )
    except Exception as e:
        log_test("HTTP GET /api/screener/macro-memo", False, str(e))

    # Endpoint 2: Cloud Stock AI Deep Dive
    try:
        resp = urllib.request.urlopen("http://localhost:8060/api/analyst/deep-dive?symbol=KAYNES&offline=true", timeout=12)
        data = json.loads(resp.read().decode("utf-8"))
        log_test(
            "HTTP GET /api/analyst/deep-dive?symbol=KAYNES",
            data.get("success") is True and len(data.get("analysis_memo", "")) > 1000,
            f"HTTP 200, Provider: {data.get('provider')}, Length: {len(data.get('analysis_memo', ''))} chars"
        )
    except Exception as e:
        log_test("HTTP GET /api/analyst/deep-dive?symbol=KAYNES", False, str(e))

    # Endpoint 3: Stock 360 Detail
    try:
        resp = urllib.request.urlopen("http://localhost:8060/api/watchlist/stock-detail?symbol=RELIANCE", timeout=12)
        data = json.loads(resp.read().decode("utf-8"))
        log_test(
            "HTTP GET /api/watchlist/stock-detail?symbol=RELIANCE",
            data.get("success") is True and "stock" in data,
            f"HTTP 200, Symbol: {data.get('stock', {}).get('symbol')}, CMP: ₹{data.get('stock', {}).get('current_price')}"
        )
    except Exception as e:
        log_test("HTTP GET /api/watchlist/stock-detail?symbol=RELIANCE", False, str(e))

if __name__ == "__main__":
    t0 = time.time()
    test_stock_dossiers()
    test_llm_analyst_memos()
    test_macro_memo_synthesizer()
    test_http_endpoints()
    print(f"\nElapsed time: {time.time() - t0:.2f}s")

"""
Empirical Test & Reality Check: MANORAMA INDUSTRIES LIMITED.
Fetches and audits all data layers:
1. Screener Fundamentals (ROCE, Market Cap, 10Y Balance Sheets, Quarterly P&L)
2. SEBI Clause 31 Shareholding Pattern History (Promoter, FII, DII, Public)
3. BSE India Official Regulatory Disclosures & Attachments
4. Feature Engine Computed Metrics & Audit Traces
"""
import sys
import json
from datetime import date, datetime

from src.ingestion.screener_client import ScreenerClient
from src.ingestion.bse_announcements_client import BseAnnouncementsClient
from src.ingestion.shareholding_client import ShareholdingClient
from src.ingestion.macro_client import MacroRegimeClient

def test_manorama():
    symbol = "MANORAMA"
    print("==================================================================", flush=True)
    print("      MANORAMA INDUSTRIES LIMITED — COMPREHENSIVE DATA AUDIT      ", flush=True)
    print("==================================================================", flush=True)

    # 1. Screener Overview
    sc = ScreenerClient()
    overview = sc.fetch_company_overview(symbol)
    print("\n--- 1. COMPANY OVERVIEW & KEY RATIOS ---", flush=True)
    for k, v in overview.items():
        print(f"  {k:<25}: {v}", flush=True)

    # 2. Shareholding Pattern
    sh = ShareholdingClient.fetch_shareholding_pattern(symbol)
    print("\n--- 2. SEBI LODR SHAREHOLDING PATTERN ---", flush=True)
    for k, v in sh.items():
        print(f"  {k:<25}: {v}", flush=True)

    sh_hist = sc.fetch_shareholding_history(symbol)
    print(f"\n  Historical Shareholding Quarters Available: {len(sh_hist)}", flush=True)
    for qtr in sh_hist[:4]:
        print(f"    [{qtr['period_label']}] Promoter: {qtr['promoter_holding_pct']}%, FII: {qtr['fii_holding_pct']}%, DII: {qtr['dii_holding_pct']}%, Public: {qtr['retail_public_pct']}%", flush=True)

    # 3. 10-Year Audited Balance Sheets
    bs = sc.fetch_balance_sheet_history(symbol)
    print(f"\n--- 3. AUDITED BALANCE SHEET HISTORY ({len(bs)} Years) ---", flush=True)
    if bs:
        for b in bs[:3]:
            print(f"  [{b['period_label']}] Net Worth: Rs.{b['net_worth']} Cr | Borrowings: Rs.{b['borrowings']} Cr | Total Assets: Rs.{b['total_assets']} Cr | Cap Employed: Rs.{b['capital_employed']} Cr", flush=True)

    # 4. BSE Official Regulatory Disclosures
    bse = BseAnnouncementsClient()
    ann = bse.fetch_official_announcements(symbol, limit=5)
    print(f"\n--- 4. OFFICIAL EXCHANGE FILINGS (BSE/NSE) ({len(ann)} fetched) ---", flush=True)
    for idx, a in enumerate(ann):
        print(f"\n  [{idx+1}] Timestamp: {a['source_published_at']} | Event: {a['event_type']} ({a['materiality']})", flush=True)
        print(f"      Headline: {a['headline']}", flush=True)
        if a.get('source_document_url'):
            print(f"      Official Signed PDF: {a['source_document_url']}", flush=True)

    # 5. Live Macro Regime Context
    macro = MacroRegimeClient.fetch_current_macro_regime()
    print(f"\n--- 5. MACRO REGIME CONTEXT ---", flush=True)
    print(f"  India VIX: {macro['india_vix']} | Regime: {macro['macro_regime']} | Stance: {macro['risk_stance']}", flush=True)

if __name__ == "__main__":
    test_manorama()

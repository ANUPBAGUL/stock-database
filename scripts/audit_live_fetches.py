"""
Live Data Reality Check Script.
Audits all external data fetchers by running real API queries and inspecting raw values.
"""
import sys
import json
from datetime import date, datetime

def run_audit():
    from src.ingestion.yfinance_client import YFinanceClient
    from src.ingestion.nse_client import NseClient
    from src.ingestion.shareholding_client import ShareholdingClient
    from src.ingestion.structured_events_client import StructuredDisclosuresClient
    from src.ingestion.macro_client import MacroRegimeClient

    symbols = ['DIXON', 'TCS', 'RELIANCE']

    print('=== 1. YFINANCE FINANCIALS & PRICES AUDIT ===', flush=True)
    yf_client = YFinanceClient(rate_limit_seconds=0.2)
    for sym in symbols:
        print(f'\n--- Symbol: {sym} ---', flush=True)
        try:
            info = yf_client.fetch_company_info(sym)
            print(f"Info: sector={info.get('sector')}, mcap_cr={info.get('market_cap_crores')}, pe={info.get('trailing_pe')}, shares={info.get('shares_outstanding')}", flush=True)
        except Exception as e:
            print(f"Info ERROR: {e}", flush=True)

        try:
            fin = yf_client.fetch_quarterly_financials(sym)
            print(f"Financials fetched: {len(fin)} quarters", flush=True)
            if fin:
                for idx, q in enumerate(fin[:2]):
                    m = q.get('metrics', {})
                    print(f"  Q[{idx}] Period: {q.get('period_end_date')}, PubDate: {q.get('publication_date')}, Scope: {q.get('consolidation_scope')}", flush=True)
                    print(f"       Rev={m.get('revenue')} Cr, PAT={m.get('pat')} Cr, EBIT={m.get('ebit')} Cr", flush=True)
                    print(f"       TotDebt={m.get('total_debt')} Cr, FinDebtLT={m.get('financial_debt_lt')} Cr, NetWorth={m.get('net_worth')} Cr", flush=True)
                    print(f"       TotAssets={m.get('total_assets')} Cr, CurrLiab={m.get('current_liabilities')} Cr, NetDebt={m.get('net_debt')} Cr", flush=True)
                    print(f"       OCF={m.get('operating_cash_flow')} Cr, CapEx={m.get('capex')} Cr", flush=True)
        except Exception as e:
            print(f"Financials ERROR: {e}", flush=True)

        try:
            prices = yf_client.fetch_daily_prices(sym, date(2024, 8, 1), date(2024, 8, 15))
            print(f"Daily prices: {len(prices)} candles", flush=True)
            if prices:
                print(f"  Sample candle: {prices[-1]}", flush=True)
        except Exception as e:
            print(f"Prices ERROR: {e}", flush=True)

    print('\n=== 2. SHAREHOLDING CLIENT AUDIT ===', flush=True)
    for sym in symbols:
        try:
            sh = ShareholdingClient.fetch_shareholding_pattern(sym)
            print(f"\n{sym} Shareholding:", flush=True)
            print(f"  Source: {sh.get('source')}, Quality: {sh.get('data_quality_flag')}", flush=True)
            print(f"  Promoter: {sh.get('promoter_holding_pct')}%, FII: {sh.get('fii_holding_pct')}%, DII: {sh.get('dii_holding_pct')}%, Public: {sh.get('retail_public_pct')}%", flush=True)
            print(f"  Period: {sh.get('period_end_date')}", flush=True)
        except Exception as e:
            print(f"{sym} Shareholding ERROR: {e}", flush=True)

    print('\n=== 3. NSE CLIENT DIRECT AUDIT ===', flush=True)
    nse = NseClient(rate_limit_seconds=0.5)
    for sym in symbols:
        print(f"\n--- NSE Direct for {sym} ---", flush=True)
        try:
            sh_nse = nse.fetch_shareholding_pattern(sym)
            print(f"  NSE Shareholding count: {len(sh_nse)}", flush=True)
            if sh_nse:
                print(f"    Latest: {sh_nse[0]}", flush=True)
        except Exception as e:
            print(f"  NSE Shareholding ERROR: {e}", flush=True)

        try:
            ann = nse.fetch_corporate_announcements(sym)
            print(f"  NSE Announcements count: {len(ann)}", flush=True)
            if ann:
                print(f"    Sample: {ann[0]}", flush=True)
        except Exception as e:
            print(f"  NSE Announcements ERROR: {e}", flush=True)

        try:
            bm = nse.fetch_board_meetings(sym)
            print(f"  NSE Board Meetings count: {len(bm)}", flush=True)
            if bm:
                print(f"    Sample: {bm[0]}", flush=True)
        except Exception as e:
            print(f"  NSE Board Meetings ERROR: {e}", flush=True)

    print('\n=== 4. STRUCTURED EVENTS AUDIT ===', flush=True)
    for sym in symbols:
        try:
            events = StructuredDisclosuresClient.extract_structured_events(sym, limit=2)
            print(f"\n{sym} Structured Events: {len(events)}", flush=True)
            if events:
                print(f"  Sample: {events[0]}", flush=True)
        except Exception as e:
            print(f"{sym} Structured Events ERROR: {e}", flush=True)

    print('\n=== 5. MACRO REGIME AUDIT ===', flush=True)
    try:
        macro = MacroRegimeClient.fetch_current_macro_regime()
        print(f"Macro Regime: {macro}", flush=True)
    except Exception as e:
        print(f"Macro ERROR: {e}", flush=True)

if __name__ == '__main__':
    run_audit()

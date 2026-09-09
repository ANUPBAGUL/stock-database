"""
Interactive CLI Runner: Institutional Adaptive Market Intelligence Screener & Trade Action Cards.
Usage:
    python scripts/run_adaptive_market_screener.py --horizon SWING
    python scripts/run_adaptive_market_screener.py --horizon SWING --intent "pharma and realty breakouts" --limit 10
    python scripts/run_adaptive_market_screener.py --horizon INTRADAY
    python scripts/run_adaptive_market_screener.py --horizon LONG_TERM
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.screener.session_strategy_manager import SessionStrategyManager
from src.screener.tv_dynamic_compiler import TVDynamicCompiler


def main():
    parser = argparse.ArgumentParser(description="Adaptive Market Intelligence & Dynamic TradingView Action Card Dispatcher")
    parser.add_argument("--horizon", type=str, default="SWING", choices=["INTRADAY", "SWING", "LONG_TERM"],
                        help="Trading horizon (INTRADAY, SWING, LONG_TERM)")
    parser.add_argument("--intent", type=str, default=None,
                        help="Optional user tactical guidance (e.g. 'Pharma momentum and auto ancillaries')")
    parser.add_argument("--limit", type=int, default=10, help="Number of trade cards to emit")
    parser.add_argument("--refresh", action="store_true", help="Force refresh live market intelligence")

    args = parser.parse_args()

    print("=" * 80)
    print(f"[*] INITIALIZING 5-VECTOR INSTITUTIONAL MARKET DISPATCHER (Horizon: {args.horizon})")
    print("=" * 80)

    # 1. Fetch Market Intelligence & Strategy Blueprint
    market_data = SessionStrategyManager.get_market_intelligence(force_refresh=args.refresh)
    ast, source = SessionStrategyManager.get_active_strategy(
        horizon=args.horizon,
        user_intent=args.intent,
        force_refresh=args.refresh
    )

    regime = market_data["overall_regime"]
    cmmi = market_data.get("cmmi_score", 50.0)
    breadth = market_data["market_breadth"]
    flows = market_data["institutional_flows_cash"]
    deriv = market_data.get("derivatives_positioning", {})
    spreads = market_data.get("market_dispersion_spreads", {})
    vol = market_data.get("volatility_regime", {})
    rot = market_data["sector_rotation_matrix"]

    print(f"\n[1. LIVE 5-VECTOR MARKET MOOD & POSITIONING] ({market_data['as_of_timestamp'][:19]})")
    print(f"  • Composite Mood Index (CMMI): {cmmi}/100 -> Regime: {regime} (Risk Budget: {market_data['risk_budget_pct']}%)")
    print(f"  • FII Derivatives Positioning: FII Long: {deriv.get('fii_index_future_long_pct')}% | FII Short: {deriv.get('fii_index_future_short_pct')}%")
    print(f"  • Derivatives Stance:         {deriv.get('positioning_stance')}")
    print(f"  • Option Chain PCR:           {deriv.get('index_options_pcr')} (Total Put OI: {deriv.get('total_index_put_oi'):,} | Call OI: {deriv.get('total_index_call_oi'):,})")
    print(f"  • Volatility & Tail Risk:     India VIX: {vol.get('india_vix')} ({vol.get('vix_day_change_pct')}%) -> Volatility Compression: {vol.get('volatility_compression')}")
    print(f"  • Nifty 500 Breadth:          {breadth['advances']} Adv / {breadth['declines']} Dec ({breadth['percent_advancing']}% advancing)")
    print(f"  • Net 52-Week Highs/Lows:     +{breadth.get('net_new_52w_highs')} ({breadth.get('new_52w_highs_count')} Highs / {breadth.get('new_52w_lows_count')} Lows)")
    print(f"  • Midcap vs Nifty Spread:     {spreads.get('midcap_vs_nifty_spread_pct'):+0.2f}% ({spreads.get('risk_appetite_stance')})")
    print(f"  • Institutional Cash Flow:    DII: Rs.{flows['dii_net_cr']:+,.2f} Cr | FII: Rs.{flows['fii_net_cr']:+,.2f} Cr | Total: Rs.{flows['total_net_cr']:+,.2f} Cr")
    print(f"  • Strategist Engine:          {source}")

    print("\n[2. RELATIVE ROTATION GRAPH (RRG) SECTOR MATRIX]")
    print(f"  • Leading Sectors:    {', '.join(rot['leading_sectors']) if rot['leading_sectors'] else 'None'}")
    print(f"  • Improving Sectors:  {', '.join(rot['improving_sectors']) if rot['improving_sectors'] else 'None'}")
    print(f"  • Lagging Sectors:    {', '.join(rot['lagging_sectors']) if rot['lagging_sectors'] else 'None'}")

    print("\n[3. ACTIVE STRATEGY BLUEPRINT]")
    print(f"  • Tactical Posture:   {ast.tactical_posture}")
    if ast.user_intent_evaluated:
        print(f"  • Intent Guidance:    {ast.user_intent_evaluated}")
    print(f"  • Favored Sectors:    {', '.join(ast.favored_sectors)}")
    print(f"  • Target TV Clusters: {', '.join(ast.target_tv_industry_clusters[:6])}...")
    print(f"  • Technical Corridor: RSI [{ast.min_rsi} - {ast.max_rsi}] | RVOL >= {ast.min_relative_volume}x | Max P/E: {ast.max_pe_ratio}x | Min Turnover: Rs.{ast.min_turnover_cr} Cr")

    # 2. Execute Dynamic Scan on TradingView
    print(f"\n[4. EXECUTING REAL-TIME TRADINGVIEW SCANNER DISPATCHER (Limit: {args.limit})]...")
    cards = TVDynamicCompiler.execute_strategy_scan(ast, limit=args.limit)

    if not cards:
        print("\n[-] No candidates currently match the strict adaptive criteria. Capital preservation active.")
        print("=" * 80)
        return

    print(f"\n[+] FOUND {len(cards)} ACTIONABLE INSTITUTIONAL TRADE CARDS:")
    print("=" * 80)

    for i, c in enumerate(cards, 1):
        print(f"\n#{i:02d} [{c.symbol}] — {c.sector} | Industry: {c.industry or 'N/A'}")
        print(f"    Thesis: {c.setup_thesis}")
        print(f"    DVM Scores: Composite: {c.dvm_composite_score}/100 [Durability: {c.dvm_durability_score} | Valuation: {c.dvm_valuation_score} | Momentum: {c.dvm_momentum_score}]")
        print(f"    Execution Bracket (Risk/Reward 1:{c.risk_reward_ratio:.1f}):")
        print(f"      • Entry Trigger:  Rs.{c.entry_price:,.2f}")
        print(f"      • Stop Loss (SL): Rs.{c.stop_loss:,.2f} (-{c.risk_pct}%) [Risk Budget per share: Rs.{c.entry_price - c.stop_loss:.2f}]")
        print(f"      • Target 1 (2R):  Rs.{c.target_1:,.2f} (+{c.target_1_pct}%) [Book 50%, Trail SL to Breakeven]")
        print(f"      • Target 2 (3R):  Rs.{c.target_2:,.2f} (+{c.target_2_pct}%) [Runner]")
        print(f"    Position Sizing:    {c.position_sizing_verdict}")
        print("-" * 80)

    print("\n[*] Execution dispatch completed successfully.\n")


if __name__ == "__main__":
    main()

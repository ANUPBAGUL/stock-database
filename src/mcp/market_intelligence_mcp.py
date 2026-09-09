"""
Institutional Market Intelligence MCP Server.
Exposes standard FastMCP tools for real-time market regime, 5-vector institutional positioning,
FII Index Futures Long/Short ratio, Option PCR, and Sector RRG for Indian equities (NSE/BSE).
"""

import json
from mcp.server.fastmcp import FastMCP
from src.mcp.market_intelligence_client import MarketIntelligenceClient
from src.mcp.sector_constituents_store import SectorConstituentsStore

# Initialize FastMCP Server
mcp = FastMCP("market-intelligence-mcp")
_client = MarketIntelligenceClient()


@mcp.tool()
def get_market_regime_matrix() -> str:
    """
    Returns the real-time macroeconomic stance, Composite Market Mood Index (CMMI, 0-100),
    FII Index Futures positioning, market breadth, and recommended capital risk budget.
    """
    data = _client.fetch_live_market_intelligence()
    summary = {
        "as_of_timestamp": data["as_of_timestamp"],
        "cmmi_score": data["cmmi_score"],
        "overall_regime": data["overall_regime"],
        "risk_budget_pct": data["risk_budget_pct"],
        "benchmark_nifty50": data["benchmark_nifty50"],
        "volatility_regime": data["volatility_regime"],
        "market_breadth": data["market_breadth"],
        "derivatives_positioning": data["derivatives_positioning"],
        "institutional_flows_cash": data["institutional_flows_cash"],
        "market_dispersion_spreads": data["market_dispersion_spreads"]
    }
    return json.dumps(summary, indent=2)


@mcp.tool()
def get_derivatives_positioning_and_pcr() -> str:
    """
    Returns official FII Index Futures Long/Short %, Client Long/Short %, and Index Options PCR.
    High predictive value for asymmetric short-covering rallies and overbought reversals.
    """
    data = _client.fetch_participant_derivatives_positioning()
    return json.dumps(data, indent=2)


@mcp.tool()
def get_market_breadth_and_spreads() -> str:
    """
    Returns Nifty 500 Advance/Decline, Net 52-Week Highs/Lows, and Midcap vs Nifty 50 performance spreads.
    """
    data = _client.fetch_live_market_intelligence()
    summary = {
        "market_breadth": data["market_breadth"],
        "market_dispersion_spreads": data["market_dispersion_spreads"]
    }
    return json.dumps(summary, indent=2)


@mcp.tool()
def get_sector_relative_rotation() -> str:
    """
    Returns the 14 NSE Sectoral Indices classified into Relative Rotation Graph (RRG) quadrants
    (LEADING, IMPROVING, WEAKENING, LAGGING) relative to Nifty 50.
    """
    data = _client.fetch_live_market_intelligence()
    return json.dumps(data["sector_rotation_matrix"], indent=2)


@mcp.tool()
def get_sector_constituents_and_clusters(sector_name: str) -> str:
    """
    Returns official constituent symbols and broader TradingView industry clusters
    for an NSE Sectoral Index (e.g. 'NIFTY AUTO', 'NIFTY PHARMA').
    """
    constituents = SectorConstituentsStore.get_index_constituents(sector_name)
    clusters = SectorConstituentsStore.get_tv_industry_clusters(sector_name)
    return json.dumps({
        "sector_name": sector_name.upper(),
        "official_constituents_count": len(constituents),
        "official_constituents": constituents,
        "broad_tradingview_clusters": clusters
    }, indent=2)


if __name__ == "__main__":
    mcp.run()

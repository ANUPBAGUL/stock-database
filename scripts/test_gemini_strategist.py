import os, sys, json, requests
sys.path.insert(0, ".")
from dotenv import load_dotenv
from src.mcp.market_intelligence_client import MarketIntelligenceClient
from src.llm.market_strategist_models import AdaptiveStrategyAST

load_dotenv()
key = os.environ.get("GEMINI_API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={key}"

client = MarketIntelligenceClient()
data = client.fetch_live_market_intelligence()

prompt = f"""You are an Institutional CIO for Indian Equities.
Analyze this live NSE market data and return ONLY a JSON object matching this schema:
{{
  "horizon": "SWING",
  "regime": "{data.get('overall_regime')}",
  "tactical_posture": "Selective accumulation in leaders with VCP contractions",
  "user_intent_evaluated": null,
  "favored_sectors": ["NIFTY AUTO", "NIFTY PHARMA"],
  "excluded_sectors": [],
  "target_tv_industry_clusters": ["Motor Vehicles", "Pharmaceuticals: Major"],
  "min_rsi": 50.0,
  "max_rsi": 70.0,
  "min_relative_volume": 1.5,
  "max_debt_to_equity": 1.5,
  "max_pe_ratio": 60.0,
  "min_turnover_cr": 5.0,
  "near_52w_high_pct": 6.0,
  "risk_budget_pct": {data.get('risk_budget_pct', 75.0)},
  "strategy_name": "Dynamic Swing Strategy",
  "cio_memo": "CIO summary memo grounded in real data"
}}

Live Market Data:
{json.dumps(data, indent=2)}
"""

req_body = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {
        "temperature": 0.1,
        "responseMimeType": "application/json"
    }
}
resp = requests.post(url, json=req_body, timeout=20)
print("HTTP Status:", resp.status_code)
if resp.status_code == 200:
    parsed = json.loads(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
    print("CIO Memo:", parsed.get("cio_memo"))
    print("Favored Sectors:", parsed.get("favored_sectors"))
    print("Strategy Name:", parsed.get("strategy_name"))
else:
    print("Error:", resp.text)

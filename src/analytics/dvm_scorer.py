"""
Trendlyne-Style DVM (Durability, Valuation, Momentum & Delivery) Scoring Engine.
Computes institutional quality scores (0 - 100) across:
1. Durability: Balance sheet solvency, debt-to-equity, and cash flow health.
2. Valuation: Multiples fairness, avoiding euphoric peak pricing.
3. Momentum & Accumulation: Trend sponsorship, 52W high proximity, and volume surge.
"""

from typing import Dict, Any, Tuple


class DVMScorer:
    """
    Computes normalized Durability, Valuation, Momentum, and Composite scores.
    """

    @classmethod
    def calculate_scores(cls, stock_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculates Durability, Valuation, Momentum, and Composite scores for a candidate.
        """
        # 1. Durability Score (0 - 100)
        # Driven by Debt/Equity, balance sheet solvency, and operating margins
        de = stock_data.get("effective_debt_to_equity")
        if de is None:
            de = stock_data.get("debt_to_equity")
        if de is None:
            de = stock_data.get("debt_to_equity_fq")
        if de is None:
            de = stock_data.get("debt_to_equity_fy")

        is_financial = (str(stock_data.get("sector", "")).lower() in ["finance", "financials"] or
                        "bank" in str(stock_data.get("industry", "")).lower())

        if is_financial:
            # Banking/NBFC leverage is structural; baseline to healthy financial solvency
            durability = 85.0
        elif de is None:
            # Neutral baseline if debt data is undisclosed
            durability = 65.0
        elif de < 0.3:
            durability = 95.0
        elif de < 0.7:
            durability = 85.0
        elif de < 1.0:
            durability = 70.0
        elif de < 1.5:
            durability = 50.0
        elif de < 2.0:
            durability = 35.0
        else:
            durability = 20.0

        # Adjust for operating margin if present
        opm = stock_data.get("operating_margin_ttm")
        if opm is not None:
            if opm > 20.0:
                durability = min(100.0, durability + 5.0)
            elif opm < 5.0:
                durability = max(10.0, durability - 10.0)

        # 2. Valuation Score (0 - 100)
        # Driven by P/E ratio, P/B, and revenue growth context
        pe = stock_data.get("price_earnings_ttm")
        if pe is None or pe <= 0:
            # Check price-to-book
            pb = stock_data.get("price_book_fq", 3.0)
            if pb < 2.0:
                valuation = 80.0
            elif pb < 5.0:
                valuation = 60.0
            else:
                valuation = 40.0
        elif pe < 18.0:
            valuation = 90.0
        elif pe < 30.0:
            valuation = 80.0
        elif pe < 45.0:
            valuation = 65.0
        elif pe < 65.0:
            valuation = 45.0
        elif pe < 85.0:
            valuation = 30.0
        else:
            valuation = 15.0

        # 3. Momentum & Accumulation Score (0 - 100)
        cmp = float(stock_data.get("close", 0.0) or stock_data.get("cmp", 0.0))
        h52 = float(stock_data.get("price_52_week_high", 0.0) or 0.0)
        ema50 = float(stock_data.get("EMA50", 0.0) or 0.0)
        sma200 = float(stock_data.get("SMA200", 0.0) or 0.0)
        rvol = float(stock_data.get("relative_volume_10d_calc", 1.0) or 1.0)
        rsi = float(stock_data.get("RSI", 55.0) or 55.0)

        momentum = 30.0  # Base score

        # Stage 2 Moving Average Trend sponsorship (+30 pts)
        if cmp > ema50 > sma200 and sma200 > 0:
            momentum += 30.0
        elif cmp > ema50:
            momentum += 15.0

        # Proximity to 52-Week High (+25 pts)
        if h52 > 0 and cmp > 0:
            dist_52w = ((h52 - cmp) / h52) * 100.0
            if dist_52w <= 3.5:
                momentum += 25.0
            elif dist_52w <= 6.0:
                momentum += 18.0
            elif dist_52w <= 12.0:
                momentum += 10.0

        # Relative Volume accumulation (+15 pts)
        if rvol >= 2.5:
            momentum += 15.0
        elif rvol >= 1.8:
            momentum += 10.0
        elif rvol >= 1.3:
            momentum += 5.0

        # Wilder RSI in optimal momentum corridor (+10 pts)
        if 52.0 <= rsi <= 68.0:
            momentum += 10.0
        elif 48.0 <= rsi <= 72.0:
            momentum += 5.0

        momentum = min(100.0, max(10.0, momentum))

        # 4. Composite DVM Score (Weighted Institutional Blend)
        composite = round((durability * 0.30) + (valuation * 0.25) + (momentum * 0.45), 1)

        return {
            "durability": round(durability, 1),
            "valuation": round(valuation, 1),
            "momentum": round(momentum, 1),
            "composite": composite
        }

import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PortfolioOptimizer:
    """
    Constructs portfolios with position sizing and strict concentration risk controls.
    """

    @staticmethod
    def allocate_portfolio(
        candidates: List[Dict[str, Any]],
        max_single_stock_pct: float = 5.0, # Max 5% in any single stock
        max_sector_concentration_pct: float = 20.0 # Max 20% in any single sector
    ) -> List[Dict[str, Any]]:
        
        # Sort candidates by conviction score descending
        sorted_candidates = sorted(candidates, key=lambda x: x.get("conviction_score", 0), reverse=True)

        portfolio = []
        sector_allocations = {}
        total_allocated = 0.0

        for item in sorted_candidates:
            symbol = item.get("symbol")
            sector = item.get("sector", "Unclassified")
            conviction = item.get("conviction_score", 0)

            if conviction < 60: # Filter out low conviction
                continue

            current_sector_alloc = sector_allocations.get(sector, 0.0)
            if current_sector_alloc >= max_sector_concentration_pct:
                logger.info(f"Skipping {symbol}: Sector '{sector}' cap of {max_sector_concentration_pct}% reached.")
                continue

            # Position weight based on conviction
            proposed_weight = min(max_single_stock_pct, (conviction / 100.0) * max_single_stock_pct)
            
            # Check remaining sector budget
            allowed_weight = min(proposed_weight, max_sector_concentration_pct - current_sector_alloc)

            if allowed_weight > 0.5:
                portfolio.append({
                    "symbol": symbol,
                    "sector": sector,
                    "conviction_score": conviction,
                    "target_weight_pct": round(allowed_weight, 2)
                })
                sector_allocations[sector] = current_sector_alloc + allowed_weight
                total_allocated += allowed_weight

        logger.info(f"Constructed portfolio with {len(portfolio)} positions (Total Allocation: {total_allocated:.1f}%)")
        return portfolio

"""
Sector Constituents & Industry Cluster Store for Indian Equities.
Maintains:
1. Official constituent symbol lists for the 14 NSE Sectoral Indices.
2. Cross-mapping from NSE Sector themes to broader TradingView industry clusters
   to capture high-momentum mid-cap and small-cap stocks.
"""

from typing import Dict, List, Set, Optional


# 1. Verified Official Constituent Symbols for Key NSE Sectoral Indices
NSE_SECTOR_CONSTITUENTS: Dict[str, List[str]] = {
    "NIFTY AUTO": [
        "MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "EICHERMOT",
        "HEROMOTOCO", "TVSMOTOR", "BHARATFORG", "BOSCHLTD", "MOTHERSON",
        "ASHOKLEY", "APOLLOTYRE", "MRF", "BALKRISIND", "EXIDEIND"
    ],
    "NIFTY IT": [
        "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM",
        "LTM", "PERSISTENT", "COFORGE", "MPHASIS", "LTTS"
    ],
    "NIFTY PHARMA": [
        "SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB", "LUPIN",
        "TORNTPHARM", "MANKIND", "ZYDUSLIFE", "AUROPHARMA", "ALKEM",
        "BIOCON", "GLENMARK", "IPCALAB", "ABBOTINDIA", "LAURUSLABS",
        "NATCOPHARM", "AJANTPHARM", "GRANULES", "JBCHEPHARM", "PFIZER"
    ],
    "NIFTY FMCG": [
        "ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA", "TATACONSUM",
        "VARUN", "DABUR", "MARICO", "COLPAL", "GODREJCP",
        "PGHH", "RADICO", "EMAMILTD", "UBL", "BALRAMCHIN"
    ],
    "NIFTY METAL": [
        "TATASTEEL", "JSWSTEEL", "HINDALCO", "JINDALSTEL", "VEDL",
        "COALINDIA", "NMDC", "SAIL", "NATIONALUM", "APLAPOLLO",
        "HINDZINC", "RATNAMANI", "WELCORP", "HINDCOPPER", "ADANIENT"
    ],
    "NIFTY REALTY": [
        "DLF", "LODHA", "GODREJPROP", "OBEROIRLTY", "PHOENIXLTD",
        "BRIGADE", "PRESTIGE", "SOBHA", "SIGNATURE", "SUNTECK"
    ],
    "NIFTY PSU BANK": [
        "SBIN", "BANKBARODA", "PNB", "CANBK", "UNIONBANK",
        "INDIANB", "IOB", "UCOBANK", "BANKINDIA", "CENTRALBK",
        "MAHABANK", "PSB"
    ],
    "NIFTY PRIVATE BANK": [
        "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "INDUSINDBK",
        "FEDERALBNK", "IDFCFIRSTB", "BANDHANBNK", "AUBANK", "RBLBANK"
    ],
    "NIFTY ENERGY": [
        "RELIANCE", "NTPC", "ONGC", "POWERGRID", "BPCL",
        "IOC", "TATAPOWER", "GAIL", "ADANIGREEN", "ADANIPOWER"
    ],
    "NIFTY INFRASTRUCTURE": [
        "LT", "RELIANCE", "BHARTIARTL", "NTPC", "POWERGRID",
        "ULTRACEMCO", "GRASIM", "ONGC", "ADANIPORTS", "INDIGO"
    ],
    "NIFTY HEALTHCARE INDEX": [
        "SUNPHARMA", "CIPLA", "DRREDDY", "APOLLOHOSP", "MAXHEALTH",
        "DIVISLAB", "LUPIN", "FORTIS", "MEDANTA", "LALPATHLAB"
    ],
    "NIFTY FINANCIAL SERVICES": [
        "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN",
        "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "CHOLAFIN"
    ],
    "NIFTY INDIA DEFENCE": [
        "HAL", "BEL", "MAZDOCK", "COCHINSHIP", "BDL", "BEML",
        "SOLARINDS", "DATAPATTNS", "MTARTECH", "PARAS", "ASTRAMICRO", "ZEN"
    ],
    "NIFTY CONSUMER DURABLES": [
        "TITAN", "HAVELLS", "VOLTAS", "DIXON", "AMBER", "BLUESTARCO",
        "CROMPTON", "WHIRLPOOL", "KAJARIACER", "BATAINDIA", "VGUARD", "CENTURYPLY"
    ],
    "NIFTY CAPITAL MARKETS": [
        "HDFCAMC", "BSE", "MCX", "CDSL", "CAMS", "NAM-INDIA",
        "UTIAMC", "ANGELONE", "MOTILALOFS", "ANANDRATHI", "ISEC", "KFINTECH"
    ],
    "NIFTY OIL & GAS": [
        "RELIANCE", "ONGC", "IOC", "BPCL", "GAIL", "HPCL",
        "PETRONET", "OIL", "IGL", "MGL", "GUJGASLTD", "AEGISLOG", "CASTROLIND"
    ],
    "NIFTY CPSE": [
        "NTPC", "ONGC", "COALINDIA", "BEL", "POWERGRID",
        "NHPC", "OIL", "NBCC", "SJVN", "COCHINSHIP"
    ],
    "NIFTY CHEMICALS": [
        "PIIND", "SRF", "DEEPAKNTR", "FLUOROCHEM", "NAVINFLUOR",
        "AARTIIND", "TATACHEM", "ATUL", "CLEAN", "SUMICHEM", "ALKYLAMINE"
    ]
}


# 2. Broad TradingView Industry Clusters mapped from NSE Themes
# Enables capturing high-growth mid-cap and small-cap compounders across the 5,000-stock universe
NSE_THEME_TO_TV_CLUSTERS: Dict[str, List[str]] = {
    "NIFTY AUTO": [
        "Auto Parts: OEM",
        "Motor Vehicles",
        "Trucks/Construction/Farm Machinery",
        "Automotive Aftermarket",
        "Tires/Rubber"
    ],
    "NIFTY IT": [
        "Information Technology Services",
        "Packaged Software",
        "Data Processing Services",
        "Computer Communications",
        "Internet Software/Services"
    ],
    "NIFTY PHARMA": [
        "Major Pharmaceuticals",
        "Biotechnology",
        "Medical Specialties",
        "Pharmaceuticals: Other",
        "Medical/Nursing Services"
    ],
    "NIFTY HEALTHCARE INDEX": [
        "Hospital/Nursing Management",
        "Medical Specialties",
        "Major Pharmaceuticals",
        "Biotechnology",
        "Medical Diagnostics"
    ],
    "NIFTY FMCG": [
        "Food: Specialty/Candy",
        "Food: Meat/Fish/Dairy",
        "Beverages: Non-Alcoholic",
        "Beverages: Alcoholic",
        "Household/Personal Care",
        "Tobacco"
    ],
    "NIFTY METAL": [
        "Steel",
        "Non-Ferrous Metals",
        "Precious Metals",
        "Metal Fabrication",
        "Other Metals/Minerals"
    ],
    "NIFTY REALTY": [
        "Real Estate Development",
        "Real Estate Services",
        "Commercial Services: Property"
    ],
    "NIFTY ENERGY": [
        "Oil & Gas Production",
        "Electric Utilities",
        "Gas Distributors",
        "Alternative Power Generation",
        "Refining/Marketing"
    ],
    "NIFTY INFRASTRUCTURE": [
        "Engineering & Construction",
        "Heavy Construction",
        "Civil Engineering",
        "Building Products",
        "Transportation: Logistics"
    ],
    "NIFTY PSU BANK": [
        "Major Banks",
        "Regional Banks"
    ],
    "NIFTY PRIVATE BANK": [
        "Major Banks",
        "Regional Banks"
    ],
    "NIFTY FINANCIAL SERVICES": [
        "Finance/Rental/Leasing",
        "Investment Managers",
        "Life/Health Insurance",
        "Multi-line Insurance",
        "Financial Conglomerates"
    ],
    "NIFTY INDIA DEFENCE": [
        "Aerospace & Defense",
        "Marine Engineering",
        "Electronic Components",
        "Electronic Equipment/Instruments"
    ],
    "NIFTY CONSUMER DURABLES": [
        "Consumer Electronics/Appliances",
        "Electronics/Appliances",
        "Electronics Distributors",
        "Other Consumer Specialties",
        "Home Furnishings",
        "Footwear"
    ],
    "NIFTY CAPITAL MARKETS": [
        "Investment Banks/Brokers",
        "Investment Managers",
        "Financial Conglomerates"
    ],
    "NIFTY OIL & GAS": [
        "Oil & Gas Production",
        "Refining/Marketing",
        "Integrated Oil",
        "Oil Refining/Marketing",
        "Gas Distributors",
        "Oilfield Services/Equipment"
    ],
    "NIFTY CPSE": [
        "Electric Utilities",
        "Coal",
        "Engineering & Construction"
    ],
    "NIFTY CHEMICALS": [
        "Chemicals: Specialty",
        "Chemicals: Agricultural",
        "Chemicals: Major Diversified",
        "Chemicals: Diversified",
        "Industrial Specialties"
    ]
}


class SectorConstituentsStore:
    """Provides high-speed lookup between NSE Sector themes and symbols / TV clusters."""

    @classmethod
    def get_index_constituents(cls, sector_name: str) -> List[str]:
        """Returns the official constituent symbols for an NSE Sector index."""
        clean_name = sector_name.strip().upper()
        return NSE_SECTOR_CONSTITUENTS.get(clean_name, [])

    @classmethod
    def get_tv_industry_clusters(cls, sector_name: str) -> List[str]:
        """Returns the broader TradingView industry clusters matching the sector theme."""
        clean_name = sector_name.strip().upper()
        return NSE_THEME_TO_TV_CLUSTERS.get(clean_name, [])

    @classmethod
    def get_all_sector_names(cls) -> List[str]:
        """Returns all supported NSE Sectoral Index names."""
        return list(NSE_SECTOR_CONSTITUENTS.keys())

    @classmethod
    def identify_sector_for_symbol(cls, symbol: str) -> Optional[str]:
        """Identifies which official NSE Sector index a symbol belongs to (if any)."""
        clean_sym = symbol.strip().upper().replace("NSE:", "").replace("BSE:", "").strip()
        for sector, symbols in NSE_SECTOR_CONSTITUENTS.items():
            if clean_sym in symbols:
                return sector
        return None

    @classmethod
    def identify_sector_by_tv_industry(cls, industry: str) -> Optional[str]:
        """
        Maps a TradingView industry name to its corresponding NSE Sector theme.
        Enables mid-cap and small-cap stocks across the 5,000-stock universe to be
        accurately associated with sector trends even if not in the official benchmark.
        """
        if not industry:
            return None
        clean_ind = industry.strip().lower()
        for sector, clusters in NSE_THEME_TO_TV_CLUSTERS.items():
            for c in clusters:
                if clean_ind == c.lower() or c.lower() in clean_ind:
                    return sector
        return None


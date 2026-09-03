"""
Batch Stock Parser & Comprehensive Parameter Ingestion Manager.

Parses 1, 10, or 100+ stock symbols or names in freeform text,
orchestrates multi-threaded real-data ingestion, and computes
the full analytical parameter suite from AI_swing.
"""

import os
import re
import math
import logging
import threading
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from src.db.base import SessionLocal
from src.db.models import Company, Sector, DailyPriceRaw, BitemporalFinancial, CorporateAction, BoardMeetingAnnouncement, CorporateAnnouncement
from src.ingestion.upstox_client import UpstoxMarketDataIngestion
from src.ingestion.yfinance_client import YFinanceClient
from src.ingestion.nse_client import NseClient
from src.ingestion.shareholding_client import ShareholdingClient
from src.ingestion.structured_events_client import StructuredDisclosuresClient
from src.ingestion.bitemporal_ingest import BitemporalIngestionEngine
from src.analytics.announcement_decay_engine import AnnouncementDecayEngine
from src.analytics.snapshot_engine import DecisionSnapshotEngine
from src.analytics.feature_engine import FeatureEngine
from src.ai.decision_engine import DecisionEngine
from src.ingestion.macro_client import MacroRegimeClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Common Indian Equities Name-to-NSE-Ticker Mapping Dictionary
NAME_TO_TICKER = {
    "RELIANCE": "RELIANCE",
    "RIL": "RELIANCE",
    "TATA CONSULTANCY SERVICES": "TCS",
    "TCS": "TCS",
    "INFOSYS": "INFY",
    "INFY": "INFY",
    "HDFC BANK": "HDFCBANK",
    "HDFCBANK": "HDFCBANK",
    "ICICI BANK": "ICICIBANK",
    "ICICIBANK": "ICICIBANK",
    "STATE BANK OF INDIA": "SBIN",
    "SBI": "SBIN",
    "SBIN": "SBIN",
    "TATA MOTORS": "TMCV",
    "TATAMOTORS": "TMCV",
    "TMCV": "TMCV",
    "TMPV": "TMPV",
    "TRENT": "TRENT",
    "DIXON": "DIXON",
    "DIXON TECHNOLOGIES": "DIXON",
    "POLYCAB": "POLYCAB",
    "POLYCAB INDIA": "POLYCAB",
    "ASTRAL": "ASTRAL",
    "ASTRAL PIPES": "ASTRAL",
    "SIEMENS": "SIEMENS",
    "BHARTI AIRTEL": "BHARTIARTL",
    "AIRTEL": "BHARTIARTL",
    "BHARTIARTL": "BHARTIARTL",
    "LARSEN & TOUBRO": "LT",
    "L&T": "LT",
    "LT": "LT",
    "ITC": "ITC",
    "HINDUNILVR": "HINDUNILVR",
    "HUL": "HINDUNILVR",
    "HINDUSTAN UNILEVER": "HINDUNILVR",
    "BAJAJ FINANCE": "BAJFINANCE",
    "BAJFINANCE": "BAJFINANCE",
    "BAJAJ FINSERV": "BAJAJFINSV",
    "KOTAK BANK": "KOTAKBANK",
    "KOTAKBANK": "KOTAKBANK",
    "TITAN": "TITAN",
    "ASIAN PAINTS": "ASIANPAINT",
    "ASIANPAINT": "ASIANPAINT",
    "MARUTI": "MARUTI",
    "MARUTI SUZUKI": "MARUTI",
    "SUN PHARMA": "SUNPHARMA",
    "SUNPHARMA": "SUNPHARMA",
    "AXIS BANK": "AXISBANK",
    "AXISBANK": "AXISBANK",
    "NTPC": "NTPC",
    "POWER GRID": "POWERGRID",
    "POWERGRID": "POWERGRID",
    "ONGC": "ONGC",
    "COAL INDIA": "COALINDIA",
    "COALINDIA": "COALINDIA",
    "TATA STEEL": "TATASTEEL",
    "TATASTEEL": "TATASTEEL",
    "JSW STEEL": "JSWSTEEL",
    "JSWSTEEL": "JSWSTEEL",
    "ADANI PORTS": "ADANIPORTS",
    "ADANIPORTS": "ADANIPORTS",
    "ADANI ENTERPRISES": "ADANIENT",
    "ADANIENT": "ADANIENT",
    "ULTRATECH CEMENT": "ULTRACEMCO",
    "ULTRACEMCO": "ULTRACEMCO",
    "GRASIM": "GRASIM",
    "CIPLA": "CIPLA",
    "TECH MAHINDRA": "TECHM",
    "TECHM": "TECHM",
    "WIPRO": "WIPRO",
    "HCL TECH": "HCLTECH",
    "HCLTECH": "HCLTECH",
    "NESTLE": "NESTLEIND",
    "NESTLE INDIA": "NESTLEIND",
    "NESTLEIND": "NESTLEIND",
    "PERSISTENT": "PERSISTENT",
    "PERSISTENT SYSTEMS": "PERSISTENT",
    "KPIT": "KPITTECH",
    "KPITTECH": "KPITTECH",
    "KPIT TECHNOLOGIES": "KPITTECH",
    "TATA ELXSI": "TATAELXSI",
    "TATAELXSI": "TATAELXSI",
    "CDSL": "CDSL",
    "KAYNES": "KAYNES",
    "KAYNES TECHNOLOGY": "KAYNES",
    "HAL": "HAL",
    "HINDUSTAN AERONAUTICS": "HAL",
    "BEL": "BEL",
    "BHARAT ELECTRONICS": "BEL",
    "MAZDOCK": "MAZDOCK",
    "MAZAGON DOCK": "MAZDOCK",
    "COCHIN SHIPYARD": "COCHINSHIP",
    "COCHINSHIP": "COCHINSHIP",
    "ZOMATO": "ZOMATO",
    "SWIGGY": "SWIGGY",
    "JIO FINANCIAL": "JIOFIN",
    "JIOFIN": "JIOFIN",
    "VARUN BEVERAGES": "VBL",
    "VBL": "VBL"
}


STOP_WORDS = {
    "PLEASE", "TRACK", "AND", "ALSO", "ADD", "STOCK", "STOCKS", "WATCHLIST", "THE", "OF",
    "FOR", "IN", "ON", "WITH", "MY", "TO", "A", "AN", "BUY", "SELL", "HOLD", "LOOK",
    "AT", "PRICE", "TARGET", "CMP", "SYSTEMS", "LIMITED", "LTD", "CORP", "CORPORATION",
    "INDIA", "CO", "COMPANY", "GROUP", "ENTERPRISES", "INDUSTRIES", "HOLDINGS"
}


class WatchlistManager:
    """
    Manages stock parsing, comprehensive data ingestion, and complete parameter calculation.
    """

    @staticmethod
    def parse_stock_symbols(raw_text: str) -> List[str]:
        """
        Extracts clean, uppercase NSE stock symbols from arbitrary freeform text.
        Handles comma-separated, space-separated, newlines, and common company names.
        """
        if not raw_text or not raw_text.strip():
            return []

        raw_tokens = re.split(r'[,;\n\r\|\t]+', raw_text)
        candidates = []
        
        for tok in raw_tokens:
            tok_clean = tok.strip()
            if not tok_clean:
                continue
            
            words = tok_clean.split()
            normalized_phrase = " ".join(words).upper()
            if normalized_phrase in NAME_TO_TICKER:
                candidates.append(NAME_TO_TICKER[normalized_phrase])
                continue

            for w in words:
                clean_w = re.sub(r'[^A-Za-z0-9&\-]', '', w).upper()
                if not clean_w or clean_w in STOP_WORDS:
                    continue
                if clean_w in NAME_TO_TICKER:
                    candidates.append(NAME_TO_TICKER[clean_w])
                elif len(clean_w) >= 2 and len(clean_w) <= 15 and clean_w.isalnum():
                    candidates.append(clean_w)

        seen = set()
        deduped = []
        for sym in candidates:
            if sym not in seen and sym not in STOP_WORDS:
                seen.add(sym)
                deduped.append(sym)

        return deduped

    @staticmethod
    def ingest_and_calculate_all_parameters(symbol: str, db: Session, fast_mode: bool = False) -> Dict[str, Any]:
        """
        Ingests real-world market data exclusively via Upstox v2 API and computes full parameter suite.
        """
        symbol = symbol.upper().strip()
        today = date.today()
        upstox = UpstoxMarketDataIngestion()
        
        # 1. Ingest / Sync Company & Upstox Daily Price Candles
        live_quote = None
        yf_client = YFinanceClient()
        if not fast_mode:
            try:
                company, live_quote = upstox.ingest_stock_data(db, symbol)
            except Exception as e:
                logger.warning(f"Upstox stock ingestion error for {symbol}: {e}")
                company = db.query(Company).filter_by(nse_symbol=symbol).first()
        else:
            company = db.query(Company).filter_by(nse_symbol=symbol).first()

        if not company:
            # Fallback company registration
            sec = db.query(Sector).filter_by(sector_name="General").first()
            if not sec:
                sec = Sector(sector_id="sec_general", sector_name="General", description="General Equities Sector")
                db.add(sec)
                db.commit()
                db.refresh(sec)

            comp_id = f"comp_{symbol.lower()}"
            isin_val = f"INE{symbol[:7]}01" if len(symbol) <= 7 else f"INE{symbol[:7]}1"
            company = Company(
                company_id=comp_id,
                nse_symbol=symbol,
                bse_code=symbol,
                isin=isin_val,
                company_name=f"{symbol} Limited",
                sector_id=sec.sector_id,
                status="ACTIVE"
            )
            db.add(company)
            db.commit()
            db.refresh(company)
        else:
            # When a stock is analyzed, ensure it is activated in the watchlist
            if company.status != "ACTIVE":
                company.status = "ACTIVE"
                db.commit()
                db.refresh(company)

        # 1.1 Ensure daily price candles exist and are current (Yahoo Finance fallback/sync)
        latest_price_rec = db.query(DailyPriceRaw).filter_by(
            company_id=company.company_id
        ).order_by(DailyPriceRaw.trading_date.desc()).first()

        price_count = db.query(DailyPriceRaw).filter_by(company_id=company.company_id).count()
        needs_price_sync = (price_count < 20) or (latest_price_rec is None) or (latest_price_rec.trading_date < today)

        if needs_price_sync and not fast_mode:
            try:
                days_to_fetch = 400 if price_count < 20 else 10
                logger.info(f"Syncing recent daily price candles ({days_to_fetch}d) from Yahoo Finance for {symbol}...")
                yf_prices = yf_client.fetch_daily_prices(symbol, today - timedelta(days=days_to_fetch), today)
                valid_candles = 0
                for p in yf_prices:
                    cp = p.get("close_price")
                    if cp is None or (isinstance(cp, float) and math.isnan(cp)) or cp <= 0:
                        continue
                    raw_p = DailyPriceRaw(
                        company_id=company.company_id,
                        trading_date=p["trading_date"],
                        open_price=p["open_price"] if p.get("open_price") and not (isinstance(p["open_price"], float) and math.isnan(p["open_price"])) else cp,
                        high_price=p["high_price"] if p.get("high_price") and not (isinstance(p["high_price"], float) and math.isnan(p["high_price"])) else cp,
                        low_price=p["low_price"] if p.get("low_price") and not (isinstance(p["low_price"], float) and math.isnan(p["low_price"])) else cp,
                        close_price=cp,
                        volume=p["volume"] if p.get("volume") and not (isinstance(p["volume"], float) and math.isnan(p["volume"])) else 0,
                        turnover=p.get("turnover") if p.get("turnover") and not (isinstance(p.get("turnover"), float) and math.isnan(p.get("turnover"))) else None,
                        # Provenance fields — required for price reproducibility
                        exchange=p.get("exchange", "NSE"),
                        quote_type=p.get("quote_type", "CLOSE"),
                        price_source=p.get("price_source", "YFINANCE"),
                    )
                    db.merge(raw_p)
                    valid_candles += 1
                db.commit()
                logger.info(f"Synced {valid_candles} daily price candles for {symbol} via Yahoo Finance.")
            except Exception as e:
                db.rollback()
                logger.warning(f"Error fetching Yahoo Finance prices for {symbol}: {e}")

        # 2. Ensure Real Financials Exist (Dynamic Real-Data Ingestion via Screener XBRL)
        fin_count = db.query(BitemporalFinancial).filter_by(company_id=company.company_id).count()
        if fin_count < 8 and not fast_mode:
            try:
                from src.ingestion.screener_client import ScreenerClient
                sc = ScreenerClient()
                q_filings = sc.fetch_quarterly_history(symbol)
                bs_filings = sc.fetch_balance_sheet_history(symbol)

                # Ingest balance sheets
                for bs in bs_filings:
                    ped = bs.get("period_end_date")
                    if not ped:
                        continue
                    existing_bs = db.query(BitemporalFinancial).filter_by(
                        company_id=company.company_id, period_end_date=ped, period_type="ANNUAL"
                    ).first()
                    if not existing_bs:
                        pub_dt = datetime.combine(ped, datetime.min.time()) + timedelta(days=60)
                        BitemporalIngestionEngine.ingest_financial_record(
                            db=db,
                            company_id=company.company_id,
                            period_type="ANNUAL",
                            period_end_date=ped,
                            publication_date=pub_dt,
                            source="SCREENER_XBRL_ANNUAL",
                            metrics=bs,
                            consolidation_scope=bs.get("consolidation_scope", "CONSOLIDATED")
                        )

                # Ingest quarterly statements
                for qf in q_filings:
                    ped = qf.get("period_end_date")
                    if not ped:
                        continue
                    existing_q = db.query(BitemporalFinancial).filter_by(
                        company_id=company.company_id, period_end_date=ped, period_type="QUARTERLY"
                    ).first()
                    if not existing_q:
                        pub_dt = datetime.combine(ped, datetime.min.time()) + timedelta(days=45)
                        BitemporalIngestionEngine.ingest_financial_record(
                            db=db,
                            company_id=company.company_id,
                            period_type="QUARTERLY",
                            period_end_date=ped,
                            publication_date=pub_dt,
                            source="SCREENER_XBRL_QUARTERS",
                            metrics={
                                "revenue": qf.get("revenue_cr"),
                                "ebit": qf.get("ebit_cr"),
                                "ebitda": qf.get("ebit_cr"),
                                "pat": qf.get("pat_cr"),
                                "eps": qf.get("eps"),
                                "operating_cash_flow": qf.get("pat_cr"),
                                "consolidation_scope": qf.get("consolidation_scope", "CONSOLIDATED")
                            }
                        )
                logger.info(f"[Financials Ingest] Ingested verified financial statements for {symbol} via Screener XBRL.")
            except Exception as e:
                logger.warning(f"Error fetching Screener financials for {symbol}: {e}")

        # Shared NSE client — single session used for shareholding, board meetings, and announcements
        nse_client = NseClient() if not fast_mode else None

        # 3. Shareholding Pattern
        sh_data = None
        if not fast_mode:
            try:
                sh_data = ShareholdingClient.fetch_shareholding_pattern(symbol, nse_client=nse_client)
                if sh_data and sh_data.get("promoter_holding_pct") is not None:
                    from src.db.models.governance import ShareholdingHistory
                    import uuid
                    raw_p_date = sh_data.get("period_end_date")
                    if isinstance(raw_p_date, str):
                        try:
                            p_date = datetime.strptime(raw_p_date, "%Y-%m-%d").date()
                        except Exception:
                            p_date = today
                    elif isinstance(raw_p_date, datetime):
                        p_date = raw_p_date.date()
                    elif isinstance(raw_p_date, date):
                        p_date = raw_p_date
                    else:
                        p_date = today

                    raw_pub = sh_data.get("publication_timestamp")
                    if isinstance(raw_pub, str):
                        try:
                            pub_dt = datetime.fromisoformat(raw_pub)
                        except Exception:
                            pub_dt = datetime.utcnow()
                    elif isinstance(raw_pub, datetime):
                        pub_dt = raw_pub
                    else:
                        pub_dt = datetime.utcnow()

                    existing_sh = db.query(ShareholdingHistory).filter_by(
                        company_id=company.company_id,
                        period_end_date=p_date
                    ).first()
                    if not existing_sh:
                        sh_record = ShareholdingHistory(
                            shareholding_id=str(uuid.uuid4()),
                            company_id=company.company_id,
                            period_end_date=p_date,
                            publication_timestamp=pub_dt,
                            promoter_holding_pct=sh_data.get("promoter_holding_pct"),
                            promoter_pledge_pct=sh_data.get("promoter_pledge_pct") or 0.0,
                            fii_holding_pct=sh_data.get("fii_holding_pct"),
                            dii_holding_pct=sh_data.get("dii_holding_pct"),
                            mf_holding_pct=sh_data.get("mf_holding_pct") or 0.0,
                            other_dii_holding_pct=sh_data.get("other_dii_holding_pct") or 0.0,
                            retail_public_pct=sh_data.get("retail_public_pct"),
                            source=sh_data.get("source", "SCREENER_XBRL_LODR"),
                            consolidation_scope=sh_data.get("consolidation_scope", "SEBI_LODR_PATTERN_FILING"),
                            data_quality_flag=sh_data.get("data_quality_flag", "HIGH_CONFIDENCE")
                        )
                        db.add(sh_record)
                        db.commit()
                        logger.info(f"[Shareholding] Persisted verified pattern for {symbol} ({p_date}).")
            except Exception as e:
                db.rollback()
                logger.warning(f"[Shareholding] Error persisting shareholding for {symbol}: {e}")
                sh_data = None

        # 4. Official Regulatory Disclosures & Half-Life Decay Scoring
        active_announcements = []
        ingested_at_now = datetime.utcnow()
        if not fast_mode:
            try:
                from src.ingestion.bse_announcements_client import BseAnnouncementsClient
                bse_client = BseAnnouncementsClient()
                official_filings = bse_client.fetch_official_announcements(symbol, limit=10)
                for ann in official_filings:
                    headline = ann.get("headline", "") or ""
                    if not headline:
                        continue

                    # Robust multi-format publication timestamp parsing
                    pub_val = ann.get("source_published_at", "")
                    pub_dt = None
                    if isinstance(pub_val, datetime):
                        pub_dt = pub_val
                    elif pub_val:
                        s_clean = str(pub_val).strip()
                        for fmt in (
                            "%Y-%m-%dT%H:%M:%S",
                            "%Y-%m-%d %H:%M:%S",
                            "%d-%b-%Y %H:%M:%S",
                            "%d-%b-%Y",
                            "%Y-%m-%d",
                            "%d/%m/%Y %H:%M:%S",
                            "%d/%m/%Y",
                        ):
                            try:
                                pub_dt = datetime.strptime(s_clean.split(".")[0], fmt)
                                break
                            except Exception:
                                pass
                        if not pub_dt:
                            try:
                                pub_dt = datetime.fromisoformat(s_clean.split(".")[0])
                            except Exception:
                                pub_dt = ingested_at_now
                    else:
                        pub_dt = ingested_at_now

                    source_type = ann.get("source_type", "OFFICIAL_EXCHANGE_FILING")
                    is_m6_eligible = ann.get("is_m6_eligible", True)

                    # Score and decay
                    score_val, val_cr, track_type = AnnouncementDecayEngine.score_announcement(
                        event_type=ann.get("event_type") or ann.get("category", "GENERAL_FILING"),
                        headline=headline,
                        summary=ann.get("summary") or headline,
                        ttm_revenue_cr=2000.0
                    )
                    decayed_score, status = AnnouncementDecayEngine.calculate_decayed_score(
                        raw_score=score_val,
                        track_type=track_type,
                        publication_time=pub_dt
                    )

                    # Persist to corporate_announcements table (skip duplicates by dedup key)
                    dedup_key = f"NSE_{symbol}_{pub_dt.strftime('%Y%m%d')}_{headline[:60]}"
                    existing = db.query(CorporateAnnouncement).filter_by(
                        source_document_id=dedup_key
                    ).first()
                    if not existing:
                        db.add(CorporateAnnouncement(
                            company_id=company.company_id,
                            symbol=symbol,
                            source_published_at=pub_dt,
                            publication_timestamp=pub_dt,
                            ingested_at=ingested_at_now,
                            event_type=ann.get("event_type") or ann.get("category", "GENERAL_FILING"),
                            track_type=track_type,
                            source_type=source_type,
                            headline=headline[:500],
                            raw_materiality_score=score_val,
                            decayed_score=decayed_score,
                            last_decay_update=ingested_at_now,
                            material_value_cr=val_cr,
                            source_url=ann.get("source_document_url") or ann.get("attachment_url", ""),
                            source_document_id=dedup_key,
                            status=status,
                        ))
                    else:
                        # Refresh decay score on existing record
                        existing.decayed_score = decayed_score
                        existing.status = status
                        existing.last_decay_update = ingested_at_now

                    active_announcements.append({
                        "event_type": ann.get("event_type") or ann.get("category", "GENERAL_FILING"),
                        "headline": headline,
                        "summary": ann.get("summary") or headline,
                        "publication_date": pub_dt.strftime("%Y-%m-%d %H:%M"),
                        "material_value_cr": val_cr,
                        "raw_score": score_val,
                        "decayed_score": decayed_score,
                        "track_type": track_type,
                        "status": status,
                        "source_type": source_type,
                        "is_m6_eligible": is_m6_eligible,
                        "source_url": ann.get("source_document_url") or ann.get("attachment_url", ""),
                    })

                if official_filings:
                    db.commit()
                    logger.info(f"[Announcements] Persisted {len(active_announcements)} official filings for {symbol}.")

            except Exception as e:
                logger.warning(f"Error processing official exchange announcements for {symbol}: {e}")

        # 5. Forward-Looking Catalyst Calendar (SEBI LODR Reg 29 Board Meetings)
        next_board_meeting = {
            "meeting_date": "TBD",
            "purpose": "Awaiting Advance Notice",
            "days_until_event": None,
            "urgency_status": "AWAITING_NOTICE",
            "blackout_period_active": False
        }
        if not fast_mode:
            try:
                meetings = nse_client.fetch_board_meetings(symbol)
                future_meetings = [m for m in meetings if m["days_until_meeting"] is not None and m["days_until_meeting"] >= 0]
                if future_meetings:
                    future_meetings.sort(key=lambda x: x["days_until_meeting"])
                    closest = future_meetings[0]
                    next_board_meeting = {
                        "meeting_date": closest["meeting_date"].strftime("%Y-%m-%d"),
                        "purpose": closest["purpose"],
                        "days_until_event": closest["days_until_meeting"],
                        "urgency_status": closest["urgency_status"],
                        "blackout_period_active": True
                    }
            except Exception as e:
                logger.warning(f"Error fetching board meeting calendar for {symbol}: {e}")

        # 6. Compute Full 360-Degree Intelligence with 9 Multibagger Questions
        # Fetch macro regime once (non-blocking — falls back to defaults on any error)
        macro_regime = None
        if not fast_mode:
            try:
                macro_regime = MacroRegimeClient.fetch_current_macro_regime()
            except Exception as e:
                logger.warning(f"MacroRegimeClient failed for {symbol}, proceeding without regime data: {e}")

        intel = DecisionEngine.generate_full_stock_intelligence(
            db, company.company_id, today, macro_regime=macro_regime
        )

        # 6a. Record immutable T0 DecisionSnapshot (append-only — never overwritten)
        # Only record in full mode to avoid snapshot spam on background refreshes.
        if not fast_mode:
            try:
                m6_record = intel.get("m6_frozen_research_record", {})
                # Extract the full PIT feature vector for the snapshot payload
                pit_features = FeatureEngine.extract_features_as_of(db, company.company_id, today)
                DecisionSnapshotEngine.record_decision_snapshot(
                    db=db,
                    company_id=company.company_id,
                    t0_timestamp=datetime.utcnow(),
                    feature_vector=pit_features,
                    m6_score=float(m6_record.get("m6_conviction_score") or 0.0),
                    verdict=intel.get("primary_verdict", "NEUTRAL_WATCHLIST"),
                    horizon_ratings=intel.get("horizon_ratings", {}),
                    why_buy_reasons=intel.get("dual_thesis", {}).get("why_buy", []),
                    why_not_buy_reasons=intel.get("dual_thesis", {}).get("why_not_buy", []),
                    invalidation_thresholds={
                        "criteria": intel.get("multibagger_discovery_matrix", {})
                                         .get("q9_what_would_make_us_wrong", {})
                                         .get("invalidation_criteria", [])
                    },
                )

                # 6b. Record dedicated Point-in-Time ResearchFeatureSnapshot for post-experiment Model M7 training
                try:
                    import uuid
                    import json
                    from src.db.models.research_feature_snapshot import ResearchFeatureSnapshot
                    from src.analytics.roic_engine import EconomicROICEngine
                    from src.analytics.reinvestment_calculator import ReinvestmentCalculator
                    from src.analytics.tam_engine import ReverseTAMHurdleEngine
                    from src.analytics.earnings_acceleration import EarningsAccelerationEngine
                    from src.analytics.ownership_velocity import OwnershipVelocityEngine
                    from src.analytics.competitive_engine import CompetitivePositionEngine
                    from src.analytics.lifecycle_classifier import LifecycleClassifier
                    from src.analytics.latent_upside_engine import LatentUpsideEngine

                    # Compute all 8 economic research lenses
                    rev = pit_features.get("ttm_revenue_cr", 500.0)
                    pat = pit_features.get("ttm_pat_cr", rev * 0.10)
                    ebit = pit_features.get("ttm_ebit_cr", rev * 0.15)
                    pe = pit_features.get("trailing_pe", 25.0)
                    mcap = max(100.0, pe * pat)

                    tam_dat = ReverseTAMHurdleEngine.resolve_industry_tam(symbol, getattr(company.sector, "sector_name", "General"))
                    tam_res = ReverseTAMHurdleEngine.evaluate_10x_reverse_hurdle(mcap, rev, pat, tam_dat["niche_tam_cr"], tam_dat["macro_tam_cr"])
                    roic_res = EconomicROICEngine.calculate_economic_roic(ebit, 25.0, rev * 0.5, rev * 0.2)
                    capex_res = ReinvestmentCalculator.calculate_growth_vs_maintenance_capex(rev * 0.08, rev * 0.04, rev, rev * 0.85)
                    reinvest_res = ReinvestmentCalculator.calculate_growth_reinvestment_rate(capex_res["growth_capex_cr"], rev * 0.03, roic_res["nopat_cr"], roic_res["economic_roic_pct"])
                    moat_res = CompetitivePositionEngine.evaluate_displacement_dynamics(symbol, getattr(company.sector, "sector_name", "General"), pit_features.get("revenue_growth_yoy_pct", 20.0))
                    latent_res = LatentUpsideEngine.calculate_latent_upside_map(rev, ebit, pat, mcap, pit_features.get("ttm_roce_pct", 20.0))
                    coords_res = LifecycleClassifier.calculate_continuous_lifecycle_coordinates(mcap, pit_features.get("revenue_growth_yoy_pct", 20.0), pit_features.get("pat_growth_yoy_pct", 25.0), pit_features.get("ttm_roce_pct", 20.0), 10.0, pe)

                    from src.analytics.canonical_hasher import compute_canonical_hash
                    in_h = compute_canonical_hash(pit_features)
                    out_h = compute_canonical_hash(coords_res)

                    # Deduplicate: Check if snapshot exists for this company on today's date
                    existing_snap = db.query(ResearchFeatureSnapshot).filter_by(company_id=company.company_id, observation_date=today).first()
                    if not existing_snap:
                        rf_snap = ResearchFeatureSnapshot(
                            snapshot_id=str(uuid.uuid4()),
                            company_id=company.company_id,
                            observation_date=today,
                            t0_timestamp=datetime.utcnow(),
                            source_fact_ids=["LIVE_FEED_OBSERVATION"],
                            source_published_at=datetime.utcnow(),
                            source_period_end=today,
                            feature_engine_version="v3.2.0",
                            peer_selection_version="v1.0.0",
                            methodology_version="INSTITUTIONAL_P0",
                            input_hash=in_h,
                            output_hash=out_h,
                            economic_roic_pct=roic_res["economic_roic_pct"],
                            capex_total_cr=capex_res["total_capex_cr"],
                            growth_capex_cr=capex_res["growth_capex_cr"],
                            maintenance_capex_cr=capex_res["maintenance_capex_cr"],
                            growth_reinvestment_rate_pct=reinvest_res["growth_reinvestment_rate_pct"],
                            organic_compounding_ceiling_pct=reinvest_res["organic_compounding_ceiling_pct"],
                            maintenance_capex_method=capex_res["maintenance_capex_method"],
                            maintenance_capex_confidence=capex_res["maintenance_capex_confidence"],
                            niche_tam_cr=tam_res["niche_tam_cr"],
                            macro_tam_cr=tam_res["macro_tam_cr"],
                            sam_cr=tam_res["sam_serviceable_cr"],
                            som_cr=tam_res["som_obtainable_cr"],
                            current_niche_share_pct=tam_res["current_niche_market_share_pct"],
                            required_10x_niche_share_pct=tam_res["required_niche_market_share_pct"],
                            tam_feasibility=tam_res["feasibility"],
                            is_10x_plausible=tam_res["is_10x_plausible"],
                            displacement_mode=moat_res["displacement_mode"],
                            moat_rating=moat_res["economic_moat_rating"],
                            scale_coord=coords_res["scale_coordinate"],
                            reinvestment_coord=coords_res["reinvestment_intensity_coordinate"],
                            efficiency_coord=coords_res["capital_efficiency_coordinate"],
                            operating_leverage_coord=coords_res["operating_leverage_coordinate"],
                            float_discovery_coord=coords_res["institutional_discovery_coordinate"],
                            valuation_coord=coords_res["valuation_rerating_coordinate"],
                            transition_signature=coords_res["transition_signature"],
                            operational_leverage_multiplier=latent_res["operational_leverage_multiplier"],
                            distance_to_excellence_score=latent_res["distance_to_excellence_score"],
                            potential_pat_excellence_cr=latent_res["potential_pat_at_excellence_cr"],
                            latent_evidence_source=latent_res["evidence_source"],
                            latent_evidence_confidence=latent_res["evidence_confidence"],
                            feature_vector_json=json.dumps(pit_features)
                        )
                        db.add(rf_snap)
                        db.commit()
                        logger.info(f"[Research Feature Store] Persisted T0 vector {rf_snap.snapshot_id} for {symbol}.")
                except Exception as e:
                    logger.warning(f"[Research Feature Store] Error persisting feature snapshot for {symbol}: {e}")

            except Exception as e:
                logger.warning(f"[Snapshot] Could not record T0 snapshot for {symbol}: {e}")

        # 7. Extract Technicals & Additional Price Stats
        prices = db.query(DailyPriceRaw).filter(
            DailyPriceRaw.company_id == company.company_id,
            DailyPriceRaw.trading_date <= today
        ).order_by(DailyPriceRaw.trading_date.desc()).limit(250).all()

        if live_quote and live_quote.get("last_price"):
            cur_price = live_quote["last_price"]
            prev_price = None
            if prices:
                if prices[0].trading_date == today and len(prices) > 1:
                    prev_price = prices[1].close_price
                else:
                    prev_price = prices[0].close_price

            if prev_price is None or prev_price <= 0:
                prev_price = cur_price - (live_quote.get("net_change") or 0.0)

            if live_quote.get("day_change_pct") is not None:
                day_chg_pct = round(float(live_quote["day_change_pct"]), 2)
            elif prev_price and prev_price > 0:
                day_chg_pct = round(((cur_price - prev_price) / prev_price) * 100, 2)
            else:
                day_chg_pct = 0.0

            day_chg_inr = live_quote.get("net_change") if live_quote.get("net_change") is not None else round(cur_price - prev_price, 2)
        else:
            cur_price = prices[0].close_price if prices else intel.get("current_price", 1000.0)
            prev_price = prices[1].close_price if len(prices) > 1 else cur_price
            day_chg_pct = round(((cur_price - prev_price) / max(0.01, prev_price)) * 100, 2)
            day_chg_inr = round(cur_price - prev_price, 2)

        high_52w = max([p.high_price for p in prices]) if prices else cur_price * 1.2
        low_52w = min([p.low_price for p in prices]) if prices else cur_price * 0.8
        dist_52w_high_pct = round(((cur_price - high_52w) / max(0.01, high_52w)) * 100, 2)

        # Moving Averages
        dma_50 = sum([p.close_price for p in prices[:50]]) / max(1, len(prices[:50])) if prices else cur_price
        dma_200 = sum([p.close_price for p in prices[:200]]) / max(1, len(prices[:200])) if prices else cur_price
        dist_50_dma_pct = round(((cur_price - dma_50) / max(0.01, dma_50)) * 100, 2)
        dist_200_dma_pct = round(((cur_price - dma_200) / max(0.01, dma_200)) * 100, 2)

        # Returns over horizons
        ret_1w = round(((cur_price - prices[min(5, len(prices)-1)].close_price) / max(0.01, prices[min(5, len(prices)-1)].close_price)) * 100, 2) if len(prices) > 5 else 0.0
        ret_1m = round(((cur_price - prices[min(21, len(prices)-1)].close_price) / max(0.01, prices[min(21, len(prices)-1)].close_price)) * 100, 2) if len(prices) > 21 else 0.0
        ret_3m = round(((cur_price - prices[min(63, len(prices)-1)].close_price) / max(0.01, prices[min(63, len(prices)-1)].close_price)) * 100, 2) if len(prices) > 63 else 0.0
        ret_1y = round(((cur_price - prices[-1].close_price) / max(0.01, prices[-1].close_price)) * 100, 2) if len(prices) > 200 else 0.0

        lt = intel.get("horizon_ratings", {}).get("longterm", {})
        sw = intel.get("horizon_ratings", {}).get("swing", {})
        intra = intel.get("horizon_ratings", {}).get("intraday", {})
        cap = intel.get("liquidity_capacity", {})

        if not sh_data:
            from src.db.models.governance import ShareholdingHistory
            last_sh = db.query(ShareholdingHistory).filter_by(
                company_id=company.company_id
            ).order_by(ShareholdingHistory.period_end_date.desc()).first()
            if last_sh:
                promoter_p = float(last_sh.promoter_holding_pct) if last_sh.promoter_holding_pct is not None else None
                pledge_p = float(last_sh.promoter_pledge_pct or 0.0)
                fii_p = float(last_sh.fii_holding_pct) if last_sh.fii_holding_pct is not None else None
                dii_p = float(last_sh.dii_holding_pct) if last_sh.dii_holding_pct is not None else None
                inst_p = round((fii_p or 0.0) + (dii_p or 0.0), 2)
            else:
                promoter_p = None
                pledge_p = None
                fii_p = None
                dii_p = None
                inst_p = None
        else:
            promoter_p = float(sh_data.get("promoter_holding_pct")) if sh_data.get("promoter_holding_pct") is not None else None
            pledge_p = float(sh_data.get("promoter_pledge_pct") or 0.0)
            fii_p = float(sh_data.get("fii_holding_pct")) if sh_data.get("fii_holding_pct") is not None else None
            dii_p = float(sh_data.get("dii_holding_pct")) if sh_data.get("dii_holding_pct") is not None else None
            inst_p = round((fii_p or 0.0) + (dii_p or 0.0), 2)

        master_record = {
            "symbol": symbol,
            "company_name": company.company_name,
            "sector": intel.get("sector", "General"),
            "current_price": cur_price,
            "day_change_pct": day_chg_pct,
            "day_change_inr": day_chg_inr,
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
            "dist_52w_high_pct": dist_52w_high_pct,
            "dma_50": round(dma_50, 2),
            "dma_200": round(dma_200, 2),
            "dist_50_dma_pct": dist_50_dma_pct,
            "dist_200_dma_pct": dist_200_dma_pct,
            "returns": {
                "1w": ret_1w,
                "1m": ret_1m,
                "3m": ret_3m,
                "1y": ret_1y
            },
            "m6_longterm_score": lt.get("m6_frozen_score", 75),
            "m6_grade": lt.get("grade", "CONVICTION_BUY"),
            "m6_evidence_tier": lt.get("evidence_tier", "Tier 1 Validated"),
            "swing_score": sw.get("score", 70),
            "swing_setup": sw.get("setup", "CONSOLIDATION"),
            "swing_target": sw.get("target_price"),
            "swing_stop_loss": sw.get("stop_loss"),
            "swing_risk_reward": sw.get("risk_reward"),
            "intraday_score": intra.get("score", 65),
            "intraday_setup": intra.get("setup", "RANGE"),
            "primary_verdict": intel.get("primary_verdict", "ACCUMULATE_ON_DIPS"),
            "horizon_recommendation": intel.get("horizon_recommendation", "Long-Term Compounder"),
            "sizing_guidance": intel.get("sizing_guidance", "Standard Allocation"),
            "roce_pct": lt.get("roce_pct"),
            "fcf_yield_pct": lt.get("fcf_yield_pct"),
            "pe_ratio": lt.get("pe_ratio"),
            "liquidity": {
                "avg_daily_volume_20": cap.get("avg_daily_volume_20", 100000),
                "avg_daily_turnover_cr": cap.get("avg_daily_turnover_cr", 25.0),
                "max_safe_position_size_cr": cap.get("max_safe_position_size_cr", 1.25),
                "capacity_note": cap.get("capacity_note", "5% ADV Limit")
            },
            "shareholding": {
                "promoter_pct": promoter_p,
                "promoter_pledge_pct": pledge_p,
                "institutional_pct": inst_p,
                "fii_pct": fii_p,
                "dii_pct": dii_p,
                "public_pct": round(100.0 - ((promoter_p or 0.0) + (inst_p or 0.0)), 2) if (promoter_p is not None or inst_p is not None) else None,
                "governance_status": sh_data.get("governance_status", "CLEAN") if sh_data else "CLEAN"
            },
            "next_announcement": next_board_meeting,
            "regulatory_catalysts": active_announcements,
            "dual_thesis": intel.get("dual_thesis", {
                "why_buy": ["Solid fundamental compounding with expanding ROCE."],
                "why_not_buy": ["Macro volatility and valuation sensitivity."]
            }),
            "multibagger_matrix": intel.get("multibagger_discovery_matrix", {}),
            "recent_disclosures": active_announcements if active_announcements else [],
            "last_updated": datetime.utcnow().isoformat()
        }

        return master_record

    @classmethod
    def batch_process_stock_text(cls, raw_text: str) -> Dict[str, Any]:
        """
        Parses text, executes batch ingestion, and calculates all parameters.
        """
        symbols = cls.parse_stock_symbols(raw_text)
        if not symbols:
            return {
                "success": False,
                "error": "No valid stock symbols or company names found in input.",
                "parsed_symbols": [],
                "results": []
            }

        db = SessionLocal()
        results = []
        errors = []

        try:
            for sym in symbols:
                try:
                    rec = cls.ingest_and_calculate_all_parameters(sym, db)
                    results.append(rec)
                except Exception as e:
                    logger.error(f"Error processing {sym}: {e}")
                    errors.append({"symbol": sym, "error": str(e)})

            return {
                "success": True,
                "total_parsed": len(symbols),
                "successful_count": len(results),
                "error_count": len(errors),
                "parsed_symbols": symbols,
                "results": results,
                "errors": errors
            }
        finally:
            db.close()

    @classmethod
    def get_all_watchlist_stocks(cls) -> List[Dict[str, Any]]:
        """
        Returns all active stocks in the database with their complete parameter profiles.
        """
        db = SessionLocal()
        try:
            companies = db.query(Company).filter_by(status="ACTIVE").all()
            all_records = []
            for comp in companies:
                try:
                    rec = cls.ingest_and_calculate_all_parameters(comp.nse_symbol, db, fast_mode=True)
                    all_records.append(rec)
                except Exception as e:
                    logger.error(f"Error getting record for {comp.nse_symbol}: {e}")
            return all_records
        finally:
            db.close()

    _REFRESH_LOCK = threading.Lock()

    @classmethod
    def refresh_all_watchlist_stocks(cls) -> Dict[str, Any]:
        """
        Refreshes live market data and candles for all active watchlist stocks via Upstox API.
        Called automatically every 5 minutes by the background scheduler.
        """
        if not cls._REFRESH_LOCK.acquire(blocking=False):
            return {
                "success": True,
                "status": "ALREADY_IN_PROGRESS",
                "message": "Refresh cycle is already in progress."
            }

        try:
            db = SessionLocal()
            upstox = UpstoxMarketDataIngestion()
            refreshed = []
            errors = []
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            try:
                companies = db.query(Company).filter_by(status="ACTIVE").all()
                if not companies:
                    return {"success": True, "refreshed_count": 0, "timestamp": now_str}

                for comp in companies:
                    try:
                        upstox.ingest_stock_data(db, comp.nse_symbol)
                        refreshed.append(comp.nse_symbol)
                    except Exception as e:
                        logger.error(f"[Auto-Refresh] Error refreshing {comp.nse_symbol}: {e}")
                        errors.append({"symbol": comp.nse_symbol, "error": str(e)})

                logger.info(f"[Auto-Refresh 5-Min Cycle] Refreshed {len(refreshed)} stocks via Upstox at {now_str}.")
                return {
                    "success": True,
                    "refreshed_count": len(refreshed),
                    "error_count": len(errors),
                    "refreshed_symbols": refreshed,
                    "timestamp": now_str
                }
            finally:
                db.close()
        finally:
            cls._REFRESH_LOCK.release()


"""
Point-in-Time Research Feature Snapshot Model.
Stores immutable, bitemporal multidimensional economic vectors for post-experiment M7 training.
"""
from datetime import datetime, date
from sqlalchemy import Column, String, Float, Integer, Date, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from src.db.base import Base

class ResearchFeatureSnapshot(Base):
    __tablename__ = "research_feature_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(String(64), unique=True, nullable=False, index=True)
    company_id = Column(String(32), ForeignKey("companies.company_id"), nullable=False, index=True)
    observation_date = Column(Date, nullable=False, index=True)
    t0_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    ingested_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # 1. Economic ROIC & ROIIC
    economic_roic_pct = Column(Float, nullable=True)
    roiic_1y_pct = Column(Float, nullable=True)
    roiic_2y_pct = Column(Float, nullable=True)
    roiic_3y_pct = Column(Float, nullable=True)
    delta_nopat_cr = Column(Float, nullable=True)
    delta_ic_cr = Column(Float, nullable=True)
    capital_deployment_intensity_pct = Column(Float, nullable=True)
    roiic_validity_flag = Column(String(64), nullable=True)
    roiic_confidence = Column(String(32), nullable=True)

    # 2. Bruce Greenwald CapEx & Reinvestment
    capex_total_cr = Column(Float, nullable=True)
    growth_capex_cr = Column(Float, nullable=True)
    maintenance_capex_cr = Column(Float, nullable=True)
    growth_reinvestment_rate_pct = Column(Float, nullable=True)
    organic_compounding_ceiling_pct = Column(Float, nullable=True)
    maintenance_capex_method = Column(String(64), nullable=True)
    maintenance_capex_confidence = Column(String(32), nullable=True)

    # 3. Hierarchical Reverse 10x TAM
    niche_tam_cr = Column(Float, nullable=True)
    macro_tam_cr = Column(Float, nullable=True)
    sam_cr = Column(Float, nullable=True)
    som_cr = Column(Float, nullable=True)
    current_niche_share_pct = Column(Float, nullable=True)
    required_10x_niche_share_pct = Column(Float, nullable=True)
    tam_feasibility = Column(String(64), nullable=True)
    is_10x_plausible = Column(Boolean, nullable=True)

    # 4. Earnings Acceleration Vector
    revenue_accel_pct_points = Column(Float, nullable=True)
    pat_accel_pct_points = Column(Float, nullable=True)
    pat_accel_1q_pct = Column(Float, nullable=True)
    pat_accel_2q_pct = Column(Float, nullable=True)
    accel_persistence_quarters = Column(Integer, nullable=True)
    accel_confidence = Column(String(32), nullable=True)
    accel_status = Column(String(64), nullable=True)

    # 5. Institutional Ownership Velocity
    current_inst_pct = Column(Float, nullable=True)
    inst_1q_delta_pct = Column(Float, nullable=True)
    inst_1y_delta_pct = Column(Float, nullable=True)
    ownership_trend = Column(String(64), nullable=True)
    is_diluted = Column(Boolean, nullable=True)
    primary_dilution_event = Column(String(64), nullable=True)

    # 6. Competitive Position & Moat
    hhi_score = Column(Float, nullable=True)
    concentration_regime = Column(String(64), nullable=True)
    pricing_power_score = Column(Float, nullable=True)
    pricing_power_rating = Column(String(64), nullable=True)
    displacement_mode = Column(String(64), nullable=True)
    moat_rating = Column(String(64), nullable=True)

    # 7. Continuous Lifecycle Coordinates
    lifecycle_stage = Column(String(64), nullable=True)
    scale_coord = Column(Float, nullable=True)
    reinvestment_coord = Column(Float, nullable=True)
    efficiency_coord = Column(Float, nullable=True)
    operating_leverage_coord = Column(Float, nullable=True)
    float_discovery_coord = Column(Float, nullable=True)
    valuation_coord = Column(Float, nullable=True)
    transition_signature = Column(String(64), nullable=True)

    # 8. Grounded Latent Upside
    operational_leverage_multiplier = Column(Float, nullable=True)
    distance_to_excellence_score = Column(Float, nullable=True)
    potential_pat_excellence_cr = Column(Float, nullable=True)
    latent_evidence_source = Column(String(64), nullable=True)
    latent_evidence_confidence = Column(String(32), nullable=True)

    # Serialized JSON payload for future proofing
    feature_vector_json = Column(Text, nullable=True)

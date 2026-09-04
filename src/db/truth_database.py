"""
Immutable Truth Database Engine (Protocol Layer 4).

Logs every pre-trade prediction state before outcome realization, and records
post-trade realized outcomes (slippage, taxes, MFE, MAE, implementation shortfall)
without ever modifying or overwriting the original prediction record.
"""

import uuid
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship, Session
from src.db.base import Base, engine, SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PredictionRecord(Base):
    """
    Immutable Pre-Trade Prediction Log (Logged at Timestamp T0).
    """
    __tablename__ = "truth_predictions"

    prediction_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    symbol = Column(String(32), nullable=False, index=True)
    engine_type = Column(String(32), nullable=False, index=True) # LONGTERM_M6, SWING, INTRADAY
    model_score = Column(Integer, nullable=False)
    evidence_tier = Column(String(64), nullable=False)
    arrival_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    expected_risk_reward = Column(String(32), nullable=True)
    data_quality_score = Column(Integer, nullable=False, default=100)
    model_code_hash = Column(String(64), nullable=False)
    input_snapshot_hash = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="PENDING") # PENDING, RESOLVED, CANCELLED

    outcome = relationship("OutcomeRecord", back_populates="prediction", uselist=False)


class OutcomeRecord(Base):
    """
    Post-Trade Realized Outcome Log (Appended at Timestamp T1).
    """
    __tablename__ = "truth_outcomes"

    outcome_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    prediction_id = Column(String(64), ForeignKey("truth_predictions.prediction_id"), nullable=False, unique=True)
    resolved_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    actual_exit_price = Column(Float, nullable=False)
    executed_entry_price = Column(Float, nullable=False)
    executed_exit_price = Column(Float, nullable=False)
    max_favorable_excursion_pct = Column(Float, nullable=True)
    max_adverse_excursion_pct = Column(Float, nullable=True)
    hit_target = Column(Boolean, nullable=False, default=False)
    hit_stop = Column(Boolean, nullable=False, default=False)
    holding_period_days = Column(Integer, nullable=False, default=1)
    slippage_cost_inr = Column(Float, nullable=False, default=0.0)
    statutory_taxes_inr = Column(Float, nullable=False, default=0.0)
    realized_net_pnl_inr = Column(Float, nullable=False, default=0.0)
    realized_net_return_pct = Column(Float, nullable=False, default=0.0)
    implementation_shortfall_inr = Column(Float, nullable=False, default=0.0)

    prediction = relationship("PredictionRecord", back_populates="outcome")


def init_truth_db(target_engine=None):
    """Initializes truth database tables on the specified engine or default engine."""
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)


class TruthDatabaseManager:
    """
    Manager interface for immutable prediction logging and outcome reconciliation.
    """

    @staticmethod
    def record_pre_trade_prediction(
        db: Session,
        symbol: str,
        engine_type: str,
        model_score: int,
        evidence_tier: str,
        arrival_price: float,
        stop_loss: Optional[float],
        target_price: Optional[float],
        expected_risk_reward: Optional[str],
        data_quality_score: int,
        model_code_hash: str,
        input_snapshot_hash: str
    ) -> PredictionRecord:
        """
        Records an immutable pre-trade prediction state into the Truth Database.
        """
        pred = PredictionRecord(
            prediction_id=str(uuid.uuid4()),
            created_at=datetime.utcnow(),
            symbol=symbol.upper(),
            engine_type=engine_type.upper(),
            model_score=model_score,
            evidence_tier=evidence_tier,
            arrival_price=arrival_price,
            stop_loss=stop_loss,
            target_price=target_price,
            expected_risk_reward=expected_risk_reward,
            data_quality_score=data_quality_score,
            model_code_hash=model_code_hash,
            input_snapshot_hash=input_snapshot_hash,
            status="PENDING"
        )
        db.add(pred)
        db.commit()
        db.refresh(pred)
        return pred

    @staticmethod
    def record_realized_outcome(
        db: Session,
        prediction_id: str,
        actual_exit_price: float,
        executed_entry_price: float,
        executed_exit_price: float,
        hit_target: bool,
        hit_stop: bool,
        holding_period_days: int,
        slippage_cost_inr: float,
        statutory_taxes_inr: float,
        realized_net_pnl_inr: float,
        realized_net_return_pct: float,
        implementation_shortfall_inr: float,
        max_favorable_excursion_pct: Optional[float] = None,
        max_adverse_excursion_pct: Optional[float] = None
    ) -> OutcomeRecord:
        """
        Reconciles a realized outcome against an immutable prediction.
        """
        pred = db.query(PredictionRecord).filter_by(prediction_id=prediction_id).first()
        if not pred:
            raise ValueError(f"Prediction ID '{prediction_id}' not found in Truth Database")

        outcome = OutcomeRecord(
            outcome_id=str(uuid.uuid4()),
            prediction_id=prediction_id,
            resolved_at=datetime.utcnow(),
            actual_exit_price=actual_exit_price,
            executed_entry_price=executed_entry_price,
            executed_exit_price=executed_exit_price,
            max_favorable_excursion_pct=max_favorable_excursion_pct,
            max_adverse_excursion_pct=max_adverse_excursion_pct,
            hit_target=hit_target,
            hit_stop=hit_stop,
            holding_period_days=holding_period_days,
            slippage_cost_inr=slippage_cost_inr,
            statutory_taxes_inr=statutory_taxes_inr,
            realized_net_pnl_inr=realized_net_pnl_inr,
            realized_net_return_pct=realized_net_return_pct,
            implementation_shortfall_inr=implementation_shortfall_inr
        )
        pred.status = "RESOLVED"
        db.add(outcome)
        db.commit()
        db.refresh(outcome)
        return outcome

    @staticmethod
    def get_recent_truth_log(db: Session, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Returns recent predictions and their reconciled outcomes.
        """
        preds = db.query(PredictionRecord).order_by(PredictionRecord.created_at.desc()).limit(limit).all()
        results = []
        for p in preds:
            item = {
                "prediction_id": p.prediction_id,
                "timestamp": p.created_at.isoformat(),
                "symbol": p.symbol,
                "engine_type": p.engine_type,
                "model_score": p.model_score,
                "evidence_tier": p.evidence_tier,
                "arrival_price": p.arrival_price,
                "stop_loss": p.stop_loss,
                "target_price": p.target_price,
                "data_quality_score": p.data_quality_score,
                "model_code_hash": p.model_code_hash[:12] + "...",
                "status": p.status
            }
            if p.outcome:
                item["outcome"] = {
                    "resolved_at": p.outcome.resolved_at.isoformat(),
                    "actual_exit_price": p.outcome.actual_exit_price,
                    "realized_net_return_pct": p.outcome.realized_net_return_pct,
                    "hit_target": p.outcome.hit_target,
                    "hit_stop": p.outcome.hit_stop,
                    "implementation_shortfall_inr": p.outcome.implementation_shortfall_inr
                }
            results.append(item)
        return results

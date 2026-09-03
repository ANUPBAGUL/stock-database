# Quantitative Test Architecture & System Dependency Map
**Repository:** Stock Watchlist Hub — Institutional Quantitative Truth Laboratory  
**Subsystem:** P0 Truth & Temporal Integrity Infrastructure  
**Specification Level:** Institutional Empirical Research Standard  

---

## 1. System Component Map & Dependencies

```
                               ┌────────────────────────────────────────┐
                               │       EXTERNAL REGULATORY FEEDS        │
                               │ (BSE / NSE / SEBI LODR / Screener XBRL)│
                               └───────────────────┬────────────────────┘
                                                   │
                                                   ▼
                               ┌────────────────────────────────────────┐
                               │          INGESTION PIPELINES           │
                               │ (BitemporalIngest, Screener, Upstox)   │
                               └───────────────────┬────────────────────┘
                                                   │
                                                   ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                          POINT-IN-TIME STORE                                           │
│  • BitemporalFinancial (period_end_date, publication_date, superseded_at, is_restatement)              │
│  • DailyPriceRaw (trading_date, open, high, low, close, volume, price_source)                          │
│  • UniverseMembership (effective_from, effective_to, listing_status, tradability_status)               │
│  • ShareholdingHistory (period_end_date, filing_date, promoter_pct, fii_pct, dii_pct)                  │
│  • CorporateAnnouncement (announcement_date, broadcast_timestamp, category, sentiment)                │
└───────────────────────────────────┬───────────────────────────────────┬────────────────────────────────┘
                                    │                                   │
              Strict Temporal Filter│ (T_pub <= T0, TradingDate <= T0)  │ Strict Temporal Filter (T_event > T0)
                                    ▼                                   ▼
┌──────────────────────────────────────────────────────┐  ┌──────────────────────────────────────────────┐
│             PIT FEATURE ENGINE LAYER                 │  │          FORWARD OUTCOME ENGINE LAYER        │
│  • EconomicROICEngine (NOPAT, Invested Capital)      │  │  • WealthCompoundingEngine (W_{t+1})         │
│  • ReinvestmentCalculator (Greenwald CapEx)          │  │  • OutcomeLabeler (2x, 5x, 10x milestones)   │
│  • ReverseTAMHurdleEngine (10x Hurdle, SAM, SOM)     │  │  • TerminalRecoveryEngine (CIRP/Liquidation) │
│  • EarningsAccelerationEngine (Persistence)          │  │  • CompetingRiskClassifier (Censoring)       │
│  • CompetitivePositionEngine (HHI Bounds, Moat)      │  └──────────────────────┬───────────────────────┘
│  • LifecycleClassifier (6D Continuous Coordinates)   │                         │
│  • LatentUpsideEngine (Operational Leverage)         │                         │
└──────────────────────────┬───────────────────────────┘                         │
                           │                                                     │
                           ▼                                                     │
┌──────────────────────────────────────────────────────┐                         │
│           RESEARCH FEATURE SNAPSHOT STORE            │                         │
│  • ResearchFeatureSnapshot (Company x T0 Vector)     │                         │
│  • CanonicalHasher (Deterministic SHA-256 Digest)    │                         │
│  • Machine-Readable Provenance Audit Metadata        │                         │
└──────────────────────────┬───────────────────────────┘                         │
                           │                                                     │
                           └─────────────────────────┬───────────────────────────┘
                                                     │
                                                     ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   STATISTICAL VALIDATION & PARTITIONING                                │
│  • PurgedFoldSplitter (Half-Open Interval Overlap [label_start, label_end) across Fold Boundaries)     │
│  • OOSFirewall (M7_OOS_2026_V1 Locked Boundary, Right-Censoring & Mutation Firewall)                   │
│  • LongitudinalDatasetAuditor (10 Empirical Health & Scale Metrics)                                    │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Inventory & Audit Analysis

| Component | Responsibility | Inputs | Outputs | Temporal Dependencies | Database Dependencies | Existing Tests | Suspected Failure Modes / Hostile Risks |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`BitemporalFinancial`** | Audited financial facts with filing publication timestamp | Regulatory XBRL statements | Financial facts with bitemporal dates | `publication_date`, `period_end_date`, `superseded_at` | `bitemporal_financials` | `test_pit_truth_database.py` | Querying without `publication_date <= T0` using `period_end_date` alone introduces look-ahead leak. |
| **`UniverseMembership`** | Point-in-time constituent & survivorship registry | Historical index constituents & delistings | Historical universe state as of $T_0$ | `effective_from`, `effective_to` | `universe_memberships`, `companies` | `test_institutional_acceptance_invariants.py` | Off-by-one boundary errors (`<` vs `<=`); survivorship filtering omitting delisted bankruptcies. |
| **`CanonicalHasher`** | Bit-for-bit deterministic serialization & SHA-256 hashing | Any Python dictionary / primitive | Normalized string & SHA-256 hex | Timestamps normalized to ISO-8601 UTC | None (pure math/encoding) | `test_institutional_acceptance_invariants.py` | Float representation jitter beyond 6 decimal places; dict key ordering; NaN/Infinity edge cases. |
| **`WealthCompoundingEngine`** | Cumulative wealth path evolution ($W_{t+1}$) & terminal recovery | Price series, cash distributions, corporate proceeds, terminal event | `wealth_start`, `wealth_end`, `total_realized_wealth_return_pct` | Realization sequence ($t=0 \to T$) | `daily_prices_raw`, `corporate_actions` | `test_institutional_acceptance_invariants.py` | Double counting dividends; naive -100% loss hardcoding on bankruptcy; adjusted price double adjustments. |
| **`PurgedFoldSplitter`** | Generic half-open interval overlap $[start, end)$ label purging | Train/Test observation lists with `LabelInterval` | Purged train sets, disjoint folds | $[label\_start, label\_end)$ | `forward_outcomes` | `test_institutional_acceptance_invariants.py` | Closed interval $[start, end]$ vs half-open $[start, end)$ causing false purging of adjacent periods. |
| **`OOSFirewall`** | Partitioning and immutability enforcement for out-of-sample sets | Observation dates, horizon length | Partition (`DEVELOPMENT`, `VALIDATION`, `LOCKED_OOS`), censoring status | Split cutoffs ($2021-12-31$, $2023-12-31$) | `forward_outcomes`, `research_feature_snapshots` | `test_institutional_acceptance_invariants.py` | Converting immature right-censored outcomes into negative failures; accidental mutation of locked OOS records. |
| **`CompetitivePositionEngine`** | Herfindahl-Hirschman Index & moat bounds | Market shares of identified & unidentified players | $HHI$, $HHI_{\min}$, $HHI_{\max}$, Moat Rating | Observation period market shares | Sector mappings | `test_multibagger_deep_engines.py` | Invalid mathematical bounds if $N_{\text{unknown}} < 1$ or $\sum s_i > 1.0$. |
| **`ResearchFeatureSnapshot`** | Immutable $T_0$ economic feature vector store | 30+ economic primitives | Audited snapshot row with hash and provenance | $T_0$ observation timestamp | `research_feature_snapshots` | `test_200iq_research_pipeline.py` | Accidental relationship or foreign key referencing `ForwardOutcome` causing structural leak. |
| **`ForwardOutcome`** | Forward realization outcomes & event intervals | Future price runway, distributions | Forward return metrics, interval timestamps | $T_0 \to T_{\text{horizon}}$ | `forward_outcomes`, `decision_snapshots` | `test_200iq_research_pipeline.py` | Label leakage into feature snapshot payload; improper censoring classification. |

---

## 3. Critical Temporal & Database Firewalls

### Firewall 1: Bitemporal Query Invariant
```python
# MANDATORY TEMPORAL FILTER PATTERN
db.query(BitemporalFinancial).filter(
    BitemporalFinancial.company_id == comp_id,
    BitemporalFinancial.publication_date <= t0_datetime,
    (BitemporalFinancial.superseded_at.is_(None) | (BitemporalFinancial.superseded_at > t0_datetime))
)
```

### Firewall 2: Structural Schema Decoupling
```text
ResearchFeatureSnapshot (T0) <--- NO FOREIGN KEY / RELATIONSHIP ---> ForwardOutcome (T > T0)
```

### Firewall 3: Half-Open Interval Overlap Definition
```python
def overlaps(a: LabelInterval, b: LabelInterval) -> bool:
    return (a.label_start < b.label_end) and (b.label_start < a.label_end)
```

---

## 4. Verification & Testing Matrix

```
┌────────────────────────────────────────────────────────────────────────┐
│                        INSTITUTIONAL TEST SUITE                        │
├────────────────────────────────┬───────────────────────────────────────┤
│ Layer A: Unit Primitives       │ Math, HHI bounds, interval formulas   │
│ Layer B: Integration           │ Multi-component PIT dataflows         │
│ Layer C: Property (Hypothesis) │ Invariants over randomized input sets │
│ Layer D: Metamorphic Testing   │ Order independence & neutral mutations│
│ Layer E: Adversarial Leakage   │ Synthetic look-ahead poison injection │
│ Layer F: Economic Reconciliation│ Manual math vs engine wealth paths    │
│ Layer G: Survivorship Universe │ Delisted & active universe replay     │
│ Layer H: OOS Security Boundary │ Locked partitions & censoring rules   │
│ Layer I: Determinism & Provenance│ 100-run SHA-256 bit-for-bit parity  │
│ Layer J: Golden Dataset E2E    │ 15-company immutable reference cohort │
└────────────────────────────────┴───────────────────────────────────────┘
```

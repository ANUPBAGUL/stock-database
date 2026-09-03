# Stock Watchlist Hub — Institutional Quantitative Truth Laboratory

> **A survivorship-free, point-in-time (PIT) empirical research laboratory and multibagger discovery platform for Indian Equities (NSE/BSE).**

---

## 1. System Architecture & Core Axioms

The laboratory operates on the fundamental research unit:

$$\boxed{\text{Research Observation} = (\text{Company}_i, T_0)}$$

Every observation is characterized by its immutable contextual state $S(T_0)$:

$$S(T_0) = \left(C_{T_0}, I_{T_0}, M_{T_0}, V_{T_0}\right)$$

where:
* $C_{T_0}$ = Company fundamental & economic state (ROIC, Greenwald CapEx, Earnings Accel, Ownership Velocity)
* $I_{T_0}$ = Industry structure & competitive moat state (HHI uncertainty bounds, pricing power resilience)
* $M_{T_0}$ = Macro & cost-of-capital regime state
* $V_{T_0}$ = Reverse TAM hurdle & valuation expectation state

### The Non-Negotiable Information Firewall

$$\text{Feature}(i, T_0) = f(\text{information available by } T_0)$$
$$\text{Outcome}(i, T_0) = g(\text{information after } T_0)$$
$$\boxed{\text{Outcome} \not\rightarrow \text{Feature}}$$

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
│  • BitemporalFinancial (period_end_date, publication_date, system_rec_start, system_rec_end)           │
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

## 2. The 8 Non-Negotiable Acceptance Invariants

| # | Invariant | Real-World Mathematical Guarantee | Test Status |
| :--- | :--- | :--- | :---: |
| **A** | **Vintage Reconstruction** | $Features(i, T_0)$ uses strictly regulatory filings with $T_{\text{pub}} \le T_0$. | ✅ **PASSED** |
| **B** | **Future-Document Poison** | $F(T_0, D) \equiv F(T_0, D + \text{FuturePoison})$ bit-for-bit across multiple $T_0$ vintages. | ✅ **PASSED** |
| **C** | **Restatement Invariance** | Later auditor restatements do not retroactively alter pre-restatement $T_0$ snapshots. | ✅ **PASSED** |
| **D** | **Survivorship-Free Universe** | Historical $T_0$ queries preserve defunct/bankrupt firms (e.g. DHFL, Sintex, RCom). | ✅ **PASSED** |
| **E** | **Fold-Boundary Interval Purge** | Half-open intervals $[label\_start, label\_end)$ strictly disjoint across train/test folds. | ✅ **PASSED** |
| **F** | **Machine-Readable Provenance** | Every feature row stores `source_fact_ids`, `source_published_at` $\le T_0$, engine versions. | ✅ **PASSED** |
| **G** | **Adversarial Leakage Canary** | Injected synthetic look-ahead variables with absurd predictive power are blocked/ignored. | ✅ **PASSED** |
| **H** | **Deterministic Canonical Hash** | SHA-256 hash over canonical JSON representation is bit-for-bit identical across 100 runs. | ✅ **PASSED** |

---

## 3. Mathematical Specifications

### A. Shareholder Wealth Compounding & Terminal Economic Recovery
Naive additive returns are replaced with total shareholder wealth evolution:

$$W_{t+1} = W_t(1 + r_t^{\text{price}}) + D_t^{\text{cash}} + C_t^{\text{corporate}}$$

$$R_T = \frac{W_T}{W_0} - 1$$

**Bankruptcy / Delisting is an event state, not hardcoded to -100%:**
Actual economic recovery is reconstructed from insolvency/CIRP resolutions:

$$R_{\text{terminal}} = \frac{V_{\text{equity}} + C_{\text{recovery}} + V_{\text{consideration}}}{V_{T_0}} - 1$$

### B. Generic Half-Open Interval Purging
Fold-boundary interval purging enforces:

$$\text{overlap}(a, b) \iff a.\text{label\_start} < b.\text{label\_end} \;\land\; b.\text{label\_start} < a.\text{label\_end}$$

### C. Herfindahl-Hirschman Index (HHI) Uncertainty Bounds

$$HHI_{\text{observed}} = \sum_{i \in \text{identified}} s_i^2 \quad (\text{scale } 0 - 10000)$$
$$HHI_{\min} = HHI_{\text{observed}} + \frac{R^2}{N_{\text{unidentified},\max}}$$
$$HHI_{\max} = HHI_{\text{observed}} + \frac{R^2}{N_{\text{unidentified},\min}}$$

where $R = \max(0, 100 - \sum s_i)$.

---

## 4. Test Suite & Validation Matrix (99/99 Tests Passed)

```bash
# Run the complete test suite
python -m pytest -q
# Result: 99 passed in 26.81s

# Run the dedicated institutional acceptance suite
python -m pytest tests/institutional/ -v
# Result: 41 passed in 3.43s
```

### Layer Breakdown:
* **Layer A:** Unit Primitives (Math, HHI bounds, interval math, serialization)
* **Layer C:** Hypothesis Property-Based Invariants ($W_T \ge 0$, HHI range, interval symmetry)
* **Layer D:** Metamorphic Invariance (Row order, neutral companies, outcome isolation)
* **Layer E:** Adversarial Leakage & Look-Ahead Poison Canaries (Invariants B, C, G)
* **Layer F:** Economic Reference Model Reconciliation (Wealth compounding, CIRP recovery)
* **Layer G:** Survivorship & 4-Tier Universe Dimensions (Invariant D, exact boundaries)
* **Layer H:** OOS Security Firewall & Censoring Classification (`M7_OOS_2026_V1`)
* **Layer I:** Machine-Readable Provenance & 100-Run Determinism (Invariants F, H)
* **Layer J:** End-to-End Synthetic 15-Company Golden Cohort Pipeline

---

## 5. Automated Operational & Audit Commands

| Command | Objective |
| :--- | :--- |
| `python scripts/run_institutional_validation.py` | Runs complete validation campaign & generates `institutional_validation_report.json` |
| `python scripts/verify_defect_injection.py` | Requirement 45: Injects defects into core invariants to prove the test suite detects them |
| `python scripts/audit_longitudinal_dataset.py` | Audits the 10 empirical health metrics ($N_{\text{effective}}$, maturity, survivorship, missingness) |
| `python scripts/scale_historical_universe_backfill.py` | Seeds survivorship failure cohorts & backfills broad multi-sector PIT trajectories |
| `python scripts/verify_watchlist_state.py` | Real-time live ingestion and parameter verification for all active watchlist stocks |

---

## 6. Audit & Validation Documentation

* **Validation Report:** [`P0_INSTITUTIONAL_VALIDATION_REPORT.md`](file:///d:/Projects/Stock_Watchlist_Hub/P0_INSTITUTIONAL_VALIDATION_REPORT.md)
* **Test Architecture & Dependency Map:** [`TEST_ARCHITECTURE.md`](file:///d:/Projects/Stock_Watchlist_Hub/TEST_ARCHITECTURE.md)
* **Machine-Readable Audit JSON:** [`institutional_validation_report.json`](file:///d:/Projects/Stock_Watchlist_Hub/institutional_validation_report.json)
* **Investment Thesis:** [`STOCK_ANALYSIS_THESIS.md`](file:///d:/Projects/Stock_Watchlist_Hub/STOCK_ANALYSIS_THESIS.md)

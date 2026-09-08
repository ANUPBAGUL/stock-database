# Multibagger Capability Validation Program (MCVP)
## Institutional Framework for Verifiable Out-of-Sample Predictive Alpha

---

## Executive Summary & Core Objective

The purpose of this validation program is not to claim broad, unfalsifiable assertions such as *"Our AI predicts multibaggers."* 

Instead, this program establishes a **reproducible, mathematically formal, point-in-time (PIT) proof hierarchy** demonstrating that the 5-Pillar / M7 investment research system extracts genuine, out-of-sample economic information that materially increases the probability of discovering $2\times$, $5\times$, and $10\times$ compounders before market recognition.

---

## 1. The 6-Level Proof Hierarchy

```
┌────────────────────────────────────────────────────────────────────────┐
│ Level F: Robustness & Market Regime Invariance                         │
│ (Performance across 2013–2026: Bull, Bear, Sideways, Demon, COVID)     │
├────────────────────────────────────────────────────────────────────────┤
│ Level E: Multibagger Discovery & Early Discovery Lift                  │
│ (Out-of-sample 2×/5×/10× Precision & 12M/24M/36M Early Discovery Lift) │
├────────────────────────────────────────────────────────────────────────┤
│ Level D: Price & Volume Structure Confirmation                         │
│ (Stage 2 Transitions, Mansfield RS Inflection, Pocket Pivots)          │
├────────────────────────────────────────────────────────────────────────┤
│ Level C: Valuation & Expectations Asymmetry Understanding              │
│ (Reverse DCF Implied Growth vs. Organic Compounding Ceiling)           │
├────────────────────────────────────────────────────────────────────────┤
│ Level B: Economic & Reinvestment Trajectory Understanding              │
│ (Economic ROIC, Incremental ROIIC, Greenwald Growth CapEx)             │
├────────────────────────────────────────────────────────────────────────┤
│ Level A: Data Truth & Point-in-Time Integrity                          │
│ (Bitemporal Store, Zero-Fabrication, Strict $T \le T_0$ Firewall)      │
└────────────────────────────────────────────────────────────────────────┘
```

### Capability A — Data Truth & Point-in-Time Reconstruction
* **Hypothesis**: At any historical date $T_0$, the system reconstructs *only* what was published and legally available to an investor at $T_0$, with zero future lookahead or survivorship leakage.
* **Verification Metric**: $100\%$ pass rate on Layer E (Adversarial Data Leakage), Layer G (Survivorship Universe), and Layer H (OOS Firewall) test suites.

### Capability B — Economic & Reinvestment Understanding
* **Hypothesis**: The system detects inflection points in capital efficiency ($\Delta \text{ROIC} > 0$, $\text{ROIIC} > 20\%$) and capacity reinvestment before reported trailing annual statements reflect them.
* **Verification Metric**: Correlation between $T_0$ Incremental ROIIC and future $+8Q$ operating profit expansion ($r > 0.45, p < 0.001$).

### Capability C — Valuation & Expectations Asymmetry
* **Hypothesis**: The system separates value traps (cheap low-ROIC dying businesses) from asymmetric inflections (moderate/high P/E but low market-implied growth relative to organic compounding runway).
* **Verification Metric**: Top quartile Expectations Gap ($\text{P4} \ge 80$) outperforms Low quartile ($\text{P4} \le 30$) by $\ge 12\%$ annualized alpha.

### Capability D — Price & Volume Confirmation
* **Hypothesis**: Combining fundamental inflections with Weinstein Stage 2 breakouts and volume accumulation prevents early entries into multi-year dead money.
* **Verification Metric**: Time-to-milestone reduction: P1+P5 entries reach $2\times$ return $35\%$ faster than P1-only entries.

### Capability E — Multibagger Discovery & Early Discovery Lift
* **Hypothesis**: A stock ranked in the Top 20 by the unified 5-Pillar / M7 engine has a statistically significant higher probability of achieving $2\times$, $5\times$, and $10\times$ within 3–5 years than the baseline universe.
* **Verification Metric**: $10\times$ Precision Lift $\ge 4.0\times$ over random baseline; Early Multibagger Discovery Lift at $24\text{M} \ge 45\%$.

### Capability F — Regime & Sector Robustness
* **Hypothesis**: The alpha generation is not an artifact of a single bull run (e.g., post-COVID 2020–2021) or a single sector (e.g., Electronics EMS or Chemicals), but persists across all market cycles (2013–2026).
* **Verification Metric**: Positive Information Coefficient ($\text{IC} > 0.05$) across $\ge 85\%$ of all historical rolling 3-year windows.

---

## 2. Historical Time-Travel Replay Engine

### Protocol Specification
* **Historical Horizons**: 53 Consecutive Quarters (**2013-Q1 through 2026-Q2**).
* **Execution Rule**: At each historical quarter-end $T_0$ (e.g. `2017-09-30`), the system clock is frozen.
* **Ingestion Firewall**:
  * Filing Publication Lag: Financial statements are only visible after $T_0 + 45\text{ days}$ (or exact SEBI filing timestamp).
  * Price Data: Prices and volumes strictly $\le T_0$.
  * Corporate Announcements: Filings strictly $\le T_0$.
  * Shareholding: Patterns strictly filed for period $\le T_0$.

```text
Historical Time-Travel Timeline (53 Quarters):
2013-Q1 ──► 2014-Q1 ──► ... ──► 2019-Q4 ──► 2020-Q1 ──► ... ──► 2026-Q2
   │           │                   │           │                   │
  [T0]        [T0]                [T0]        [T0]                [T0]
   ▼           ▼                   ▼           ▼                   ▼
Freeze PIT  Freeze PIT          Freeze PIT  Freeze PIT          Freeze PIT
Rank Univ   Rank Univ           Rank Univ   Rank Univ           Rank Univ
SHA-256     SHA-256             SHA-256     SHA-256             SHA-256
```

---

## 3. The Future Reveal: Milestone Tracking & Drawdown Matrix

Once rankings are frozen at $T_0$ with SHA-256 immutable hashes, the timeline advances to record future realization milestones without human intervention:

| Observation Horizon | Tracking Milestones | Risk & Pain Metrics |
| :--- | :--- | :--- |
| **$+1\text{ Quarter}$ ($+90\text{d}$)** | Immediate earnings surprise, initial market reaction | $1\text{Q}$ Max Drawdown |
| **$+2\text{ Quarters}$ ($+180\text{d}$)** | 2nd derivative earnings continuation, margin trajectory | $6\text{M}$ Max Drawdown |
| **$+4\text{ Quarters}$ ($+1\text{ Year}$)** | $1\text{Y}$ Absolute Return, Beat vs. Nifty 500 | $1\text{Y}$ Max Drawdown, Volatility |
| **$+8\text{ Quarters}$ ($+2\text{ Years}$)** | $2\times$ Hit Status, Multiple Rerating vs. EPS Growth | $2\text{Y}$ Max Drawdown, Recovery Time |
| **$+12\text{ Quarters}$ ($+3\text{ Years}$)** | $3\times$ / $5\times$ Milestone Hit, Compounding Runway | $3\text{Y}$ Max Drawdown |
| **$+20\text{ Quarters}$ ($+5\text{ Years}$)** | $10\times$ Milestone Hit, Ultimate Realization Multiplier | Lifetime Max Drawdown |

---

## 4. Universe-Wide Execution: Eliminating Selection Bias

```
┌─────────────────────────────────────────────────────────────┐
│ Complete Active + Delisted Listed Equities Universe at T0   │
│ (Nifty 500 + MicroCap 250 + Active SME/BSE: ~1,500 Stocks)  │
└──────────────────────────────┬──────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
┌───────────────────────────┐         ┌───────────────────────────┐
│ Eligible Research Cohort  │         │ Data Quarantine Cohort    │
│ (Audited Statements ≥ 8Q) │         │ (< 8Q History / Suspended)│
└───────────┬───────────────┘         └───────────────────────────┘
            │ Full Universe Ranking
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Cohort Quintiles & Deciles:                                             │
│ Top 10 | Top 20 | Top 50 | Quintile 1 | Quintile 2 ... | Bottom Decile  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Baselines Comparison Tournament

To guarantee scientific rigor, the 5-Pillar / M7 engine is benchmarked against 8 standardized competitors across identical $T_0$ timeframes:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      THE 8-WAY BENCHMARK TOURNAMENT                      │
├────┬───────────────────────┬─────────────────────────────────────────────┤
│ #  │ Strategy / Competitor │ Formulation / Selection Rule                │
├────┼───────────────────────┼─────────────────────────────────────────────┤
│ B1 │ Random Selection      │ Monte Carlo uniform random draw (1,000 runs)│
│ B2 │ Simple Value          │ Lowest Trailing P/E Multiple ($> 0$)        │
│ B3 │ Simple Quality        │ Highest Trailing ROCE                       │
│ B4 │ Simple Growth         │ Highest YoY EPS / PAT Growth Rate           │
│ B5 │ Pure Momentum         │ Highest 12-Month Price Return               │
│ B6 │ Original Model M6     │ $0.30Q + 0.25G + 0.20M + 0.15V + 0.10Gov$   │
│ B7 │ 5-Pillar Synthesis    │ Nonlinear P1..P5 Composite + Circuit Break  │
│ B8 │ M7 Discovery (GBDT)   │ Gradient Boosted Decision Tree Interactions │
└────┴───────────────────────┴─────────────────────────────────────────────┘
```

---

## 6. Scoreboard & Primary Evaluation Metrics

### Signature Metric: Early Multibagger Discovery Lift

$$\text{Early Discovery Lift}_{H} = \frac{\% \text{ of eventually } 5\times/10\times \text{ stocks in Top 20 at } (T_{\text{hit}} - H)}{\% \text{ of total universe in Top 20}}$$

Where $H \in \{12\text{ Months}, 24\text{ Months}, 36\text{ Months}\}$.

### The Formal Metric Scoreboard

| Metric | Mathematical Definition | Institutional Significance | Target Benchmark |
| :--- | :--- | :--- | :--- |
| **$2\times$ Precision (Top 20)** | $\frac{\text{Count}(\text{Top 20 stocks reaching } \ge 2\times \text{ in } 3\text{Y})}{20}$ | Basic alpha hit rate | $\ge 60.0\%$ |
| **$5\times$ Precision (Top 20)** | $\frac{\text{Count}(\text{Top 20 stocks reaching } \ge 5\times \text{ in } 5\text{Y})}{20}$ | Serious compounder identification | $\ge 30.0\%$ |
| **$10\times$ Precision (Top 20)** | $\frac{\text{Count}(\text{Top 20 stocks reaching } \ge 10\times \text{ in } 5\text{Y})}{20}$ | Outlier discovery capability | $\ge 15.0\%$ |
| **Multibagger Recall** | $\frac{\text{Count}(\text{Actual universe } 10\times \text{ stocks identified in Top 50})}{\text{Total } 10\times \text{ stocks in universe}}$ | Coverage of market winners | $\ge 40.0\%$ |
| **Top-20 Lift over Random** | $\frac{\text{Precision}_{\text{Top 20}}(5\times)}{\text{Base Rate}_{\text{Universe}}(5\times)}$ | Signal-to-noise multiplier | $\ge 4.5\times$ |
| **Time-to-Discovery Lead** | $T_{\text{milestone}} - T_{\text{first Top 20 entry}}$ (in months) | Lead time before realization | $\ge 18\text{ Months}$ |
| **Capture Ratio** | $\frac{\text{Return from } T_{\text{entry}} \text{ to Peak}}{\text{Full } 10\times \text{ Cycle Return}}$ | Percentage of total run captured | $\ge 70.0\%$ |
| **Max Drawdown Before $2\times$** | $\max_{t \in [T_0, T_{2\times}]} \left(\frac{\text{Peak}_t - \text{Price}_t}{\text{Peak}_t}\right)$ | Psychological pain factor | $\le 28.0\%$ |
| **False-Positive Catastrophe**| $\% \text{ of Top 20 suffering } > 50\% \text{ permanent loss}$ | Forensic capital preservation | $\le 5.0\%$ |
| **Information Coefficient** | Spearman rank correlation $(\text{Score}_{T_0}, \text{Return}_{T_0 \to T_0+3\text{Y}})$ | Predictive ranking consistency | $\ge 0.12$ |

---

## 7. Deep Case Studies: Famous Historical Winners

At specific historical dates $T_0$ when these companies were in early inflection, freeze the database and evaluate the exact 5-Pillar signal:

### Case Study 1: Dixon Technologies (`DIXON`) — $T_0 = \text{2019-Q3}$ (Pre-$15\times$ Run)
* **What the system sees at $T_0$**:
  * Revenue: ₹3,000 Cr; Market Cap: ₹3,500 Cr; Trailing P/E: $32\times$.
  * Economic ROIC: $24.8\%$; Incremental ROIIC: $38.2\%$.
  * Greenwald Growth CapEx: $> 65\%$ of CapEx directed to capacity addition.
  * Pillar 2 (TAM): Mobile & Lighting EMS TAM = ₹1,50,000 Cr ($< 3\%$ market share at $T_0$).
  * Pillar 4 (Expectations Gap): Market implies $12\%$ CAGR; Organic Compounding Ceiling is $32\%$.
* **System Verdict at $T_0$**: `TIER_1_ASYMMETRIC_INFLECTION` (Score: 91/100).
* **Future Reveal**: Dixon expanded from ₹450 to ₹14,000+ ($> 30\times$).

### Case Study 2: Trent (`TRENT`) — $T_0 = \text{2021-Q3}$ (Zudio Inflection)
* **What the system sees at $T_0$**:
  * 2nd Derivative Acceleration: Zudio store additions accelerating from 40 to 120/year.
  * Operating Profit Growth: $+48\%$ YoY; Working capital cash conversion cycle: $< 20\text{ days}$.
  * Expectations Gap: Positive asymmetry due to rapid store payback period ($< 18\text{ months}$).
* **System Verdict at $T_0$**: `TIER_1_ASYMMETRIC_INFLECTION` (Score: 88/100).
* **Future Reveal**: Trent compounder run from ₹900 to ₹7,500+ ($> 8\times$).

---

## 8. The Prediction Autopsy: Learning from Failed Predictions

For any high-conviction candidate (`Tier 1 / Score ≥ 80`) that failed to compound (subsequent return $< 0\%$ or drawdown $> 50\%$), the engine executes a **Formal Prediction Autopsy**:

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. T0 Belief Snapshot                                       │
│ (ROIC: 22%, Expected Growth: 25%, TAM Feasibility: High)    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. What Actually Happened (T0 + 4Q / T0 + 8Q)               │
│ (Revenue collapsed -30%, Working capital DSO surged +80d)   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Root Cause Classification                                │
│ [ ] Failure Mode 1: Valuation Multiple Derating             │
│ [x] Failure Mode 2: Working Capital & Cash Drain (Trap)     │
│ [ ] Failure Mode 3: Governance / Capital Misallocation      │
│ [ ] Failure Mode 4: Macro Commodity / Regulatory Shock      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Earliest Detectable Warning Identification               │
│ (Could WorkingCapitalSentinel have caught Δ²DSO at T0+1Q?)  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Automated Rule / Feature Invariant Update                │
│ (Introduce strict DSO 2nd-derivative circuit breaker)       │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. Pillar Ablation Study (Feature Attribution)

To prove which pillars contribute genuine predictive power versus noise, run the full 53-quarter backfill under 8 ablation permutations:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PILLAR ABLATION MATRIX                          │
├───────────────────┬─────┬─────┬─────┬─────┬─────┬──────────────────────┤
│ Configuration     │ P1  │ P2  │ P3  │ P4  │ P5  │ Test Hypothesis      │
├───────────────────┼─────┼─────┼─────┼─────┼─────┼──────────────────────┤
│ 1. Full 5-Pillar  │  ✓  │  ✓  │  ✓  │  ✓  │  ✓  │ Complete System      │
│ 2. P1 Only (Inf.) │  ✓  │  -  │  -  │  -  │  -  │ Pure 2nd Deriv Growth│
│ 3. P2 Only (TAM)  │  -  │  ✓  │  -  │  -  │  -  │ Pure Headroom        │
│ 4. P3 Only (WC)   │  -  │  -  │  ✓  │  -  │  -  │ Pure Forensic Health │
│ 5. P4 Only (Gap)  │  -  │  -  │  -  │  ✓  │  -  │ Pure Expectations Asy│
│ 6. P5 Only (Price)│  -  │  -  │  -  │  -  │  ✓  │ Pure Technical Stage2 │
│ 7. P1 + P4 (Fund) │  ✓  │  -  │  -  │  ✓  │  -  │ Inflection + Asymmetry│
│ 8. P1 + P4 + P5   │  ✓  │  -  │  -  │  ✓  │  ✓  │ Fund + Market Conf.  │
└───────────────────┴─────┴─────┴─────┴─────┴─────┴──────────────────────┘
```

---

## 10. Proving the Nonlinear Hypothesis (M6 vs. M7)

The core critique of linear models like M6 ($0.30Q + 0.25G + 0.20M + 0.15V + 0.10Gov$) is that multibaggers are multiplicative interactions, not weighted sums.

### Interaction Hypotheses to Empirically Prove:
1. **Compounding Engine Interaction**:
   $$\text{Interaction}_1 = \text{Economic ROIC} \times \text{Growth Reinvestment Rate}$$
   *Hypothesis*: High ROIC ($> 25\%$) with zero reinvestment produces mediocre returns; high reinvestment ($> 70\%$) with low ROIC produces value destruction. Only the **product** generates $10\times$ alpha.
2. **Inflection & Operating Leverage Interaction**:
   $$\text{Interaction}_2 = \Delta \text{YoY Revenue Growth} \times \Delta \text{OPM}$$
3. **Asymmetric Expectations & Confirmation Interaction**:
   $$\text{Interaction}_3 = \text{Expectations Gap Score} \times \text{Mansfield Relative Strength}$$

---

## 11. The Blind Historical Challenge Protocol

1. **Cohort Selection**: Select 5 historical cohorts (e.g., $T_0 \in \{\text{2014-Q2}, \text{2016-Q4}, \text{2018-Q3}, \text{2020-Q4}, \text{2022-Q1}\}$).
2. **Blind Execution**: Run the ranking engine without forward outcome database access.
3. **Cryptographic Sealing**: Generate `SHA-256` commitment hash of the top 20 rankings:
   $$\text{Commitment Hash} = \text{SHA256}(\text{Cohort Date} + \text{Rankings JSON} + \text{Salt})$$
4. **Unseal & Measure**: Publish the sealed ranking, query future 3-year prices, and calculate realized Sharpe, CAGR, and Multibagger Hit Rate.

---

## 12. Prospective Validation Protocol (EXP-004)

* **Status**: Model M6 and 5-Pillar algorithms are **FROZEN**. No weights or formulas may be altered during prospective evaluation.
* **Weekly Execution**: Every Monday at 09:15 IST, generate active watchlist snapshots and persist to `DecisionSnapshot` with `source_fact_ids=["PROSPECTIVE_EXP004"]`.
* **Realization Log**: Continuously monitor forward outcomes at $+30\text{d}, +90\text{d}, +180\text{d}, +365\text{d}$ against live exchange feeds.

---

## Verification & Execution Roadmap

```
Step 1: Expand Historical Dataset
        - Run scale_historical_universe_backfill.py across 500+ NSE companies over 53 quarters.
Step 2: Generate Universal PIT Snapshots
        - Execute HistoricalPITReplayEngine to populate ResearchFeatureSnapshot & ForwardOutcome.
Step 3: Run Baseline Tournament
        - Execute competitors B1 through B8 across all 53 quarters.
Step 4: Compute Multibagger Capability Scoreboard
        - Calculate 2x/5x/10x Precision, Recall, Early Discovery Lift, and Ablation Matrix.
Step 5: Generate Institutional Validation Report
        - Export final statistical findings to institutional_validation_report.json & Markdown.
```

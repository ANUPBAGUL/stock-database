# MASTER PLAN: Institutional Positional Swing Trading Engine — Indian Equities

### Mission

Build a statistically defensible **2–6 week positional swing trading engine for NSE/BSE equities**.

The engine answers four separate, causal questions:

1. **Setup Detection (Layer 1):** What is happening?
2. **Setup Quality (Layer 2):** How structurally attractive is it?
3. **Empirical Probability (Layer 3):** What historically happened in comparable situations?
4. **Portfolio Decision (Layer 4):** Should capital be deployed, and how much?

The system prioritizes **out-of-sample evidence over complexity**.

No feature, threshold, score, probability, or trading rule may be accepted merely because it looks intuitively correct.

---

# 1. NON-NEGOTIABLE RESEARCH PRINCIPLES

## 1.1 Point-in-Time Truth
Every decision at $T_0$ must use only information available at $T_0$.
No future:
* prices
* corporate actions
* financial results
* revised filings
* index membership
* sector classification
* calibration outcomes
* model parameters
may enter the $T_0$ decision.

## 1.2 Survivorship-Bias-Free Universe
Historical replay must include securities that subsequently:
* failed
* delisted
* merged
* demerged
* changed symbols
* changed ISINs
* left an index
* became illiquid
The historical universe must represent what was actually investable at each historical date.

## 1.3 Corporate-Action Correctness
The market-data layer must correctly handle:
* splits
* bonuses
* rights
* dividends where relevant to the chosen return convention
* mergers
* demergers
* symbol changes
* ISIN changes
* relistings
Technical signals must never be generated from improperly adjusted historical prices.

## 1.4 No Look-Ahead Through Outcome Completion
A trade can enter calibration only after its complete outcome is known.
For a 45-day horizon:
$$\mathcal{D}_{calibration}(T_0) = \{trade:\ outcome\ fully\ observable < T_0 \quad (exit\_date < T_0)\}$$
A trade still running at $T_0$ cannot contribute its eventual result to $T_0$ calibration.
This invariant is mandatory.

---

# 2. EXP-SWING-001 FROZEN SIGNAL ENGINE

The following definitions are **frozen** for the first major validation experiment. Do not tune them using OOS results.

## 2.1 Setup Types
* VCP contraction breakout
* 52-week-high breakout
* Base consolidation breakout
* 50EMA pullback
* Failed breakout / reversal

## 2.2 Volatility
Primary contraction measure:
$$ATRRatio = \frac{ATR_{10}}{ATR_{30}}$$
Store the raw components as well:
```text
ATR10
ATR30
ATR10_ATR30_ratio
```
Do not rely only on the derived ratio.

## 2.3 Volume Dry-Up
$$VolumeDryUp = \frac{AvgVolume_5}{AvgVolume_{40}}$$
Dry-up becomes structurally meaningful only when accompanied by price stability/base support.
Store:
```text
volume_5
volume_40
volume_ratio
recent_low_5d
base_low
support_holding
```

## 2.4 Volume Asymmetry
$$UDRatio = \frac{\sum Volume_{up\ days}}{\sum Volume_{down\ days}}$$
Also retain:
```text
up_days
down_days
high_volume_up_days
high_volume_down_days
distribution_days
```
Never label this as literal "smart-money detection."
Use: **Positive volume accumulation signature**.

---

# 3. ENTRY ENGINE

Structural pivot is determined independently of current CMP.
Entry:
$$Entry = PivotHigh + \max(0.12ATR_{10}, 0.0015CMP)$$
The constants are frozen for EXP-SWING-001. They are **not assumed to be optimal**.
After the experiment, they may only be changed through a separate parameter experiment.

---

# 4. STOP ENGINE

Primary principle:
$$Structure \longrightarrow Volatility \longrightarrow PositionSize$$
Structural floor:
* Final contraction low, or
* Appropriate 50EMA structural support
Stop:
$$Stop = StructuralFloor - 0.05ATR_{10}$$
The stop represents **thesis invalidation**, not an arbitrary maximum loss.

---

# 5. TARGET ENGINE

Two targets:
* **T1 (Conservative structural target):** $T1 = Pivot + BaseDepth$ or appropriate 52-week-high objective where applicable.
* **T2 (Positional extension):** $T2 = Pivot + 1.5BaseDepth$ or the predefined ATR-based alternative.
These are **candidate exit levels**, not assumed probability-weighted returns.

---

# 6. ACTIONABILITY ENGINE

Maintain:
```text
CONSTRUCTING_BASE
TRIGGER_WATCH
ACTIONABLE_BUY
LATE_BUY_ZONE
EXTENDED
FAILED_SETUP
```
A failed setup is never converted into a buy merely because its historical empirical expectancy is positive. Structural invalidation has priority.

---

# 7. STRUCTURAL SCORE

Maintain the frozen 0–100 score:
$$Score = 0.35EntryQuality + 0.30TapeConfirmation + 0.20VolumeStructure + 0.15RRScore$$
This score must remain **completely independent of historical outcome statistics** during EXP-SWING-001.
No $backtest \longrightarrow score \longrightarrow backtest$ feedback loop is permitted.

---

# 8. LAYER 3 — EMPIRICAL ENGINE

For every historical setup, record:
```text
T0, setup_type, contraction_quality, market_regime, sector_regime, structural_score,
entry, stop, T1, T2, outcome, exit_date, exit_reason, realized_R
```
Then calculate:
* $P(T1\ before\ Stop)$
* $P(T2\ before\ Stop)$
* $P(Stop)$
* $E[R \mid X]$
* $ProfitFactor$

---

# 9. UNCERTAINTY SYSTEM

Use Wilson 95% confidence intervals for binomial probabilities.
Every empirical probability must display:
```text
estimate
CI_low
CI_high
n
sample evidence
```
Use:
* `LIMITED` ($n < 20$)
* `PRELIMINARY` ($20 \le n < 150$)
* `MODERATE` ($150 \le n < 400$)
* `ADEQUATE` ($n \ge 400$)
These labels describe **evidence quantity**, not statistical certainty.

---

# 10. BAYESIAN SHRINKAGE

Small samples must not be allowed to dominate decisions.
Use hierarchical shrinkage toward an appropriate parent/universe prior ($k = 15.0$):
$$w = \frac{n}{n + 15}$$
$$E[R \mid X]_{shrunk} = w \cdot E[R \mid X]_{observed} + (1 - w) \cdot E[R]_{prior}$$
The shrinkage parameter itself is a research parameter. It must eventually be evaluated out of sample rather than assumed optimal.

---

# 11. HIERARCHICAL CALIBRATION

Progressive conditioning:
* **Level 1:** Setup
* **Level 2:** Setup × contraction
* **Level 3:** Setup × market regime
* **Level 4:** Setup × contraction × market regime
* **Level 5:** Add sector/volume only when sample size permits.
Never display a conditional probability simply because a database query produced a number. Require minimum evidence hurdles ($n \ge 3$ L1, $n \ge 4$ L2, $n \ge 5$ L3).

---

# 12. MFE / MAE SYSTEM

Record both:
* **Trade-life excursion (only while alive):** `mfe_pre_stop`, `mae_pre_stop`
* **Full-path excursion (regardless of exit):** `mfe_1d` to `mfe_45d`, `mae_1d` to `mae_45d`
Never interpret full-path MFE as realized strategy return.

---

# 13. SAME-BAR EXECUTION POLICY

Every trade must record `same_bar_ambiguity`.
If stop and target are both touched during one daily bar:
* **Conservative:** Stop first (loss).
* **Optimistic:** Target first (win).
* **Excluded:** Remove ambiguous observations from calculation.
Report all three where ambiguity exists.

---

# 14. INDIA-SPECIFIC EXECUTION REALISM

Mandatory for the Indian-market version:
* **Liquidity:** Average traded value, ADV, turnover, position size / ADV.
* **Spread:** Realistic estimates where bid/ask data exists.
* **Slippage:** Model according to $Slippage = f(liquidity, volatility, positionSize, marketRegime)$.
* **Circuit limits:** Account for NSE/BSE price-band behavior. A theoretical stop is not necessarily an executable stop.
* **Trading restrictions:** Record historical ASM/GSM and suspension states. Distinguish signal validity from execution feasibility.

---

# 15. MARKET REGIME

Every trade must have a historical market-regime label: `BULL`, `NEUTRAL`, `BEAR`.
The regime classifier must be frozen before OOS evaluation. Evaluate $E[R \mid Setup, MarketRegime]$.

---

# 16. SECTOR REGIME

Record: `sector`, `sector_trend`, `sector_relative_strength`, `sector_regime`.
Evaluate $E[R \mid Setup, MarketRegime, SectorRegime]$.

---

# 17. PORTFOLIO DECISION ENGINE

Separate:
* **Structural risk:** $Risk\% = \frac{Entry - Stop}{Entry}$
* **Position risk:** $PortfolioRisk = PositionSize \times Risk\%$
* **Portfolio constraints:** Single-stock max, open risk, sector concentration, liquidity, regime.
Do **not** force a minimum 4% position. If a trade deserves 0%, it gets 0%. The 1% risk budget is a maximum risk objective, not an obligation to trade.

---

# 18. REGIME SIZING

Market regime may modify **position size**, but must not rewrite **stock-level structural conviction**.

---

# 19. PROBABILITY CALIBRATION

Track:
* Reliability diagrams / calibration curves
* Brier score
* Brier Skill Score ($BSS = 1 - Brier_{model} / Brier_{unconditional}$)
* Primary benchmark: $BSS > 0$ against naive climatology.
The preliminary BSS of $-7.15\%$ is treated as an **overconfidence warning**, not a success.

---

# 20. WALK-FORWARD VALIDATION

Use rolling/expanding walk-forward validation:
```text
TRAIN 2017–2020 → TEST 2021
TRAIN 2018–2021 → TEST 2022
TRAIN 2019–2022 → TEST 2023
TRAIN 2020–2023 → TEST 2024
TRAIN 2021–2024 → TEST 2025
TRAIN 2022–2025 → TEST 2026
```
For every test period:
1. Freeze training calibration
2. Generate OOS predictions
3. Realize future outcomes
4. Calculate performance
5. Move window forward
Never tune on the OOS period.

---

# 21. PRIMARY EXPERIMENT: EXP-SWING-001

* **Objective:** Determine whether the predefined Indian-equity setup framework generates positive risk-adjusted expectancy out of sample.
* **Primary metrics:** $E[R]$, $ProfitFactor$, $P(T1)$, $P(T2)$, $P(Stop)$, $MaxDrawdown$, $BSS$.
* **Secondary metrics:** MFE, MAE, holding period, turnover, exposure, costs, slippage, setup frequency, sector concentration.

---

# 22. SUCCESS CRITERIA

* **Trading edge:** Positive expectancy after realistic costs.
* **Persistence:** Positive or economically acceptable results across multiple walk-forward periods.
* **Ranking:** Higher structural-score groups demonstrate better outcomes than lower groups.
* **Probability:** $BSS_{OOS} > 0$.
* **Robustness:** Results do not depend on one stock, sector, year, or setup.
* **Execution:** Edge survives spread, slippage, liquidity, and circuit limits.

---

# 23. REQUIRED DATA SCALE

* **Current:** 77 trades / 24 companies / 272 sessions is a **pilot sample**, not final evidence.
* **Target:** 500+ symbols, thousands of setups, multiple complete market cycles across large/mid/small caps.

---

# 24. REQUIRED BASELINES

Compare against:
* **Baseline A:** Buy-and-hold Nifty / benchmark
* **Baseline B:** Simple momentum strategy
* **Baseline C:** Simple 52-week breakout
* **Baseline D:** Structural score without empirical calibration
* **Baseline E:** Setup-type empirical probability
* **Model:** Full four-layer engine

---

# 25. ABLATION TESTS

After EXP-SWING-001, run controlled ablation experiments (remove volume, contraction, RS, regime, empirical calibration, or score) to measure incremental OOS contribution. A feature earns its place only if removing it causes meaningful deterioration.

---

# 26. MULTIPLE-TESTING CONTROL

Maintain an experiment registry (`EXPERIMENT_REGISTRY.md`). Never silently discard failed experiments.

---

# 27. DATA-SNOOPING FIREWALL

Once an OOS period has been evaluated, it is contaminated for future model selection. Maintain:
```text
Development data → Validation data → Final untouched test data
```

---

# 28. LIVE PAPER-TRADING PHASE
Only after successful historical OOS validation: record signal timestamp, entry availability, actual executable price, slippage, liquidity, circuit constraints, and stop execution without capital.

---

# 29. LIVE SHADOW PHASE
Run alongside the market without executing to validate $ExpectedEntry$ vs $RealisticEntry$ and $ExpectedStop$ vs $ActualExitFeasibility$.

---

# 30. CAPITAL DEPLOYMENT GATE
Real capital permitted only after passing historical PIT/OOS tests, surviving paper trading, acceptable calibration, zero leakage, understood drawdowns, and controlled portfolio concentration.

---

# 31. DASHBOARD DESIGN
Always display:
`SETUP`, `STATUS`, `STRUCTURAL SCORE`, `ENTRY`, `STOP`, `T1`, `T2`, `STRUCTURAL R:R`, `EMPIRICAL P(T1)`, `95% CI`, `SAMPLE N`, `EVIDENCE`, `SHRUNK E[R]`, `MARKET REGIME`, `SECTOR REGIME`, `RS VS NIFTY`, `RS VS SECTOR`, `EXECUTION RISK`, `POSITION SIZE`, `INVALIDATION CONDITION`.

---

# 32. WHAT MUST NEVER HAPPEN
* Claim a probability without an evidence count
* Call $n=7$ statistically strong
* Use future outcomes in historical calibration
* Use future financial revisions, index membership, or sector classifications
* Silently change signal definitions
* Optimize against an OOS period
* Treat MFE as realized return
* Assume stop execution when a circuit prevents exit
* Treat volume asymmetry as proof of institutional intent
* Use empirical EV to override structural invalidation
* Add indicators because one experiment failed
* Select a model because it looks better in-sample

---

# 33. EXPERIMENTAL STATUS
* **Technical definitions:** **FROZEN**
* **Empirical evidence:** **PRELIMINARY**
* **Probability calibration:** **NOT YET DEMONSTRATED OOS**
* **Trading hypothesis:** **FALSIFIABLE AND UNDER VALIDATION**
* **Research objective:** **Expand data $\longrightarrow$ walk-forward OOS $\longrightarrow$ validate execution $\longrightarrow$ evaluate robustness.**

---

# 34. THE FINAL ARCHITECTURE

```text
                 NSE / BSE HISTORICAL DATA
                           │
                           ▼
                ┌─────────────────────┐
                │ PIT DATA FOUNDATION │
                │ Corporate Actions   │
                │ Survivorship         │
                │ Identity             │
                │ Liquidity            │
                └──────────┬──────────┘
                           │
                           ▼
                  L1 SETUP DETECTION
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
       VCP              52W Breakout       Pullback
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                  L2 SETUP QUALITY
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
           Volatility    Volume        Structure
              │            │            │
              └────────────┼────────────┘
                           ▼
                 FROZEN STRUCTURAL SCORE
                           │
                           ▼
                 L3 EMPIRICAL ENGINE
                           │
          ┌────────────────┼─────────────────┐
          ▼                ▼                 ▼
       P(T1)             P(T2)            P(Stop)
          │                │                 │
          └────────────────┼─────────────────┘
                           ▼
                      E[R | X]
                           │
                    Wilson + Shrinkage
                           │
                           ▼
                 WALK-FORWARD OOS TEST
                           │
                           ▼
                 L4 PORTFOLIO DECISION
                           │
          ┌────────────────┼─────────────────┐
          ▼                ▼                 ▼
        Entry            Stop             Targets
          │                │                 │
          └────────────────┼─────────────────┘
                           ▼
                  Position Risk Engine
                           │
             ┌─────────────┼──────────────┐
             ▼             ▼              ▼
          Liquidity      Sector         Market
          Constraint     Exposure       Regime
             │             │              │
             └─────────────┼──────────────┘
                           ▼
                    PAPER TRADING
                           │
                           ▼
                    SHADOW LIVE
                           │
                           ▼
                  CAPITAL DEPLOYMENT
```

# FINAL DIRECTIVE

**Freeze the signal engine now.**
Do not add another indicator.
Do not tune VCP thresholds because VCP currently looks good.
Do not remove 50EMA because it currently looks bad.
Do not optimize against the current 77-trade sample.
Do not turn the current empirical results into claims of profitability.

**From this point onward, the project is driven by evidence, not feature accumulation.**

# EXPERIMENT REGISTRY: Institutional Swing Trading Engine

This registry controls multiple-testing risk and enforces the research firewall. Every parameter experiment, hypothesis test, and walk-forward validation run must be permanently recorded here. No experiment may be silently discarded.

---

## Experiment: EXP-SWING-001

* **Experiment ID:** `EXP-SWING-001`
* **Status:** **FROZEN (Pre-Walk-Forward Baseline)**
* **Registration Date:** 2026-09-04
* **Hypothesis:** A 4-layer decoupled swing engine (Minervini Stage 2, normalized ATR contraction, volume dry-up, adaptive pivot buffer, and structural floor stop) generates positive risk-adjusted expectancy ($E[R] > 0$, $PF > 1.0$) across a 45-day positional holding horizon on Indian equities.
* **Architecture:**
  - Layer 1: Setup Detection (VCP, 52W Breakout, Base Consolidation, 50EMA Pullback, Failed Setup)
  - Layer 2: Setup Quality (ATR Ratio $ATR_{10}/ATR_{30}$, Vol Dry-Up $Vol_5/Vol_{40}$, Positive Vol Asymmetry $\ge 1.5\text{x}$)
  - Layer 3: Empirical Probability (Wilson 95% CI, Empirical Bayesian Shrinkage $k=15$, Brier Score Benchmarks)
  - Layer 4: Portfolio Decision (Adaptive buffer $\max(0.12ATR_{10}, 0.0015CMP)$, Floor Stop $Floor - 0.05ATR_{10}$, 1% Account Risk Budget)
* **Parameter Constants (Strictly Frozen):**
  - Contraction threshold: $< 0.85$ (Ratio $ATR_{10} / ATR_{30}$)
  - Volume dry-up threshold: $< 0.75$ (Ratio $Vol_5 / Vol_{40}$)
  - Up/Down volume ratio target: $\ge 1.5\text{x}$
  - Adaptive entry buffer: $\max(0.12 \times ATR_{10}, 0.0015 \times CMP)$
  - Structural floor stop buffer: $0.05 \times ATR_{10}$
  - Target 1: $Pivot + BaseDepth$
  - Target 2: $Pivot + 1.5 \times BaseDepth$ (or $3.2 \times ATR_{10}$)
  - Maximum structural risk cap: $8.5\%$ (above which position size is strictly $0.0\%$)
  - Holding horizon: 45 trading sessions (2–6 weeks)
* **In-Sample Pilot Replay Dataset:**
  - Date range: Point-in-time daily candles across 272 sessions
  - Traded Universe: 25 screened Indian companies (24 active traded symbols)
  - Completed trade episodes: 77
  - Outcome-Completion Filter: Enforced ($exit\_date < T_0$)
  - Same-bar ambiguity rate: $0 / 77$ ($0.0\%$, verified via synthetic dual-breach testing)
* **Pilot Replay Observations (Preliminary Baseline):**
  - Total trades: 77
  - Mode A (Conservative): Win Rate $28.6\%$ [Wilson 95% CI: $19.7\% - 39.5\%$] | Profit Factor $1.34\text{x}$ | Average Realized $+0.23R$
  - Mode B (Ambiguity Excluded): Win Rate $28.6\%$ [Wilson 95% CI: $19.7\% - 39.5\%$]
  - Mode C (Optimistic): Win Rate $28.6\%$ | Profit Factor $1.34\text{x}$
  - Execution Risk Spread ($\Delta R$): $+0.00R$
  - Pre-Stop MFE / MAE: $+9.3\% / -5.8\%$
  - Full 45-Day Path MFE / MAE: $+19.8\% / -9.9\%$ ($2.0\text{x}$ excursion asymmetry)
  - Model Brier Score: $0.2187$
  - Benchmark 1 Brier (Unconditional 28.6% Base Rate): $0.2041$
  - Brier Skill Score (BSS): $-7.15\%$ (**Overconfidence Diagnostic Flagged**)
  - Subgroup VCP Contraction Breakout: $N=7$, Win Rate $42.9\%$ [Wilson 95% CI: $15.8\% - 75.0\%$], PF $3.86\text{x}$, Raw $+1.32R$, Shrunk $E[R] = +0.58R$ (Evidence: `LIMITED`)
* **Decision:** **FROZEN**. Signal definitions and scoring formulas are locked. Feature accumulation is stopped.
* **Next Gate:** Expand universe to 500+ Indian symbols and execute rolling walk-forward OOS validation without tuning on test folds.

---

## Template for Subsequent Experiments

```text
Experiment ID: EXP-SWING-XXX
Hypothesis: 
Parent Experiment: 
Changes from Parent: 
Frozen Parameters: 
Training Window: 
OOS Window: 
Performance:
  OOS Realized E[R]:
  OOS Profit Factor:
  OOS Win Rate P(T1):
  OOS Brier Score:
  OOS Brier Skill Score (BSS):
  OOS Max Drawdown:
Decision: ACCEPTED / REJECTED / RETIRED
Rationale:
```

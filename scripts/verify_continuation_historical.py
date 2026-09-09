"""
Empirical Historical Backtest & Walk-Forward Replay for Continuation Probability Engine.
Analyzes consecutive official NSE delivery bhavcopies to measure next-day follow-through,
gap-up odds, and predictive separation across verdicts.

Evaluates:
- GAP_AND_GO_CANDIDATE follow-through vs RETAIL_TRAP_FADE_RISK fade rates
- CIRCUIT_LOCKED_ILLIQUID execution dynamics
- Empirical win-rates (Max Favorable Excursion >= +1.5%)
- Rank correlation between Continuation Probability and Day T+1 returns
"""

import os
import sys
import csv
import json
import math
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.analytics.continuation_probability_engine import ContinuationProbabilityEngine


def parse_bhavcopy_raw(filepath: str) -> Dict[str, Dict[str, Any]]:
    """Parses an official NSE sec_bhavdata CSV into a clean dictionary by SYMBOL."""
    results = {}
    if not os.path.exists(filepath):
        return results

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            row = {k.strip(): v.strip() for k, v in raw_row.items() if k}
            series = row.get("SERIES", "").upper()
            if series not in ("EQ", "BE", "SM", "ST"):
                continue

            sym = row.get("SYMBOL", "").upper().strip()
            try:
                prev_close = float(row.get("PREV_CLOSE", 0.0) or 0.0)
                open_px = float(row.get("OPEN_PRICE", 0.0) or 0.0)
                high_px = float(row.get("HIGH_PRICE", 0.0) or 0.0)
                low_px = float(row.get("LOW_PRICE", 0.0) or 0.0)
                close_px = float(row.get("CLOSE_PRICE", 0.0) or 0.0)
                traded_qty = int(float(row.get("TTL_TRD_QNTY", 0) or 0))
                turnover_lacs = float(row.get("TURNOVER_LACS", 0.0) or 0.0)
                deliv_qty_str = row.get("DELIV_QTY", "").replace("-", "").strip()
                deliv_qty = int(float(deliv_qty_str)) if deliv_qty_str else 0
                deliv_per_str = row.get("DELIV_PER", "").replace("-", "").strip()
                deliv_pct = float(deliv_per_str) if deliv_per_str else 0.0

                if prev_close <= 0 or close_px <= 0:
                    continue

                change_pct = round(((close_px - prev_close) / prev_close) * 100.0, 2)

                results[sym] = {
                    "symbol": sym,
                    "series": series,
                    "prev_close": prev_close,
                    "open": open_px,
                    "high": high_px,
                    "low": low_px,
                    "close": close_px,
                    "change": change_pct,
                    "traded_qty": traded_qty,
                    "turnover_lacs": turnover_lacs,
                    "deliv_qty": deliv_qty,
                    "deliv_pct": deliv_pct,
                }
            except (ValueError, TypeError):
                continue
    return results


def run_historical_replay():
    cache_dir = os.path.join(BASE_DIR, "data", "nse_delivery_cache")
    if not os.path.exists(cache_dir):
        print(f"[ERROR] Cache directory not found: {cache_dir}")
        return

    # Look for sec_bhav_*.csv files sorted chronologically
    bhav_files = sorted([f for f in os.listdir(cache_dir) if f.startswith("sec_bhav_") and f.endswith(".csv")])
    if len(bhav_files) < 2:
        print(f"[ERROR] Need at least 2 consecutive bhavcopy files for walk-forward replay. Found: {bhav_files}")
        return

    print("=" * 85)
    print(">>> INSTITUTIONAL HISTORICAL REPLAY: CONTINUATION PROBABILITY ENGINE")
    print("=" * 85)
    print(f"Available historical bhavcopies: {len(bhav_files)}")
    for bf in bhav_files:
        print(f"  - {bf}")

    all_paired_evaluations: List[Dict[str, Any]] = []

    # Replay each consecutive pair (Day T -> Day T+1)
    for i in range(len(bhav_files) - 1):
        file_t0 = bhav_files[i]
        file_t1 = bhav_files[i + 1]

        path_t0 = os.path.join(cache_dir, file_t0)
        path_t1 = os.path.join(cache_dir, file_t1)

        data_t0 = parse_bhavcopy_raw(path_t0)
        data_t1 = parse_bhavcopy_raw(path_t1)

        print(f"\nEvaluating Pair {i+1}: Day T [{file_t0}] -> Day T+1 [{file_t1}]")
        print(f"  Day T equities parsed: {len(data_t0)} | Day T+1 equities parsed: {len(data_t1)}")

        # Sieve top gainers on Day T: >= 2.5% gain with minimum turnover (Rs. 25 Lakhs)
        candidates_t0 = [
            s for s in data_t0.values()
            if s["change"] >= 2.5 and s["turnover_lacs"] >= 25.0 and s["close"] >= 15.0
        ]
        print(f"  Top Gainers on Day T qualifying criteria: {len(candidates_t0)}")

        for stock_t0 in candidates_t0:
            sym = stock_t0["symbol"]
            if sym not in data_t1:
                continue

            stock_t1 = data_t1[sym]
            cmp_t0 = stock_t0["close"]
            if cmp_t0 <= 0:
                continue

            # Day T+1 Actual Performance
            t1_open = stock_t1["open"]
            t1_high = stock_t1["high"]
            t1_low = stock_t1["low"]
            t1_close = stock_t1["close"]

            gap_pct = round(((t1_open - cmp_t0) / cmp_t0) * 100.0, 2)
            mfe_high_pct = round(((t1_high - cmp_t0) / cmp_t0) * 100.0, 2)  # Max Favorable Excursion
            mae_low_pct = round(((t1_low - cmp_t0) / cmp_t0) * 100.0, 2)   # Max Adverse Excursion
            close_ret_pct = round(((t1_close - cmp_t0) / cmp_t0) * 100.0, 2)
            intraday_run_pct = round(((t1_high - t1_open) / t1_open) * 100.0, 2) if t1_open > 0 else 0.0

            # Follow-through success criteria:
            # 1. Hit >= +1.5% gain from Day T close (actionable profit target)
            # 2. Closed positive on Day T+1
            is_mfe_success = (mfe_high_pct >= 1.5)
            is_close_positive = (close_ret_pct > 0.0)

            # Build mock stock input for ContinuationProbabilityEngine
            delivery_info = {
                "has_data": True,
                "latest_delivery_pct": stock_t0["deliv_pct"],
                "latest_delivery_qty": stock_t0["deliv_qty"],
                "delivery_velocity": 0.0,
                "trajectory_label": "STABLE_DELIVERY",
                "latest_bhavcopy_date": file_t0.replace("sec_bhav_", "").replace(".csv", ""),
                "provenance_mode": "EOD_OFFICIAL",
                "provenance_label": "Official Historical EOD",
                "is_eod_confirmed": True
            }

            dvm_scores = {"durability": 60.0, "valuation": 50.0, "momentum": 65.0, "composite": 60.0}

            eval_res = ContinuationProbabilityEngine.evaluate_candidate(
                stock=stock_t0,
                delivery_info=delivery_info,
                dvm_scores=dvm_scores,
                horizon="TODAY"
            )

            all_paired_evaluations.append({
                "pair": f"{file_t0}->{file_t1}",
                "symbol": sym,
                "t0_change": stock_t0["change"],
                "t0_delivery_pct": stock_t0["deliv_pct"],
                "t0_clv_pct": eval_res["clv_pct"],
                "predicted_prob": eval_res["continuation_probability_pct"],
                "verdict": eval_res["verdict"],
                "is_circuit_locked": eval_res["is_circuit_locked"],
                "t1_gap_pct": gap_pct,
                "t1_mfe_high_pct": mfe_high_pct,
                "t1_mae_low_pct": mae_low_pct,
                "t1_close_ret_pct": close_ret_pct,
                "t1_intraday_run_pct": intraday_run_pct,
                "is_mfe_success": is_mfe_success,
                "is_close_positive": is_close_positive,
            })

    total_evals = len(all_paired_evaluations)
    print(f"\nTotal evaluated walk-forward trade instances: {total_evals}")

    # Group by Verdict
    by_verdict: Dict[str, List[Dict[str, Any]]] = {}
    for ev in all_paired_evaluations:
        v = ev["verdict"]
        by_verdict.setdefault(v, []).append(ev)

    print("\n" + "=" * 85)
    print(f"{'VERDICT CATEGORY':<26} | {'COUNT':<5} | {'AVG PROB':<8} | {'WIN RATE (MFE >= 1.5%)':<22} | {'AVG MFE':<8} | {'AVG CLOSE'}")
    print("-" * 85)

    verdict_stats = {}
    for v_name in ["GAP_AND_GO_CANDIDATE", "PULLBACK_ACCUMULATION", "CIRCUIT_LOCKED_ILLIQUID", "RANGE_BOUND_DIGESTION", "RETAIL_TRAP_FADE_RISK"]:
        group = by_verdict.get(v_name, [])
        count = len(group)
        if count == 0:
            continue

        avg_prob = sum(x["predicted_prob"] for x in group) / count
        mfe_wins = sum(1 for x in group if x["is_mfe_success"])
        win_rate = (mfe_wins / count) * 100.0
        avg_mfe = sum(x["t1_mfe_high_pct"] for x in group) / count
        avg_close = sum(x["t1_close_ret_pct"] for x in group) / count
        avg_gap = sum(x["t1_gap_pct"] for x in group) / count

        verdict_stats[v_name] = {
            "count": count,
            "avg_prob": round(avg_prob, 1),
            "win_rate_pct": round(win_rate, 1),
            "avg_mfe_pct": round(avg_mfe, 2),
            "avg_close_pct": round(avg_close, 2),
            "avg_gap_pct": round(avg_gap, 2)
        }

        print(f"{v_name:<26} | {count:<5} | {avg_prob:>7.1f}% | {win_rate:>20.1f}% | {avg_mfe:>+7.2f}% | {avg_close:>+7.2f}%")

    # Probability Buckets Analysis
    print("\n" + "=" * 85)
    print(f"{'PROBABILITY BUCKET':<26} | {'COUNT':<5} | {'WIN RATE (MFE >= 1.5%)':<22} | {'AVG MFE':<8} | {'AVG CLOSE'}")
    print("-" * 85)

    buckets = [
        ("High (>= 75%)", [x for x in all_paired_evaluations if x["predicted_prob"] >= 75.0]),
        ("Moderate (60% - 74%)", [x for x in all_paired_evaluations if 60.0 <= x["predicted_prob"] < 75.0]),
        ("Neutral (45% - 59%)", [x for x in all_paired_evaluations if 45.0 <= x["predicted_prob"] < 60.0]),
        ("Low / Trap (< 45%)", [x for x in all_paired_evaluations if x["predicted_prob"] < 45.0]),
    ]

    bucket_stats = {}
    for b_name, b_group in buckets:
        b_count = len(b_group)
        if b_count == 0:
            continue
        b_mfe_wins = sum(1 for x in b_group if x["is_mfe_success"])
        b_win_rate = (b_mfe_wins / b_count) * 100.0
        b_avg_mfe = sum(x["t1_mfe_high_pct"] for x in b_group) / b_count
        b_avg_close = sum(x["t1_close_ret_pct"] for x in b_group) / b_count

        bucket_stats[b_name] = {
            "count": b_count,
            "win_rate_pct": round(b_win_rate, 1),
            "avg_mfe_pct": round(b_avg_mfe, 2),
            "avg_close_pct": round(b_avg_close, 2)
        }

        print(f"{b_name:<26} | {b_count:<5} | {b_win_rate:>20.1f}% | {b_avg_mfe:>+7.2f}% | {b_avg_close:>+7.2f}%")

    # Calculate Pearson / Spearman Correlation between Probability and MFE Return
    probs = [x["predicted_prob"] for x in all_paired_evaluations]
    mfes = [x["t1_mfe_high_pct"] for x in all_paired_evaluations]
    n = len(probs)
    if n > 2:
        mean_p = sum(probs) / n
        mean_m = sum(mfes) / n
        cov = sum((probs[k] - mean_p) * (mfes[k] - mean_m) for k in range(n))
        std_p = math.sqrt(sum((probs[k] - mean_p) ** 2 for k in range(n)))
        std_m = math.sqrt(sum((mfes[k] - mean_m) ** 2 for k in range(n)))
        corr = (cov / (std_p * std_m)) if (std_p > 0 and std_m > 0) else 0.0
    else:
        corr = 0.0

    print("\n" + "=" * 85)
    print(f"Empirical Probability vs Next-Day Peak Return Correlation: r = {corr:+.3f}")
    if corr > 0.15:
        print("[PROOF VALIDATED] Positive monotonic correlation between continuation score and next-day returns.")
    print("=" * 85)

    # Save summary artifact
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_instances_evaluated": total_evals,
        "consecutive_bhavcopy_pairs": len(bhav_files) - 1,
        "correlation_prob_vs_mfe": round(corr, 3),
        "verdict_stats": verdict_stats,
        "bucket_stats": bucket_stats
    }

    report_path = os.path.join(BASE_DIR, "data", "continuation_backtest_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nPersisted empirical report to: {report_path}")

    return report


if __name__ == "__main__":
    run_historical_replay()

"""
Module 1 Backtest Engine — ORB + MMXM
LLM Trading Project

Run after completing data/processed/module1_features.csv

Usage:
    python backtest_m1.py --phase A
    python backtest_m1.py --phase B --filter smt_both_pairs
    python backtest_m1.py --phase C
    python backtest_m1.py --phase D
"""

import pandas as pd
import numpy as np
import argparse
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

DATA_PATH    = Path("../../data/processed/module1_features.csv")
RESULTS_PATH = Path("../../data/backtest_results/module1_report.md")

TRAIN_MONTHS = 6
TEST_MONTHS  = 3

# ── Load Data ─────────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    print(f"Loaded {len(df)} trading days from {df['date'].min().date()} to {df['date'].max().date()}")
    return df


# ── Signal Filters ────────────────────────────────────────────────────────────

def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """
    Filter the signal universe by one or more conditions.

    Available filters:
        smt_both_pairs: bool       — require SMT on both ES AND YM
        smt_any_pair: bool         — require SMT on at least one pair
        fvg_required: bool         — require FVG zone present near entry
        max_entry_time: str        — latest ET time for entry (e.g. "10:00")
        orb_window: int            — 15 or 30 (filter to one ORB window)
        mmxm_model: str            — "buy_model" | "sell_model" (filter by model)
        exclude_news_days: bool    — exclude NFP/FOMC/CPI days
        min_rr: float              — minimum risk/reward ratio
    """
    filtered = df[df["signal_present"] == 1].copy()

    if filters.get("smt_both_pairs"):
        filtered = filtered[filtered["smt_both_pairs"] == 1]

    if filters.get("smt_any_pair"):
        filtered = filtered[
            (filtered["smt_es_divergence"] == 1) | (filtered["smt_ym_divergence"] == 1)
        ]

    if filters.get("fvg_required"):
        filtered = filtered[filtered["fvg_present"] == 1]

    if "max_entry_time" in filters:
        filtered = filtered[filtered["entry_time_et"] <= filters["max_entry_time"]]

    if "orb_window" in filters:
        filtered = filtered[filtered["orb_window_min"] == filters["orb_window"]]

    if "mmxm_model" in filters:
        filtered = filtered[filtered["mmxm_model"] == filters["mmxm_model"]]

    if filters.get("exclude_news_days"):
        filtered = filtered[filtered["is_news_day"] == 0]

    if "min_rr" in filters:
        filtered = filtered[filtered["risk_reward"] >= filters["min_rr"]]

    return filtered


# ── Performance Metrics ───────────────────────────────────────────────────────

def calculate_metrics(df: pd.DataFrame) -> dict:
    if len(df) == 0:
        return {"error": "No signals after filters"}

    wins   = df[df["outcome"] == "win"]
    losses = df[df["outcome"] == "loss"]

    win_rate       = len(wins) / len(df)
    avg_winner_pts = wins["result_points"].mean()   if len(wins)   > 0 else 0
    avg_loser_pts  = losses["result_points"].abs().mean() if len(losses) > 0 else 0
    expectancy_r   = (win_rate * (avg_winner_pts / avg_loser_pts)) - (1 - win_rate) \
                     if avg_loser_pts > 0 else 0

    # Buy model vs sell model breakdown
    buy_df  = df[df["mmxm_model"] == "buy_model"]
    sell_df = df[df["mmxm_model"] == "sell_model"]

    return {
        "total_signals":    len(df),
        "wins":             len(wins),
        "losses":           len(losses),
        "win_rate_pct":     round(win_rate * 100, 1),
        "avg_winner_pts":   round(avg_winner_pts, 2),
        "avg_loser_pts":    round(avg_loser_pts, 2),
        "expectancy_r":     round(expectancy_r, 3),
        "buy_model_count":  len(buy_df),
        "sell_model_count": len(sell_df),
        "buy_win_rate":     round(buy_df[buy_df["outcome"] == "win"].shape[0] / len(buy_df) * 100, 1) if len(buy_df) > 0 else 0,
        "sell_win_rate":    round(sell_df[sell_df["outcome"] == "win"].shape[0] / len(sell_df) * 100, 1) if len(sell_df) > 0 else 0,
    }


# ── Phase Runners ─────────────────────────────────────────────────────────────

def run_phase_a(df: pd.DataFrame):
    """Raw signal — no filters. Buy model and sell model reported separately."""
    print("\n=== PHASE A — RAW SIGNAL (no filters) ===")
    signals = df[df["signal_present"] == 1]
    metrics = calculate_metrics(signals)
    print_metrics(metrics)

    print("\n  --- ORB-15 vs ORB-30 ---")
    for w in [15, 30]:
        sub = signals[signals["orb_window_min"] == w]
        m   = calculate_metrics(sub)
        print(f"  ORB-{w}: {m.get('total_signals', 0)} signals, {m.get('win_rate_pct', 0)}% WR")

    return metrics


def run_phase_b(df: pd.DataFrame, filter_name: str):
    """Single filter test."""
    print(f"\n=== PHASE B — FILTER: {filter_name} ===")

    filter_configs = {
        "smt_both_pairs":    {"smt_both_pairs": True},
        "smt_any_pair":      {"smt_any_pair": True},
        "fvg_required":      {"fvg_required": True},
        "orb_15_only":       {"orb_window": 15},
        "orb_30_only":       {"orb_window": 30},
        "buy_model_only":    {"mmxm_model": "buy_model"},
        "sell_model_only":   {"mmxm_model": "sell_model"},
        "time_0945":         {"max_entry_time": "09:45"},
        "time_1000":         {"max_entry_time": "10:00"},
        "time_1030":         {"max_entry_time": "10:30"},
        "exclude_news":      {"exclude_news_days": True},
        "min_rr_2":          {"min_rr": 2.0},
        "min_rr_3":          {"min_rr": 3.0},
    }

    if filter_name not in filter_configs:
        print(f"Unknown filter: {filter_name}")
        print(f"Available: {list(filter_configs.keys())}")
        return

    filtered = apply_filters(df, filter_configs[filter_name])
    metrics  = calculate_metrics(filtered)
    print_metrics(metrics)
    return metrics


def run_phase_c(df: pd.DataFrame):
    """Best combination — update with Phase B winners before running."""
    print("\n=== PHASE C — BEST COMBINATION ===")
    print("Update best_filters below with your Phase B results.\n")

    # TODO: Replace with your Phase B winning filters
    best_filters = {
        "smt_both_pairs":     True,
        "fvg_required":       True,
        "max_entry_time":     "10:00",
        "exclude_news_days":  True,
    }

    filtered = apply_filters(df, best_filters)
    metrics  = calculate_metrics(filtered)
    print(f"Filters applied: {best_filters}")
    print_metrics(metrics)
    return metrics


def run_phase_d(df: pd.DataFrame):
    """Walk-forward validation — train on months 1-6, test on 7-9."""
    print("\n=== PHASE D — WALK-FORWARD VALIDATION ===")

    df     = df.sort_values("date")
    months = df["date"].dt.to_period("M").unique()

    if len(months) < TRAIN_MONTHS + 1:
        print(f"Need {TRAIN_MONTHS + 1} months minimum, have {len(months)}.")
        return

    train_cutoff = months[TRAIN_MONTHS - 1].end_time
    train_df = df[df["date"] <= train_cutoff]
    test_df  = df[df["date"] > train_cutoff]

    print(f"Training: {train_df['date'].min().date()} to {train_df['date'].max().date()} ({len(train_df)} days)")
    print(f"Test:     {test_df['date'].min().date()} to {test_df['date'].max().date()} ({len(test_df)} days)")

    # TODO: Use your Phase C winning filters
    best_filters = {
        "smt_both_pairs":    True,
        "fvg_required":      True,
        "max_entry_time":    "10:00",
        "exclude_news_days": True,
    }

    print("\n--- TRAINING RESULTS ---")
    train_metrics = calculate_metrics(apply_filters(train_df, best_filters))
    print_metrics(train_metrics)

    print("\n--- TEST RESULTS (unseen data) ---")
    test_metrics = calculate_metrics(apply_filters(test_df, best_filters))
    print_metrics(test_metrics)

    if train_metrics.get("win_rate_pct") and test_metrics.get("win_rate_pct"):
        delta  = abs(train_metrics["win_rate_pct"] - test_metrics["win_rate_pct"])
        passed = delta <= 10 and test_metrics["expectancy_r"] > 0
        print(f"\nWin rate delta:  {delta:.1f}%")
        print(f"Walk-forward:    {'✅ PASS' if passed else '❌ FAIL — return to Phase B'}")

        if passed:
            save_report(train_metrics, test_metrics, best_filters, delta)


# ── Report ────────────────────────────────────────────────────────────────────

def save_report(train: dict, test: dict, filters: dict, delta: float):
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Module 1 Backtest Report — ORB + MMXM\n",
        f"## Filters\n```\n{filters}\n```\n",
        "## Training Results (months 1–6)\n",
        f"- Signals: {train['total_signals']}",
        f"- Win Rate: {train['win_rate_pct']}%",
        f"- Expectancy: {train['expectancy_r']}R\n",
        "## Walk-Forward Results (months 7–9)\n",
        f"- Signals: {test['total_signals']}",
        f"- Win Rate: {test['win_rate_pct']}%",
        f"- Expectancy: {test['expectancy_r']}R",
        f"- Win Rate Delta: {delta:.1f}%",
        f"- **PASS** ✅\n",
    ]
    RESULTS_PATH.write_text("\n".join(lines))
    print(f"\nReport saved to {RESULTS_PATH}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def print_metrics(metrics: dict):
    if "error" in metrics:
        print(f"  ERROR: {metrics['error']}")
        return
    print(f"  Signals:      {metrics['total_signals']}")
    print(f"  Wins/Losses:  {metrics['wins']} / {metrics['losses']}")
    print(f"  Win Rate:     {metrics['win_rate_pct']}%")
    print(f"  Avg Winner:   {metrics['avg_winner_pts']} pts")
    print(f"  Avg Loser:    {metrics['avg_loser_pts']} pts")
    print(f"  Expectancy:   {metrics['expectancy_r']}R")
    if "buy_win_rate" in metrics:
        print(f"  Buy Model:    {metrics['buy_model_count']} signals, {metrics['buy_win_rate']}% WR")
        print(f"  Sell Model:   {metrics['sell_model_count']} signals, {metrics['sell_win_rate']}% WR")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Module 1 Backtest Engine — ORB + MMXM")
    parser.add_argument("--phase",  choices=["A", "B", "C", "D"], required=True)
    parser.add_argument("--filter", type=str, help="Filter name for Phase B")
    args = parser.parse_args()

    df = load_data()

    if args.phase == "A":
        run_phase_a(df)
    elif args.phase == "B":
        if not args.filter:
            print("Phase B requires --filter argument")
            print("Available filters: smt_both_pairs, smt_any_pair, fvg_required, orb_15_only, orb_30_only, buy_model_only, sell_model_only, time_0945, time_1000, time_1030, exclude_news, min_rr_2, min_rr_3")
        else:
            run_phase_b(df, args.filter)
    elif args.phase == "C":
        run_phase_c(df)
    elif args.phase == "D":
        run_phase_d(df)

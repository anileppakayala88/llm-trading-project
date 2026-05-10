"""
Module 2 Backtest Engine — PM Range Sweep + SMT
LLM Trading Project

Run this after completing data/processed/module2_features.csv

Usage:
    python backtest_m2.py --phase A
    python backtest_m2.py --phase B --filter smt_both_pairs
    python backtest_m2.py --phase C
    python backtest_m2.py --phase D
"""

import pandas as pd
import numpy as np
import argparse
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

DATA_PATH = Path("../../data/processed/module2_features.csv")
RESULTS_PATH = Path("../../data/backtest_results/module2_report.md")

TRAIN_MONTHS = 6   # Months 1-6 for walk-forward training
TEST_MONTHS = 3    # Months 7-9 for walk-forward test

# ── Load Data ─────────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    print(f"Loaded {len(df)} trading days from {df['date'].min().date()} to {df['date'].max().date()}")
    return df


# ── Signal Filter ─────────────────────────────────────────────────────────────

def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """
    Apply filters to the dataset. Each filter reduces the signal universe.

    Available filters:
        smt_both_pairs: bool — require SMT on both ES AND YM
        min_pm2_volume_ratio: float — minimum PM2 volume vs avg (e.g. 1.0)
        max_entry_time: str — latest ET time for entry (e.g. "10:00")
        exclude_news_days: bool — exclude NFP/FOMC/CPI days
    """
    filtered = df[df["signal_present"] == 1].copy()

    if filters.get("smt_both_pairs"):
        filtered = filtered[filtered["smt_both_pairs"] == 1]

    if "min_pm2_volume_ratio" in filters:
        filtered = filtered[filtered["pm2_volume_ratio"] >= filters["min_pm2_volume_ratio"]]

    if "max_entry_time" in filters:
        filtered = filtered[filtered["entry_time_et"] <= filters["max_entry_time"]]

    if filters.get("exclude_news_days"):
        filtered = filtered[filtered["is_news_day"] == 0]

    return filtered


# ── Performance Metrics ───────────────────────────────────────────────────────

def calculate_metrics(df: pd.DataFrame) -> dict:
    """Calculate win rate, expectancy, and other metrics from signal results."""
    if len(df) == 0:
        return {"error": "No signals in dataset after filters applied"}

    wins = df[df["outcome"] == "win"]
    losses = df[df["outcome"] == "loss"]

    win_rate = len(wins) / len(df) if len(df) > 0 else 0
    avg_winner_pts = wins["result_points"].mean() if len(wins) > 0 else 0
    avg_loser_pts = losses["result_points"].abs().mean() if len(losses) > 0 else 0

    # Expectancy in R (1R = risk per trade)
    expectancy_r = (win_rate * (avg_winner_pts / avg_loser_pts)) - (1 - win_rate) if avg_loser_pts > 0 else 0

    return {
        "total_signals": len(df),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate * 100, 1),
        "avg_winner_pts": round(avg_winner_pts, 2),
        "avg_loser_pts": round(avg_loser_pts, 2),
        "expectancy_r": round(expectancy_r, 3),
    }


# ── Phase Runners ─────────────────────────────────────────────────────────────

def run_phase_a(df: pd.DataFrame):
    """Raw signal — no filters."""
    print("\n=== PHASE A — RAW SIGNAL (no filters) ===")
    signals = df[df["signal_present"] == 1]
    metrics = calculate_metrics(signals)
    print_metrics(metrics)
    return metrics


def run_phase_b(df: pd.DataFrame, filter_name: str):
    """Single filter test."""
    print(f"\n=== PHASE B — FILTER: {filter_name} ===")

    filter_configs = {
        "smt_both_pairs":           {"smt_both_pairs": True},
        "pm2_vol_1.0":              {"min_pm2_volume_ratio": 1.0},
        "pm2_vol_1.2":              {"min_pm2_volume_ratio": 1.2},
        "pm2_vol_1.5":              {"min_pm2_volume_ratio": 1.5},
        "time_window_0945":         {"max_entry_time": "09:45"},
        "time_window_1000":         {"max_entry_time": "10:00"},
        "time_window_1030":         {"max_entry_time": "10:30"},
        "exclude_news":             {"exclude_news_days": True},
    }

    if filter_name not in filter_configs:
        print(f"Unknown filter: {filter_name}")
        print(f"Available: {list(filter_configs.keys())}")
        return

    filtered = apply_filters(df, filter_configs[filter_name])
    metrics = calculate_metrics(filtered)
    print_metrics(metrics)
    return metrics


def run_phase_c(df: pd.DataFrame):
    """Best combination test — hardcode the winning combo from Phase B here."""
    print("\n=== PHASE C — BEST COMBINATION ===")
    print("Update this function with your Phase B winning filters.")

    # TODO: Replace with your Phase B winners
    best_filters = {
        "smt_both_pairs": True,
        "min_pm2_volume_ratio": 1.0,
        "max_entry_time": "10:00",
        "exclude_news_days": True,
    }

    filtered = apply_filters(df, best_filters)
    metrics = calculate_metrics(filtered)
    print(f"Filters applied: {best_filters}")
    print_metrics(metrics)
    return metrics


def run_phase_d(df: pd.DataFrame):
    """Walk-forward validation."""
    print("\n=== PHASE D — WALK-FORWARD VALIDATION ===")

    df = df.sort_values("date")
    months = df["date"].dt.to_period("M").unique()

    if len(months) < TRAIN_MONTHS + 1:
        print(f"Not enough months in dataset. Need {TRAIN_MONTHS + 1}, have {len(months)}.")
        return

    train_cutoff = months[TRAIN_MONTHS - 1].end_time
    train_df = df[df["date"] <= train_cutoff]
    test_df = df[df["date"] > train_cutoff]

    print(f"Training: {train_df['date'].min().date()} to {train_df['date'].max().date()} ({len(train_df)} days)")
    print(f"Test:     {test_df['date'].min().date()} to {test_df['date'].max().date()} ({len(test_df)} days)")

    # TODO: Use your Phase C winning filters here
    best_filters = {
        "smt_both_pairs": True,
        "min_pm2_volume_ratio": 1.0,
        "max_entry_time": "10:00",
        "exclude_news_days": True,
    }

    print("\n--- TRAINING RESULTS ---")
    train_filtered = apply_filters(train_df, best_filters)
    train_metrics = calculate_metrics(train_filtered)
    print_metrics(train_metrics)

    print("\n--- TEST RESULTS (unseen data) ---")
    test_filtered = apply_filters(test_df, best_filters)
    test_metrics = calculate_metrics(test_filtered)
    print_metrics(test_metrics)

    # Walk-forward pass/fail
    if train_metrics.get("win_rate_pct") and test_metrics.get("win_rate_pct"):
        delta = abs(train_metrics["win_rate_pct"] - test_metrics["win_rate_pct"])
        passed = delta <= 10 and test_metrics["expectancy_r"] > 0
        print(f"\nWin rate delta: {delta:.1f}%")
        print(f"Walk-forward: {'✅ PASS' if passed else '❌ FAIL — return to Phase B'}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def print_metrics(metrics: dict):
    if "error" in metrics:
        print(f"  ERROR: {metrics['error']}")
        return
    print(f"  Signals:     {metrics['total_signals']}")
    print(f"  Wins/Losses: {metrics['wins']} / {metrics['losses']}")
    print(f"  Win Rate:    {metrics['win_rate_pct']}%")
    print(f"  Avg Winner:  {metrics['avg_winner_pts']} pts")
    print(f"  Avg Loser:   {metrics['avg_loser_pts']} pts")
    print(f"  Expectancy:  {metrics['expectancy_r']}R")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Module 2 Backtest Engine")
    parser.add_argument("--phase", choices=["A", "B", "C", "D"], required=True)
    parser.add_argument("--filter", type=str, help="Filter name for Phase B")
    args = parser.parse_args()

    df = load_data()

    if args.phase == "A":
        run_phase_a(df)
    elif args.phase == "B":
        if not args.filter:
            print("Phase B requires --filter argument")
        else:
            run_phase_b(df, args.filter)
    elif args.phase == "C":
        run_phase_c(df)
    elif args.phase == "D":
        run_phase_d(df)

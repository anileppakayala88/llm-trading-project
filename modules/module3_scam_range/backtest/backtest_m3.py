"""
Module 3 Backtest Engine — SCAM Range Break + Midpoint Retest
LLM Trading Project

Run after completing data/processed/module3_features.csv

Usage:
    python backtest_m3.py --phase A
    python backtest_m3.py --phase B --filter min_zone_size_10
    python backtest_m3.py --phase C
    python backtest_m3.py --phase D
"""

import pandas as pd
import numpy as np
import argparse
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

DATA_PATH    = Path("../../data/processed/module3_features.csv")
RESULTS_PATH = Path("../../data/backtest_results/module3_report.md")

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
    Filter the signal universe.

    Available filters:
        min_zone_size_pts: float   — minimum zone range in points
        max_zone_size_pts: float   — maximum zone range in points
        min_break_volume: float    — minimum break candle volume ratio vs avg
        max_entry_time: str        — latest ET time for entry (e.g. "10:30")
        break_direction: str       — "bull" | "bear"
        min_rr: float              — minimum risk/reward ratio
        exclude_news_days: bool    — exclude NFP/FOMC/CPI days
        max_retest_bars: int       — maximum bars from break to retest
    """
    filtered = df[df["signal_present"] == 1].copy()

    if "min_zone_size_pts" in filters:
        filtered = filtered[filtered["zone_range_pts"] >= filters["min_zone_size_pts"]]

    if "max_zone_size_pts" in filters:
        filtered = filtered[filtered["zone_range_pts"] <= filters["max_zone_size_pts"]]

    if "min_break_volume" in filters:
        filtered = filtered[filtered["break_volume_ratio"] >= filters["min_break_volume"]]

    if "max_entry_time" in filters:
        filtered = filtered[filtered["entry_time_et"] <= filters["max_entry_time"]]

    if "break_direction" in filters:
        filtered = filtered[filtered["break_direction"] == filters["break_direction"]]

    if "min_rr" in filters:
        filtered = filtered[filtered["risk_reward"] >= filters["min_rr"]]

    if filters.get("exclude_news_days"):
        filtered = filtered[filtered["is_news_day"] == 0]

    if "max_retest_bars" in filters:
        filtered = filtered[filtered["bars_to_retest"] <= filters["max_retest_bars"]]

    return filtered


# ── Performance Metrics ───────────────────────────────────────────────────────

def calculate_metrics(df: pd.DataFrame) -> dict:
    if len(df) == 0:
        return {"error": "No signals after filters"}

    wins   = df[df["outcome"] == "win"]
    losses = df[df["outcome"] == "loss"]

    win_rate       = len(wins) / len(df)
    avg_winner_pts = wins["result_points"].mean()        if len(wins)   > 0 else 0
    avg_loser_pts  = losses["result_points"].abs().mean() if len(losses) > 0 else 0
    expectancy_r   = (win_rate * (avg_winner_pts / avg_loser_pts)) - (1 - win_rate) \
                     if avg_loser_pts > 0 else 0

    bull_df = df[df["break_direction"] == "bull"]
    bear_df = df[df["break_direction"] == "bear"]

    return {
        "total_signals":  len(df),
        "wins":           len(wins),
        "losses":         len(losses),
        "win_rate_pct":   round(win_rate * 100, 1),
        "avg_winner_pts": round(avg_winner_pts, 2),
        "avg_loser_pts":  round(avg_loser_pts, 2),
        "expectancy_r":   round(expectancy_r, 3),
        "avg_rr":         round(df["risk_reward"].mean(), 2) if "risk_reward" in df.columns else None,
        "avg_zone_pts":   round(df["zone_range_pts"].mean(), 2) if "zone_range_pts" in df.columns else None,
        "bull_count":     len(bull_df),
        "bear_count":     len(bear_df),
        "bull_win_rate":  round(bull_df[bull_df["outcome"] == "win"].shape[0] / len(bull_df) * 100, 1) if len(bull_df) > 0 else 0,
        "bear_win_rate":  round(bear_df[bear_df["outcome"] == "win"].shape[0] / len(bear_df) * 100, 1) if len(bear_df) > 0 else 0,
    }


# ── Phase Runners ─────────────────────────────────────────────────────────────

def run_phase_a(df: pd.DataFrame):
    """Raw signal — no filters. Bull and bear breaks reported separately."""
    print("\n=== PHASE A — RAW SIGNAL (no filters) ===")
    signals = df[df["signal_present"] == 1]
    metrics = calculate_metrics(signals)
    print_metrics(metrics)
    return metrics


def run_phase_b(df: pd.DataFrame, filter_name: str):
    """Single filter test."""
    print(f"\n=== PHASE B — FILTER: {filter_name} ===")

    filter_configs = {
        "min_zone_10":       {"min_zone_size_pts": 10.0},
        "min_zone_15":       {"min_zone_size_pts": 15.0},
        "min_zone_20":       {"min_zone_size_pts": 20.0},
        "max_zone_40":       {"max_zone_size_pts": 40.0},
        "break_vol_1.0":     {"min_break_volume": 1.0},
        "break_vol_1.2":     {"min_break_volume": 1.2},
        "time_1000":         {"max_entry_time": "10:00"},
        "time_1030":         {"max_entry_time": "10:30"},
        "time_1100":         {"max_entry_time": "11:00"},
        "bull_only":         {"break_direction": "bull"},
        "bear_only":         {"break_direction": "bear"},
        "min_rr_1.5":        {"min_rr": 1.5},
        "min_rr_2.0":        {"min_rr": 2.0},
        "retest_15bars":     {"max_retest_bars": 15},
        "retest_20bars":     {"max_retest_bars": 20},
        "exclude_news":      {"exclude_news_days": True},
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
        "min_zone_size_pts":  10.0,
        "min_break_volume":   1.0,
        "max_entry_time":     "10:30",
        "min_rr":             1.5,
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
        "min_zone_size_pts":  10.0,
        "min_break_volume":   1.0,
        "max_entry_time":     "10:30",
        "min_rr":             1.5,
        "exclude_news_days":  True,
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
        "# Module 3 Backtest Report — SCAM Range Break + Midpoint Retest\n",
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
    if metrics.get("avg_rr"):
        print(f"  Avg R/R:      {metrics['avg_rr']}")
    if metrics.get("avg_zone_pts"):
        print(f"  Avg Zone:     {metrics['avg_zone_pts']} pts")
    if "bull_count" in metrics:
        print(f"  Bull breaks:  {metrics['bull_count']} signals, {metrics['bull_win_rate']}% WR")
        print(f"  Bear breaks:  {metrics['bear_count']} signals, {metrics['bear_win_rate']}% WR")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Module 3 Backtest Engine — SCAM Range")
    parser.add_argument("--phase",  choices=["A", "B", "C", "D"], required=True)
    parser.add_argument("--filter", type=str, help="Filter name for Phase B")
    args = parser.parse_args()

    df = load_data()

    if args.phase == "A":
        run_phase_a(df)
    elif args.phase == "B":
        if not args.filter:
            print("Phase B requires --filter argument")
            print("Available filters: min_zone_10, min_zone_15, min_zone_20, max_zone_40, break_vol_1.0, break_vol_1.2, time_1000, time_1030, time_1100, bull_only, bear_only, min_rr_1.5, min_rr_2.0, retest_15bars, retest_20bars, exclude_news")
        else:
            run_phase_b(df, args.filter)
    elif args.phase == "C":
        run_phase_c(df)
    elif args.phase == "D":
        run_phase_d(df)

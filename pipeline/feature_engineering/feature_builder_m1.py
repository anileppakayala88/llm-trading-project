"""
Feature Builder — Module 1: ORB + MMXM
LLM Trading Project

Reads aligned_5min.parquet, computes per-day features for Module 1 backtest.
Outputs: data/processed/module1_features.csv

Usage:
    python feature_builder_m1.py
    python feature_builder_m1.py --orb 15     # 15-min ORB only
    python feature_builder_m1.py --orb 30     # 30-min ORB only
"""

import pandas as pd
import numpy as np
import argparse
import datetime
from pathlib import Path

PROCESSED   = Path("../../data/processed")
INPUT_FILE  = PROCESSED / "aligned_5min.parquet"
OUTPUT_FILE = PROCESSED / "module1_features.csv"

# ── Session time boundaries ───────────────────────────────────────────────────
T_PM2_END   = datetime.time(9, 30)
T_ORB15_END = datetime.time(9, 45)
T_ORB30_END = datetime.time(10, 0)
T_PRIMARY   = datetime.time(11, 30)

SWING_LEN   = 3   # pivot detection lookback (bars)


# ── Helpers ───────────────────────────────────────────────────────────────────

def pivot_highs(series: pd.Series, n: int) -> pd.Series:
    """Returns pivot high values; NaN where not a pivot."""
    shifted_left  = [series.shift(i) for i in range(1, n + 1)]
    shifted_right = [series.shift(-i) for i in range(1, n + 1)]
    is_pivot = pd.concat(
        [series > s for s in shifted_left + shifted_right], axis=1
    ).all(axis=1)
    return series.where(is_pivot)


def pivot_lows(series: pd.Series, n: int) -> pd.Series:
    shifted_left  = [series.shift(i) for i in range(1, n + 1)]
    shifted_right = [series.shift(-i) for i in range(1, n + 1)]
    is_pivot = pd.concat(
        [series < s for s in shifted_left + shifted_right], axis=1
    ).all(axis=1)
    return series.where(is_pivot)


def detect_fvg(df_day: pd.DataFrame) -> pd.DataFrame:
    """Add bull_fvg and bear_fvg columns. FVG = 3-candle imbalance."""
    df = df_day.copy()
    df["bull_fvg"] = df["mnq_high"].shift(2) < df["mnq_low"]    # gap above
    df["bear_fvg"] = df["mnq_low"].shift(2)  > df["mnq_high"]   # gap below
    df["fvg_high"] = np.where(df["bull_fvg"], df["mnq_low"],     np.nan)
    df["fvg_low"]  = np.where(df["bull_fvg"], df["mnq_high"].shift(2), np.nan)
    df["fvg_high"] = np.where(df["bear_fvg"], df["mnq_low"].shift(2), df["fvg_high"])
    df["fvg_low"]  = np.where(df["bear_fvg"], df["mnq_high"],   df["fvg_low"])
    return df


def detect_smt(day: pd.DataFrame, pivot_bar_idx: int, side: str) -> dict:
    """
    At pivot_bar_idx, check if MNQ made new extreme while ES/YM held.
    side: 'low' for bullish SMT, 'high' for bearish SMT
    """
    if pivot_bar_idx < 2:
        return {"smt_es": False, "smt_ym": False}

    prior = day.iloc[:pivot_bar_idx]
    curr  = day.iloc[pivot_bar_idx]

    if side == "low":
        mnq_new = curr["mnq_low"] < prior["mnq_low"].min()
        es_new  = curr["es_low"]  < prior["es_low"].min()
        ym_new  = curr["ym_low"]  < prior["ym_low"].min()
    else:
        mnq_new = curr["mnq_high"] > prior["mnq_high"].max()
        es_new  = curr["es_high"]  > prior["es_high"].max()
        ym_new  = curr["ym_high"]  > prior["ym_high"].max()

    return {
        "smt_es": bool(mnq_new and not es_new),
        "smt_ym": bool(mnq_new and not ym_new),
    }


# ── Per-day Feature Extraction ────────────────────────────────────────────────

def process_day(date: datetime.date, day: pd.DataFrame, orb_minutes: int) -> dict:
    row = {"date": date, "orb_window_min": orb_minutes}

    times = day.index.time

    # ── ORB range ─────────────────────────────────────────────────────────────
    orb_end_time = T_ORB15_END if orb_minutes == 15 else T_ORB30_END
    orb_mask     = (times >= T_PM2_END) & (times < orb_end_time)
    orb_bars     = day[orb_mask]

    if orb_bars.empty:
        row["signal_present"] = 0
        return row

    row["orb_high"]  = orb_bars["mnq_high"].max()
    row["orb_low"]   = orb_bars["mnq_low"].min()
    row["orb_range"] = round(row["orb_high"] - row["orb_low"], 2)

    # ── Primary trade window bars (after ORB closes) ──────────────────────────
    primary_mask = (times >= orb_end_time) & (times < T_PRIMARY)
    primary      = day[primary_mask]

    if primary.empty:
        row["signal_present"] = 0
        return row

    # ── Liquidity raid detection (pre-ORB-close or within first few bars) ────
    # Raid = wick through prior swing low/high, close back inside
    pre_orb  = day[times < T_PM2_END]
    if not pre_orb.empty:
        swing_ref_lo = pre_orb["mnq_low"].min()
        swing_ref_hi = pre_orb["mnq_high"].max()
    else:
        swing_ref_lo = row["orb_low"]
        swing_ref_hi = row["orb_high"]

    # Check first 6 primary bars for a raid candle
    raid_detected = False
    raid_side     = None
    raid_time     = None
    raid_bar_idx  = None

    for i, (ts, bar) in enumerate(primary.head(6).iterrows()):
        bull_raid = bar["mnq_low"] < swing_ref_lo and bar["mnq_close"] > swing_ref_lo
        bear_raid = bar["mnq_high"] > swing_ref_hi and bar["mnq_close"] < swing_ref_hi
        if bull_raid:
            raid_detected, raid_side, raid_time = True, "bull", ts.time()
            raid_bar_idx = i
            break
        if bear_raid:
            raid_detected, raid_side, raid_time = True, "bear", ts.time()
            raid_bar_idx = i
            break

    row["raid_detected"] = int(raid_detected)
    row["raid_side"]     = raid_side
    row["raid_time_et"]  = str(raid_time) if raid_time else None
    row["mmxm_model"]    = ("buy_model" if raid_side == "bull" else
                            "sell_model" if raid_side == "bear" else "unclear")

    # ── ORB break detection ───────────────────────────────────────────────────
    orb_break_side     = None
    orb_break_time     = None
    orb_break_bar_idx  = None

    for i, (ts, bar) in enumerate(primary.iterrows()):
        if bar["mnq_close"] > row["orb_high"] and (i == 0 or primary.iloc[i-1]["mnq_close"] <= row["orb_high"]):
            orb_break_side, orb_break_time, orb_break_bar_idx = "bull", ts.time(), i
            break
        if bar["mnq_close"] < row["orb_low"] and (i == 0 or primary.iloc[i-1]["mnq_close"] >= row["orb_low"]):
            orb_break_side, orb_break_time, orb_break_bar_idx = "bear", ts.time(), i
            break

    row["orb_break_side"]      = orb_break_side
    row["orb_break_time_et"]   = str(orb_break_time) if orb_break_time else None
    row["orb_break_confirmed"] = int(orb_break_side is not None)

    if not orb_break_side:
        row["signal_present"] = 0
        return row

    # ── SMT divergence at raid bar ────────────────────────────────────────────
    smt_es, smt_ym = False, False
    if raid_detected and raid_bar_idx is not None:
        full_day_to_raid = day[day.index <= primary.index[min(raid_bar_idx, len(primary)-1)]]
        smt = detect_smt(full_day_to_raid, len(full_day_to_raid) - 1,
                         "low" if raid_side == "bull" else "high")
        smt_es = smt["smt_es"]
        smt_ym = smt["smt_ym"]

    row["smt_es_divergence"] = int(smt_es)
    row["smt_ym_divergence"] = int(smt_ym)
    row["smt_both_pairs"]    = int(smt_es and smt_ym)

    # ── FVG near entry ────────────────────────────────────────────────────────
    day_fvg      = detect_fvg(primary)
    fvg_present  = (day_fvg["bull_fvg"].any() if orb_break_side == "bull"
                    else day_fvg["bear_fvg"].any())
    row["fvg_present"] = int(fvg_present)

    # ── MMXM phase at ORB break ───────────────────────────────────────────────
    if raid_detected and orb_break_bar_idx is not None:
        bars_post_raid = orb_break_bar_idx - (raid_bar_idx or 0)
        if bars_post_raid <= 1:
            mmxm_phase = "raid"
        elif bars_post_raid <= 8:
            mmxm_phase = "accumulation" if row["mmxm_model"] == "buy_model" else "distribution"
        else:
            mmxm_phase = "markup" if row["mmxm_model"] == "buy_model" else "markdown"
    else:
        mmxm_phase = "markup" if orb_break_side == "bull" else "markdown"

    row["mmxm_phase"] = mmxm_phase

    # ── Entry / Stop / Target levels ──────────────────────────────────────────
    if orb_break_bar_idx is not None:
        entry_bar = primary.iloc[orb_break_bar_idx]
        row["entry_price"]    = entry_bar["mnq_close"]
        row["entry_time_et"]  = str(primary.index[orb_break_bar_idx].time())
    else:
        row["entry_price"]   = None
        row["entry_time_et"] = None

    if orb_break_side == "bull":
        row["stop_price"]   = row["orb_low"]
        row["target_price"] = row["entry_price"] + (row["orb_range"] * 2) if row.get("entry_price") else None
    else:
        row["stop_price"]   = row["orb_high"]
        row["target_price"] = row["entry_price"] - (row["orb_range"] * 2) if row.get("entry_price") else None

    if row.get("entry_price") and row.get("stop_price"):
        risk   = abs(row["entry_price"] - row["stop_price"])
        reward = abs(row.get("target_price", 0) - row["entry_price"]) if row.get("target_price") else 0
        row["risk_reward"] = round(reward / risk, 2) if risk > 0 else None
    else:
        row["risk_reward"] = None

    # ── Signal present: break confirmed + model aligned ───────────────────────
    model_match = (
        (orb_break_side == "bull" and row["mmxm_model"] == "buy_model") or
        (orb_break_side == "bear" and row["mmxm_model"] == "sell_model")
    )
    row["signal_present"] = int(model_match)

    # ── Outcome: measured against target and stop (to be filled manually or via replay) ─
    # Forward-fill from primary bars after entry
    row["outcome"]       = "unknown"
    row["result_points"] = None

    if orb_break_bar_idx is not None and row.get("entry_price"):
        post_entry = primary.iloc[orb_break_bar_idx + 1:]
        for _, bar in post_entry.iterrows():
            if orb_break_side == "bull":
                if bar["mnq_high"] >= row["target_price"]:
                    row["outcome"]       = "win"
                    row["result_points"] = round(row["target_price"] - row["entry_price"], 2)
                    break
                if bar["mnq_low"] <= row["stop_price"]:
                    row["outcome"]       = "loss"
                    row["result_points"] = round(row["stop_price"] - row["entry_price"], 2)
                    break
            else:
                if bar["mnq_low"] <= row["target_price"]:
                    row["outcome"]       = "win"
                    row["result_points"] = round(row["entry_price"] - row["target_price"], 2)
                    break
                if bar["mnq_high"] >= row["stop_price"]:
                    row["outcome"]       = "loss"
                    row["result_points"] = round(row["entry_price"] - row["stop_price"], 2)
                    break

    row["is_news_day"] = 0  # populated externally via news calendar

    return row


# ── Main ──────────────────────────────────────────────────────────────────────

def main(orb_minutes: int = None):
    print(f"Loading {INPUT_FILE}...")
    df = pd.read_parquet(INPUT_FILE)
    df.index = pd.to_datetime(df.index)

    orb_windows = [orb_minutes] if orb_minutes else [15, 30]
    records     = []

    trading_days = df.groupby(df.index.date)
    print(f"Processing {len(trading_days)} trading days...")

    for date, day in trading_days:
        if day.index.dayofweek[0] >= 5:  # skip weekends
            continue
        for orb_w in orb_windows:
            try:
                rec = process_day(date, day, orb_w)
                records.append(rec)
            except Exception as e:
                print(f"  Warning: {date} ORB-{orb_w} failed — {e}")

    out = pd.DataFrame(records)
    out = out.sort_values(["date", "orb_window_min"]).reset_index(drop=True)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT_FILE, index=False)

    signals = out[out["signal_present"] == 1]
    print(f"\nDone. {len(out)} day-rows written to {OUTPUT_FILE}")
    print(f"Signals present: {len(signals)} ({len(signals)/len(out)*100:.1f}% of days)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Module 1 Feature Builder")
    parser.add_argument("--orb", type=int, choices=[15, 30],
                        help="ORB window in minutes (default: both)")
    args = parser.parse_args()
    main(args.orb)

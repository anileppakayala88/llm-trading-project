"""
Feature Builder — Module 2: PM Range Sweep + SMT
LLM Trading Project

Reads aligned_5min.parquet, computes per-day features for Module 2 backtest.
Outputs: data/processed/module2_features.csv

Usage:
    python feature_builder_m2.py
"""

import pandas as pd
import numpy as np
import datetime
from pathlib import Path

PROCESSED   = Path("../../data/processed")
INPUT_FILE  = PROCESSED / "aligned_5min.parquet"
OUTPUT_FILE = PROCESSED / "module2_features.csv"

# Session boundaries
T_PM1_START = datetime.time(7, 0)
T_PM1_END   = datetime.time(8, 30)
T_PM2_START = datetime.time(8, 30)
T_PM2_END   = datetime.time(9, 30)
T_PRIMARY   = datetime.time(11, 30)
T_CUTOFF    = datetime.time(10, 30)  # latest valid sweep time

SWEEP_MIN_PTS = 2.0   # minimum wick extension beyond level


# ── Per-day Feature Extraction ────────────────────────────────────────────────

def process_day(date: datetime.date, day: pd.DataFrame) -> dict:
    row   = {"date": date}
    times = day.index.time

    # ── PM1 range ─────────────────────────────────────────────────────────────
    pm1 = day[(times >= T_PM1_START) & (times < T_PM1_END)]
    pm2 = day[(times >= T_PM2_START) & (times < T_PM2_END)]

    if pm1.empty or pm2.empty:
        row["signal_present"] = 0
        return row

    row["pm1_high"]  = pm1["mnq_high"].max()
    row["pm1_low"]   = pm1["mnq_low"].min()
    row["pm1_range"] = round(row["pm1_high"] - row["pm1_low"], 2)

    row["pm2_high"]  = pm2["mnq_high"].max()
    row["pm2_low"]   = pm2["mnq_low"].min()
    row["pm2_range"] = round(row["pm2_high"] - row["pm2_low"], 2)

    # PM2 volume ratio vs PM1 volume (proxy for average)
    pm2_vol = pm2["mnq_volume"].sum() if "mnq_volume" in pm2.columns else 0
    pm1_vol = pm1["mnq_volume"].sum() if "mnq_volume" in pm1.columns else 1
    row["pm2_volume_ratio"] = round(pm2_vol / pm1_vol, 3) if pm1_vol > 0 else None

    # ── Post-open bars ────────────────────────────────────────────────────────
    primary = day[(times >= T_PM2_END) & (times < T_PRIMARY)]

    if primary.empty:
        row["signal_present"] = 0
        return row

    # Compute running session extremes (reset at 09:30)
    primary = primary.copy()
    primary["sess_lo_mnq"] = primary["mnq_low"].cummin()
    primary["sess_lo_es"]  = primary["es_low"].cummin()
    primary["sess_lo_ym"]  = primary["ym_low"].cummin()
    primary["sess_hi_mnq"] = primary["mnq_high"].cummax()
    primary["sess_hi_es"]  = primary["es_high"].cummax()
    primary["sess_hi_ym"]  = primary["ym_high"].cummax()

    # ── Sweep detection ───────────────────────────────────────────────────────
    levels = {
        "pm2_low":  row["pm2_low"],
        "pm1_low":  row["pm1_low"],
        "pm2_high": row["pm2_high"],
        "pm1_high": row["pm1_high"],
    }

    sweep_detected = False
    sweep_side     = None
    sweep_level    = None
    sweep_time     = None
    smt_es         = False
    smt_ym         = False

    for i, (ts, bar) in enumerate(primary.iterrows()):
        t = ts.time()
        if t >= T_CUTOFF:
            break

        prior_lo_mnq = primary["sess_lo_mnq"].iloc[i-1] if i > 0 else bar["mnq_low"]
        prior_lo_es  = primary["sess_lo_es"].iloc[i-1]  if i > 0 else bar["es_low"]
        prior_lo_ym  = primary["sess_lo_ym"].iloc[i-1]  if i > 0 else bar["ym_low"]
        prior_hi_mnq = primary["sess_hi_mnq"].iloc[i-1] if i > 0 else bar["mnq_high"]
        prior_hi_es  = primary["sess_hi_es"].iloc[i-1]  if i > 0 else bar["es_high"]
        prior_hi_ym  = primary["sess_hi_ym"].iloc[i-1]  if i > 0 else bar["ym_high"]

        # Bull sweep (low side): wick below level, close back inside
        for lvl_name, lvl_val in [("pm2_low", levels["pm2_low"]), ("pm1_low", levels["pm1_low"])]:
            if bar["mnq_low"] < lvl_val - SWEEP_MIN_PTS and bar["mnq_close"] > lvl_val:
                mnq_new_lo = bar["mnq_low"] < prior_lo_mnq
                es_no_new  = bar["es_low"]  >= prior_lo_es
                ym_no_new  = bar["ym_low"]  >= prior_lo_ym
                sweep_detected = True
                sweep_side     = "bull_sweep"
                sweep_level    = lvl_name
                sweep_time     = t
                smt_es         = bool(mnq_new_lo and es_no_new)
                smt_ym         = bool(mnq_new_lo and ym_no_new)
                break

        if sweep_detected:
            break

        # Bear sweep (high side): wick above level, close back inside
        for lvl_name, lvl_val in [("pm2_high", levels["pm2_high"]), ("pm1_high", levels["pm1_high"])]:
            if bar["mnq_high"] > lvl_val + SWEEP_MIN_PTS and bar["mnq_close"] < lvl_val:
                mnq_new_hi = bar["mnq_high"] > prior_hi_mnq
                es_no_new  = bar["es_high"]  <= prior_hi_es
                ym_no_new  = bar["ym_high"]  <= prior_hi_ym
                sweep_detected = True
                sweep_side     = "bear_sweep"
                sweep_level    = lvl_name
                sweep_time     = t
                smt_es         = bool(mnq_new_hi and es_no_new)
                smt_ym         = bool(mnq_new_hi and ym_no_new)
                break

        if sweep_detected:
            break

    row["sweep_detected"]    = int(sweep_detected)
    row["sweep_side"]        = sweep_side
    row["sweep_level"]       = sweep_level
    row["sweep_time_et"]     = str(sweep_time) if sweep_time else None
    row["smt_es_divergence"] = int(smt_es)
    row["smt_ym_divergence"] = int(smt_ym)
    row["smt_both_pairs"]    = int(smt_es and smt_ym)

    # ── Directional expansion detection ───────────────────────────────────────
    expansion_detected  = False
    expansion_direction = None

    for i, (ts, bar) in enumerate(primary.iterrows()):
        if ts.time() >= T_CUTOFF:
            break
        prev_close = primary["mnq_close"].iloc[i-1] if i > 0 else bar["mnq_close"]

        bull_exp = (bar["mnq_close"] > levels["pm2_high"] and prev_close <= levels["pm2_high"] and
                    bar["es_high"] > levels["pm2_high"] and bar["ym_high"] > levels["pm2_high"])
        bear_exp = (bar["mnq_close"] < levels["pm2_low"] and prev_close >= levels["pm2_low"] and
                    bar["es_low"] < levels["pm2_low"] and bar["ym_low"] < levels["pm2_low"])

        if bull_exp:
            expansion_detected, expansion_direction = True, "bull"
            break
        if bear_exp:
            expansion_detected, expansion_direction = True, "bear"
            break

    row["expansion_detected"]  = int(expansion_detected)
    row["expansion_direction"] = expansion_direction

    # ── Signal classification ─────────────────────────────────────────────────
    sweep_reversal = sweep_detected and smt_es and smt_ym
    dir_expansion  = expansion_detected

    if sweep_reversal:
        row["signal_type"] = "sweep_reversal"
    elif dir_expansion:
        row["signal_type"] = "directional_expansion"
    else:
        row["signal_type"] = "no_signal"

    row["signal_present"] = int(sweep_reversal or dir_expansion)

    # ── Entry / Stop / Target ─────────────────────────────────────────────────
    if sweep_reversal and sweep_time:
        sweep_bar = primary[primary.index.time == sweep_time]
        if not sweep_bar.empty:
            sb = sweep_bar.iloc[0]
            row["entry_time_et"] = str(sweep_time)
            row["entry_price"]   = round(sb["mnq_close"], 2)

            if sweep_side == "bull_sweep":
                wick_extreme         = sb["mnq_low"]
                row["stop_price"]    = round(wick_extreme - 2.0, 2)
                opp_level            = levels.get("pm2_high", row["pm2_high"])
                row["target_price"]  = round(opp_level, 2)
            else:
                wick_extreme         = sb["mnq_high"]
                row["stop_price"]    = round(wick_extreme + 2.0, 2)
                opp_level            = levels.get("pm2_low", row["pm2_low"])
                row["target_price"]  = round(opp_level, 2)

            risk   = abs(row["entry_price"] - row["stop_price"])
            reward = abs(row["target_price"] - row["entry_price"])
            row["risk_reward"] = round(reward / risk, 2) if risk > 0 else None
        else:
            row["entry_price"] = row["stop_price"] = row["target_price"] = row["risk_reward"] = None
    else:
        row["entry_price"] = row["stop_price"] = row["target_price"] = row["risk_reward"] = None
        row["entry_time_et"] = None

    # ── Outcome simulation ────────────────────────────────────────────────────
    row["outcome"]       = "unknown"
    row["result_points"] = None

    if (row["signal_present"] and row.get("entry_price") and row.get("stop_price")
            and row.get("target_price") and sweep_time):
        post = primary[primary.index.time > sweep_time]
        ep, sp, tp = row["entry_price"], row["stop_price"], row["target_price"]
        for _, bar in post.iterrows():
            if sweep_side == "bull_sweep":
                if bar["mnq_high"] >= tp:
                    row["outcome"] = "win";  row["result_points"] = round(tp - ep, 2); break
                if bar["mnq_low"]  <= sp:
                    row["outcome"] = "loss"; row["result_points"] = round(sp - ep, 2); break
            else:
                if bar["mnq_low"]  <= tp:
                    row["outcome"] = "win";  row["result_points"] = round(ep - tp, 2); break
                if bar["mnq_high"] >= sp:
                    row["outcome"] = "loss"; row["result_points"] = round(ep - sp, 2); break

    row["is_news_day"] = 0
    return row


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Loading {INPUT_FILE}...")
    df = pd.read_parquet(INPUT_FILE)
    df.index = pd.to_datetime(df.index)

    records      = []
    trading_days = df.groupby(df.index.date)
    print(f"Processing {len(trading_days)} trading days...")

    for date, day in trading_days:
        if day.index.dayofweek[0] >= 5:
            continue
        try:
            records.append(process_day(date, day))
        except Exception as e:
            print(f"  Warning: {date} failed — {e}")

    out = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT_FILE, index=False)

    signals = out[out["signal_present"] == 1]
    print(f"\nDone. {len(out)} days written to {OUTPUT_FILE}")
    print(f"Signals: {len(signals)} ({len(signals)/len(out)*100:.1f}% of days)")
    print(f"  Sweep reversals:   {(out['signal_type'] == 'sweep_reversal').sum()}")
    print(f"  Dir. expansions:   {(out['signal_type'] == 'directional_expansion').sum()}")


if __name__ == "__main__":
    main()

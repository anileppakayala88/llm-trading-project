"""
Feature Builder — Module 3: SCAM Range Break + Midpoint Retest
LLM Trading Project

Reads aligned_5min.parquet, computes per-day features for Module 3 backtest.
Outputs: data/processed/module3_features.csv

Usage:
    python feature_builder_m3.py
"""

import pandas as pd
import numpy as np
import datetime
from pathlib import Path

PROCESSED   = Path("../../data/processed")
INPUT_FILE  = PROCESSED / "aligned_5min.parquet"
OUTPUT_FILE = PROCESSED / "module3_features.csv"

T_NY_OPEN   = datetime.time(9, 30)
T_PRIMARY   = datetime.time(11, 30)

SWING_LEN       = 3      # pivot lookback bars
ZONE_MAX_ATR    = 3.0    # zone must be narrower than N * ATR
BREAK_MIN_PTS   = 1.0    # close must exceed zone by this many points
RETEST_TOL_PTS  = 1.0    # midpoint tolerance in points
RETEST_MAX_BARS = 30     # max bars from break to retest


def pivot_highs(series: pd.Series, n: int) -> pd.Series:
    shifted = [series.shift(i) for i in range(1, n + 1)] + [series.shift(-i) for i in range(1, n + 1)]
    return series.where(pd.concat([series > s for s in shifted], axis=1).all(axis=1))


def pivot_lows(series: pd.Series, n: int) -> pd.Series:
    shifted = [series.shift(i) for i in range(1, n + 1)] + [series.shift(-i) for i in range(1, n + 1)]
    return series.where(pd.concat([series < s for s in shifted], axis=1).all(axis=1))


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([
        df["mnq_high"] - df["mnq_low"],
        (df["mnq_high"] - df["mnq_close"].shift()).abs(),
        (df["mnq_low"]  - df["mnq_close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def process_day(date: datetime.date, day: pd.DataFrame) -> list[dict]:
    """Can return multiple records if multiple zones break in one day."""
    times   = day.index.time
    primary = day[(times >= T_NY_OPEN) & (times < T_PRIMARY)].copy()

    if len(primary) < 10:
        return []

    # Compute ATR and pivots on the full day
    atr14    = atr(day).reindex(primary.index).ffill()
    ph       = pivot_highs(primary["mnq_high"], SWING_LEN)
    pl       = pivot_lows(primary["mnq_low"],   SWING_LEN)

    records = []

    # Track last confirmed swing high and low
    last_sh = last_sl = None
    last_sh_idx = last_sl_idx = None

    # Track active break state
    break_dir    = None
    brk_top      = brk_bot = brk_mid = None
    brk_bar_idx  = None
    brk_time     = None
    brk_vol_ratio = None

    avg_vol = primary["mnq_volume"].mean() if "mnq_volume" in primary.columns else 1

    for i, (ts, bar) in enumerate(primary.iterrows()):
        t = ts.time()

        # Update pivots
        if not pd.isna(ph.iloc[i]):
            last_sh     = ph.iloc[i]
            last_sh_idx = i
        if not pd.isna(pl.iloc[i]):
            last_sl     = pl.iloc[i]
            last_sl_idx = i

        # Zone validity check
        if last_sh is None or last_sl is None:
            continue

        zone_range  = last_sh - last_sl
        pivot_gap   = abs((last_sh_idx or 0) - (last_sl_idx or 0))
        avg_atr     = atr14.iloc[i] if not pd.isna(atr14.iloc[i]) else zone_range
        zone_valid  = zone_range > 0 and zone_range < avg_atr * ZONE_MAX_ATR and pivot_gap < 50

        if not zone_valid:
            continue

        zone_top = last_sh
        zone_bot = last_sl
        zone_mid = (zone_top + zone_bot) / 2

        # ── Break detection ───────────────────────────────────────────────────
        if break_dir is None:
            prev_close = primary["mnq_close"].iloc[i-1] if i > 0 else bar["mnq_close"]

            bull_break = (bar["mnq_close"] > zone_top + BREAK_MIN_PTS and
                          prev_close <= zone_top and t < T_PRIMARY)
            bear_break = (bar["mnq_close"] < zone_bot - BREAK_MIN_PTS and
                          prev_close >= zone_bot and t < T_PRIMARY)

            if bull_break or bear_break:
                break_dir    = "bull" if bull_break else "bear"
                brk_top      = zone_top
                brk_bot      = zone_bot
                brk_mid      = zone_mid
                brk_bar_idx  = i
                brk_time     = t
                bar_vol      = bar["mnq_volume"] if "mnq_volume" in bar.index else avg_vol
                brk_vol_ratio = round(bar_vol / avg_vol, 3) if avg_vol > 0 else None
            continue

        # ── Retest detection (after break) ───────────────────────────────────
        if break_dir is not None and brk_bar_idx is not None:
            bars_since = i - brk_bar_idx

            if bars_since > RETEST_MAX_BARS:
                # Retest window expired — log as no-retest signal and reset
                records.append(_build_record(
                    date, break_dir, brk_top, brk_bot, brk_mid,
                    brk_time, brk_vol_ratio, avg_vol,
                    retest_triggered=False,
                    entry_bar=None, primary=primary, avg_vol=avg_vol
                ))
                break_dir = brk_top = brk_bot = brk_mid = brk_bar_idx = brk_time = None
                continue

            # Zone reclaimed check (invalidation)
            if break_dir == "bull" and bar["mnq_close"] < brk_bot:
                break_dir = brk_top = brk_bot = brk_mid = brk_bar_idx = brk_time = None
                continue
            if break_dir == "bear" and bar["mnq_close"] > brk_top:
                break_dir = brk_top = brk_bot = brk_mid = brk_bar_idx = brk_time = None
                continue

            # Retest condition
            bull_retest = (break_dir == "bull" and
                           bar["mnq_low"] <= brk_mid + RETEST_TOL_PTS and
                           bar["mnq_low"] >= brk_mid - RETEST_TOL_PTS and
                           bar["mnq_close"] > brk_bot)
            bear_retest = (break_dir == "bear" and
                           bar["mnq_high"] >= brk_mid - RETEST_TOL_PTS and
                           bar["mnq_high"] <= brk_mid + RETEST_TOL_PTS and
                           bar["mnq_close"] < brk_top)

            if bull_retest or bear_retest:
                rec = _build_record(
                    date, break_dir, brk_top, brk_bot, brk_mid,
                    brk_time, brk_vol_ratio, avg_vol,
                    retest_triggered=True,
                    entry_bar=(ts, bar), primary=primary, avg_vol=avg_vol
                )
                rec["bars_to_retest"] = bars_since
                rec["retest_time_et"] = str(t)
                records.append(rec)
                break_dir = brk_top = brk_bot = brk_mid = brk_bar_idx = brk_time = None

    return records


def _build_record(date, break_dir, brk_top, brk_bot, brk_mid,
                  brk_time, brk_vol_ratio, avg_vol,
                  retest_triggered, entry_bar, primary, avg_vol_):
    row = {
        "date":             date,
        "zone_top":         round(brk_top, 2),
        "zone_bottom":      round(brk_bot, 2),
        "zone_midpoint":    round(brk_mid, 2),
        "zone_range_pts":   round(brk_top - brk_bot, 2),
        "break_direction":  break_dir,
        "break_confirmed":  1,
        "break_time_et":    str(brk_time) if brk_time else None,
        "break_volume_ratio": brk_vol_ratio,
        "retest_triggered": int(retest_triggered),
        "retest_time_et":   None,
        "bars_to_retest":   None,
        "signal_present":   int(retest_triggered),
        "outcome":          "unknown",
        "result_points":    None,
        "is_news_day":      0,
    }

    if retest_triggered and entry_bar is not None:
        ts, bar  = entry_bar
        ep       = round(bar["mnq_close"], 2)
        sp       = round(brk_bot if break_dir == "bull" else brk_top, 2)
        tp       = round(brk_top if break_dir == "bull" else brk_bot, 2)
        risk     = abs(ep - sp)
        reward   = abs(tp - ep)

        row["entry_price"]   = ep
        row["stop_price"]    = sp
        row["target_price"]  = tp
        row["risk_reward"]   = round(reward / risk, 2) if risk > 0 else None
        row["entry_time_et"] = str(ts.time())

        # Simulate outcome from bars after entry
        post = primary[primary.index > ts]
        for _, b in post.iterrows():
            if break_dir == "bull":
                if b["mnq_high"] >= tp: row["outcome"] = "win";  row["result_points"] = round(tp - ep, 2); break
                if b["mnq_low"]  <= sp: row["outcome"] = "loss"; row["result_points"] = round(sp - ep, 2); break
            else:
                if b["mnq_low"]  <= tp: row["outcome"] = "win";  row["result_points"] = round(ep - tp, 2); break
                if b["mnq_high"] >= sp: row["outcome"] = "loss"; row["result_points"] = round(ep - sp, 2); break
    else:
        row["entry_price"] = row["stop_price"] = row["target_price"] = row["risk_reward"] = row["entry_time_et"] = None

    return row


def main():
    print(f"Loading {INPUT_FILE}...")
    df = pd.read_parquet(INPUT_FILE)
    df.index = pd.to_datetime(df.index)

    all_records  = []
    trading_days = df.groupby(df.index.date)
    print(f"Processing {len(trading_days)} trading days...")

    for date, day in trading_days:
        if day.index.dayofweek[0] >= 5:
            continue
        try:
            recs = process_day(date, day)
            all_records.extend(recs)
        except Exception as e:
            print(f"  Warning: {date} failed — {e}")

    out = pd.DataFrame(all_records).sort_values("date").reset_index(drop=True)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT_FILE, index=False)

    signals = out[out["signal_present"] == 1]
    print(f"\nDone. {len(out)} zone events written to {OUTPUT_FILE}")
    print(f"Retest signals: {len(signals)}")
    if len(signals):
        print(f"  Bull retests: {(signals['break_direction'] == 'bull').sum()}")
        print(f"  Bear retests: {(signals['break_direction'] == 'bear').sum()}")


if __name__ == "__main__":
    main()

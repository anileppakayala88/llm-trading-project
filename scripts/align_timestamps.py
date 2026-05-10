"""
scripts/align_timestamps.py
LLM Trading Project

Aligns MNQ1!, ES1!, and YM1! CSV exports from TradingView
to a common ET timestamp index. Outputs a merged CSV per instrument
and a multi-instrument aligned parquet file.

Usage:
    python align_timestamps.py

Prerequisites:
    - data/raw/MNQ1_5min.csv
    - data/raw/ES1_5min.csv
    - data/raw/YM1_5min.csv

TradingView CSV export format expected:
    time, open, high, low, close, volume
"""

import pandas as pd
from pathlib import Path
import pytz

RAW = Path("../data/raw")
PROCESSED = Path("../data/processed")
PROCESSED.mkdir(parents=True, exist_ok=True)

ET = pytz.timezone("America/New_York")

INSTRUMENTS = {
    "MNQ": RAW / "MNQ1_5min.csv",
    "ES":  RAW / "ES1_5min.csv",
    "YM":  RAW / "YM1_5min.csv",
}

# ── Load ──────────────────────────────────────────────────────────────────────

def load_csv(path: Path, instrument: str) -> pd.DataFrame:
    print(f"Loading {instrument} from {path}...")
    df = pd.read_csv(path)

    # TradingView exports 'time' as Unix timestamp or datetime string
    if df["time"].dtype == "int64" or df["time"].dtype == "float64":
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    else:
        df["time"] = pd.to_datetime(df["time"], utc=True)

    # Convert to ET
    df["time"] = df["time"].dt.tz_convert(ET)
    df = df.set_index("time")
    df.columns = [f"{instrument.lower()}_{col}" for col in df.columns]
    df.index.name = "datetime_et"

    print(f"  {instrument}: {len(df)} bars from {df.index.min()} to {df.index.max()}")
    return df


# ── Align ─────────────────────────────────────────────────────────────────────

def align_instruments(dfs: dict) -> pd.DataFrame:
    print("\nAligning instruments on common timestamps...")

    # Inner join — only keep bars where all 3 have data
    aligned = pd.concat(dfs.values(), axis=1, join="inner")
    print(f"Aligned: {len(aligned)} bars")

    # Filter to trading hours only: 07:00–16:00 ET
    aligned = aligned.between_time("07:00", "16:00")
    print(f"After trading hours filter: {len(aligned)} bars")

    return aligned


# ── Session Labeling ──────────────────────────────────────────────────────────

def label_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Add session labels to each bar."""
    times = df.index.time
    import datetime

    pm1_start = datetime.time(7, 0)
    pm1_end   = datetime.time(8, 30)
    pm2_start = datetime.time(8, 30)
    pm2_end   = datetime.time(9, 30)
    orb_end   = datetime.time(10, 0)
    primary_end = datetime.time(11, 30)

    def get_session(t):
        if pm1_start <= t < pm1_end:   return "PM1"
        if pm2_start <= t < pm2_end:   return "PM2"
        if pm2_end   <= t < orb_end:   return "ORB"
        if orb_end   <= t < primary_end: return "PRIMARY"
        return "OTHER"

    df["session"] = [get_session(t) for t in times]
    return df


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    dfs = {}
    for instrument, path in INSTRUMENTS.items():
        if not path.exists():
            print(f"WARNING: {path} not found — skipping {instrument}")
            continue
        dfs[instrument] = load_csv(path, instrument)

    if len(dfs) == 0:
        print("No data files found. Export CSVs from TradingView first.")
        print("Expected files:")
        for path in INSTRUMENTS.values():
            print(f"  {path}")
        return

    aligned = align_instruments(dfs)
    aligned = label_sessions(aligned)

    # Save aligned data
    output_csv = PROCESSED / "aligned_5min.csv"
    output_parquet = PROCESSED / "aligned_5min.parquet"

    aligned.to_csv(output_csv)
    aligned.to_parquet(output_parquet)

    print(f"\nSaved aligned data:")
    print(f"  CSV:     {output_csv}")
    print(f"  Parquet: {output_parquet}")
    print(f"\nDate range: {aligned.index.min().date()} to {aligned.index.max().date()}")
    print(f"Total bars: {len(aligned)}")
    print(f"\nColumns: {list(aligned.columns)}")


if __name__ == "__main__":
    main()

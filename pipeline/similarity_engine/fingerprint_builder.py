"""
Fingerprint Builder — Similarity Engine
LLM Trading Project

Converts a day's feature row into a normalized numeric vector (fingerprint)
used for cosine similarity search against historical days.

Each module produces a different fingerprint schema. The combined fingerprint
merges all three modules' features into one vector for cross-module similarity.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional


# ── Fingerprint Schemas ───────────────────────────────────────────────────────
# Each schema defines which fields are included and their relative weights.
# Higher weight = more influence on similarity score.

MODULE1_FIELDS = {
    # ORB structure
    "orb_range":           1.5,
    "orb_break_confirmed": 1.0,
    # MMXM — one-hot encoded: buy_model=1, sell_model=-1, unclear=0
    "mmxm_direction":      2.0,
    "raid_detected":       1.5,
    # SMT
    "smt_es_divergence":   2.0,
    "smt_ym_divergence":   2.0,
    "smt_both_pairs":      1.0,
    "fvg_present":         1.0,
}

MODULE2_FIELDS = {
    "pm1_range":            1.0,
    "pm2_range":            1.0,
    "pm2_volume_ratio":     1.5,
    "sweep_detected":       2.0,
    # sweep direction: bull_sweep=1, bear_sweep=-1, none=0
    "sweep_direction_enc":  1.5,
    "smt_es_divergence":    2.0,
    "smt_ym_divergence":    2.0,
    "smt_both_pairs":       1.0,
    "expansion_detected":   1.5,
}

MODULE3_FIELDS = {
    "zone_range_pts":       1.0,
    "break_confirmed":      2.0,
    # break direction: bull=1, bear=-1
    "break_direction_enc":  1.5,
    "break_volume_ratio":   1.0,
    "retest_triggered":     2.0,
    "risk_reward":          1.5,
}

# Combined fingerprint (all modules together, for cross-module similarity)
COMBINED_FIELDS = {**MODULE1_FIELDS, **MODULE2_FIELDS, **MODULE3_FIELDS}


@dataclass
class Fingerprint:
    date: str
    vector: np.ndarray
    field_names: list[str]
    weights: np.ndarray
    module: str = "combined"
    raw: dict = field(default_factory=dict)


# ── Encoders ──────────────────────────────────────────────────────────────────

def encode_mmxm_direction(row: dict) -> float:
    m = row.get("mmxm_model", "unclear")
    return 1.0 if m == "buy_model" else -1.0 if m == "sell_model" else 0.0


def encode_sweep_direction(row: dict) -> float:
    s = row.get("sweep_side", None)
    return 1.0 if s == "bull_sweep" else -1.0 if s == "bear_sweep" else 0.0


def encode_break_direction(row: dict) -> float:
    d = row.get("break_direction", None)
    return 1.0 if d == "bull" else -1.0 if d == "bear" else 0.0


# ── Normalization Stats ───────────────────────────────────────────────────────

def compute_normalization_stats(df: pd.DataFrame, fields: list[str]) -> dict:
    """Compute mean and std for each field across historical data."""
    stats = {}
    for f in fields:
        if f in df.columns:
            col = df[f].dropna()
            stats[f] = {"mean": col.mean(), "std": col.std() if col.std() > 0 else 1.0}
        else:
            stats[f] = {"mean": 0.0, "std": 1.0}
    return stats


def normalize_value(val: float, mean: float, std: float) -> float:
    if pd.isna(val):
        return 0.0
    return (val - mean) / std


# ── Fingerprint Construction ──────────────────────────────────────────────────

def build_fingerprint(
    row: dict,
    module: str,
    norm_stats: dict,
) -> Fingerprint:
    """
    Convert a feature row dict into a weighted, normalized fingerprint vector.

    Args:
        row: dict of feature values for one trading day
        module: "m1" | "m2" | "m3" | "combined"
        norm_stats: normalization stats from compute_normalization_stats()

    Returns:
        Fingerprint with normalized, weighted vector
    """
    if module == "m1":
        schema = MODULE1_FIELDS
    elif module == "m2":
        schema = MODULE2_FIELDS
    elif module == "m3":
        schema = MODULE3_FIELDS
    else:
        schema = COMBINED_FIELDS

    # Encode derived fields
    encoded_row = dict(row)
    encoded_row["mmxm_direction"]       = encode_mmxm_direction(row)
    encoded_row["sweep_direction_enc"]  = encode_sweep_direction(row)
    encoded_row["break_direction_enc"]  = encode_break_direction(row)

    field_names = list(schema.keys())
    weights     = np.array(list(schema.values()), dtype=float)
    vector      = np.zeros(len(field_names))

    for i, fname in enumerate(field_names):
        raw_val = encoded_row.get(fname, np.nan)
        stats   = norm_stats.get(fname, {"mean": 0.0, "std": 1.0})
        vector[i] = normalize_value(
            float(raw_val) if not pd.isna(raw_val) else np.nan,
            stats["mean"], stats["std"]
        )

    # Apply weights
    weighted_vector = vector * weights

    return Fingerprint(
        date=str(row.get("date", "")),
        vector=weighted_vector,
        field_names=field_names,
        weights=weights,
        module=module,
        raw=dict(row),
    )


def build_fingerprint_matrix(
    df: pd.DataFrame,
    module: str,
    norm_stats: Optional[dict] = None,
) -> tuple[list[Fingerprint], np.ndarray]:
    """
    Build fingerprints for all rows in a DataFrame.

    Returns:
        (fingerprints list, matrix of shape [n_days, n_features])
    """
    if norm_stats is None:
        schema = MODULE1_FIELDS if module == "m1" else \
                 MODULE2_FIELDS if module == "m2" else \
                 MODULE3_FIELDS if module == "m3" else COMBINED_FIELDS
        norm_stats = compute_normalization_stats(df, list(schema.keys()))

    fingerprints = []
    for _, row in df.iterrows():
        fp = build_fingerprint(row.to_dict(), module, norm_stats)
        fingerprints.append(fp)

    matrix = np.vstack([fp.vector for fp in fingerprints])
    return fingerprints, matrix, norm_stats


# ── Usage Example ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    from pathlib import Path

    # Load Module 2 features as example
    data_path = Path("../../data/processed/module2_features.csv")
    if not data_path.exists():
        print("Run feature_builder_m2.py first to generate module2_features.csv")
    else:
        df = pd.read_csv(data_path, parse_dates=["date"])
        fps, matrix, stats = build_fingerprint_matrix(df, module="m2")
        print(f"Built {len(fps)} fingerprints, shape: {matrix.shape}")
        print(f"First fingerprint ({fps[0].date}):")
        for name, val in zip(fps[0].field_names, fps[0].vector):
            print(f"  {name:30s}: {val:.4f}")

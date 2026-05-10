"""
Similarity Search — Analog Day Finder
LLM Trading Project

Given a live day's fingerprint, finds the top-N most similar historical days
using cosine similarity. Returns analog day context for the LLM reasoning layer.

Usage:
    python similarity_search.py --module m2 --date 2026-05-10
"""

import numpy as np
import pandas as pd
import argparse
import json
from pathlib import Path
from typing import Optional

from fingerprint_builder import build_fingerprint, build_fingerprint_matrix

PROCESSED   = Path("../../data/processed")
TOP_N       = 10
MIN_SIM     = 0.70   # minimum cosine similarity to include in results


# ── Cosine Similarity ─────────────────────────────────────────────────────────

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def cosine_similarity_matrix(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between query vector and all rows in matrix."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-8, norms)
    normed = matrix / norms
    query_norm = query / (np.linalg.norm(query) + 1e-8)
    return normed @ query_norm


# ── FAISS-backed Search (fast, optional) ──────────────────────────────────────

def search_faiss(query: np.ndarray, matrix: np.ndarray, top_n: int) -> np.ndarray:
    """Use FAISS for fast similarity search (preferred for large datasets)."""
    try:
        import faiss
        dim     = matrix.shape[1]
        index   = faiss.IndexFlatIP(dim)   # inner product = cosine on normalized vecs
        normed  = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8)
        index.add(normed.astype(np.float32))
        q = (query / (np.linalg.norm(query) + 1e-8)).reshape(1, -1).astype(np.float32)
        scores, indices = index.search(q, top_n)
        return indices[0], scores[0]
    except ImportError:
        # Fallback to numpy cosine similarity
        sims    = cosine_similarity_matrix(query, matrix)
        indices = np.argsort(sims)[::-1][:top_n]
        return indices, sims[indices]


# ── Analog Day Builder ────────────────────────────────────────────────────────

def build_analog_context(
    hist_df: pd.DataFrame,
    indices: np.ndarray,
    scores: np.ndarray,
    module: str,
) -> list[dict]:
    """
    Convert top-N similar day indices into analog day context dicts
    for inclusion in the LLM prompt.
    """
    analogs = []
    for rank, (idx, score) in enumerate(zip(indices, scores)):
        if score < MIN_SIM:
            continue
        if idx >= len(hist_df):
            continue

        day = hist_df.iloc[idx]
        analog = {
            "rank":             rank + 1,
            "date":             str(day.get("date", "unknown")),
            "similarity_score": round(float(score), 3),
            "outcome":          str(day.get("outcome", "unknown")),
            "signal_type":      str(day.get("signal_type", day.get("mmxm_model", "unknown"))),
            "result_points":    float(day["result_points"]) if pd.notna(day.get("result_points")) else None,
        }

        # Module-specific context fields
        if module == "m1":
            analog.update({
                "orb_range":    float(day["orb_range"]) if pd.notna(day.get("orb_range")) else None,
                "mmxm_model":   str(day.get("mmxm_model", "")),
                "mmxm_phase":   str(day.get("mmxm_phase", "")),
                "smt_both":     bool(day.get("smt_both_pairs", False)),
                "fvg_present":  bool(day.get("fvg_present", False)),
            })
        elif module == "m2":
            analog.update({
                "pm2_range":        float(day["pm2_range"]) if pd.notna(day.get("pm2_range")) else None,
                "sweep_side":       str(day.get("sweep_side", "")),
                "sweep_level":      str(day.get("sweep_level", "")),
                "smt_both":         bool(day.get("smt_both_pairs", False)),
                "pm2_volume_ratio": float(day["pm2_volume_ratio"]) if pd.notna(day.get("pm2_volume_ratio")) else None,
            })
        elif module == "m3":
            analog.update({
                "zone_range_pts":   float(day["zone_range_pts"]) if pd.notna(day.get("zone_range_pts")) else None,
                "break_direction":  str(day.get("break_direction", "")),
                "break_vol_ratio":  float(day["break_volume_ratio"]) if pd.notna(day.get("break_volume_ratio")) else None,
                "risk_reward":      float(day["risk_reward"]) if pd.notna(day.get("risk_reward")) else None,
            })

        analogs.append(analog)

    return analogs


# ── Main Search Function ──────────────────────────────────────────────────────

def find_analogs(
    live_context: dict,
    module: str,
    top_n: int = TOP_N,
    exclude_date: Optional[str] = None,
) -> list[dict]:
    """
    Find top-N analog days for a live session context.

    Args:
        live_context: current day's feature dict (from live_context_builder)
        module: "m1" | "m2" | "m3"
        top_n: number of analogs to return
        exclude_date: exclude this date from results (prevents self-match)

    Returns:
        List of analog day dicts for inclusion in LLM prompt
    """
    data_files = {
        "m1": PROCESSED / "module1_features.csv",
        "m2": PROCESSED / "module2_features.csv",
        "m3": PROCESSED / "module3_features.csv",
    }

    data_file = data_files.get(module)
    if not data_file or not data_file.exists():
        print(f"Historical data not found: {data_file}")
        return []

    hist_df = pd.read_csv(data_file, parse_dates=["date"])

    # Exclude current date from history
    if exclude_date:
        hist_df = hist_df[hist_df["date"].astype(str) != exclude_date]

    # Only compare against days with signals
    signal_df = hist_df[hist_df["signal_present"] == 1].reset_index(drop=True)

    if signal_df.empty:
        return []

    # Build historical fingerprint matrix
    _, hist_matrix, norm_stats = build_fingerprint_matrix(signal_df, module)

    # Build live day fingerprint using same normalization
    live_fp = build_fingerprint(live_context, module, norm_stats)

    # Search
    indices, scores = search_faiss(live_fp.vector, hist_matrix, top_n)

    return build_analog_context(signal_df, indices, scores, module)


# ── Summary Stats for Analog Set ─────────────────────────────────────────────

def analog_summary(analogs: list[dict]) -> dict:
    """Compute win rate and avg result from the top analog set."""
    if not analogs:
        return {"count": 0}

    outcomes = [a["outcome"] for a in analogs]
    wins     = outcomes.count("win")
    losses   = outcomes.count("loss")
    total    = wins + losses

    pts = [a["result_points"] for a in analogs if a.get("result_points") is not None]

    return {
        "count":          len(analogs),
        "win_rate_pct":   round(wins / total * 100, 1) if total > 0 else None,
        "avg_result_pts": round(sum(pts) / len(pts), 2) if pts else None,
        "avg_similarity": round(sum(a["similarity_score"] for a in analogs) / len(analogs), 3),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find analog trading days")
    parser.add_argument("--module", choices=["m1", "m2", "m3"], required=True)
    parser.add_argument("--date",   type=str, help="Date to exclude (YYYY-MM-DD)")
    parser.add_argument("--top",    type=int, default=TOP_N)
    args = parser.parse_args()

    # Sample live context for testing
    sample_contexts = {
        "m2": {
            "date": args.date or "2026-05-10",
            "pm1_range": 32.0,
            "pm2_range": 24.5,
            "pm2_volume_ratio": 1.25,
            "sweep_detected": 1,
            "sweep_side": "bull_sweep",
            "sweep_level": "pm2_low",
            "smt_es_divergence": 1,
            "smt_ym_divergence": 1,
            "smt_both_pairs": 1,
            "expansion_detected": 0,
        }
    }

    ctx     = sample_contexts.get(args.module, {})
    analogs = find_analogs(ctx, args.module, top_n=args.top, exclude_date=args.date)
    summary = analog_summary(analogs)

    print(f"\nTop {len(analogs)} analog days for {args.module.upper()}:")
    print(json.dumps(analogs, indent=2, default=str))
    print(f"\nSummary: {summary}")

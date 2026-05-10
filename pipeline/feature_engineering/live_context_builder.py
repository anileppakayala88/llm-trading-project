"""
Live Context Builder
LLM Trading Project

Builds the structured context object sent to the LLM reasoning layer.
Called progressively during the NY session:
  - 09:30 ET: Initial context (PM ranges locked in)
  - 09:45/10:00 ET: ORB established (Module 1 context complete)
  - On sweep alert: Module 2 context complete
  - On retest alert: Module 3 context complete

Usage (from webhook handler or scheduler):
    from live_context_builder import build_context_m1, build_context_m2, build_context_m3
"""

import datetime
import json
import os
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Historical average volume per 5-min bar (updated after data collection)
# Used for volume_ratio calculation. Override via env or pass directly.
HIST_AVG_VOLUME_5MIN = float(os.getenv("HIST_AVG_VOLUME_5MIN", "5000"))


# ── Session Helpers ───────────────────────────────────────────────────────────

def now_et() -> datetime.datetime:
    return datetime.datetime.now(tz=ET)


def session_date() -> str:
    return now_et().strftime("%Y-%m-%d")


def current_time_et() -> str:
    return now_et().strftime("%H:%M")


def volume_ratio(current_volume: float, avg_volume: float = HIST_AVG_VOLUME_5MIN) -> float:
    """Compute volume ratio vs historical 5-min average."""
    return round(current_volume / avg_volume, 3) if avg_volume > 0 else 1.0


# ── Module 1 Context ──────────────────────────────────────────────────────────

def build_context_m1(
    webhook_payload: dict,
    daily_pnl_usd:  float = 0.0,
    open_positions: int   = 0,
    is_news_day:    bool  = False,
    news_times:     Optional[list] = None,
) -> dict:
    """
    Build Module 1 context from webhook payload (ORB+MMXM signal).

    webhook_payload expected keys:
        orb_high, orb_low, orb_range, orb_break_side,
        mmxm_model, mmxm_phase, smt_signal, fvg_present,
        fvg_high, fvg_low, volume, price, timestamp
    """
    p = webhook_payload
    vol_ratio = volume_ratio(float(p.get("volume", 0)))

    return {
        "module":         "orb_mmxm",
        "session_date":   session_date(),
        "current_time":   current_time_et(),
        "instrument":     "MNQ1!",
        # ORB data
        "orb_high":       p.get("orb_high"),
        "orb_low":        p.get("orb_low"),
        "orb_range":      p.get("orb_range"),
        "orb_break_side": p.get("orb_break_side", "none"),
        "orb_break_confirmed": p.get("orb_break_confirmed", False),
        # MMXM
        "mmxm_model":     p.get("mmxm_model", "unclear"),
        "mmxm_phase":     p.get("mmxm_phase", "consolidation"),
        # SMT
        "smt_signal":     p.get("smt_signal", "none"),
        # FVG
        "fvg_present":    p.get("fvg_present", False),
        "fvg_high":       p.get("fvg_high"),
        "fvg_low":        p.get("fvg_low"),
        # Market
        "current_price":  p.get("price"),
        "volume_ratio":   vol_ratio,
        # Session state
        "daily_pnl_usd":  daily_pnl_usd,
        "open_positions": open_positions,
        "is_news_day":    is_news_day,
        "news_times":     news_times or [],
    }


# ── Module 2 Context ──────────────────────────────────────────────────────────

def build_context_m2(
    webhook_payload: dict,
    daily_pnl_usd:  float = 0.0,
    open_positions: int   = 0,
    is_news_day:    bool  = False,
    news_times:     Optional[list] = None,
) -> dict:
    """
    Build Module 2 context from webhook payload (PM Sweep+SMT signal).

    webhook_payload expected keys:
        pm1_high, pm1_low, pm2_high, pm2_low,
        sweep_detected, sweep_side, sweep_level,
        smt_es, smt_ym, expansion_detected, expansion_direction,
        signal_type, volume, price, timestamp
    """
    p = webhook_payload
    vol_ratio = volume_ratio(float(p.get("volume", 0)))

    return {
        "module":               "pm_sweep_smt",
        "session_date":         session_date(),
        "current_time":         current_time_et(),
        "instrument":           "MNQ1!",
        # PM ranges
        "pm1_high":             p.get("pm1_high"),
        "pm1_low":              p.get("pm1_low"),
        "pm2_high":             p.get("pm2_high"),
        "pm2_low":              p.get("pm2_low"),
        # Sweep
        "sweep_detected":       p.get("sweep_detected", False),
        "sweep_side":           p.get("sweep_side"),
        "sweep_level":          p.get("sweep_level"),
        # SMT
        "smt_es":               p.get("smt_es", False),
        "smt_ym":               p.get("smt_ym", False),
        # Expansion
        "expansion_detected":   p.get("expansion_detected", False),
        "expansion_direction":  p.get("expansion_direction"),
        # Signal
        "signal_type":          p.get("signal_type", "no_signal"),
        # Market
        "current_price":        p.get("price"),
        "volume_ratio":         vol_ratio,
        # Session state
        "daily_pnl_usd":        daily_pnl_usd,
        "open_positions":       open_positions,
        "is_news_day":          is_news_day,
        "news_times":           news_times or [],
    }


# ── Module 3 Context ──────────────────────────────────────────────────────────

def build_context_m3(
    webhook_payload: dict,
    daily_pnl_usd:  float = 0.0,
    open_positions: int   = 0,
    is_news_day:    bool  = False,
    news_times:     Optional[list] = None,
) -> dict:
    """
    Build Module 3 context from webhook payload (SCAM Range retest signal).

    webhook_payload expected keys:
        zone_top, zone_bottom, zone_midpoint,
        break_direction, entry_price, stop_price, target_price,
        volume, price, timestamp
    """
    p = webhook_payload
    vol_ratio = volume_ratio(float(p.get("volume", 0)))

    ep = p.get("entry_price") or p.get("price")
    sp = p.get("stop_price")
    tp = p.get("target_price")
    rr = None
    if ep and sp and tp:
        risk   = abs(ep - sp)
        reward = abs(tp - ep)
        rr     = round(reward / risk, 2) if risk > 0 else None

    return {
        "module":           "scam_range",
        "session_date":     session_date(),
        "current_time":     current_time_et(),
        "instrument":       "MNQ1!",
        # Zone
        "zone_top":         p.get("zone_top"),
        "zone_bottom":      p.get("zone_bottom"),
        "zone_midpoint":    p.get("zone_midpoint"),
        # Break
        "break_direction":  p.get("break_direction"),
        "break_confirmed":  True,
        "retest_triggered": True,
        # Levels
        "entry_price":      ep,
        "stop_price":       sp,
        "target_price":     tp,
        "risk_reward":      rr,
        # Market
        "current_price":    p.get("price"),
        "volume_ratio":     vol_ratio,
        # Session state
        "daily_pnl_usd":    daily_pnl_usd,
        "open_positions":   open_positions,
        "is_news_day":      is_news_day,
        "news_times":       news_times or [],
    }


# ── Router ────────────────────────────────────────────────────────────────────

BUILDERS = {
    "orb_mmxm":    build_context_m1,
    "pm_sweep_smt": build_context_m2,
    "scam_range":  build_context_m3,
}


def build_context(
    webhook_payload: dict,
    daily_pnl_usd:  float = 0.0,
    open_positions: int   = 0,
    is_news_day:    bool  = False,
    news_times:     Optional[list] = None,
) -> dict:
    """Route to the correct context builder based on webhook module field."""
    module  = webhook_payload.get("module", "")
    builder = BUILDERS.get(module)

    if not builder:
        raise ValueError(f"Unknown module: {module}. Must be one of: {list(BUILDERS.keys())}")

    return builder(
        webhook_payload=webhook_payload,
        daily_pnl_usd=daily_pnl_usd,
        open_positions=open_positions,
        is_news_day=is_news_day,
        news_times=news_times,
    )


# ── CLI / Quick Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample_payload = {
        "module":      "pm_sweep_smt",
        "event":       "signal",
        "timestamp":   "2026-05-10 09:37:00",
        "ticker":      "MNQ1!",
        "price":       19218.00,
        "pm1_high":    19230.00,
        "pm1_low":     19198.25,
        "pm2_high":    19234.50,
        "pm2_low":     19210.00,
        "sweep_detected":      True,
        "sweep_side":          "bull_sweep",
        "sweep_level":         "pm2_low",
        "smt_es":              True,
        "smt_ym":              True,
        "expansion_detected":  False,
        "expansion_direction": None,
        "signal_type":         "sweep_reversal",
        "volume":              6800,
    }

    ctx = build_context(sample_payload, daily_pnl_usd=0.0, open_positions=0)
    print(json.dumps(ctx, indent=2, default=str))

"""
Kill Switch Evaluator
LLM Trading Project

Evaluates all kill switch conditions before allowing a trade signal
to proceed to the LLM reasoning layer.

All conditions from CLAUDE.md and PROJECT_SPEC.md are enforced here.
"""

import datetime
import os
from dataclasses import dataclass, field
from typing import Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Kill switch thresholds (can be overridden via env vars)
DAILY_LOSS_LIMIT       = float(os.getenv("MAX_DAILY_LOSS_USD",       "-200"))
MAX_OPEN_POSITIONS     = int(os.getenv("MAX_OPEN_POSITIONS",          "1"))
TRADE_CUTOFF_HOUR      = 11
TRADE_CUTOFF_MINUTE    = 30
NEWS_BUFFER_MINUTES    = int(os.getenv("NEWS_BUFFER_MINUTES",         "30"))
MIN_VOLUME_RATIO       = float(os.getenv("MIN_VOLUME_RATIO",          "0.8"))

# Known high-impact news event times (ET) — update each month
# Format: (hour, minute) ET
HIGH_IMPACT_NEWS_TIMES: list[tuple[int, int]] = [
    # Add NFP, FOMC, CPI times here before each trading week
    # e.g. (8, 30) for 08:30 ET NFP release
]


@dataclass
class KillSwitchResult:
    blocked:  bool
    reasons:  list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "blocked":  self.blocked,
            "reasons":  self.reasons,
            "warnings": self.warnings,
        }


def evaluate_kill_switch(
    current_time_et: Optional[datetime.datetime] = None,
    daily_pnl_usd:   float = 0.0,
    open_positions:   int   = 0,
    volume_ratio:     float = 1.0,
    is_news_day:      bool  = False,
    news_times:       Optional[list[tuple[int, int]]] = None,
) -> KillSwitchResult:
    """
    Evaluate all kill switch conditions.

    Args:
        current_time_et: Current ET datetime (defaults to now)
        daily_pnl_usd:   Realized P&L for today in USD (negative = loss)
        open_positions:   Number of currently open positions
        volume_ratio:     Current volume vs historical average (1.0 = average)
        is_news_day:      True if a high-impact news event is scheduled today
        news_times:       List of (hour, minute) ET tuples for today's news events

    Returns:
        KillSwitchResult with blocked status and reason list
    """
    result  = KillSwitchResult(blocked=False)
    now     = current_time_et or datetime.datetime.now(tz=ET)
    times   = news_times or HIGH_IMPACT_NEWS_TIMES

    # ── Hard stop: daily loss limit ───────────────────────────────────────────
    if daily_pnl_usd <= DAILY_LOSS_LIMIT:
        result.blocked = True
        result.reasons.append(
            f"daily_loss_exceeded: P&L ${daily_pnl_usd:.0f} ≤ limit ${DAILY_LOSS_LIMIT:.0f}"
        )

    # ── Hard stop: trade cutoff time ──────────────────────────────────────────
    cutoff = now.replace(hour=TRADE_CUTOFF_HOUR, minute=TRADE_CUTOFF_MINUTE, second=0)
    if now >= cutoff:
        result.blocked = True
        result.reasons.append(
            f"time_after_1130_ET: current time {now.strftime('%H:%M')} ET"
        )

    # ── Hard stop: open positions ─────────────────────────────────────────────
    if open_positions >= MAX_OPEN_POSITIONS:
        result.blocked = True
        result.reasons.append(
            f"open_position_exists: {open_positions} open position(s) — must be flat"
        )

    # ── News proximity check ──────────────────────────────────────────────────
    if is_news_day or times:
        for (news_h, news_m) in times:
            news_dt = now.replace(hour=news_h, minute=news_m, second=0)
            mins_to_news = (news_dt - now).total_seconds() / 60

            if abs(mins_to_news) <= NEWS_BUFFER_MINUTES:
                result.blocked = True
                result.reasons.append(
                    f"news_event_within_{NEWS_BUFFER_MINUTES}min: "
                    f"event at {news_h:02d}:{news_m:02d} ET "
                    f"({mins_to_news:+.0f} min)"
                )

    # ── Volume warning (advisory downgrade, not hard block) ───────────────────
    if volume_ratio < MIN_VOLUME_RATIO:
        result.warnings.append(
            f"volume_below_threshold: ratio {volume_ratio:.2f} < {MIN_VOLUME_RATIO} — "
            "advisory mode only, no auto-execution"
        )

    return result


def is_trade_allowed(context: dict) -> KillSwitchResult:
    """
    Convenience wrapper — extract kill switch inputs from a live context dict.

    Context keys used:
        daily_pnl_usd, open_positions, volume_ratio, is_news_day, news_times
    """
    return evaluate_kill_switch(
        daily_pnl_usd=context.get("daily_pnl_usd", 0.0),
        open_positions=context.get("open_positions", 0),
        volume_ratio=context.get("volume_ratio", 1.0),
        is_news_day=context.get("is_news_day", False),
        news_times=context.get("news_times", []),
    )


# ── CLI / Quick Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    test_cases = [
        {
            "label": "All clear",
            "daily_pnl_usd": 0, "open_positions": 0,
            "volume_ratio": 1.2, "is_news_day": False, "news_times": [],
        },
        {
            "label": "Daily loss exceeded",
            "daily_pnl_usd": -210, "open_positions": 0,
            "volume_ratio": 1.0, "is_news_day": False, "news_times": [],
        },
        {
            "label": "News in 15 minutes",
            "daily_pnl_usd": 0, "open_positions": 0,
            "volume_ratio": 1.0, "is_news_day": True,
            "news_times": [
                (datetime.datetime.now(tz=ET).hour,
                 (datetime.datetime.now(tz=ET).minute + 15) % 60)
            ],
        },
        {
            "label": "Open position",
            "daily_pnl_usd": 50, "open_positions": 1,
            "volume_ratio": 1.0, "is_news_day": False, "news_times": [],
        },
        {
            "label": "Low volume (warning only)",
            "daily_pnl_usd": 0, "open_positions": 0,
            "volume_ratio": 0.65, "is_news_day": False, "news_times": [],
        },
    ]

    for tc in test_cases:
        label = tc.pop("label")
        res   = evaluate_kill_switch(**tc)
        status = "BLOCKED" if res.blocked else "CLEAR  "
        print(f"[{status}] {label}")
        for r in res.reasons:  print(f"         ✗ {r}")
        for w in res.warnings: print(f"         ⚠ {w}")

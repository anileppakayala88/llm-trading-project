# Project Specification — LLM Trading System

**Version:** 1.0  
**Date:** May 2026  
**Instrument:** MNQ1! Futures  

---

## 1. Objective

Build a multi-module LLM-assisted trading system for MNQ1! futures that:
- Identifies high-probability trade setups using rule-based signal detection
- Cross-references signals with historical analog days
- Generates natural language trade plans via Claude API
- Progresses from advisory-only to conditional automation after proven edge

---

## 2. Architecture Overview

```
TradingView (Pine Script)
  → Webhook alerts (structured JSON)
    → Vercel serverless receiver
      → Python feature builder
        → Similarity engine (finds analog days)
          → Claude API (reasoning + plan generation)
            → GitHub Pages dashboard (advisory output)
              → Tradovate API (execution — Stage 2+)
```

---

## 3. Modules

### 3.1 Module 1 — ORB + MMXM

**Purpose:** Identify opening range breakout direction confirmed by MMXM phase and SMT divergence.

**Pine Script Inputs:**
- ORB window: 15min or 30min (toggle)
- ORB high/low plotted as horizontal levels
- MMXM phase detection from swing structure
- SMT divergence via `security()` calls for ES and YM
- FVG detection (3-candle imbalance)

**Signal Logic:**
```
1. ORB established at 09:45 or 10:00 ET
2. MMXM phase identified (consolidation → raid → accumulation → markup)
3. SMT divergence checked across ES and YM
4. FVG zone present near entry level
5. If all align → webhook fires with full context JSON
```

**Webhook Payload:**
```json
{
  "module": "orb_mmxm",
  "event": "signal",
  "timestamp": "{{timenow}}",
  "ticker": "MNQ1!",
  "price": {{close}},
  "orb_high": 0,
  "orb_low": 0,
  "orb_range": 0,
  "mmxm_model": "",
  "mmxm_phase": "",
  "smt_signal": "",
  "fvg_present": false,
  "fvg_high": 0,
  "fvg_low": 0,
  "volume": {{volume}},
  "session": "NY"
}
```

---

### 3.2 Module 2 — PM Range Sweep + SMT

**Purpose:** Identify post-open sweep of pre-market ranges confirmed by SMT divergence, or directional expansion when all 3 pairs align.

**Pine Script Inputs:**
- PM1 session: 07:00–08:30 ET → high/low box
- PM2 session: 08:30–09:30 ET → high/low box
- Sweep detection: price wicks beyond level then closes back inside
- SMT check: `security()` calls for ES and YM at sweep bar

**Signal Types:**
```
Type A — Sweep Reversal:
  Price sweeps PM1 or PM2 level
  ES AND YM do NOT make same extreme
  → Reversal signal against sweep

Type B — Directional Expansion:
  Price breaks PM level cleanly
  ES AND YM break same level
  → Trend continuation signal
```

**Webhook Payload:**
```json
{
  "module": "pm_sweep_smt",
  "event": "signal",
  "timestamp": "{{timenow}}",
  "ticker": "MNQ1!",
  "price": {{close}},
  "pm1_high": 0,
  "pm1_low": 0,
  "pm2_high": 0,
  "pm2_low": 0,
  "sweep_detected": false,
  "sweep_side": "",
  "sweep_level": "",
  "smt_es": false,
  "smt_ym": false,
  "expansion_detected": false,
  "expansion_direction": "",
  "signal_type": "",
  "volume": {{volume}}
}
```

---

### 3.3 Module 3 — SCAM Range Break + Midpoint Retest

**Purpose:** Identify consolidation zone breaks with midpoint retest entries.

**Pine Script Base:** NOCTISX-SCAM RANGES (modified)

**Additions to base script:**
- Zone break detection (candle close outside zone)
- Midpoint (0.5 fib) retest detection post-break
- Entry arrow plotshape
- TP/SL lines drawn automatically
- Webhook alert on retest trigger

**Signal Logic:**
```
1. Consolidation zone drawn on BOS/CHoCH
2. Candle closes above zone top → bull break flag set
3. Candle closes below zone bottom → bear break flag set
4. Price returns to zone midpoint (0.5 fib level)
5. Entry triggered at midpoint
6. TP = zone top (bull) or zone bottom (bear)
7. SL = zone bottom (bull) or zone top (bear)
```

**Webhook Payload:**
```json
{
  "module": "scam_range",
  "event": "retest_entry",
  "timestamp": "{{timenow}}",
  "ticker": "MNQ1!",
  "price": {{close}},
  "zone_top": 0,
  "zone_bottom": 0,
  "zone_midpoint": 0,
  "break_direction": "",
  "entry_price": {{close}},
  "stop_price": 0,
  "target_price": 0,
  "volume": {{volume}}
}
```

---

## 4. Backtesting Methodology

See `docs/BACKTEST_METHODOLOGY.md` for full details.

**Phases per module:**
- Phase A: Raw signal edge (no filters)
- Phase B: Filter optimization (one filter at a time)
- Phase C: Best filter combinations
- Phase D: Walk-forward validation on unseen data

**Minimum sample size:** 50 signals per module before conclusions drawn.

**Pass criteria for walk-forward:**
- Win rate within 10% of in-sample rate
- Expectancy remains positive
- No single filter responsible for >50% of edge

---

## 5. LLM Reasoning Layer

**Model:** claude-haiku-4-5 (development), claude-sonnet-4-6 (live)

**Call triggers:**
- 09:45 ET — ORB established (Module 1)
- 09:35 ET — First sweep detection (Module 2)
- On retest alert (Module 3)

**Context sent per call:**
1. Live session context object (current day data)
2. Top 10 analog days from similarity engine
3. Module-specific system prompt
4. Kill switch status

**Output:** Structured JSON + narrative trade plan

---

## 6. Execution Stages

### Stage 1 — Advisory Only
- Dashboard displays plan
- Trader executes manually on Tradovate
- Minimum duration: 4–6 weeks live

### Stage 2 — Semi-Automated
- Telegram bot delivers signal
- Approve/Reject buttons
- On approval: Tradovate API places bracket order

### Stage 3 — Conditional Automation
- Auto-execute when:
  - Confidence ≥ "high"
  - All kill switch conditions pass
  - Within primary trade window
- All else → advisory mode

### Stage 4 — Full Automation
- Only after Stage 1–3 proven over multiple months
- Full audit trail maintained

---

## 7. Kill Switch Conditions

```python
KILL_SWITCH = {
    "daily_loss_limit": -200,        # USD — hard stop
    "max_open_positions": 1,         # No pyramiding
    "trade_cutoff_time": "11:30 ET", # No late session
    "news_buffer_minutes": 30,       # Before/after major news
    "min_confidence": "medium",      # Below this = no auto
    "min_volume_ratio": 0.8          # Below avg volume = skip
}
```

---

## 8. Data Requirements

| Instrument | History Needed | Format | Source |
|---|---|---|---|
| MNQ1! | 9 months | CSV (5-min OHLCV) | TradingView export |
| ES1! | 9 months | CSV (5-min OHLCV) | TradingView export |
| YM1! | 9 months | CSV (5-min OHLCV) | TradingView export |

All exports must be aligned to ET timezone and include volume.

---

## 9. Environment Variables Required

```
ANTHROPIC_API_KEY=
TRADOVATE_USERNAME=
TRADOVATE_PASSWORD=
TRADOVATE_APP_ID=
TRADOVATE_APP_VERSION=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
GITHUB_TOKEN=
GITHUB_REPO=
WEBHOOK_SECRET=
```

# CLAUDE.md — LLM Trading Project Context

This file provides full project context to Claude API instances called within this pipeline.
Read this before processing any trading signal or generating any trade plan.

---

## Project Identity

- **Instrument:** MNQ1! (Micro Nasdaq Futures, $2/point/contract)
- **Correlated Pairs:** ES1! (S&P 500), YM1! (Dow Jones)
- **Trading Session:** New York — 09:30–11:30 ET primary window
- **Operator:** Human trader, advisory mode — all plans are suggestions only

---

## Session Time Windows

| Window | Time (ET) | Purpose |
|---|---|---|
| PM1 Range | 07:00–08:30 | Pre-market range 1 |
| PM2 Range | 08:30–09:30 | Pre-market range 2 (news session) |
| ORB Window | 09:30–09:45 or 09:30–10:00 | Opening Range Breakout |
| Primary Trade Window | 09:30–11:30 | Main execution window |
| No-trade zone | After 11:30 | Kill switch enforced |

---

## Module Definitions

### Module 1 — ORB + MMXM
**Signal logic:**
- ORB high/low established on first 15 or 30 minutes
- MMXM phase sequence: Consolidation → Liquidity Raid → Accumulation/Distribution → Markup/Markdown
- SMT divergence between MNQ and ES/YM confirms direction
- FVG zones used for retest entry confirmation

**Output fields required:**
- `mmxm_model`: "buy_model" | "sell_model" | "unclear"
- `mmxm_phase`: "consolidation" | "raid" | "accumulation" | "distribution" | "markup" | "markdown"
- `orb_break_side`: "bull" | "bear" | "none"
- `orb_break_confirmed`: true | false
- `smt_signal`: "bullish_divergence" | "bearish_divergence" | "aligned_bull" | "aligned_bear" | "none"
- `fvg_present`: true | false
- `fvg_zone`: [low, high] or null
- `entry_price`: float or null
- `stop_price`: float or null
- `target_price`: float or null
- `entry_window`: "HH:MM–HH:MM ET"
- `confidence`: "high" | "medium" | "low" | "no_signal"
- `narrative`: string (plain English trade plan)

---

### Module 2 — PM Range Sweep + SMT
**Signal logic:**
- PM1 and PM2 ranges defined from session OHLC
- Post 9:30: detect sweep of PM1 or PM2 high/low
- Sweep + SMT divergence on both ES AND YM = reversal signal
- All 3 pairs expanding same direction = directional signal
- No sweep + no alignment = no signal

**Output fields required:**
- `sweep_detected`: true | false
- `sweep_side`: "bull_sweep" | "bear_sweep" | null
- `sweep_level`: "pm1_high" | "pm1_low" | "pm2_high" | "pm2_low" | null
- `smt_es_divergence`: true | false
- `smt_ym_divergence`: true | false
- `expansion_detected`: true | false
- `expansion_direction`: "bull" | "bear" | null
- `signal_type`: "sweep_reversal" | "directional_expansion" | "no_signal"
- `entry_price`: float or null
- `stop_price`: float or null
- `target_price`: float or null
- `entry_window`: "HH:MM–HH:MM ET"
- `confidence`: "high" | "medium" | "low" | "no_signal"
- `narrative`: string

---

### Module 3 — SCAM Range Break + Midpoint Retest
**Signal logic:**
- Consolidation zone identified from market structure (swing high to swing low)
- Candle close above zone top = bull break confirmed
- Candle close below zone bottom = bear break confirmed
- Price retraces to 0.5 fib (midpoint) of zone = entry trigger
- TP = zone high (bull) or zone low (bear)
- SL = zone low (bull) or zone high (bear)

**Output fields required:**
- `zone_top`: float
- `zone_bottom`: float
- `zone_midpoint`: float
- `break_direction`: "bull" | "bear" | null
- `break_confirmed`: true | false
- `retest_triggered`: true | false
- `retest_price`: float or null
- `entry_price`: float or null
- `stop_price`: float or null
- `target_price`: float or null
- `risk_reward`: float or null
- `confidence`: "high" | "medium" | "low" | "no_signal"
- `narrative`: string

---

## Kill Switch Conditions

If ANY of these are true, output `confidence: "no_signal"` and state reason:

```
- daily_loss_exceeded: true
- news_event_within_30min: true
- time_after_1130_ET: true
- volume_below_threshold: true
- confidence_score_below_75pct: true
- no_smt_confirmation: true (for Modules 1 and 2)
```

---

## SMT Divergence Definition

**Bullish divergence (buy signal):**
- MNQ makes a new low that ES and/or YM do NOT make
- Indicates MNQ is being manipulated lower for liquidity before reversal

**Bearish divergence (sell signal):**
- MNQ makes a new high that ES and/or YM do NOT make
- Indicates MNQ is being manipulated higher for liquidity before reversal

**Directional alignment (expansion signal):**
- All 3 pairs (MNQ, ES, YM) breaking same level in same direction
- No divergence — trend continuation expected

---

## Analog Day Context

When analog days are provided, use them to:
1. Assess probability of current setup playing out
2. Identify what time the move typically initiated
3. Note any common failure patterns
4. Adjust confidence score accordingly

Format: `analog_days: [{date, similarity_score, outcome, entry_time, result}]`

---

## Output Format Rules

1. Always output a `narrative` field in plain English
2. Always output a `confidence` field
3. If no valid signal: state clearly "No signal — reason: [reason]"
4. Never fabricate prices — use only values from the input context
5. Entry, stop, target must be mathematically consistent
6. Risk/reward must be stated when entry/stop/target are provided

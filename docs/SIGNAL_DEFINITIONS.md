# Signal Definitions

Exact definitions used across all modules, backtesting, and LLM prompts.
All code and prompts must use these definitions consistently.

---

## Session Windows (All times ET)

| Session | Start | End | Purpose |
|---|---|---|---|
| PM1 | 07:00 | 08:30 | Pre-market range 1 |
| PM2 | 08:30 | 09:30 | Pre-market range 2 (news session) |
| ORB-15 | 09:30 | 09:45 | 15-minute opening range |
| ORB-30 | 09:30 | 10:00 | 30-minute opening range |
| Primary | 09:30 | 11:30 | Main trade execution window |
| Cutoff | 11:30 | — | No new trades after this |

---

## MMXM Phase Definitions

### Buy Model Sequence
```
Phase 1 — Original Consolidation
  Price ranges between two clear levels
  No directional bias
  Volume typically below average

Phase 2 — Liquidity Raid (Low Side)
  Price sweeps below consolidation low
  Wicks through equal lows or prior swing low
  Often coincides with news or open
  Volume spike on raid candle

Phase 3 — Accumulation
  Price stalls after raid
  Rejection candle forms (hammer, engulfing)
  SMT divergence present (MNQ new low, ES/YM hold)
  This is the entry zone

Phase 4 — Markup (Expansion)
  Price breaks above consolidation high
  Strong directional candles
  Volume confirms
  ORB high typically in this zone

Phase 5 — Distribution
  Price stalls near prior swing high or PM high
  Take profit zone
```

### Sell Model Sequence
```
Phase 1 — Original Consolidation
Phase 2 — Liquidity Raid (High Side)  ← Mirror of buy model
Phase 3 — Distribution
Phase 4 — Markdown (Expansion)
Phase 5 — Accumulation
```

---

## SMT Divergence Definitions

### Bullish SMT Divergence
**Condition:** MNQ makes a new swing low that ES AND/OR YM do not make.

```
Valid example:
  MNQ: Low at 09:34 = 19205 (new low of day)
  ES:  Low at 09:34 = 5298 (NOT a new low — held above prior low)
  YM:  Low at 09:34 = 42055 (NOT a new low — held above prior low)
  → Bullish SMT confirmed on both pairs

Partial example (weaker):
  MNQ: New low
  ES:  New low also
  YM:  Holds above prior low
  → Single pair divergence — lower confidence
```

### Bearish SMT Divergence
**Condition:** MNQ makes a new swing high that ES AND/OR YM do not make.

### Directional Alignment (No Divergence)
**Condition:** MNQ, ES, AND YM all break the same level in the same direction.
Used for expansion signals in Module 2.

---

## Sweep Definitions (Module 2)

### Valid Sweep
```
1. Price wicks below PM1 low or PM2 low (bull sweep setup)
   OR price wicks above PM1 high or PM2 high (bear sweep setup)
2. The wick extends at least 2 points beyond the level
3. The candle CLOSES back inside the PM range
4. SMT divergence present on ES or YM at the sweep bar

All 4 conditions required for a valid sweep signal.
```

### False Sweep (Do Not Trade)
```
- Price closes beyond the level (not a wick — a break)
- Wick is less than 2 points beyond level
- No SMT divergence on either pair
- Sweep happens after 10:30 ET
```

---

## Zone Break Definitions (Module 3)

### Valid Bull Break
```
1. Consolidation zone identified (box drawn by SCAM RANGES script)
2. 5-minute candle CLOSES above zone top (not just wicks)
3. Close must be at least 1 point above zone top
4. Break must occur within primary trade window (before 11:30 ET)
```

### Valid Bear Break
```
Mirror of bull break — close below zone bottom.
```

### Valid Midpoint Retest
```
1. Bull or bear break confirmed (see above)
2. Price pulls back toward zone midpoint (0.5 fib level)
3. Price touches within 1 point of midpoint
4. Retest candle does not close back inside zone
   (if it does — zone is invalidated, no trade)
```

---

## FVG (Fair Value Gap) Definition

```
A 3-candle pattern where:
  Candle 1 high < Candle 3 low (bullish FVG — imbalance above)
  OR
  Candle 1 low > Candle 3 high (bearish FVG — imbalance below)

The gap between Candle 1 and Candle 3 is the FVG zone.
Price often returns to fill this gap before continuation.

Used in Module 1 as retest entry confirmation zone.
```

---

## Confidence Score Definitions

| Level | Criteria |
|---|---|
| **High** | 3+ confluence factors aligned, SMT confirmed on both pairs, within optimal time window, volume above average |
| **Medium** | 2 confluence factors, SMT on one pair, acceptable time window |
| **Low** | 1 confluence factor, no SMT, or outside optimal window — advisory only, no auto |
| **No Signal** | Conditions not met OR kill switch triggered |

---

## Kill Switch Definitions

| Condition | Threshold | Action |
|---|---|---|
| Daily P&L | ≤ -$200 | Block all new trades |
| Open positions | ≥ 1 | No new entries until flat |
| Time | ≥ 11:30 ET | No new trades |
| News proximity | ≤ 30 min to event | Block |
| Volume ratio | < 0.8x average | Downgrade to advisory |
| Confidence | < medium | Advisory only |

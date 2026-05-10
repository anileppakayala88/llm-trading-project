# System Architecture — LLM Trading Project

---

## High-Level Data Flow

```
┌─────────────────────────────────────────────────────────┐
│                   TRADINGVIEW                           │
│                                                         │
│  Module 1: ORB+MMXM Indicator                          │
│  Module 2: PM Range Sweep+SMT Indicator                │
│  Module 3: SCAM Range Indicator                        │
│       │                                                 │
│       └── Webhook Alert (JSON) ──────────────────────► │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  VERCEL (Serverless)                    │
│                                                         │
│  /api/webhook                                          │
│  - Validate secret                                     │
│  - Parse module type                                   │
│  - Route to feature builder                            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              PYTHON PIPELINE                            │
│                                                         │
│  1. Live Context Builder                               │
│     - Progressive session object (9:30 → 10:00)       │
│     - News event check                                 │
│     - Volume ratio calculation                         │
│     - Kill switch evaluation                           │
│                                                         │
│  2. Similarity Engine                                  │
│     - Build today's fingerprint vector                 │
│     - FAISS search against 9-month history             │
│     - Return top 10 analog days with outcomes          │
│                                                         │
│  3. Claude API Call                                    │
│     - System prompt (module-specific)                  │
│     - Live context + analog days                       │
│     - Returns: plan JSON + narrative                   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              OUTPUT LAYER                               │
│                                                         │
│  Stage 1: GitHub Pages Dashboard (advisory)            │
│  Stage 2: Telegram Bot (one-tap approval)              │
│  Stage 3: Tradovate API (conditional auto)             │
└─────────────────────────────────────────────────────────┘
```

---

## Session Timeline

```
ET Time    Event                           Action
────────── ──────────────────────────────  ──────────────────────────
07:00      PM1 range starts                Pine Script tracking begins
08:30      PM1 range locked                PM1 H/L finalized
08:30      PM2 range starts                Pine Script tracking begins
09:00      Pre-market context snapshot     Feature builder primed
09:30      Market open                     Module 2 sweep detection ON
09:30      ORB window starts               Module 1 ORB tracking begins
09:35+     First sweep detection (M2)      Webhook fires if sweep + SMT
09:45/10:00 ORB established (M1)           Webhook fires with ORB context
09:30+     SCAM zone break detected (M3)   Module 3 monitors continuously
09:30+     Midpoint retest trigger (M3)    Webhook fires on retest
10:00      Full context available          LLM has complete picture
10:00-11:30 Primary trade window           Optimal execution window
11:30      Kill switch time cutoff         No new trades after this
```

---

## Module Interaction Map

```
                    ┌─────────────┐
                    │  Module 1   │
                    │ ORB + MMXM  │
                    └──────┬──────┘
                           │
                           │ Provides: ORB levels, MMXM phase,
                           │           FVG zones, SMT direction
                           │
┌─────────────┐            │            ┌─────────────┐
│  Module 2   │────────────┼────────────│  Module 3   │
│ PM Sweep    │            │            │ SCAM Range  │
│   + SMT     │            │            │   + Retest  │
└─────────────┘            │            └─────────────┘
      │                    │                   │
      │ Provides:          │            Provides:
      │ PM levels,         ▼            Zone levels,
      │ sweep type,   ┌─────────┐       break dir,
      │ expansion     │   LLM   │       retest price
      │ direction     │ Scoring │
      └───────────────►  Layer  │◄──────────────┘
                      └────┬────┘
                           │
                     Confluence score
                     when combinations
                     are enabled (Phase 8)
```

---

## Day Fingerprint Schema (Similarity Engine)

Each historical trading day is encoded as a feature vector:

```python
fingerprint = {
    # Session ranges
    "pm1_range_points": float,
    "pm2_range_points": float,
    "pm1_pm2_range_ratio": float,

    # Gap context
    "gap_direction": int,       # 1=gap up, -1=gap down, 0=flat
    "gap_points": float,

    # Volume
    "pm2_volume_ratio": float,  # vs historical average
    "orb_volume_ratio": float,

    # ORB
    "orb_range_points": float,
    "orb_break_direction": int, # 1=bull, -1=bear, 0=none

    # MMXM
    "mmxm_model": int,          # 1=buy, -1=sell, 0=unclear
    "mmxm_phase_at_open": int,  # 0-5 encoding

    # SMT
    "smt_signal_present": int,  # 1=yes, 0=no
    "smt_direction": int,       # 1=bull, -1=bear, 0=none
    "smt_both_pairs": int,      # 1=both ES+YM, 0=one only

    # Sweep (Module 2)
    "sweep_detected": int,      # 1=yes, 0=no
    "sweep_side": int,          # 1=bull, -1=bear, 0=none
    "sweep_level": int,         # 1=PM1H, 2=PM1L, 3=PM2H, 4=PM2L

    # SCAM Range (Module 3)
    "scam_zone_present": int,   # 1=yes, 0=no
    "scam_break_direction": int # 1=bull, -1=bear, 0=none
}
```

---

## Kill Switch Logic

```python
def kill_switch_check(context: dict) -> dict:
    reasons = []

    if context["daily_pnl"] <= KILL_SWITCH["daily_loss_limit"]:
        reasons.append("daily_loss_limit_hit")

    if context["open_positions"] >= KILL_SWITCH["max_open_positions"]:
        reasons.append("max_positions_reached")

    if context["et_time"] >= "11:30":
        reasons.append("time_cutoff")

    if context["minutes_to_news"] <= 30:
        reasons.append("news_event_imminent")

    if context["volume_ratio"] < KILL_SWITCH["min_volume_ratio"]:
        reasons.append("volume_below_threshold")

    return {
        "blocked": len(reasons) > 0,
        "reasons": reasons
    }
```

---

## Tradovate Order Structure (Stage 2+)

```json
{
  "accountSpec": "YOUR_ACCOUNT",
  "accountId": 12345,
  "action": "Buy",
  "symbol": "MNQM6",
  "orderQty": 1,
  "orderType": "Limit",
  "price": 19238.00,
  "isAutomated": true,
  "bracket1": {
    "action": "Sell",
    "orderType": "Stop",
    "stopPrice": 19225.00
  },
  "bracket2": {
    "action": "Sell",
    "orderType": "Limit",
    "price": 19265.00
  }
}
```

**Note:** `isAutomated: true` is required per CME Group rules for algorithmic orders.

---

## Repository Structure (Single Repo)

One repo keeps everything together — easier to manage cross-module context, shared utilities, and the CLAUDE.md file that all LLM calls reference.

```
llm-trading-project/          ← Single GitHub repo
├── .env.example
├── .gitignore
├── README.md
├── CLAUDE.md                 ← Shared LLM context
├── docs/
├── modules/
│   ├── module1_orb_mmxm/
│   ├── module2_pm_sweep/
│   ├── module3_scam_range/
│   └── combinations/
├── pipeline/
│   ├── webhook/
│   ├── feature_engineering/
│   ├── similarity_engine/
│   └── llm_layer/
├── dashboard/
├── scripts/
├── data/
└── config/
```

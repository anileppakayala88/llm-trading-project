# LLM Trading Project — MNQ1! Futures

> **Status:** Pre-build | Phase 1 in progress  
> **Instrument:** MNQ1! (Micro Nasdaq Futures)  
> **Correlated Pairs:** ES1!, YM1!  
> **LLM Backend:** Anthropic Claude API (claude-sonnet-4-20250514)  
> **Execution:** Tradovate API  
> **Alerts:** TradingView Webhooks → Vercel → Pipeline  

---

## Project Overview

An LLM-assisted trading system for MNQ1! futures that:
1. Identifies market structure and session range behavior
2. Detects MMXM buy/sell model phases
3. Cross-references SMT divergence across 3 correlated pairs
4. Scores confluence across multiple modules
5. Delivers advisory trade plans with optional automated execution

---

## Repository Structure

```
llm-trading-project/
│
├── README.md                        ← You are here
├── CLAUDE.md                        ← Context file for Claude API calls
├── .env.example                     ← Environment variables template
├── .gitignore
│
├── docs/
│   ├── PROJECT_SPEC.md              ← Full project specification
│   ├── TASK_LIST.md                 ← Master task checklist
│   ├── ARCHITECTURE.md              ← System architecture diagrams
│   ├── BACKTEST_METHODOLOGY.md      ← Backtesting rules and standards
│   └── SIGNAL_DEFINITIONS.md       ← Exact definitions for all signals
│
├── modules/
│   ├── module1_orb_mmxm/            ← ORB + MMXM model
│   │   ├── pinescript/              ← TradingView indicator code
│   │   ├── backtest/                ← Python backtest engine
│   │   └── prompts/                 ← Claude system prompts
│   │
│   ├── module2_pm_sweep/            ← PM Range Sweep + SMT model
│   │   ├── pinescript/
│   │   ├── backtest/
│   │   └── prompts/
│   │
│   ├── module3_scam_range/          ← SCAM Range Break + Midpoint Retest
│   │   ├── pinescript/
│   │   ├── backtest/
│   │   └── prompts/
│   │
│   └── combinations/                ← Confluence combinations (post-testing only)
│
├── pipeline/
│   ├── webhook/                     ← Vercel webhook receiver
│   ├── feature_engineering/         ← Python feature builders
│   ├── similarity_engine/           ← Historical analog finder
│   └── llm_layer/                   ← Claude API reasoning layer
│
├── dashboard/                       ← GitHub Pages dashboard
├── scripts/                         ← Utility scripts
├── data/
│   ├── raw/                         ← Raw CSV exports from TradingView
│   ├── processed/                   ← Feature-engineered datasets
│   └── backtest_results/            ← Backtest output reports
│
└── config/                          ← Configuration files
```

---

## Three Standalone Modules

### Module 1 — ORB + MMXM
- Opening Range Breakout (15/30 min) levels
- Market Maker Buy/Sell model phase detection
- SMT divergence confirmation layer
- FVG zone retest entries
- **Status:** 🔴 Not started

### Module 2 — PM Range Sweep + SMT
- PM1 range: 07:00–08:30 ET
- PM2 range: 08:30–09:30 ET
- Post-open sweep detection + SMT across MNQ, ES, YM
- Directional expansion when all 3 pairs align
- **Status:** 🔴 Not started

### Module 3 — SCAM Range Break + Midpoint Retest
- Consolidation zone detection from market structure
- Break confirmation (bull/bear)
- Midpoint (0.5 fib) retest entry
- TP at zone high/low, SL at zone opposite
- **Status:** 🔴 Not started

---

## Execution Progression

| Stage | Mode | Description |
|---|---|---|
| 1 | Advisory | Model outputs plan, human executes manually |
| 2 | Semi-auto | Telegram alert + one-tap approval → Tradovate |
| 3 | Conditional auto | Auto-execute when confidence > threshold + kill switch pass |
| 4 | Full auto | After Stage 1–3 proven over live months |

---

## Cost Profile

| Phase | Model | Est. Cost |
|---|---|---|
| Development | Claude Haiku | < $0.50 |
| Testing | Claude Haiku | ~$5 |
| Live trading | Claude Sonnet | ~$1/month |
| Year 1 total | Mixed | ~$14–27 |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Indicators | TradingView Pine Script v6 |
| Alerts | TradingView Webhooks |
| Webhook receiver | Vercel (serverless) |
| Data processing | Python (pandas, numpy) |
| Similarity search | FAISS / cosine similarity |
| LLM reasoning | Anthropic Claude API |
| Trade execution | Tradovate REST API |
| Dashboard | GitHub Pages |
| Version control | GitHub |

---

## Rules

1. **No module goes live without passing Phase A–D backtesting**
2. **No combination testing until all solo modules prove edge**
3. **Advisory mode minimum 4–6 weeks before any automation**
4. **Kill switch conditions always enforced**
5. **Walk-forward test required — no exceptions**

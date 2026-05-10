# Master Task List — LLM Trading Project

> Check off tasks as completed. Do not skip phases. Do not combine modules before solo testing is complete.

---

## Phase 1 — Pine Script Development

### Module 1 — ORB + MMXM Indicator
- [ ] Build ORB 15/30min session range (toggle between both)
- [ ] Plot ORB high/low as horizontal levels extending right
- [ ] Add MMXM phase detection (consolidation, raid, accumulation, distribution, markup, markdown)
- [ ] Add SMT divergence layer using security() for ES1! and YM1!
- [ ] Add FVG detection (3-candle imbalance zone)
- [ ] Add plotshape for entry signal
- [ ] Add webhook alertcondition with structured JSON payload
- [ ] Test on MNQ1! chart — verify all plots render correctly
- [ ] Save final script to `modules/module1_orb_mmxm/pinescript/`

### Module 2 — PM Range Sweep + SMT Indicator
- [ ] Build PM1 session box (07:00–08:30 ET) with high/low
- [ ] Build PM2 session box (08:30–09:30 ET) with high/low
- [ ] Add vertical session separator lines
- [ ] Add sweep detection logic (wick beyond level + close back inside)
- [ ] Add SMT divergence check on ES1! and YM1! at sweep bar
- [ ] Add directional expansion detection (all 3 pairs breaking same side)
- [ ] Add plotshape for sweep signal and expansion signal
- [ ] Add webhook alertcondition with structured JSON payload
- [ ] Test on MNQ1! chart — verify sweep and expansion detection
- [ ] Save final script to `modules/module2_pm_sweep/pinescript/`

### Module 3 — SCAM Range Break + Midpoint Retest
- [ ] Start from NOCTISX-SCAM RANGES base script
- [ ] Add zone break detection (candle close above/below zone)
- [ ] Add break direction flag (bull_break / bear_break)
- [ ] Add midpoint (0.5 fib) retest detection post-break
- [ ] Add entry arrow plotshape at retest trigger
- [ ] Add TP line (zone top for bull, zone bottom for bear)
- [ ] Add SL line (zone bottom for bull, zone top for bear)
- [ ] Add webhook alertcondition with structured JSON payload
- [ ] Test on MNQ1! chart — verify zone, break, retest logic
- [ ] Save final script to `modules/module3_scam_range/pinescript/`

---

## Phase 2 — Data Engineering (Python)

### Data Collection
- [ ] Export 9 months MNQ1! 5-min OHLCV from TradingView (CSV)
- [ ] Export 9 months ES1! 5-min OHLCV from TradingView (CSV)
- [ ] Export 9 months YM1! 5-min OHLCV from TradingView (CSV)
- [ ] Save raw files to `data/raw/`
- [ ] Run `scripts/align_timestamps.py` to align all 3 instruments by ET timestamp
- [ ] Verify no gaps or missing sessions in aligned data

### Feature Engineering — Module 1
- [ ] Calculate ORB high/low per trading day (15min and 30min)
- [ ] Detect swing highs and lows (fractal points)
- [ ] Detect equal highs/lows (liquidity pools)
- [ ] Detect liquidity raids (wick through EQH/EQL + reversal)
- [ ] Detect FVG zones (3-candle imbalance)
- [ ] Classify MMXM phase per day
- [ ] Calculate SMT divergence (MNQ vs ES, MNQ vs YM)
- [ ] Tag day outcome (win / loss / no signal)
- [ ] Save processed data to `data/processed/module1_features.csv`

### Feature Engineering — Module 2
- [ ] Calculate PM1 high/low per trading day
- [ ] Calculate PM2 high/low per trading day
- [ ] Detect sweep events post 9:30 (which level, which direction)
- [ ] Cross-reference ES and YM at sweep timestamp for SMT
- [ ] Detect directional expansion days (all 3 pairs)
- [ ] Calculate PM2 volume ratio vs historical average
- [ ] Tag day outcome (win / loss / no signal)
- [ ] Save processed data to `data/processed/module2_features.csv`

### Feature Engineering — Module 3
- [ ] Detect consolidation zones from price structure
- [ ] Detect zone breaks (bull and bear)
- [ ] Detect midpoint retests post-break
- [ ] Calculate zone size (points)
- [ ] Tag day outcome per signal
- [ ] Save processed data to `data/processed/module3_features.csv`

---

## Phase 3 — Backtesting

### Module 1 Backtest
- [ ] Phase A: Raw win rate — no filters applied
- [ ] Phase B: Test SMT required on both ES AND YM (vs one only)
- [ ] Phase B: Test FVG confluence filter
- [ ] Phase B: Test time window filter (9:30–10:00 vs 10:00–10:30 vs 10:30+)
- [ ] Phase B: Test news day exclusion
- [ ] Phase C: Best 2–3 filter combinations tested together
- [ ] Phase D: Walk-forward — train on months 1–6, test on months 7–9
- [ ] Generate report → save to `data/backtest_results/module1_report.md`
- [ ] **GATE: Walk-forward win rate within 10% of in-sample. If not, return to Phase B.**

### Module 2 Backtest
- [ ] Phase A: Raw win rate — sweep reversal and expansion signals separately
- [ ] Phase B: Test SMT required on BOTH ES AND YM (vs one)
- [ ] Phase B: Test PM2 volume ratio filter (>1.0x, >1.2x, >1.5x)
- [ ] Phase B: Test time window filter (9:30–9:45 vs 9:45–10:00 vs 10:00+)
- [ ] Phase B: Test news day exclusion
- [ ] Phase C: Best filter combinations tested together
- [ ] Phase D: Walk-forward — train months 1–6, test months 7–9
- [ ] Generate report → save to `data/backtest_results/module2_report.md`
- [ ] **GATE: Same pass criteria as Module 1.**

### Module 3 Backtest
- [ ] Phase A: Raw win rate — break + midpoint retest signals
- [ ] Phase B: Test zone size filter (minimum points)
- [ ] Phase B: Test volume filter at break candle
- [ ] Phase B: Test time window filter
- [ ] Phase B: Test structure length filter (swing detection sensitivity)
- [ ] Phase C: Best filter combinations
- [ ] Phase D: Walk-forward test
- [ ] Generate report → save to `data/backtest_results/module3_report.md`
- [ ] **GATE: Same pass criteria.**

---

## Phase 4 — Similarity Engine

- [ ] Design day fingerprint schema (feature vector fields)
- [ ] Build `pipeline/similarity_engine/fingerprint_builder.py`
- [ ] Build `pipeline/similarity_engine/similarity_search.py` (FAISS or cosine)
- [ ] Test: given a sample day, retrieve top 10 most similar historical days
- [ ] Manually validate 5 sample days — are analogs sensible?
- [ ] Tune similarity weights (which features matter most)
- [ ] Finalize and document fingerprint schema

---

## Phase 5 — LLM Prompt Development

### Module 1 Prompts
- [ ] Write system prompt for ORB + MMXM plan generator
- [ ] Test on 20 historical days using Haiku model
- [ ] Refine for accuracy and narrative quality
- [ ] Test edge cases (no signal days, choppy days, news days)
- [ ] Save to `modules/module1_orb_mmxm/prompts/system_prompt.md`

### Module 2 Prompts
- [ ] Write system prompt for PM Sweep plan generator
- [ ] Test on 20 historical days
- [ ] Refine and test edge cases
- [ ] Save to `modules/module2_pm_sweep/prompts/system_prompt.md`

### Module 3 Prompts
- [ ] Write system prompt for SCAM Range plan generator
- [ ] Test on 20 historical days
- [ ] Refine and test edge cases
- [ ] Save to `modules/module3_scam_range/prompts/system_prompt.md`

### Replay Testing (All Modules)
- [ ] Replay 50 historical days through Module 1 LLM — log plan vs outcome
- [ ] Replay 50 historical days through Module 2 LLM — log plan vs outcome
- [ ] Replay 50 historical days through Module 3 LLM — log plan vs outcome
- [ ] Identify failure patterns and refine prompts

---

## Phase 6 — Pipeline Integration

### Webhook Receiver
- [ ] Update Vercel receiver for Module 1 payload schema
- [ ] Update Vercel receiver for Module 2 payload schema
- [ ] Update Vercel receiver for Module 3 payload schema
- [ ] Add payload validation and error handling
- [ ] Add webhook secret verification
- [ ] Deploy to Vercel and test with TradingView test alert

### Feature Builder (Live)
- [ ] Build `pipeline/feature_engineering/live_context_builder.py`
- [ ] Progressive context object: partial at 9:30, complete by 10:00
- [ ] Add news event calendar check (NFP, FOMC, CPI)
- [ ] Add volume ratio calculation (vs historical average)
- [ ] Add kill switch evaluator

### LLM Layer
- [ ] Build `pipeline/llm_layer/claude_client.py`
- [ ] Wire: webhook payload → feature builder → similarity engine → LLM call
- [ ] Handle Haiku (dev) vs Sonnet (live) model switching via env var
- [ ] Add response parsing and error handling
- [ ] Log every LLM call: input context, output plan, timestamp

### End-to-End Test
- [ ] Simulate Module 1 signal through full pipeline
- [ ] Simulate Module 2 signal through full pipeline
- [ ] Simulate Module 3 signal through full pipeline
- [ ] Verify dashboard receives and displays output correctly

---

## Phase 7 — Output & Execution

### Dashboard Updates
- [ ] Add Module 1 plan display panel
- [ ] Add Module 2 plan display panel
- [ ] Add Module 3 plan display panel
- [ ] Add confidence score badge per module
- [ ] Add top 3 analog days display
- [ ] Add kill switch status indicator
- [ ] Add session timeline (PM1, PM2, ORB, trade window)
- [ ] Deploy to GitHub Pages

### Stage 1 — Advisory Mode
- [ ] Run live for minimum 4 weeks
- [ ] Log every signal: module, plan, confidence, actual outcome
- [ ] Weekly review: compare model plan vs market reality
- [ ] Document failures for prompt refinement

### Stage 2 — Semi-Automated (Telegram)
- [ ] Set up Telegram bot
- [ ] Format signal message with plan + confidence
- [ ] Add Approve / Reject inline buttons
- [ ] Wire approval → Tradovate API bracket order
- [ ] Test with paper trading for minimum 2 weeks
- [ ] Confirm `isAutomated: true` flag in all Tradovate orders

### Stage 3 — Conditional Automation
- [ ] Define exact confidence threshold for auto-execution
- [ ] Auto-execute only when all kill switch conditions pass
- [ ] Log auto-executions separately from advisory signals
- [ ] Set daily loss hard stop in Tradovate account settings
- [ ] Monitor for 4+ weeks before considering Stage 4

---

## Phase 8 — Combination Testing (Last — Do Not Start Early)

**Prerequisites: All 3 modules must have passed Phase D walk-forward independently.**

- [ ] Test Module 1 + Module 2 confluence signals
- [ ] Test Module 1 + Module 3 confluence signals
- [ ] Test Module 2 + Module 3 confluence signals
- [ ] Test all 3 modules together
- [ ] Keep combination only if win rate statistically better than best solo module
- [ ] Walk-forward test any winning combination before using live
- [ ] Document combination rules in `modules/combinations/`

---

## Progress Tracker

| Phase | Status | Started | Completed |
|---|---|---|---|
| Phase 1 — Pine Scripts | 🔴 Not started | | |
| Phase 2 — Data Engineering | 🔴 Not started | | |
| Phase 3 — Backtesting | 🔴 Not started | | |
| Phase 4 — Similarity Engine | 🔴 Not started | | |
| Phase 5 — LLM Prompts | 🔴 Not started | | |
| Phase 6 — Pipeline Integration | 🔴 Not started | | |
| Phase 7 — Output & Execution | 🔴 Not started | | |
| Phase 8 — Combinations | 🔴 Not started | | |

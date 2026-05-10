# Backtesting Methodology

---

## Rules

1. Each module is backtested independently — no cross-module logic during backtesting
2. Minimum 50 signals required before drawing any conclusions
3. Walk-forward test is mandatory — no exceptions
4. Filters tested one at a time in Phase B before combining in Phase C
5. A combination is only kept if it statistically outperforms the best solo filter set

---

## Phase A — Raw Signal Edge

Test the bare mechanical signal with no filters applied.

**Goal:** Does the signal have any raw edge at all?

**Inputs:**
- Feature-engineered CSV (processed data)
- Signal detection logic only (no volume, no time, no SMT filter)

**Outputs:**
- Total signals detected
- Win count / Loss count
- Win rate %
- Average winner (points)
- Average loser (points)
- Expectancy per trade (R)
- Sample size

**Pass criteria:** Positive expectancy with at least 30 signals

---

## Phase B — Filter Testing

Test each filter independently. Measure impact on win rate and expectancy.

**Filters to test (Module 2 example):**

| Filter | Values to Test |
|---|---|
| SMT requirement | One pair only vs Both ES AND YM |
| PM2 volume ratio | >0.8x, >1.0x, >1.2x, >1.5x |
| Entry time window | 9:30–9:45, 9:45–10:00, 10:00–10:30 |
| News day exclusion | Include all vs Exclude NFP/FOMC/CPI |

**For each filter value:**
- Apply ONLY that filter to Phase A dataset
- Measure: win rate, expectancy, sample size remaining
- Record in filter comparison table

**Key rule:** Sample size must remain above 30 after filter applied.
If a filter reduces sample below 30 — note it but do not rely on it.

---

## Phase C — Combination Testing

Take the 2–3 best-performing individual filters from Phase B.
Test them in combination.

**Process:**
1. Apply Filter A + Filter B → measure results
2. Apply Filter A + Filter C → measure results
3. Apply Filter B + Filter C → measure results
4. Apply Filter A + Filter B + Filter C → measure results
5. Select combination with best risk-adjusted expectancy
6. Ensure sample size still above 30

---

## Phase D — Walk-Forward Validation

**This is the most important phase. Do not skip.**

**Split:**
- Training data: Months 1–6 (in-sample)
- Test data: Months 7–9 (out-of-sample, unseen)

**Process:**
1. Run Phase A–C on training data only → select best filter set
2. Apply that exact filter set (no changes) to test data
3. Measure performance on test data

**Pass criteria:**
- Test win rate within 10% of training win rate
- Test expectancy remains positive
- No single month in test period is catastrophically negative

**Fail criteria (return to Phase B):**
- Test win rate drops >15% below training rate
- Test expectancy goes negative
- Obvious overfitting (too many filters, too small sample)

---

## Backtest Report Template

Save each module's completed backtest report to `data/backtest_results/`.

```
MODULE X BACKTEST REPORT
========================
Period: [start date] to [end date]
Instrument: MNQ1! (5-min bars)
Correlated: ES1!, YM1!

PHASE A — RAW SIGNAL
Total trading days: XXX
Days with signal: XXX (XX%)
Win: XX | Loss: XX | Win rate: XX%
Avg winner: XX pts | Avg loser: XX pts
Expectancy: X.XX R

PHASE B — BEST FILTERS
Filter applied: [description]
Win rate: XX% | Expectancy: X.XX R | Sample: XX

PHASE C — BEST COMBINATION
Filters: [list]
Win rate: XX% | Expectancy: X.XX R | Sample: XX

PHASE D — WALK-FORWARD
Training (M1–M6): Win rate XX%, Expectancy X.XX R
Test (M7–M9):     Win rate XX%, Expectancy X.XX R
Delta: XX% — PASS / FAIL

OPTIMAL ENTRY WINDOW: HH:MM – HH:MM ET
VOLUME FILTER: >X.Xx ratio
SMT REQUIREMENT: Both pairs / One pair
NEWS EXCLUSION: Yes / No

VERDICT: APPROVED FOR LIVE / NEEDS MORE WORK
```

---

## Signal Definition Standards

### What counts as a WIN:
- Price reaches TP level before SL level
- Measured from entry price to TP

### What counts as a LOSS:
- Price reaches SL level before TP level
- Measured from entry price to SL

### What counts as NO SIGNAL:
- Conditions not met → day skipped
- Not counted in win/loss stats

### Entry price:
- Module 1: First 5-min close beyond ORB level
- Module 2: First 5-min close back inside PM range after sweep
- Module 3: Touch of midpoint (0.5 fib) post-break

### Stop placement:
- Module 1: Below FVG zone (bull) or above FVG zone (bear)
- Module 2: Beyond sweep wick extreme
- Module 3: Beyond zone opposite side

### Target placement:
- Module 1: PM high/low or prior session extreme
- Module 2: Opposite PM range level
- Module 3: Zone high (bull) or zone low (bear)

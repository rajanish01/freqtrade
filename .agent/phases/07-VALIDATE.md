# Phase 7: Walk-Forward Validation & Robustness

## Prerequisite
Phase 5 VERDICT = PASS (or Phase 6 VERDICT = KEEP).

## Your Task
Try to break the strategy. You do NOT modify it in this phase — you only run
tests and report. A strategy that survives this is deployable; one that does
not is a curve fit that happened to pass one window.

---

### Test 1 — Walk-forward across all available data

Run each quarter separately and record trades, profit factor and drawdown.

```bash
for TR in 20220101-20220401 20220401-20220701 20220701-20221001 20221001-20230101 \
          20230101-20230401 20230401-20230701 20230701-20231001 20231001-20240101 \
          20240101-20240401 20240401-20240701 20240701-20241001 20241001-20250101 \
          20250101-20250401 20250401-20250701 20250701-20251001 20251001-20260101 \
          20260101-20260401 20260401-20260709 ; do
  echo "=== $TR"
  freqtrade backtesting --config configs/strategies/$STRAT.json \
    --timerange $TR 2>&1 | grep -E "Total profit %|Profit factor|Absolute Drawdown|Total/Daily Avg Trades"
done
```

Failure conditions:
- More than 2 **consecutive** quarters with profit factor < 1.0 -> regime vulnerability
- More than 40% of all quarters with profit factor < 1.0 -> not robust
- Any single quarter with drawdown > 35% -> tail risk too high

Note which market regime each losing quarter falls in (trend up, trend down,
chop). A strategy that only loses in one identifiable regime can be fixed with
a regime filter; one that loses randomly cannot.

### Test 2 — Parameter sensitivity

Take the 3 most impactful `opt_*` parameters. For each, re-run the full IS
backtest at -20%, optimal, and +20%.

To vary a parameter without editing the class, edit the value in
`user_data/strategies/<StrategyName>.json` (hyperopt's output file), run, then
restore it. Record the original values before you start.

Failure condition: profit factor drops below 1.0 at either ±20% -> brittle.
A robust parameter sits on a plateau, not a spike.

### Test 3 — Per-pair stability

```bash
freqtrade backtesting --config configs/strategies/$STRAT.json \
  --timerange 20220101-20260709 \
  2>&1 | grep -vE " INFO - " | tail -40
```
Read the per-pair table.

Failure condition: fewer than 60% of pairs profitable, or a single pair
contributing more than 50% of total profit (that is one lucky pair, not a
strategy).

### Test 4 — Cost sensitivity

Re-run the full backtest with doubled fees to model slippage:
```bash
freqtrade backtesting --config configs/strategies/$STRAT.json \
  --timerange 20220101-20260709 --fee 0.001 \
  2>&1 | grep -vE " INFO - " | tail -30
```
Failure condition: profit factor falls below 1.0 at 2x fees. That means the
edge is smaller than real-world execution costs.

## DO NOT
- Modify the strategy file
- Re-run hyperopt
- Change any config permanently (restore anything you touched)
- Skip a test because an earlier one passed

## Exit Criteria
- [ ] All 18 walk-forward quarters run and tabulated
- [ ] No more than 2 consecutive losing quarters
- [ ] Fewer than 40% of quarters losing
- [ ] Sensitivity tested on top 3 params, none brittle at ±20%
- [ ] >= 60% of pairs profitable, no pair > 50% of profit
- [ ] Profit factor > 1.0 at 2x fees
- [ ] Any temporarily modified file restored to its original value
- [ ] `.agent/reports/<strategy>/phase7-validation.md` written
- [ ] `.agent/STATE.md` and `.agent/JOURNAL.md` updated

## Output Format

```
PHASE 7 RESULTS — <StrategyName>
─────────────────────────
WALK-FORWARD
Quarter              Trades   PF     DD%    Verdict
20220101-20220401    <N>      <N>    <N>    win/loss
... (all 18 rows)
Losing quarters: <N>/18   Max consecutive losses: <N>
─────────────────────────
SENSITIVITY
Param              -20%     opt      +20%    Brittle?
<opt_x>            <PF>     <PF>     <PF>    yes/no
─────────────────────────
PER-PAIR
Profitable pairs: <N>/<N>   Top pair share of profit: <N>%
Losing pairs: <list>
─────────────────────────
COST SENSITIVITY
PF at 1x fees: <N>    PF at 2x fees: <N>
─────────────────────────
VERDICT: ROBUST (proceed to Phase 8) / FRAGILE
Failure points: <explicit list, or "none">
```

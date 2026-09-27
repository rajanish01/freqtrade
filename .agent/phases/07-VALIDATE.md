# Phase 7: Walk-Forward Validation & Robustness — MAZE tier T4 methodology

## Prerequisite
Used as the **T4** tool inside `.agent/phases/04M-MAZE.md`, applied to EVERY
T3 survivor (a node whose promoted, 1m-detail-confirmed hyperopt epoch passed
every Phase-4/CONVENTIONS gate) — not once at the end of a single linear run.
(Phase 6 FreqAI, if used, sits between T3 and this: Phase 6 VERDICT = KEEP is
also a valid entry point.)

## Your Task
Try to break the node. You do NOT modify the strategy file in this phase —
you only run tests and report. A node that survives this proceeds to T5
(OOS, then the vault); one that does not is a curve fit that happened to
pass one window, and is `PRUNED` in the ledger with the specific failing
test recorded (`maze.py mark <Name> <node_id> PRUNED --note "..."`).

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
    --timerange $TR --cache none --enable-protections 2>&1 \
    | grep -E "Total profit %|Profit factor|Absolute drawdown|Total/Daily Avg Trades"
done
```

Base list: 18 quarters. One optional 19th quarter (20260709-20260923) exists
on disk beyond the documented OOS end — run it only if the user approves the
extension (see `ENVIRONMENT.md`); it is extra evidence, not a requirement.

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

The node's genome snapshot (`.agent/reports/<Name>/maze/params/<node_id>.json`)
already has the exact values — copy it, perturb the 3 parameters ±20%, and
run through `maze.py` by pointing a scratch node at the perturbed file
(`maze.py node <Name> --parent <node_id> --tier T4 --type sensitivity --desc
"<param> -20%" --genome-from <path-to-perturbed-json>`), rather than hand
-editing the shared params-file slot. This keeps every perturbation in the
ledger instead of a manually-restored scratch file.

Failure condition: profit factor drops below 1.0 at either ±20% -> brittle.
A robust parameter sits on a plateau, not a spike.

### Test 3 — Per-pair stability

```bash
freqtrade backtesting --config configs/strategies/$STRAT.json \
  --timerange 20220101-20260709 --cache none --enable-protections \
  2>&1 | grep -vE " INFO - " | tail -40
```
Read the per-pair table.

Failure condition: fewer than 60% of pairs profitable, or a single pair
contributing more than 50% of total profit (that is one lucky pair, not a
strategy).

### Test 4 — Cost sensitivity (the realistic case)

Re-run the full backtest with doubled fees to model slippage. For 15m and 5m
strategies run it at 1m detail too — the combination of 2x fees and realistic
intra-candle exits is the honest worst case (for `LiquidationWickFade` this
IS the real number, per its plan):

```bash
freqtrade backtesting --config configs/strategies/$STRAT.json \
  --timerange 20220101-20260709 --fee 0.001 \
  --cache none --enable-protections 2>&1 | grep -vE " INFO - " | tail -30

freqtrade backtesting --config configs/strategies/$STRAT.json \
  --timerange 20220101-20260709 --fee 0.001 --timeframe-detail 1m \
  --cache none --enable-protections 2>&1 | grep -vE " INFO - " | tail -30
```
Failure condition: profit factor falls below 1.0 at 2x fees. That means the
edge is smaller than real-world execution costs. If the detail run cannot
complete (memory), record SKIPPED with the reason — do not pretend it ran.

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
- [ ] Result recorded in the ledger (`maze.py mark <Name> <node_id> ...`) and
      in `.agent/reports/<strategy>/maze/runs/`
- [ ] `.agent/STATE.md` and `.agent/JOURNAL.md` updated

## Output Format

```
MAZE T4 RESULTS — <StrategyName> <node_id>
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
VERDICT: ROBUST (proceed to T5 — OOS, then the vault) / FRAGILE (prune this node)
Failure points: <explicit list, or "none">
```

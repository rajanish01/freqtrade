# Phase 5: Hyperparameter Optimization

## Prerequisite
Phase 4 VERDICT = PASS. The strategy already works with default parameters.

Hyperopt sharpens an edge; it does not create one. If Phase 4 failed, tuning
will only produce a better-disguised failure.

---

### Step 1 — Optimise on the in-sample window only

```bash
freqtrade hyperopt --config configs/strategies/$STRAT.json \
  --spaces buy sell \
  --hyperopt-loss SharpeHyperOptLossDaily \
  --epochs 300 --timerange 20220101-20250630 \
  2>&1 | grep -vE " INFO - " | tail -60
```

- `--spaces buy sell` only. **Never** optimise `roi`, `stoploss`, `trailing`
  or `protection` — the risk layer stays deterministic. Changing this is YELLOW.
- 300 epochs default. More than 500 requires user approval.
- The timerange is the IS window. Using the OOS window here invalidates the run.

### Step 2 — Review before applying

Read `.agent/prompts/hyperopt-review.md` and produce its report.
Specifically check whether any winning parameter sits at the edge of its
declared range — that means the range was wrong, not that the value is optimal.

```bash
freqtrade hyperopt-show --config configs/strategies/$STRAT.json --best --print-json
```

### Step 3 — Understand where the parameters now live

Hyperopt writes the winning parameters to
`user_data/strategies/<StrategyName>.json`. Freqtrade **loads that file
automatically** and it overrides the `default=` values in the class.

So: do not hand-copy the values into the class and also leave the json in
place, or you will not know which set is active. Pick one:
- **Keep the json** (recommended) — leave the class defaults alone.
- **Promote to class defaults** — update `default=` in the class, then delete
  or rename the json, and state that you did so.

Record which option you chose in `.agent/JOURNAL.md`.

### Step 4 — Out-of-sample validation

```bash
freqtrade backtesting --config configs/strategies/$STRAT.json \
  --timerange 20250701-20260709 \
  --breakdown month \
  2>&1 | grep -vE " INFO - " | tail -60
```

### Step 5 — Overfitting check

Compare OOS against the IS numbers from Step 1:

| Test | Fails if |
|------|----------|
| Profit factor | OOS PF < 0.8 x IS PF |
| Max drawdown | OOS DD > 1.5 x IS DD |
| Sharpe | OOS Sharpe < 0.6 x IS Sharpe |
| Trade rate | OOS trades/month < 0.5 x IS trades/month |

Any single failure = OVERFIT. Do not proceed to Phase 6 or 7.

Response to OVERFIT, in order of preference:
1. Reduce the number of optimised parameters (fewer degrees of freedom)
2. Widen or re-centre a parameter range that pinned to an edge
3. Reduce epochs (yes, fewer — less curve-fitting)
4. Switch loss function to a more conservative one (YELLOW)

Never respond to overfitting by re-running hyperopt on more data that includes
the OOS window.

## DO NOT
- Optimise `roi` / `stoploss` / `trailing` spaces
- Run > 500 epochs without approval
- Skip out-of-sample validation
- Change indicator or signal logic here (that is Phase 2/3)
- Report IS numbers as if they were the strategy's expected performance

## Exit Criteria
- [ ] Hyperopt completed on the IS window, best epoch recorded
- [ ] Hyperopt review report produced, no parameter pinned to a range edge
- [ ] Parameter source (json vs class defaults) chosen and stated
- [ ] OOS backtest run on `20250701-20260709`
- [ ] All four overfitting tests PASS
- [ ] OOS results still pass the Phase 4 quality gates
- [ ] `.agent/STATE.md` and `.agent/JOURNAL.md` updated

## Output Format

```
PHASE 5 RESULTS — <StrategyName>
─────────────────────────
HYPEROPT (IS 20220101-20250630, <N> epochs)
Best epoch:        <N>
Loss function:     SharpeHyperOptLossDaily
Optimal params:    <param=value, one per line>
Params at range edge: NONE / <list>
IS profit factor:  <N>
IS Sharpe:         <N>
IS max drawdown:   <N>%
IS trades:         <N>
─────────────────────────
OOS VALIDATION (20250701-20260709)
Profit factor:     <N>  (ratio to IS: <N>)
Sharpe:            <N>  (ratio to IS: <N>)
Max drawdown:      <N>% (ratio to IS: <N>)
Trades:            <N>
─────────────────────────
OVERFITTING CHECK
PF ratio     > 0.8:  PASS/FAIL (<actual>)
DD ratio     < 1.5:  PASS/FAIL (<actual>)
Sharpe ratio > 0.6:  PASS/FAIL (<actual>)
Trade rate   > 0.5:  PASS/FAIL (<actual>)
─────────────────────────
Params active via: <user_data/strategies/X.json | class defaults>
─────────────────────────
VERDICT: PASS / OVERFIT
```

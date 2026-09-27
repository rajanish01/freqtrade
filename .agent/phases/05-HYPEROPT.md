# Phase 5: Hyperparameter Optimization — mechanics reference for MAZE tier T2

## Prerequisite
Used as the **T2** tool inside `.agent/phases/04M-MAZE.md`, on a node whose
structural shape (T0 root or a T1 move) is worth tuning. This file is the
"how" — the command mechanics, the flags, what each space means, how to read
the output. The "when / how many / which spaces this run" decisions belong
to 04M, not here.

Hyperopt sharpens an edge; it does not create one. A node whose T0/T1
backtest shows no signal at all (PF near 1.0, no dominant exit reason — see
`.agent/prompts/backtest-postmortem.md`'s failure-mode table) is not a good
hyperopt candidate; tuning it will only produce a better-disguised failure.

---

### Step 1 — Run via `maze.py`, not a bare `freqtrade hyperopt`

```bash
python .agent/scripts/maze.py run <StrategyName> <node_id> --cmd hyperopt \
  --timerange 20220101-20250630 \
  --spaces buy sell protection risk stoploss \
  --epochs 300 --jobs -1 --min-trades 100
```

Do not invoke `freqtrade hyperopt` directly against a strategy that has maze
nodes — `maze.py run` stages that node's inherited genome into the strategy's
params-file slot before the call and restores it after; a bare invocation can
silently pick up whatever a *different* node last left there (see
`maze.py`'s module docstring). The wrapper also writes every epoch into
`.agent/reports/<Name>/maze/runs/<node_id>_epochs.csv` for the review step
below, and updates the ledger.

**Spaces — the policy this framework used to have was narrower.** Old rule:
`--spaces buy sell` only, `roi`/`stoploss`/`trailing`/`protection` forbidden.
Current rule: all of `buy sell protection risk stoploss` are in scope at T2.
This is not "the risk layer is no longer deterministic" — the MECHANISM
(fixed-fractional sizing, half-capital reserve, which protection METHODS
exist) is still fixed by hand in the class. What is now searched is the
specific NUMBERS within a range bounded by the K2/K7 formulas
(`kotegawa-risk-layer.md`), enforced every epoch by the loss function below,
exactly as strictly as a human check used to enforce them once. `roi` and
`trailing` stay out of `--spaces` by default (the ROI ladder / trailing
shape is a structural choice, tested as a T1 move via config override, not
hyperopted point-by-point) — add them only with the same YELLOW approval
`04M-MAZE.md` describes for widening a tier's scope.

`risk` is not a freqtrade builtin space — it exists only if the strategy
declares a `space="risk"` parameter (e.g. `opt_lev_cap`, read inside
`leverage()`). Omit `risk` from `--spaces` for a strategy that has not
declared one; passing it is a no-op if there is nothing in that space
(freqtrade does not error, it just optimizes zero parameters in it), but omit
it for clarity in the journal entry.

**Correctness rule — `--analyze-per-epoch` (unchanged, still easy to miss):**
hyperopt runs `populate_indicators` ONCE by default. If any `opt_*` parameter
is used *inside* `populate_indicators` (Keltner multiplier, VWAP period,
SuperTrend period/mult...), the indicator columns are computed with the
default values and the epochs are optimising against stale columns — garbage
in, garbage out. For such strategies add `--analyze-per-epoch` (slower;
indicators recompute per epoch). Check the strategy file and state which case
applies in the report.

**Protections during hyperopt — corrected, 2026-09-27.** The old text here
said "epochs run without protections." That was wrong: `--enable-protections`
DOES apply to hyperopt (verified against `hyperopt_optimizer.py`, which sets
`enable_protections=True` on the backtester exactly like the backtest
command). `maze.py run --cmd hyperopt` passes it by default. There is no
longer a pre-circuit-breaker/post-circuit-breaker split to reconcile at OOS
time — T2 numbers already reflect protections.

**Loss function — `MazeGateLoss` is the T2 default now**, not
`SharpeHyperOptLossDaily`. It scores every epoch against the exact
`CONVENTIONS.md` gate table (profit factor, drawdown, Sharpe, rate-scaled
trade count, pair-profitability fraction, stoploss-share, funding-share, K4
payoff, K2/K7 risk formulas) instead of a generic risk-adjusted return, so
the epoch hyperopt prefers is the epoch that would actually pass Phase 4 —
read `.agent/scripts/hyperopt/MazeGateLoss.py`'s docstring for the exact
formulas and for why "No good result found for given optimization function"
is a real, informative result (no epoch cleared every gate) and not a crash.
Switching away from it is YELLOW, same as any other loss-function change;
the drawdown-aware builtins (`CalmarHyperOptLoss`,
`MaxDrawDownRelativeHyperOptLoss`, `SortinoHyperOptLossDaily`,
`MultiMetricHyperOptLoss`) remain valid alternatives if a specific reason
argues for them.

### Step 2 — Review before promoting an epoch

Read `.agent/prompts/hyperopt-review.md` and produce its report against the
`_epochs.csv` file `maze.py` wrote. Specifically check whether any winning
parameter sits at the edge of its declared range — that means the range was
wrong, not that the value is optimal.

```bash
python .agent/scripts/maze.py promote <StrategyName> <T2-node-id> --epoch <N> --tier T3 \
  --desc "epoch <N>: <one-line what changed>"
```

### Step 3 — Where the parameters live (the maze version)

The old single-strategy version of this step said "hyperopt writes params to
`user_data/strategies/<StrategyName>.json`; pick json-vs-class-defaults and
say which." With multiple nodes sharing one `.py` file, that file is now a
**shared, transient staging slot** — `maze.py run`/`promote` manage it
automatically; a node's real, permanent parameter record is its genome
snapshot at `.agent/reports/<Name>/maze/params/<node_id>.json`. Only at the
very end (Phase 8, one finalist) does the "promote to class defaults, delete
the json, state that you did so" choice from the old text apply — make it
then, not per node.

### Step 4 — Out-of-sample validation (T5, once per finalist — not per node)

```bash
freqtrade backtesting --config <finalist node's config> \
  --timerange 20250701-20260709 \
  --breakdown month --cache none --enable-protections \
  2>&1 | grep -vE " INFO - " | tail -60
```
(Or `maze.py run <Name> <node_id> --cmd backtest --timerange 20250701-20260709`
if the finalist still has a maze node config — same staging benefit.)

### Step 5 — Overfitting check

Compare OOS against the IS numbers from the node's T2/T3 measurement:

| Test | Fails if |
|------|----------|
| Profit factor | OOS PF < 0.8 x IS PF |
| Max drawdown | OOS DD > 1.5 x IS DD |
| Sharpe | OOS Sharpe < 0.6 x IS Sharpe |
| Trade rate | OOS trades/month < 0.5 x IS trades/month |

Any single failure = OVERFIT. Do not proceed to the vault or Phase 8 on this
node.

Response to OVERFIT, in order of preference:
1. Reduce the number of optimised parameters (fewer degrees of freedom) —
   spawn a narrower T2 re-run as a new sibling node, do not overwrite this one
2. Widen or re-centre a parameter range that pinned to an edge — same, new node
3. Reduce epochs (yes, fewer — less curve-fitting) — same, new node
4. Switch loss function to a more conservative one (YELLOW) — same, new node

Never respond to overfitting by re-running hyperopt on more data that
includes the OOS window. Never respond by immediately trying the vault
window — that is the one-shot resource `04M-MAZE.md` protects; an overfit
node has not earned it.

If every reasonable response is exhausted for every surviving node, this is
where the maze's exhaustion rule applies — see `04M-MAZE.md` "Exhaustion" —
not a fixed 3-iteration count.

## DO NOT
- Invoke `freqtrade hyperopt` directly on a strategy with maze nodes (use
  `maze.py run` — genome staging is not optional, see its docstring)
- Put `roi` or `trailing` in `--spaces` without the same YELLOW approval as
  any other scope widening
- Run > 500 epochs without approval
- Skip out-of-sample validation, or peek at OOS before it
- Touch the vault window from this phase — that is T5-finalist-only
- Change indicator or signal logic here (that is Phase 2/3, a `.py` edit)
- Report IS numbers as if they were the strategy's expected performance

## Exit Criteria
- [ ] Hyperopt run via `maze.py run --cmd hyperopt`, best epoch recorded in
      the ledger
- [ ] Hyperopt review report produced (`hyperopt-review.md`), no parameter
      pinned to a range edge (or the pin explained and accepted)
- [ ] Best epoch promoted to a T3 node and confirmed at 1m detail
- [ ] OOS backtest run on the T4-surviving finalist; all four overfitting
      tests PASS
- [ ] OOS results still pass every `CONVENTIONS.md` quality gate
- [ ] `.agent/STATE.md`, `.agent/JOURNAL.md` and the maze ledger updated

## Output Format

```
MAZE T2/T5 HYPEROPT RESULTS — <StrategyName> <node_id>
─────────────────────────
HYPEROPT (IS <timerange>, <N> epochs, spaces: <list>)
Best epoch:        <N>   Loss function: MazeGateLoss (or stated alternative)
Optimal params:    <param=value, one per line>
Params at range edge: NONE / <list>
Gate table (best epoch): <PASS/FAIL per gate, from the epochs.csv / gates output>
─────────────────────────
OOS VALIDATION (20250701-20260709) — finalist only
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
Genome:  .agent/reports/<Name>/maze/params/<node_id>.json
─────────────────────────
VERDICT: PASS (proceed to T4/vault) / OVERFIT (spawn a narrower sibling, or exhausted)
```

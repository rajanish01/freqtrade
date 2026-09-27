# Hyperopt Review

Run after `.agent/phases/05-HYPEROPT.md` Step 1 (MAZE tier T2), before
promoting an epoch to a T3 node. Diagnose only — no code changes, no commands
beyond reading `.agent/reports/<Name>/maze/runs/<node_id>_epochs.csv`
(written by `maze.py run --cmd hyperopt`) or `hyperopt-list` / `hyperopt-show`
directly against the `.fthypt` file named in the ledger's `artifact` column.

Note on the loss value: with `MazeGateLoss` (the T2 default), a failing
epoch's loss is `>= 1000` and a passing epoch's is a negative Calmar-like
number — do not compare raw loss magnitudes to older runs made with
`SharpeHyperOptLossDaily`, they are on a different scale by design (see
`MazeGateLoss.py`'s docstring). Use the `gate_pass` / `score` columns `maze.py` computed in that CSV, not the
raw `loss` column, when judging epochs here.

## Check 1 — Range edges
For each optimised parameter, compare the winning value to its declared range.

A value at or adjacent to a range boundary means the range was wrong. The
optimiser was still walking in that direction when it hit the wall. Either
widen the range and re-run, or accept that the parameter is degenerate (the
strategy wants it switched off).

Report as: `opt_x = 2.98 (range 0.5–3.0) — PINNED AT UPPER EDGE`.

## Check 2 — Domain sanity
Does the value make sense for the indicator?
- RSI entry threshold of 95, or ADX threshold of 2 -> the condition is
  effectively always true or always false. The parameter is not doing anything.
- A band multiplier so wide it triggers a handful of times in 3 years -> the
  trade count gate will fail even if PF looks good.

## Check 3 — Convergence
Was the loss still improving in the final epochs, or had it flattened?
- Flattened -> converged, accept.
- Still improving -> more epochs may help (but > 500 is YELLOW).
- Erratic with no trend -> the search space is noise; reduce parameter count.

## Check 4 — Result clustering
Inspect the top 10 epochs.
- **Clustered** (similar parameters, similar profit) -> well-behaved space, the
  result sits on a plateau. Good sign for Phase 7 sensitivity.
- **Scattered** (very different parameters, similar profit) -> the strategy is
  noise-fitting. The "optimum" is an artifact. Expect OOS failure.

Clustering is the single most predictive signal here. A scattered top-10 almost
always precedes an overfit verdict in Step 5.

**Cross-node version (maze-specific):** if this strategy has more than one T2
sibling (different T1 structural shapes, each hyperopted), also compare the
best epoch ACROSS nodes, not just within one. Similar parameters winning
under different structural shapes is a much stronger signal than clustering
within a single run — it means the edge is not an artifact of one specific
filter/timeframe choice. Wildly different "optimal" parameters per shape,
each barely clearing the gates, is the multi-node version of scattering —
treat it with the same suspicion `04M-MAZE.md`'s anti-pattern #13 warns about.

## Check 5 — Trade count
Does the winning epoch satisfy `hyperopt_min_trades`? Optimisers love finding a
parameter set that takes 12 perfect trades. That is not a strategy.

## DO NOT
- Modify any file
- Run hyperopt again
- Change the loss function without explaining the tradeoff
- Recommend applying parameters that pin to a range edge

## Output Format

```
HYPEROPT REVIEW — <StrategyName>
─────────────────────────
PARAMETER SANITY
<opt_x>: <value> (range <lo>-<hi>) — OK / PINNED / DEGENERATE
...
─────────────────────────
Convergence:   CONVERGED / STILL IMPROVING / ERRATIC
Top-10 spread: CLUSTERED / SCATTERED
Best-epoch trades: <N> (min required <N>)
─────────────────────────
CALL: ACCEPT / WIDEN RANGES AND RERUN / MORE EPOCHS / LIKELY OVERFIT
Reasoning: <one or two sentences>
```

# Backtest Postmortem

A node's backtest failed the gate table — the T0 root, a T1 move, or a T3/T5
promoted epoch (`.agent/phases/04M-MAZE.md`). Diagnose before touching
anything. Write the result to `.agent/reports/<strategy>/phase4-iter<N>.md`
(T0) or into the node's entry in `.agent/reports/<strategy>/maze/ledger.csv`
plus a short note in the per-strategy journal (T1+ — do not create a
numbered iter-file per node, the ledger is the per-node record).

## Input
- The Phase 4 output block (the real numbers)
- The `backtesting-analysis` entry/exit reason breakdown
- The per-pair table
- `.agent/JOURNAL.md` — what has already been tried on this strategy
- The per-strategy journal `.agent/reports/<Name>/journal.md` — the Phase 1
  risk-layer checks. Read BOTH journals: the global one is the cross-run log,
  the per-strategy one holds the risk numbers; a diagnosis that sees only one
  is half-informed.

## Step 1 — Classify the failure

Match the symptoms. More than one may apply.

| Mode | Signature |
|------|-----------|
| **Overtrading** | huge trade count, tiny avg profit, fees dominate |
| **Undertrading** | < 100 trades over 3.5y; not statistically meaningful |
| **No edge** | PF hovers near 1.0, win rate near random, no dominant exit reason |
| **Asymmetric risk** | high win rate + negative return; stoploss is top exit reason |
| **Regime dependence** | monthly breakdown shows profit clustered in one period |
| **Pair concentration** | one pair carries profit, the rest lose |
| **Cost sensitivity** | profitable at 0 fees, unprofitable at real fees |
| **Decay** | works in early years, degrades toward the present |

Use the `--breakdown month` output for regime and decay. Use the per-pair table
for concentration. Use the exit-reason breakdown for asymmetric risk.

## Step 2 — Root cause

For each mode identified, name the specific indicator, threshold or condition
responsible. "The entry is too loose" is not a root cause. "`opt_band_std`
default 1.0 puts entries inside normal noise; 78% of entries reverse within
2 candles" is.

If you cannot name a specific cause, say so — that itself is a finding, and it
usually means the hypothesis has no mechanism behind it.

## Step 3 — Check the hypothesis, not just the parameters

Before proposing a tweak, ask: does this failure mean the parameters are wrong,
or that the **hypothesis** is wrong?

Consult the "How will we know this failed?" section of the strategy idea. If
the kill criteria stated there are met, the correct output of this postmortem
is "the hypothesis is not supported" — not another parameter nudge. Say it
plainly. That is a successful outcome for the process, even though the strategy
failed.

## Step 4 — Emit moves, not a single ranked fix

This is the difference from the old (pre-maze) version of this prompt: it
used to propose "at most 3 changes, ranked, apply #1, wait." Now it feeds the
maze's T1 candidate set instead — every plausible response to the diagnosed
failure mode becomes a **sibling node**, not a sequential guess:

- Which failure mode(s) were identified, and the specific move each one
  motivates (timeframe, confirmation filter, exit-mechanism swap, regime
  filter — see `04M-MAZE.md` "T1 — the fixed candidate set")
- Whether the root cause looks like a PARAMETER problem (send it to T2
  hyperopt within the current structural shape) or a STRUCTURAL problem
  (send it to T1 as a new move)
- If this postmortem is for a T0 root-node failure: the set of moves you name
  here IS the T1 candidate set — get it approved once (YELLOW, per
  `04M-MAZE.md`), then register each as a node
  (`maze.py node <Name> --parent <T0-id> --tier T1 --type <...> --desc <...>`)
- If this postmortem is for a T1/T3/T5 node failure: is this failure mode
  different from what killed its siblings (a genuinely new move), or the
  same one recurring (evidence the whole structural shape is dead, prune the
  line, do not spawn another cosmetic variant of it)

## DO NOT
- Make code changes in this prompt — diagnose only
- Propose risk-parameter changes as the primary fix (they are now a bounded
  T2 search dimension, not a hand-tuned escape hatch — see `04M-MAZE.md`;
  do not reach for them ahead of a structural T1 move)
- Propose "try a completely different strategy" — that is the user's call
- Propose re-running hyperopt as a fix for a T0/T1 node with no signal at all
  (PF near 1.0, no dominant exit reason) — tuning cannot create an edge that
  is not there; that pattern is a prune, not a T2 candidate
- Describe a failing strategy or node as "promising" or "close"

## Output Format

```
POSTMORTEM — <StrategyName>, node <node_id> (tier <T0-T5>)
─────────────────────────
FAILED GATES:      <list with actual values>
FAILURE MODE(S):   <classification>
EVIDENCE:          <the specific numbers that support the classification>
ROOT CAUSE:        <specific parameter, indicator or condition>
HYPOTHESIS STATUS: SUPPORTED / NOT SUPPORTED / UNDETERMINED
─────────────────────────
CANDIDATE MOVES (siblings to register, not a ranked sequence)
1. <move type: timeframe/filter/exit_mode/risk/hyperopt> | <desc> | targets which failure mode | expect <effect>
2. ...
─────────────────────────
RECOMMEND: register moves as T1 siblings (name the set) / send to T2 hyperopt as-is /
           prune this line (recurring failure mode, no new move motivated) /
           abandon hypothesis (maze exhausted, see 04M-MAZE.md) / escalate to user
```

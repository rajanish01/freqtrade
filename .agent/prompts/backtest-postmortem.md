# Backtest Postmortem

Phase 4 (or Phase 5 OOS) failed. Diagnose before touching anything.
Write the result to `.agent/reports/<strategy>/phase4-iter<N>.md`.

## Input
- The Phase 4 output block (the real numbers)
- The `backtesting-analysis` entry/exit reason breakdown
- The per-pair table
- `.agent/JOURNAL.md` — what has already been tried on this strategy

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

## Step 4 — Propose

At most 3 changes, ranked, one to apply first. For each:
- Which phase to revisit (2 = indicators, 3 = signals)
- The exact change
- Expected effect and rough magnitude
- What could get worse

## DO NOT
- Make code changes in this prompt — diagnose only
- Propose risk-parameter changes as the primary fix
- Propose "try a completely different strategy"
- Propose re-running hyperopt as a fix for a failed Phase 4 — tuning cannot
  create an edge that is not there
- Describe a failing strategy as "promising" or "close"

## Output Format

```
POSTMORTEM — <StrategyName>, Phase 4 iteration <N>
─────────────────────────
FAILED GATES:      <list with actual values>
FAILURE MODE(S):   <classification>
EVIDENCE:          <the specific numbers that support the classification>
ROOT CAUSE:        <specific parameter, indicator or condition>
HYPOTHESIS STATUS: SUPPORTED / NOT SUPPORTED / UNDETERMINED
─────────────────────────
PROPOSED CHANGES (ranked)
1. <change> | phase <N> | expect <effect> | risk <what worsens>
2. ...
─────────────────────────
RECOMMEND: apply #1 / abandon hypothesis / escalate to user
```

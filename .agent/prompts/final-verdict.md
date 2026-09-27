# Final Verdict — the terminal report for a dead strategy

This is the LAST step for a strategy whose hypothesis died. It produces the
consolidated "why it failed" verdict and closes the run.

## When this prompt runs

Exactly one of:
- The plan's "How will we know this failed?" (kill criteria) are met, at any
  maze tier
- The maze is exhausted per `.agent/phases/04M-MAZE.md` "Exhaustion" (every
  named T1 candidate hyperopted with no epoch clearing every gate — not a
  fixed iteration count)
- All 3 fix iterations at Phase 0-3 (structural correctness, pre-maze)
  burned without passing exit criteria
- The user says "abandon"

If none of these hold, this prompt does NOT run — go back to
`.agent/prompts/iteration-fix.md` (Phases 0-3) or `backtest-postmortem.md`
(spawn the next maze move) instead.

## Input

Read all of it. This verdict is only as good as its evidence.
- The strategy plan — especially the kill criteria and the hypothesis
- `.agent/reports/<Name>/maze/ledger.csv` and `tree.md` — the full node
  history. State the total node count in the verdict; a verdict that does
  not disclose how many variants were tried is not trustworthy evidence
  against the next similar plan (see `anti-patterns.md` #13)
- Every postmortem in `.agent/reports/<Name>/phase4-iter*.md` (T0), plus
  every `PRUNED`/`DEAD` node's notes in the ledger (T1+)
- `.agent/JOURNAL.md` — every entry tagged with this strategy's name
- The per-strategy journal `.agent/reports/<Name>/journal.md`
- The final backtest output (re-run a read-only backtest if the numbers are
  not already recorded — do not write the verdict from memory)

## Process

1. **Trace the hypothesis arc.** What did the plan claim (in one sentence)?
   At which phase did the evidence first contradict it, and how?
2. **Consolidate every iteration.** For each fix attempt: the change, the
   measured effect, and whether it moved toward or away from the gates. A
   change that was never measured (command never ran) is recorded as such.
3. **Classify the final failure mode** (see the table in
   `backtest-postmortem.md`). More than one may apply.
4. **Name the root-cause chain.** Specific indicators, thresholds, conditions —
   not "the entry was too loose". If no specific cause can be named, write
   that: it means the hypothesis had no mechanism behind it, which is itself
   the verdict.
5. **Check the kill criteria** from the plan. List each with MET / NOT MET and
   the actual value.
6. **State why it cannot be fixed within the framework's rules** — which
   fix (signal, indicator, risk, hyperopt) was already tried, and why the
   remaining moves would violate the rules (e.g. "risk-parameter change would
   only hide the bleed", "re-hyperopt cannot create an edge").
7. **State what a retry would require** — a new hypothesis or new evidence.
   This is the user's call, never the agent's.

## Write the verdict

Create `.agent/reports/<Name>/DEAD.md`:

```
FINAL VERDICT — <StrategyName> — <ISO date>
STATUS: DEAD — hypothesis <not supported | undetermined>; do not hyperopt or
        re-run this strategy again without a new plan.
─────────────────────────────────────────────────
HYPOTHESIS:        <what the plan claimed, one sentence>
DIED AT:           tier <T0-T5>, node <node_id>
NODES EVALUATED:   <total ledger row count> (<N> pruned, <N> reached T2, ...)
KILL CRITERIA:     <each criterion, MET/NOT MET, actual value>
─────────────────────────────────────────────────
WHAT WAS TRIED (summarise the tree, do not restate every ledger row)
  T0:  baseline -> <headline gate failure>
  T1:  <move 1> -> <measured effect> | <move 2> -> <measured effect> | ...
  T2:  <best epoch across all T1 shapes> -> <measured effect>
  ...
─────────────────────────────────────────────────
FINAL EVIDENCE
  <headline numbers of the best node's last backtest: PF, DD, Sharpe, trades,
  funding, profitable pairs — plus the exit-reason attribution>
FAILURE MODE(S):   <classification with the numbers that support it>
ROOT CAUSE CHAIN:  <specific indicators/thresholds, or "no mechanism found">
─────────────────────────────────────────────────
WHY UNFIXABLE WITHIN THE RULES
  <which moves were tried across the tree; why the remaining moves violate
  the framework or were already covered by a tried sibling>
RETRY WOULD REQUIRE
  <new hypothesis or new evidence — user's call>
ARTIFACTS
  Ledger/tree:  .agent/reports/<Name>/maze/ledger.csv, maze/tree.md
  Postmortems:  .agent/reports/<Name>/phase4-iter*.md
  Journals:     .agent/JOURNAL.md, .agent/reports/<Name>/journal.md
  Strategy file/config: DELETED after this verdict (recorded here)
  Maze node configs/genomes/run blobs: KEPT (they are the evidence trail,
  not the live strategy — same reason journals are append-only and never
  deleted)
─────────────────────────────────────────────────
LESSON: <one line — what this failure teaches the rest of the portfolio>
```

The LESSON line is mandatory. It is the reason the verdict exists: a failure
recorded precisely is worth more to the next strategy than a passing one.

## Then close the run

1. Delete `user_data/strategies/<Name>.py` and
   `configs/strategies/<Name>.json` — a dead strategy must not linger where
   `list-strategies` shows it next to live candidates. Record both deletions
   in `DEAD.md` (the ARTIFACTS block).
2. `.agent/STATE.md`: `active_strategy: (none)`, `phase_status: DEAD`,
   `final_report: .agent/reports/<Name>/DEAD.md`, ledger row for this strategy
   -> `Phase <N> | DEAD`.
3. `user_data/strategies/plan/INDEX.md`: update the strategy's status line.
4. Append a JOURNAL.md entry: Phase <N> — FINAL VERDICT — DEAD, with the
   LESSON line.
5. Append a row to `.agent/reports/PORTFOLIO.md`.

## Honesty rules

- No "promising", "close", "nearly there". The strategy is dead; say so.
- No placeholder numbers. If a metric was never measured, write "not measured".
- This is a successful outcome of the process. Say that too.
- Do NOT propose parameter tweaks, new indicators, or "one more run" in this
  verdict. Those decisions belong to earlier prompts; this one closes.

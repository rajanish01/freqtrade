# Iteration Fix

A phase failed its exit criteria. Diagnose, apply the smallest fix, re-run.

## Iteration budget
Three fix attempts per phase. Count them in `.agent/STATE.md` (`iteration:`).
On the 4th failure, STOP and escalate to the user with a table of every change
tried and its measured effect. Do not keep grinding.

## Process
1. Name the phase and the exact exit criterion that failed.
2. Read the actual error or metric. Quote it — do not paraphrase from memory.
3. Identify the SINGLE most likely root cause.
4. Classify the fix as GREEN or YELLOW (root `AGENTS.md` §4).
5. Apply it (GREEN) or propose it and wait (YELLOW).
6. Re-run the failed phase's verification command.
7. Append the outcome to `.agent/JOURNAL.md` — including if it did not work.

## Green vs yellow, for fixes specifically

**Apply immediately (GREEN):**
- Syntax errors, typos, wrong column names, missing imports
- `startup_candle_count` too low
- A threshold adjustment within an already-declared `opt_*` range
- Adding the `volume > 0` guard
- Fixing a void-dtype signal assignment
- Anything that makes a broken command run at all

**Propose and wait (YELLOW):**
- Adding or removing an indicator
- Changing the hypothesis or the signal structure
- Any risk parameter change (`stoploss`, `minimal_roi`, `trailing_stop`)
- Changing pairs, timeframe or the IS/OOS split
- Going back more than one phase

## Rules
- ONE change per iteration. Not two. If you change two things and the result
  improves, you have learned nothing about which one did it.
- The change must be concrete: "line 47: `opt_band_std` default 1.0 -> 1.5",
  not "loosen the entry".
- Risk parameters are the last resort, never the first. Widening the stoploss
  to fix a losing strategy hides the problem; it does not solve it.
- If the diagnosis is genuinely ambiguous, ask. Guessing burns an iteration.
- Never propose "start over" or "try a different strategy" — that is the
  user's call, and it is made after the iteration budget is spent.

## Output Format

```
ITERATION FIX — Phase <N>, attempt <I>/3
─────────────────────────
Failed criterion:  <which one>
Observed:          <the actual error text or metric value>
Root cause:        <specific diagnosis>
Change:            <file:line, exact before -> after>
Classification:    GREEN (applying now) / YELLOW (awaiting approval)
Expected effect:   <what should change, and by roughly how much>
Risk:              <what could get worse>
─────────────────────────
```

Then, after re-running:

```
RESULT: FIXED / STILL FAILING (<new value>) / NEW FAILURE (<what>)
```

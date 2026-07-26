# Phase 4: Bias Checks, Full Backtest & Analysis

## Prerequisite
Phase 3 exit criteria all PASS. Strategy produces trades.

## Your Task
Measure the strategy on the in-sample window. You do NOT modify the strategy
file in this phase.

---

### Step 1 — Bias checks (GATE: run these before looking at any profit number)

A profitable backtest from a biased strategy is worse than useless, because it
looks like success. Run both checks first and let them decide whether the
metrics mean anything.

```bash
freqtrade lookahead-analysis --config configs/strategies/$STRAT.json \
  --timerange 20240101-20250630 \
  --pairs BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT \
  2>&1 | grep -viE "WARNING|unclosed|connector|deque|coroutine" | tail -12
```
`--pairs` is mandatory — this command ignores the config whitelist.
It needs >= 10 trades in the window, otherwise it cancels silently.

Read the `has_bias` column:
- `No` -> clean, continue.
- `Yes` -> **STOP.** The strategy is invalid. Go to
  `.agent/prompts/iteration-fix.md` and return to Phase 2 or 3.
  Do not report profit numbers for a biased strategy — they are meaningless.
- `too few trades caught` -> the check did not run. Widen the timerange.
  This is NOT a pass. Do not record it as one.

```bash
freqtrade recursive-analysis --config configs/strategies/$STRAT.json \
  --timerange 20250101-20250301 \
  2>&1 | grep -vE " INFO - " | tail -20
```
Every indicator must read `0.000%` across the warm-up columns. Any non-zero
drift -> raise `startup_candle_count` in Phase 2 and come back.

### Step 2 — Full in-sample backtest

```bash
mkdir -p results/backtests .agent/reports/$STRAT
freqtrade backtesting --config configs/strategies/$STRAT.json \
  --timerange 20220101-20250630 \
  --breakdown month --export signals \
  --backtest-directory results/backtests \
  --notes "phase4 IS baseline" \
  2>&1 | grep -vE " INFO - " | tail -60
```
Use `--backtest-directory`. `--export-filename` is deprecated and ignored —
results would silently go to `user_data/backtest_results/` instead.
The export is a timestamped `.zip`; locate it with
`ls -t results/backtests/*.zip | head -1`.

### Step 3 — Entry/exit reason breakdown

```bash
freqtrade backtesting-analysis --config configs/strategies/$STRAT.json \
  --backtest-directory results/backtests \
  --analysis-groups 0 1 2 --enter-reason-list all --exit-reason-list all \
  2>&1 | grep -viE "WARNING|unclosed|connector|deque|coroutine" | tail -30
```
A blank `enter_reason` column means Phase 3 did not tag the signals. Go back
and tag them — P&L attribution is the whole point of this step.

Read `exp_ratio` (expectancy) and the `avg_win` vs `avg_loss` columns. A high
`wl_ratio_pct` with a negative `exp_ratio` is the asymmetric-risk failure mode
(anti-pattern #5), and it is invisible in the headline win rate.
This is where you learn *which* signal is carrying the strategy and which is
bleeding money. Report it — it drives the Phase 5 and postmortem decisions.

### Step 4 — Quality gates

Read the actual numbers out of the output. Do not estimate, do not round in
your favour, do not fill in a number you did not see.

| Gate | Threshold | Rationale |
|------|-----------|-----------|
| Profit factor | > 1.2 | > 1.0 is not enough; it must survive slippage |
| Max drawdown | < 25% | above this the strategy is untradeable in practice |
| Total trades | >= 100 | over a 3.5-year window; fewer is not significant |
| Sharpe (daily) | > 0.5 | risk-adjusted, not raw return |
| Profit per pair | > 0 on >= 60% of pairs | else it is a one-pair strategy |
| Exit reason mix | stoploss share < 50% | else the entry has no edge |
| Funding share of gross profit | < 20% | futures: else you are renting money to hold |

`FundingSkewCarry` is the exception to the funding gate — for that strategy
funding is revenue, and the gate is instead "`funding_fees` must be positive".
See its plan.

Get the funding number with the snippet in `.agent/COMMANDS.md` (Phase 4
section). Do not estimate it.

Win rate is **not** a gate. A 90% win rate with fat losses fails on profit factor.

## DO NOT
- Modify the strategy file
- Run hyperopt (Phase 5)
- Change config parameters
- Report profit metrics if a bias check failed
- Skip any metric in the output format

## Exit Criteria
- [ ] `lookahead-analysis` clean
- [ ] `recursive-analysis` clean
- [ ] Full IS backtest completed, export written to `results/backtests/`
- [ ] `backtesting-analysis` breakdown reported
- [ ] Every quality gate explicitly marked PASS or FAIL with its actual value
- [ ] `.agent/STATE.md` and `.agent/JOURNAL.md` updated

## Output Format

```
PHASE 4 RESULTS — <StrategyName>
─────────────────────────
BIAS CHECKS
Lookahead analysis:  CLEAN / BIASED (<detail>)
Recursive analysis:  CLEAN / UNSTABLE (<detail>)
─────────────────────────
IN-SAMPLE 20220101-20250630
Total trades:      <N>
Win rate:          <N>%
Profit factor:     <N>
Total profit:      <N>%
Max drawdown:      <N>%
Sharpe (daily):    <N>
Avg duration:      <N>
Funding fees:      <N> (<N>% of gross profit)
Avg leverage:      <N>x
Best pair:         <pair> <N>%
Worst pair:        <pair> <N>%
Top exit reason:   <reason> (<N>% of exits)
─────────────────────────
QUALITY GATES
Profit factor > 1.2:        PASS/FAIL (<actual>)
Max drawdown < 25%:         PASS/FAIL (<actual>)
Trades >= 100:              PASS/FAIL (<actual>)
Sharpe > 0.5:               PASS/FAIL (<actual>)
Profitable pairs >= 60%:    PASS/FAIL (<actual>)
Stoploss exits < 50%:       PASS/FAIL (<actual>)
Funding < 20% of gross:     PASS/FAIL (<actual>)
─────────────────────────
VERDICT: PASS (proceed to Phase 5) / FAIL (iterate)
```

## If FAIL
Do NOT proceed to Phase 5.
1. Write the analysis to `.agent/reports/<strategy>/phase4-iter<N>.md`
2. Read `.agent/prompts/backtest-postmortem.md` and follow it
3. Append the outcome to `.agent/JOURNAL.md`
4. Propose ONE targeted change and name the phase to revisit (2 or 3)
5. Wait for approval, then re-enter that phase

After 3 failed iterations, stop and escalate to the user with a summary of
every change tried and its effect.

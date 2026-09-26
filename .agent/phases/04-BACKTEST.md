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

Protections are part of the strategy now (scaffold phase). They are **silent
without `--enable-protections`** — every backtest from here on passes it, and
all gates are evaluated with protections active (that is the production
behavior). `--cache none` prevents day-old results being reused after edits.

```bash
mkdir -p results/backtests .agent/reports/$STRAT
freqtrade backtesting --config configs/strategies/$STRAT.json \
  --timerange 20220101-20250630 \
  --breakdown month --export signals \
  --cache none --enable-protections \
  --backtest-directory results/backtests \
  --notes "phase4 IS baseline" \
  2>&1 | grep -vE " INFO - " | tail -60
```
Use `--backtest-directory`. `--export-filename` is deprecated and ignored —
results would silently go to `user_data/backtest_results/` instead.
The export is a timestamped `.zip`; locate it with
`ls -t results/backtests/*.zip | head -1`.

### Step 2b — Realism pass at 1m detail

15m candles hide intra-candle exits; freqtrade can resolve them with 1m data
(all 10 pairs have it — see `ENVIRONMENT.md`). Callbacks (trailing stop,
custom stop) then evaluate per 1m candle, which is how live behaves.

**Scale the pass to what it can decide (2026-09-26, from the
BBRSIMeanReversion run):**
- Main-TF gates **PASS** -> run the **full-window** detail. This is where
  flattery detection matters most, and a passing verdict depends on it.
- Main-TF gates already **FAIL** (verdict decided) -> run a **reduced window**
  (e.g. 6 months on the 3 most-traded pairs) and record the reduction in the
  journal. The full 3.5y pass is OOM-prone and cannot rescue a decided
  verdict — the reduced pass keeps this step honest without burning an hour.
- Never silently skip the step either way.

```bash
freqtrade backtesting --config configs/strategies/$STRAT.json \
  --timerange 20220101-20250630 --cache none --enable-protections \
  --timeframe-detail 1m \
  2>&1 | grep -vE " INFO - " | tail -30
```

Compare headline numbers against Step 2. Interpretation:
- detail run **worse** (trailing stops fire intra-candle earlier, fills
  differ): expected — report both, treat the detail run as the honest one
- **divergence > ~20% on profit factor or drawdown**: the main-TF result was
  flattering the strategy. Record it; if gates pass only on the main-TF run,
  the verdict is FAIL.
- If the run OOMs (memory), restrict to the 3 most-traded pairs, note it, and
  extrapolate carefully — never silently skip the step.

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
| Exit reason mix | stoploss share of gross **loss** < 50% | else the entry has no edge. Report the trade-count share too — count 1.3% vs loss 22% read opposite ways (BBRSIMeanReversion 2026-09-26) |
| Funding share of gross profit | < 20% | futures: else you are renting money to hold |
| Payoff ratio (Kotegawa K4) | avg_loss < 3 x avg_win | inverted risk-reward is a kill regardless of win rate |

Gates are evaluated on the **detail (1m) run** where one exists.

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
- [ ] Full IS backtest completed with `--cache none --enable-protections`,
      export written to `results/backtests/`
- [ ] 1m-detail realism pass run and compared; divergences reported
- [ ] `backtesting-analysis` breakdown reported
- [ ] Every quality gate explicitly marked PASS or FAIL with its actual value
- [ ] `.agent/STATE.md`, `.agent/JOURNAL.md` and the strategy journal updated

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
─────────────────────────────────
1m-DETAIL PASS
Profit factor:     <N> (main-TF: <N>)
Max drawdown:      <N>% (main-TF: <N>%)
Trades:            <N> (main-TF: <N>)
─────────────────────────────────
QUALITY GATES (detail run)
Profit factor > 1.2:        PASS/FAIL (<actual>)
Max drawdown < 25%:         PASS/FAIL (<actual>)
Trades >= 100:              PASS/FAIL (<actual>)
Sharpe > 0.5:               PASS/FAIL (<actual>)
Profitable pairs >= 60%:    PASS/FAIL (<actual>)
Stoploss share of gross loss < 50%: PASS/FAIL (<actual loss-share; count-share <actual>)
Funding < 20% of gross:     PASS/FAIL (<actual>)
Payoff: avg_loss < 3x avg_win: PASS/FAIL (<actual>)
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

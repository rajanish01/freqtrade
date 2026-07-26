# Phase 2: Populate Indicators

## Prerequisite
Phase 1 exit criteria all PASS.

## Your Task
Modify ONLY `populate_indicators()` in the existing strategy file, plus the
imports at the top and `startup_candle_count`.

For each indicator in the strategy idea:
1. Prefer `talib.abstract` (`import talib.abstract as ta`); use
   `ft-pandas-ta` only when ta-lib has no equivalent
2. Assign into the dataframe with an `ind_` prefix
3. Check it against `.agent/reference/indicator-catalog.md` — if the indicator
   is not in the catalog, STOP and ask before adding it

## Rules
- Vectorised only. No `iterrows`, no `itertuples`, no `.iloc[-1]`.
- No `.shift(-N)`. Negative shift pulls the future into the present.
- Multi-timeframe only via `merge_informative_pair()`, and only if the
  strategy idea calls for it.
- Set `startup_candle_count = max(all lookback periods) + 50`.
- Do not reference an indicator you have not defined.

## DO NOT
- Touch `populate_entry_trend` / `populate_exit_trend` (Phase 3)
- Touch `minimal_roi`, `stoploss`, `trailing_stop` (risk is fixed; YELLOW)
- Add FreqAI features (Phase 6)
- Create new files

## Per-indicator checklist
For EACH indicator added, confirm:
- [ ] Column name uses the `ind_` prefix
- [ ] Only current and past candles are used
- [ ] Lookback period is covered by `startup_candle_count`
- [ ] It measures something no other indicator already measures
      (see anti-pattern #7, indicator redundancy)

## Verification

```bash
freqtrade backtesting --config configs/strategies/$STRAT.json \
  --timerange 20250601-20250701 \
  2>&1 | grep -vE " INFO - " | tail -20
```
Still 0 trades — that is correct, signals arrive in Phase 3. You are only
proving the indicators compute without error.

Then check indicator stability, which is the real test of `startup_candle_count`:
```bash
freqtrade recursive-analysis --config configs/strategies/$STRAT.json \
  --timerange 20250101-20250701 \
  2>&1 | grep -vE " INFO - " | tail -30
```
Any indicator reported as changing with history length means
`startup_candle_count` is too low. Raise it and re-run.

## Exit Criteria
- [ ] Every indicator from the strategy idea is implemented, `ind_` prefixed
- [ ] No indicator outside the approved catalog (or explicitly approved)
- [ ] `startup_candle_count` = max lookback + 50
- [ ] Smoke backtest runs without error
- [ ] `recursive-analysis` reports no unstable indicators
- [ ] Entry/exit methods untouched
- [ ] `.agent/STATE.md` updated

## Output Format

```
PHASE 2 COMPLETE
─────────────────────────
Indicators:            <name (period) -> column, one per line>
startup_candle_count:  <value>
New imports:           <list>
─────────────────────────
Smoke backtest:        PASS/FAIL
recursive-analysis:    PASS/FAIL (<unstable indicators or "none">)
─────────────────────────
VERDICT: PASS (proceed to Phase 3) / FAIL (reason)
```

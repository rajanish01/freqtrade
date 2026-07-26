# Phase 1: Strategy Scaffold

## Prerequisite
Phase 0 VERDICT = PASS.

## Your Task
Create exactly one file: `user_data/strategies/<StrategyName>.py`

Structure, no logic. The file must contain:
- Class inheriting from `IStrategy`, name in PascalCase matching the filename
- `INTERFACE_VERSION = 3`
- Class docstring stating the strategy hypothesis in two or three sentences
- `timeframe` from the strategy idea
- `can_short` — `True` only if the strategy idea has short logic
- `minimal_roi`, `stoploss`, `trailing_stop` — explicit conservative defaults
  (e.g. `minimal_roi = {"0": 0.10, "60": 0.05, "120": 0.01}`, `stoploss = -0.05`)
- `startup_candle_count: int = 200` (refined in Phase 2)
- `populate_indicators()` returning the dataframe unchanged
- `populate_entry_trend()` / `populate_exit_trend()` using the empty scaffold below
- Hyperopt parameter declarations as class attributes, `opt_` prefix,
  one per tunable value named in the strategy idea

## The empty scaffold — use exactly this

pandas 3 crashes the backtester if you assign to a not-yet-existing column
with a mask that matches nothing. Write the empty methods like this:

```python
def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    dataframe.loc[:, "enter_long"] = 0
    return dataframe

def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    dataframe.loc[:, "exit_long"] = 0
    return dataframe
```

Add the `enter_short` / `exit_short` lines only if `can_short = True`.

**Never write this** — it produces a `|V0` void column and an `AssertionError`
that appears to come from pandas:
```python
dataframe.loc[(), ['enter_long', 'enter_tag']] = (1, 'enter_long')   # BROKEN
```

## DO NOT
- Add indicator calculations (Phase 2)
- Add entry/exit conditions (Phase 3)
- Add FreqAI methods or config (Phase 6)
- Create any file other than the strategy file
- Import anything beyond `freqtrade.strategy`, `pandas`, and stdlib

## Exit Criteria
- [ ] File exists at `user_data/strategies/<StrategyName>.py`
- [ ] `freqtrade list-strategies --config configs/strategies/$STRAT.json` shows the
      strategy with status `OK`
- [ ] Smoke backtest runs clean and reports 0 trades:
      `freqtrade backtesting --config configs/strategies/$STRAT.json --strategy <name> --timerange 20250601-20250701`
- [ ] `populate_indicators` returns the dataframe unchanged
- [ ] No entry/exit conditions present
- [ ] All `opt_*` params from the strategy idea are declared
- [ ] `.agent/STATE.md` updated

## Output Format

```
PHASE 1 COMPLETE
─────────────────────────
File:              user_data/strategies/<name>.py
Class:             <ClassName>
Timeframe:         <tf>
can_short:         <bool>
Hyperopt params:   <list>
─────────────────────────
list-strategies:   PASS/FAIL
Smoke backtest:    PASS/FAIL (trades: 0)
─────────────────────────
VERDICT: PASS (proceed to Phase 2) / FAIL (reason)
```

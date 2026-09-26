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
- The **risk-layer block** (see "Risk layer" below): `position_adjustment_enable = False`,
  the `leverage()` callback from `futures-playbook.md` §4 with the plan's
  `target_vol_pct` / `max_leverage_cap`, and the `@property protections`
  template from `kotegawa-risk-layer.md` §K5 (candle counts converted to the
  strategy's timeframe)
- `use_custom_stoploss = False` (flip to `True` only if the plan calls for a
  custom stop, e.g. ObeliskRSIRegime — then read `.agent/reference/callbacks-reference.md` first)
- `populate_indicators()` returning the dataframe unchanged
- `populate_entry_trend()` / `populate_exit_trend()` using the empty scaffold below
- Hyperopt parameter declarations as class attributes, `opt_` prefix,
  one per tunable value named in the strategy idea
- Run the lint check (see Exit Criteria) before the smoke backtest

## Risk layer — verify and record at scaffold time

Read `.agent/reference/kotegawa-risk-layer.md`. Compute these from the values
you just wrote and record them in `.agent/reports/<Name>/journal.md`:
- `risk_per_trade = (tradable_balance_ratio / max_open_trades) x |stoploss|` — must be <= 0.02
- `|stoploss| / max_leverage_cap` (price distance) must be <= half the
  liquidation distance `1 / max_leverage_cap`
- `trailing_stop_positive_offset < minimal_roi["0"]` (docs rule — otherwise ROI
  always fires first) and `trailing_stop_positive <= offset / 3` (Kotegawa K4)
- the exact protections values chosen, in the strategy's timeframe

Any violation = FAIL before you run anything.

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
- [ ] Lint clean — no undefined names:
      `source .venv/bin/activate && python -m pyflakes user_data/strategies/<StrategyName>.py`
      (a dropped import surfaces only as a silent per-entry NameError and a 1x
      leverage fallback at trade time; `list-strategies` imports the module but
      does NOT catch it, and `py_compile` is syntax-only. Found on the
      BBRSIMeanReversion run 2026-09-26.)
- [ ] `freqtrade list-strategies --config configs/strategies/$STRAT.json` shows the
      strategy with status `OK`
- [ ] Smoke backtest runs clean and reports 0 trades:
      `freqtrade backtesting --config configs/strategies/$STRAT.json --timerange 20250601-20250701 --cache none`
- [ ] `populate_indicators` returns the dataframe unchanged
- [ ] No entry/exit conditions present
- [ ] All `opt_*` params from the strategy idea are declared
- [ ] Risk-layer checks computed and recorded in the journal (no violation)
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

# Phase 3: Entry & Exit Signals

## Prerequisite
Phase 2 exit criteria all PASS.

## Your Task
Modify ONLY `populate_entry_trend()` and `populate_exit_trend()`.

Build conditions from the `ind_*` columns created in Phase 2, with every
threshold supplied by an `opt_*` hyperopt parameter.

## Required pattern

Initialise the column first, then assign into it. This avoids the pandas 3
void-dtype crash described in `.agent/ENVIRONMENT.md` gotcha #1.

```python
def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    dataframe.loc[:, "enter_long"] = 0

    long_cond = (
        (dataframe["ind_close_vwap_dev"] < -self.opt_band_std.value)
        & (dataframe["ind_adx_14"] < self.opt_adx_max.value)
        & (dataframe["volume"] > 0)
    )
    dataframe.loc[long_cond, "enter_long"] = 1
    dataframe.loc[long_cond, "enter_tag"] = "vwap_lower_band"
    return dataframe
```

## Rules
- `& ` for AND, `|` for OR, and parenthesise every comparison.
- Always include `(dataframe["volume"] > 0)` in entry conditions — it filters
  dead candles that would otherwise produce untradeable fills.
- Read hyperopt params with `.value`.
- Every numeric threshold must come from an `opt_*` parameter. A literal number
  in a condition is a magic number and fails review (anti-pattern #8).
- Tag every entry and exit reason. Phase 4 analysis is useless without tags.
- Vectorised only. No `.iloc[-1]`.

## DO NOT
- Add or change indicator calculations (go back to Phase 2 if one is missing)
- Change risk parameters (YELLOW — requires user approval)
- Create new files

## Verification

```bash
freqtrade backtesting --config configs/strategies/$STRAT.json \
  --timerange 20250601-20250701 \
  2>&1 | grep -vE " INFO - " | tail -25
```

Interpreting the trade count on this 1-month window:
- **0 trades** -> FAIL. Conditions are too tight, or reference a column that is
  all-NaN. Loosen one threshold or check the indicator warm-up.
- **1–200 trades** -> reasonable, proceed.
- **> 2000 trades** -> FAIL. Signals are firing on noise. Tighten before Phase 4;
  a backtest at this rate is dominated by fees.

## Exit Criteria
- [ ] `populate_entry_trend` sets at least one entry condition
- [ ] `populate_exit_trend` sets at least one exit condition
- [ ] Every threshold uses an `opt_*` parameter (zero magic numbers)
- [ ] Every entry and exit is tagged
- [ ] `volume > 0` guard present on entries
- [ ] 1-month smoke backtest produces a trade count in the sane band above
- [ ] No indicator calculations added to the signal methods
- [ ] `.agent/STATE.md` updated

## Output Format

```
PHASE 3 COMPLETE
─────────────────────────
Entry conditions:  <plain-English summary>
Exit conditions:   <plain-English summary>
Entry tags:        <list>
opt_* used:        <list>
─────────────────────────
1-month trades:    <N>
1-month profit:    <N>%
Trade count band:  PASS/FAIL
Magic numbers:     NONE / <list>
─────────────────────────
VERDICT: PASS (proceed to Phase 4) / FAIL (reason)
```

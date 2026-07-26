# Phase 6: FreqAI Integration (Optional)

## Prerequisite
Phase 5 VERDICT = PASS, **and** the user has explicitly approved enabling
FreqAI (this is a YELLOW action).

If `.agent/prompts/strategy-idea.md` says FreqAI intent = No, skip straight to
Phase 7 and mark this phase SKIPPED in `.agent/STATE.md`.

FreqAI is a filter on top of a strategy that already works. It cannot rescue a
losing strategy — it will just overfit the losses.

---

### Step 0 — Confirm the model exists

```bash
freqtrade list-freqaimodels
```
Only `LightGBM*`, `XGBoost*` and `SKLearnRandomForestClassifier` are installed
here. **CatBoost, torch and the Reinforcement Learning models are not.**
Default choice: `LightGBMRegressor`. RL requires explicit approval and an install.

### Step 1 — Design features before writing them

Read `.agent/prompts/freqai-feature-eng.md` and produce the feature proposal
list first. Get agreement, then implement.

### Step 2 — Implement feature engineering

In the strategy file, implement the FreqAI hooks:

```python
def feature_engineering_expand_all(self, dataframe, period, metadata, **kwargs):
    dataframe["%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
    return dataframe

def feature_engineering_expand_basic(self, dataframe, metadata, **kwargs):
    dataframe["%-pct-change"] = dataframe["close"].pct_change()
    dataframe["%-raw_volume"] = dataframe["volume"]
    return dataframe

def feature_engineering_standard(self, dataframe, metadata, **kwargs):
    dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
    dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
    return dataframe

def set_freqai_targets(self, dataframe, metadata, **kwargs):
    dataframe["&-s_close"] = (
        dataframe["close"]
        .shift(-self.freqai_info["feature_parameters"]["label_period_candles"])
        .rolling(self.freqai_info["feature_parameters"]["label_period_candles"])
        .mean()
        / dataframe["close"]
        - 1
    )
    return dataframe
```

Naming is enforced by FreqAI, not by our conventions:
- `%-` prefix = feature. `&-` prefix = label/target.
- The `ind_` and `feat_` conventions do **not** apply to these hooks.
- Forward-looking `.shift(-N)` is legal **only** inside `set_freqai_targets`.
  Anywhere else it is lookahead bias.

### Step 3 — Configure

`configs/strategies/<Name>.json` is already schema-valid. Adjust only:
`label_period_candles`, `include_timeframes`, `include_corr_pairlist`,
`train_period_days`, `backtest_period_days`, `model_training_parameters`.

Required blocks `feature_parameters` and `data_split_parameters` must stay.

### Step 4 — Gate the predictions, do not replace the logic

```python
long_cond = (
    existing_deterministic_conditions
    & (dataframe["do_predict"] == 1)              # model is confident / not outlier
    & (dataframe["&-s_close"] > self.opt_pred_threshold.value)
)
```
The Phase 3 conditions remain. FreqAI only removes trades; it never adds them
and it never touches the risk layer.

### Step 5 — Backtest

```bash
freqtrade backtesting --config configs/strategies/$STRAT.json --freqaimodel LightGBMRegressor \
  --timerange 20250701-20260709 \
  2>&1 | grep -vE " INFO - " | tail -50
```
FreqAI needs `train_period_days` (60) of history *before* the start date. The
data begins 2022-01-01, so any start after 2022-03-01 is safe.

Expect this to be slow — it trains a model per pair per `backtest_period_days`.

## DO NOT
- Remove or weaken the deterministic entry/exit logic
- Let FreqAI influence `stoploss`, position size or drawdown limits
- Use RL models (not installed; requires approval)
- Train across the IS/OOS boundary
- Keep FreqAI if it does not beat the Phase 5 baseline

## Exit Criteria
- [ ] Model confirmed present via `list-freqaimodels`
- [ ] Feature proposal reviewed before implementation
- [ ] `%-` features and `&-` target implemented
- [ ] `do_predict` guard present in the entry conditions
- [ ] FreqAI backtest completes without error
- [ ] Compared head-to-head against the Phase 5 OOS baseline
- [ ] `.agent/STATE.md` and `.agent/JOURNAL.md` updated

## Decision rule
Keep FreqAI only if, on the same OOS window, it improves Sharpe **or** reduces
max drawdown, **without** reducing profit factor. Extra complexity must pay for
itself. If it does not, revert to the Phase 5 strategy and record why.

## Output Format

```
PHASE 6 RESULTS — <StrategyName>
─────────────────────────
Model:             <model>
Features:          <count>
Target:            <description>
Train window:      <days>   Backtest period: <days>
─────────────────────────
COMPARISON (OOS 20250701-20260709)
                   Baseline    +FreqAI
Profit factor:     <N>         <N>
Sharpe:            <N>         <N>
Max drawdown:      <N>%        <N>%
Trades:            <N>         <N>
─────────────────────────
VERDICT: KEEP (improved) / REVERT (no improvement or degraded)
```

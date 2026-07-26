# CONVENTIONS.md — Code Standards

Read this before writing or editing any strategy code.

## Naming

| Thing | Convention | Example |
|-------|-----------|---------|
| Strategy class | PascalCase, matches filename | `VWAPBandReversion` |
| Indicator column | `ind_` prefix, snake_case | `ind_rsi_14`, `ind_bb_upper` |
| Hyperopt parameter | `opt_` prefix | `opt_rsi_buy_threshold` |
| Entry/exit tag | short snake_case reason | `vwap_lower_band` |
| FreqAI feature | `%-` prefix (**FreqAI's rule, not ours**) | `%-rsi-period` |
| FreqAI target | `&-` prefix (**FreqAI's rule**) | `&-s_close` |

The `ind_`/`opt_` conventions are ours. The `%-`/`&-` prefixes are enforced by
FreqAI itself — do not "correct" them to match our style.

## Mandatory patterns

- Initialise signal columns before conditional assignment:
  ```python
  dataframe.loc[:, "enter_long"] = 0
  dataframe.loc[cond, "enter_long"] = 1
  ```
- Vectorised operations only in `populate_*` — never `iterrows`, `itertuples`,
  or `.iloc[-1]` there.
  **Scope note:** this rule applies to `populate_indicators`,
  `populate_entry_trend` and `populate_exit_trend` only. In per-trade callbacks
  (`leverage`, `custom_stoploss`, `custom_exit`, `confirm_trade_entry`),
  reading the latest row via `df["col"].iat[-1]` is the correct pattern —
  those are evaluated once per candle by design.
- Every entry condition includes `(dataframe["volume"] > 0)`
- Every entry and exit is tagged, so Phase 4 analysis can attribute P&L
- `startup_candle_count` = max indicator lookback + 50, validated by
  `recursive-analysis`
- `minimal_roi`, `stoploss`, `trailing_stop` always declared explicitly
- Multi-timeframe only via `merge_informative_pair()`
- ta-lib (`talib.abstract`) first; `ft-pandas-ta` only where ta-lib has no equivalent
- One strategy = one `.py` file. No helper modules.

## Forbidden — automatic rejection

- `dataframe.loc[(), [...]] = (...)` — void-dtype crash on pandas 3
  (see `ENVIRONMENT.md` gotcha #1)
- `.shift(-N)` anywhere except inside `set_freqai_targets()` — lookahead bias
- `datetime.now()` / `time.time()` in strategy logic — use the candle timestamp
- Hardcoded pair names in strategy logic
- Magic numbers in conditions — every threshold is an `opt_*` parameter
- ML output influencing `stoploss`, position size, or drawdown limits
- Creating `.py` files beyond the single strategy file
- Editing anything under `freqtrade/`

## Risk layer is deterministic

`stoploss`, `minimal_roi`, `trailing_stop`, `max_open_trades`, `stake_amount`,
`target_vol_pct` and `max_leverage_cap` are set by hand and changed only with
explicit user approval (YELLOW). Hyperopt never optimises them. FreqAI never
predicts them.

Reason: when the model is wrong — and it will be — the risk layer is the only
thing standing between a bad prediction and the account.

**Dynamic leverage is still deterministic.** The `leverage()` callback scales
size by measured volatility (NATR) using a fixed formula with a hard cap. It is
rule-based, reproducible, and contains no learned parameters. See
`.agent/reference/futures-playbook.md` §4 for the canonical implementation.

**Leverage changes what stoploss means.** Freqtrade computes
`profit_ratio = price_change * leverage`, so `stoploss` is account risk, not
price distance. A `-0.05` stop at 3x fires after a 1.67% price move. Never port
a stoploss between strategies with different leverage caps without recomputing.

## Futures — this repo is futures-only

- `trading_mode: futures`, `margin_mode: isolated`, exchange `binanceusdm`
- Pair notation is always `BTC/USDT:USDT`. `BTC/USDT` is wrong and will find no data.
- Funding is charged every 8h on notional and **is modelled** in backtests.
  Report `funding_fees` in Phase 4.
- `can_short = True` is a hypothesis claim, not a feature flag. Enable it only
  where the edge is genuinely symmetric (see `futures-playbook.md` §3).
- Every strategy declares `ind_natr_14`; the leverage callback depends on it.

## One config per strategy

`configs/strategies/<Name>.json`, inheriting `configs/base.futures.json` via
`add_config_files`. The config declares its own `strategy`, so `--strategy` is
redundant.

**Never** pass, read or write `config.json` or `user_data/config.json`. A
freqtrade command without an explicit `--config` silently falls back to them.

## Quality gates

Phase 4 / Phase 5-OOS gates (all must pass):

| Metric | Threshold |
|--------|-----------|
| Data window | >= 180 days (we use 3.5y IS / 1y OOS) |
| Profit factor | > 1.2 |
| Max drawdown | < 25% |
| Total trades | >= 100 |
| Sharpe (daily) | > 0.5 |
| Profitable pairs | >= 60% |
| Stoploss share of exits | < 50% |

Phase 7 robustness gates:

| Metric | Threshold |
|--------|-----------|
| Consecutive losing quarters | <= 2 |
| Losing quarters overall | < 40% |
| Parameter sensitivity | PF > 1.0 at ±20% |
| Single-pair profit share | < 50% |
| Profit factor at 2x fees | > 1.0 |

Win rate is deliberately absent. It is not a quality signal — a 90% win rate
with oversized losses fails on profit factor, which is the gate that matters.

## Reporting

- Report the number you saw, or say the command did not run.
- Never fill an output template with placeholder or estimated values.
- Bad results are reported exactly as plainly as good ones.

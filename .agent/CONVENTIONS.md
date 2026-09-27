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
- One STRATEGY = one `.py` file, still true, no exceptions. No helper
  modules under `user_data/strategies/`.
  **Scope note (MAZE):** this rule is about strategy code, not framework
  tooling. `.agent/scripts/*.py` / `.agent/scripts/hyperopt/*.py` (the maze
  ledger tool and its gate-aligned loss function) are framework
  infrastructure living under `.agent/` (READ+WRITE per root `AGENTS.md` §1),
  not strategy files, and are exempt from this line and from the "Forbidden"
  entry below. A strategy is still ever exactly one `.py` file; the tooling
  that measures it is not part of that count.

## Forbidden — automatic rejection

- `dataframe.loc[(), [...]] = (...)` — void-dtype crash on pandas 3
  (see `ENVIRONMENT.md` gotcha #1)
- `.shift(-N)` anywhere except inside `set_freqai_targets()` — lookahead bias
- `datetime.now()` / `time.time()` in strategy logic — use the candle timestamp
- Hardcoded pair names in strategy logic
- Magic numbers in conditions — every threshold is an `opt_*` parameter
- ML output influencing `stoploss`, position size, or drawdown limits
- Creating `.py` files beyond the single strategy file under
  `user_data/strategies/` (see the scope note above for `.agent/scripts/`)
- Editing anything under `freqtrade/`

## Risk layer is deterministic

`stoploss`, `minimal_roi`, `trailing_stop`, `max_open_trades`, `stake_amount`,
`target_vol_pct`, `max_leverage_cap` and the protection VALUES are set by
hand at Phase 1 as the strategy's starting point, and the risk MECHANISM
(fixed-fractional sizing, half-capital reserve, which protection methods
exist, the K4 payoff floor as a hard gate) never changes without explicit
user approval (YELLOW) — see `reference/kotegawa-risk-layer.md`. FreqAI never
predicts any of it, ever.

**MAZE policy (2026-09-27):** from `.agent/phases/04M-MAZE.md` tier T2
onward, the specific NUMBERS for `stoploss`, `max_open_trades`,
`target_vol_pct`/`max_leverage_cap` and protection values are a bounded
hyperopt search dimension — bounded by the K2/K7 formulas, enforced every
epoch by `.agent/scripts/hyperopt/MazeGateLoss.py`, not by a human glancing
at the result afterward. `minimal_roi`/`trailing_stop` stay a structural
(T1, config-level) choice rather than a hyperopted space by default. This is
a wider, formula-gated search of the numbers — it does not touch the
mechanism, and it is still never ML.

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

### Kotegawa risk layer (mandatory — see `reference/kotegawa-risk-layer.md`)

- `tradable_balance_ratio: 0.5` — half-capital reserve (set in base config;
  strategies never override it)
- Per-trade risk: `(0.5 / max_open_trades) * |stoploss| <= 2%` of equity —
  computed and recorded at Phase 1
- Protections live in the strategy class as `@property protections`
  (StoplossGuard / MaxDrawdown / CooldownPeriod) — the set of methods is
  hand-tuned and never hyperopted; the values are a bounded MAZE T2 search
  dimension (`--spaces protection`, see `04M-MAZE.md`) — and require
  `--enable-protections` in every backtest from Phase 4 onward (verified:
  this flag also applies during hyperopt, not backtest-only)
- `position_adjustment_enable = False` — never average down
- `trailing_stop_positive_offset < minimal_roi["0"]` — docs rule; if the
  offset is at/above ROI@0, ROI always fires first and the trailing config is
  dead code
- `confirm_trade_exit` never blocks a stoploss exit
- Stoploss must fire at <= half the liquidation distance at max leverage

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

This exact table is also implemented as machine-checkable code in
`.agent/scripts/hyperopt/MazeGateLoss.py` and `.agent/scripts/maze.py`
(`compute_gates()`) — used to score every MAZE node automatically, with the
trade-count gate rate-scaled to whatever window a node was measured on
instead of a flat 100. If you change a threshold here, change it in both of
those too (each file names the other in a comment).

Phase 4 / Phase 5-OOS gates (all must pass):

| Metric | Threshold |
|--------|-----------|
| Data window | >= 180 days (we use 3.5y IS / 1y OOS) |
| Profit factor | > 1.2 |
| Max drawdown | < 25% |
| Total trades | >= 100 |
| Sharpe (daily) | > 0.5 |
| Profitable pairs | >= 60% |
| Stoploss share of exits | < 50% of gross **loss** (trade-count share is reported alongside; loss-share is the gate — count 1.3% vs loss 22% read opposite ways, BBRSIMeanReversion 2026-09-26) |
| Payoff ratio (Kotegawa K4) | avg_loss < 3 x avg_win |

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

## Journals

- Per-strategy journal: `.agent/reports/<Name>/journal.md`, created at
  Phase 0, appended once per phase completion AND once per fix iteration.
  Append-only — never edit or delete past entries.
- Every phase outcome also gets a one-line cross-entry in `.agent/JOURNAL.md`.
- Temporary config/param changes are logged in the journal and restored in
  the same turn.
- **The split:** the global `.agent/JOURNAL.md` is the cross-run log — it is
  what the postmortem and final-verdict prompts read. The per-strategy journal
  holds phase-by-phase detail, including the Phase 1 risk-layer numbers. When
  diagnosing a failure, read BOTH, and mirror the risk numbers into the global
  entry so they are never invisible to the failure analysis.
- From Phase 4 onward, `.agent/reports/<Name>/maze/ledger.csv` and `tree.md`
  (maintained by `.agent/scripts/maze.py`, see `04M-MAZE.md`) are the
  per-node record — one row per variant tried, pass or fail. This is
  additional to, not a replacement for, the per-strategy journal, which
  still carries the tier-level narrative (why a candidate set was chosen,
  why a line was pruned).
- A strategy that dies (kill criteria, or the maze exhausted per
  `04M-MAZE.md` "Exhaustion" — not a fixed iteration count from Phase 4
  onward; Phases 0-3 keep the 3-iteration budget, see `iteration-fix.md`)
  gets a terminal verdict at `.agent/reports/<Name>/DEAD.md` — see
  `.agent/prompts/final-verdict.md`.

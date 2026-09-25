# ENVIRONMENT.md — Verified Facts About This Machine

Everything here was verified by running the command shown. Do not guess these
values; if something contradicts this file, re-verify and update this file.

Last verified: 2026-09-24

---

## Runtime

| Thing | Value |
|-------|-------|
| Python | 3.13.11 (venv; `freqtrade --version`. Earlier note of 3.14.6 was stale) |
| pandas | **3.0.3** (see gotcha #1 — this breaks common freqtrade snippets) |
| numpy | 2.4.6 |
| ccxt | 4.5.61 |
| freqtrade | 2026.6 (this checkout, bleeding-edge) |
| venv | `.venv` — activate with `source .venv/bin/activate` |
| `timeout` cmd | Linux shell, available; note the bash tool kills its process group on timeout — use `setsid` for long downloads (see data-download.md) |

## Agent model

Running qwen3-coder-32b locally via Ollama.

Ollama defaults to a small context window (often 4096 tokens) regardless of what
the model supports. That is not enough: the always-loaded set
(`AGENTS.md` + `STATE.md` + `ENVIRONMENT.md`) is ~2.8k tokens before a phase
file, a command, or its output. With the default the model will silently drop
the earliest instructions — usually the file boundaries and the autonomy rules.

Set the context explicitly, e.g.:
```
/set parameter num_ctx 32768
```
or in a Modelfile: `PARAMETER num_ctx 32768`.

If the agent starts ignoring the phase gates, editing files outside the allowed
paths, or forgetting the IS/OOS split, suspect context truncation first.

## Data (verified: 2026-09-24, `freqtrade list-data --config configs/strategies/BBRSIMeanReversion.json --show-timerange`)

| Thing | Value |
|-------|-------|
| Exchange dir | `user_data/data/binanceusdm/futures/` |
| Exchange name in config | **`binanceusdm`** (NOT `binance`) |
| Trading mode | `futures` / `margin_mode: isolated` |
| Pair format | **`BTC/USDT:USDT`** (futures notation, with the `:USDT` suffix) |
| Pairs with data | BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX, LINK, LTC (all `/USDT:USDT`) |
| Timeframes on disk | 1m, 5m, 15m, 30m, 1h, 4h, 8h, 1d (all 10 pairs, all full range) |
| 1m coverage | all 10 pairs, full range — enables `--timeframe-detail 1m` realism passes |
| Common date range | **2022-01-01 → 2026-09-23** (fresh download 2026-09-24; supersedes the old 2026-07-09 end) |
| Funding rate | 10 files at **1h, native** (8h rows inside). Gotcha #13's manual copy repair is NOT needed for fresh downloads. Mark price: 1h. |
| Dataset restore commands | `.agent/reference/data-download.md` |

The IS/OOS split below is UNCHANGED (IS 20220101-20250630, OOS 20250701-20260709).
Data now extends ~2.5 months beyond the documented OOS end — that extra window
(20260709-20260923) is untouched by anything and available if the user approves
extending Phase 7 validation with a 19th quarter.

There is also a `user_data/data/binance/` directory. It is a **stale partial
copy** (6 pairs, only 15m + 1h). Do not use it. Do not delete it either.

### Network and downloads

**Network IS available** (verified 2026-09-24: api.binance.com and
data.binance.vision both reachable). Restoring the standard dataset is
pre-authorized; anything beyond it (new pairs/exchanges/modes, `--dl-trades`)
still requires asking the user first. Use the verified commands in
`.agent/reference/data-download.md` — not improvised ones.

---

## The IS / OOS split — MEMORISE THIS

| Window | Timerange | Used for |
|--------|-----------|----------|
| **In-sample (IS)** | `20220101-20250630` | Phase 4 backtest, Phase 5 hyperopt |
| **Out-of-sample (OOS)** | `20250701-20260709` | Phase 5 validation, Phase 7 — **never optimise on this** |
| Smoke / syntax check | `20250601-20250701` | fast 1-month run to prove code executes |

Touching the OOS window with hyperopt invalidates the entire run.

---

### 13. Funding-rate data was repaired — do not undo it
Binance's `funding_fee_timeframe` defaults to **1h**, but the download on disk
was **8h**, so freqtrade found no funding data and **silently applied zero
funding fees** to every futures backtest. That systematically overstated any
strategy holding positions overnight.

Inspection showed the two files are structurally identical — the "1h" file also
contains only 8-hourly rows (00:00 / 08:00 / 16:00 UTC). The timeframe in the
filename is just where freqtrade looks. So each
`*-8h-funding_rate.feather` was copied to `*-1h-funding_rate.feather`:

```bash
cd user_data/data/binanceusdm/futures
for f in *-8h-funding_rate.feather; do cp -n "$f" "${f/-8h-/-1h-}"; done
```

Verified after: the `No history for <PAIR>, funding_rate, 1h found` warnings are
gone, and 32 of 42 trades in the canary backtest now carry non-zero
`funding_fees`. Both files are kept; nothing was deleted.

If those warnings ever reappear, funding is silently free again and every
futures result is optimistic. Re-run the copy.

Funding is also readable inside a strategy (verified):
```python
self.dp.get_pair_dataframe(pair, "1h", candle_type="funding_rate")   # 769 rows
self.dp.get_pair_dataframe(pair, "1h", candle_type="mark")           # 771 rows
```
Values are `0.0` except at funding times — forward-fill before use.
`self.dp.funding_rate(pair)` is a **live** call and returns nothing in backtest.

## Configs

**One config per strategy.** Each `configs/strategies/<Name>.json` inherits
`configs/base.futures.json` through `add_config_files: ["../base.futures.json"]`,
and declares its own `strategy`, `timeframe` and `pair_whitelist`.

| File | Purpose |
|------|---------|
| `configs/base.futures.json` | shared: exchange, futures mode, pricing, api_server, fee, hyperopt_loss. **No strategy, no pairs, no timeframe.** |
| `configs/strategies/<Name>.json` | one per strategy — all phases use this single file |
| `configs/strategies/SmokeTestStrategy.json` | Phase 0 infra canary |
| `config.json`, `user_data/config.json` | **OFF-LIMITS.** Never read, write or pass. |

Verified: `freqtrade backtesting --config configs/strategies/SmokeTestStrategy.json`
loads exactly two files (the strategy config and the base) and never touches
`config.json`. `--strategy` is unnecessary because the config declares it.

Because freqtrade defaults to `user_data/config.json` or `config.json` when
`--config` is omitted, **a command without `--config` is always a bug.**

---

## GOTCHAS — each of these has actually bitten this repo

### 0. Config architecture (design decision, docs-verified)

Freqtrade's documented default is `config.json` in the cwd. This repo
deliberately bypasses that default on every command: `--config
configs/strategies/<Name>.json` (inheriting `configs/base.futures.json` via
`add_config_files` — both documented freqtrade mechanisms). Root `config.json`
and `user_data/config.json` are the user's own files: never read, never
written, never passed. Benefits: per-strategy isolation, reproducible runs,
the user's own setup keeps working untouched.

### 0b. `--cache` defaults to `day`

A backtest re-run within 24h with a matching config can silently load a
cached result. Always pass `--cache none` in framework commands (already in
all `COMMANDS.md` templates). The cache cannot see edits to imported modules
and can reuse results from runs made before late-arriving data.

### 0c. `--analyze-per-epoch` is a correctness flag, not a speed flag

Hyperopt runs `populate_indicators` once by default. Any `opt_*` parameter
used *inside* `populate_indicators` (Keltner mult, VWAP period, SuperTrend
period/mult) does not recompute per epoch — the epochs then optimise against
stale, default-valued columns. Such strategies MUST pass
`--analyze-per-epoch`, accepting the slowdown.

### 0d. Protections are silent in backtests without `--enable-protections`

Strategies define protections as a class `@property` (never config — gotcha
#3). Backtesting and hyperopt ignore them unless `--enable-protections` is
passed. Every Phase 4/5/7 backtest template includes it.

### 1. pandas 3 void-dtype crash (most important)
This common freqtrade scaffold pattern **crashes the backtester**:

```python
# BROKEN — creates a |V0 void-dtype column when the mask matches no rows
dataframe.loc[(), ['enter_long', 'enter_tag']] = (1, 'enter_long')
```

It fails deep inside `backtesting.py` with
`AssertionError: Something has gone wrong, please report a bug at pandas`.
The message names pandas, but **the bug is in the strategy**.

Correct empty scaffold:
```python
dataframe.loc[:, 'enter_long'] = 0
```
Correct populated form (assign to a column that already exists as int):
```python
dataframe.loc[cond, 'enter_long'] = 1
dataframe.loc[cond, 'enter_tag'] = 'my_tag'
```

### 2. `api_server` env vars are set in this shell
`FREQTRADE__API_SERVER__{USERNAME,PASSWORD,JWT_SECRET_KEY,WS_TOKEN}` are
exported in the environment. They inject a **partial** `api_server` block into
every config. Any config that omits `api_server` therefore fails with
`Configuration error: 'enabled' is a required property`.

Every config in `configs/` must keep its full `api_server` block. Do not remove it.

### 3. `"protections": []` is a hard error
Setting `protections` in a config file is deprecated and aborts startup.
Protections belong in the strategy class, not the config.

### 4. Ticker pricing unavailable on binanceusdm
`entry_pricing`/`exit_pricing` must use `"use_order_book": true`.
With `false` you get `Configuration error: Ticker pricing not available`.

### 5. `hyperopt` is not a config key
There is no top-level `"hyperopt": {...}` object in the freqtrade schema.
It is silently ignored. Use flat keys (`hyperopt_loss`, `hyperopt_min_trades`,
`hyperopt_random_state`, `hyperopt_jobs`) or CLI flags.

### 6. Export filenames are not user-controllable
- `freqtrade backtesting`: `--export-filename` is **deprecated and silently
  ignored**. Use `--backtest-directory <dir>`. Output is a timestamped `.zip`
  plus a `.meta.json`, not a name you choose. Find the newest with
  `ls -t <dir>/*.zip | head -1`.
- `freqtrade hyperopt`: has no export-filename option at all. Results go to
  `user_data/hyperopt_results/`, and best params are written next to the
  strategy as `<StrategyName>.json`. Read them back with `freqtrade hyperopt-show`.

If an export seems to have vanished, it went to the default directory
`user_data/backtest_results/`.

### 6b. Do not set `strategy_path` in the config
`user_data/strategies/` is already on the default search path. Adding
`"strategy_path": "user_data/strategies/"` makes freqtrade find every strategy
twice and `list-strategies` reports `DUPLICATE NAME` instead of `OK`.

### 7. Only these FreqAI models are installed
`LightGBM*`, `XGBoost*`, `SKLearnRandomForestClassifier`.
**CatBoost is not installed. torch / Reinforcement Learning models are not installed.**
Verify with `freqtrade list-freqaimodels`.

### 8. Strategy `timeframe` overrides the config
The `timeframe` in the strategy class wins over the one in the JSON config.

### 9. `lookahead-analysis` needs `--pairs`
It reads `config["pairs"]` (the `--pairs` CLI arg), **not**
`exchange.pair_whitelist`. Without `--pairs` it loads zero pairs, finds zero
trades, and reports `too few trades caught (0/10)` — which looks like a result
but means the test never ran. Always pass `--pairs` explicitly.

It also needs >= 10 trades in the window (`--minimum-trade-amount`, default 10),
so give it at least a year.

### 10. Do not set `available_capital`
`lookahead-analysis` forces `stake_amount: 10000` and
`dry_run_wallet: 1_000_000_000` internally. An `available_capital` of 1000 in
the config caps the wallet, so no trade can ever open and the analysis silently
finds nothing. `available_capital` has been removed from all `configs/*.json`
for this reason. Use `dry_run_wallet` alone.

### 11. `price_side` must be `"other"`
`lookahead-analysis` forces market orders, and freqtrade rejects market entry
orders unless `entry_pricing.price_side` is `"other"`
(`Configuration error: Market entry orders require entry_pricing.price_side = "other"`).
All configs use `"other"`, which is also the more conservative fill assumption.

### 12. Benign warnings — ignore these
- `binanceusdm requires to release all resources...` / `Unclosed connector` —
  ccxt teardown noise on exit, always printed, harmless.
- `Using N calls to get OHLCV` — startup-candle warning, not an error.

Do not spend an iteration chasing any of these.

**NOT benign — do not ignore:** `No history for <PAIR>, funding_rate, 1h
found`. It means funding fees are silently zero (gotcha #13) and every futures
backtest is optimistic. Treat it as a failure: re-verify per
`.agent/reference/data-download.md` (funding section), not as teardown noise.

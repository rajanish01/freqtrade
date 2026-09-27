# COMMANDS.md — Verified Commands

Every command here has been executed successfully in this repo. Copy them
literally; set `STRAT` once and change only the timerange.

```bash
source .venv/bin/activate
STRAT=SmokeTestStrategy           # set per run: a plan name from INDEX.md, or the canary
CFG=configs/strategies/$STRAT.json
```

**Two hard rules:**
1. Every command passes `--config $CFG`. Never omit it — freqtrade silently
   falls back to `config.json` / `user_data/config.json`, which are off-limits.
2. `--strategy` is **not needed**. Each config declares its own `strategy`.
   Passing it anyway is harmless but redundant; passing a *different* one is a bug.

Noise filter for long output:
```bash
2>&1 | grep -vE " INFO - " | tail -40
```
Some commands print ccxt teardown noise on exit; use this instead:
```bash
2>&1 | grep -viE "WARNING|unclosed|connector|deque|coroutine" | tail -30
```

---

## Phase 0 — data & infra

```bash
# What data exists, and over what range
freqtrade list-data --config $CFG --show-timerange

# Confirm the strategy is discoverable (expect status OK, not DUPLICATE NAME)
freqtrade list-strategies --config $CFG

# Infra canary — proves configs + data + engine work, independent of your strategy
freqtrade backtesting --config configs/strategies/SmokeTestStrategy.json \
  --timerange 20250601-20250701 \
  2>&1 | grep -vE " INFO - " | tail -15
```

## Phase 1–3 — fast syntax / signal checks

```bash
# 1-month smoke run. Phase 1-2: 0 trades is fine. Phase 3: must be > 0.
freqtrade backtesting --config $CFG --timerange 20250601-20250701 --cache none \
  2>&1 | grep -vE " INFO - " | tail -20
```

## Phase 4 — bias checks, then the full backtest

Bias checks run FIRST. A strategy that fails these is not measurable.

```bash
# Lookahead bias: does the strategy see the future?
# --pairs IS REQUIRED. This command reads config["pairs"], NOT the whitelist.
# Without it you get "too few trades caught (0/10)" and no analysis at all.
freqtrade lookahead-analysis --config $CFG \
  --timerange 20240101-20250630 \
  --pairs BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT \
  2>&1 | grep -viE "WARNING|unclosed|connector|deque|coroutine" | tail -12
```
Needs >= 10 trades in the window or it silently cancels. Read `has_bias`:
`No` = clean. "too few trades caught" = the test never ran; widen the window.
The cancellation reason is logged at INFO, so drop the filter to see it.

```bash
# Recursive bias: do indicators change value as history grows?
# This is how you validate startup_candle_count.
freqtrade recursive-analysis --config $CFG \
  --timerange 20250101-20250301 \
  2>&1 | grep -vE " INFO - " | tail -20
```
Every indicator must read `0.000%`. Non-zero drift = `startup_candle_count` too low.

```bash
# Full in-sample backtest with export. Protections are silent without
# --enable-protections; --cache none prevents day-old results being reused.
mkdir -p results/backtests
freqtrade backtesting --config $CFG --timerange 20220101-20250630 \
  --breakdown month --export signals --cache none --enable-protections \
  --backtest-directory results/backtests --notes "IS baseline" \
  2>&1 | grep -vE " INFO - " | tail -60
```
Use `--backtest-directory`, **not** `--export-filename` (deprecated and silently
ignored — results would land in `user_data/backtest_results/`). Output is a
timestamped `.zip`; find it with `ls -t results/backtests/*.zip | head -1`.

```bash
# Realism pass: resolves intra-candle exits on 1m data (all 10 pairs have it).
# Trailing/custom stops then behave as they will live. Compare to the main run.
freqtrade backtesting --config $CFG --timerange 20220101-20250630 \
  --cache none --enable-protections --timeframe-detail 1m \
  2>&1 | grep -vE " INFO - " | tail -30
```

```bash
# Per-entry/exit-reason breakdown. Requires --export signals above.
freqtrade backtesting-analysis --config $CFG \
  --backtest-directory results/backtests \
  --analysis-groups 0 1 2 --enter-reason-list all --exit-reason-list all \
  2>&1 | grep -viE "WARNING|unclosed|connector|deque|coroutine" | tail -30
```
A blank `enter_reason` column means the strategy is not tagging its signals.

```bash
# Futures-specific: how much did funding cost?
python3 -c "
import zipfile,glob,json,pandas as pd
z=sorted(glob.glob('results/backtests/*.zip'))[-1]
zf=zipfile.ZipFile(z); m=[n for n in zf.namelist() if n.endswith('.json') and 'config' not in n][0]
d=json.loads(zf.read(m)); s=list(d['strategy'])[0]
t=pd.DataFrame(d['strategy'][s]['trades'])
print('trades', len(t), '| funding total', round(t.funding_fees.sum(),4),
      '| gross profit', round(t.profit_abs.sum(),4))
"
```

## Phase 4M — the maze (tree search, supersedes a linear Phase 4 FAIL)

```bash
# One-time per strategy, right after the T0 (Phase 4) baseline is measured:
python .agent/scripts/maze.py init $STRAT
python .agent/scripts/maze.py status $STRAT      # tree summary, any time
python .agent/scripts/maze.py tree $STRAT        # regenerate tree.md

# Register a T1 structural move (config-level — no .py edit needed for
# timeframe/stoploss/ROI/trailing/max_open_trades; see ENVIRONMENT.md gotcha #8):
python .agent/scripts/maze.py node $STRAT --parent N0001 --tier T1 \
  --type timeframe --desc "try 1h" --set timeframe=1h

# Run a node (backtest or hyperopt) — ALWAYS through maze.py, never a bare
# freqtrade call, once a strategy has maze nodes (genome-slot staging, see
# maze.py's module docstring):
python .agent/scripts/maze.py run $STRAT N0002 --cmd backtest \
  --timerange 20220101-20250630 --detail-1m

python .agent/scripts/maze.py run $STRAT N0001 --cmd hyperopt \
  --timerange 20220101-20250630 --epochs 300 \
  --spaces buy sell protection risk stoploss

# Promote a winning epoch into a confirmable T3 child node:
python .agent/scripts/maze.py promote $STRAT N0003 --epoch 42 --tier T3 \
  --desc "epoch 42: tighter RSI + wider stop"

# Score an arbitrary existing export against the gate table directly:
python .agent/scripts/maze.py gates $STRAT --zip results/backtests/x.zip --config $CFG

# One-shot frozen-window confirmation (refuses a second call without --force):
python .agent/scripts/maze.py vault $STRAT --node N0009
```
Full protocol: `.agent/phases/04M-MAZE.md`. Do not hand-write ledger rows or
config overlays — the tool owns `.agent/reports/<Name>/maze/` and
`configs/strategies/_maze/<Name>/`.

## Phase 5 — hyperopt (mechanics; run it via `maze.py run --cmd hyperopt` above)

```bash
# What maze.py run --cmd hyperopt actually executes underneath, for reference.
# T2 spaces now include protection/risk/stoploss (bounded by K2/K7, scored by
# MazeGateLoss) — this is a policy change from the old buy/sell-only rule,
# see 04M-MAZE.md and kotegawa-risk-layer.md. --enable-protections DOES work
# during hyperopt (verified against hyperopt_optimizer.py) — the old "epochs
# run without protections" text was wrong and has been corrected.
freqtrade hyperopt --config $CFG \
  --hyperopt-path .agent/scripts/hyperopt --hyperopt-loss MazeGateLoss \
  --spaces buy sell protection risk stoploss \
  --epochs 300 --timerange 20220101-20250630 --enable-protections \
  2>&1 | grep -vE " INFO - " | tail -60
```
If any `opt_*` param is used inside `populate_indicators`, add
`--analyze-per-epoch` (indicators otherwise recompute never, and epochs
optimize stale columns).

```bash
freqtrade hyperopt-list --config $CFG --best --print-json
freqtrade hyperopt-show --config $CFG --best --print-json
```

```bash
# OOS validation (T5, once per finalist) — the window hyperopt never saw
freqtrade backtesting --config $CFG --timerange 20250701-20260709 \
  --breakdown month --cache none --enable-protections \
  2>&1 | grep -vE " INFO - " | tail -60
```

Hyperopt writes best params to `user_data/strategies/<StrategyName>.json`,
which freqtrade loads automatically and which **overrides class defaults** —
this is now a SHARED SLOT across every node of one strategy, not a permanent
per-run artifact; `maze.py run`/`promote` stage and restore it automatically
and pass `--disable-param-export` so freqtrade never writes it unprompted
mid-run. A node's permanent parameter record is its genome snapshot at
`.agent/reports/<Name>/maze/params/<node_id>.json`. There is no
`--export-filename` for hyperopt.

## Phase 6 — FreqAI

```bash
freqtrade list-freqaimodels      # LightGBM*/XGBoost* only; no CatBoost, no torch

freqtrade backtesting --config $CFG --freqaimodel LightGBMRegressor \
  --timerange 20250101-20250701 \
  2>&1 | grep -vE " INFO - " | tail -50
```
FreqAI needs `train_period_days` of history *before* the timerange start.

## Phase 7 — walk-forward

```bash
for TR in 20220101-20220401 20220401-20220701 20220701-20221001 20221001-20230101 \
          20230101-20230401 20230401-20230701 20230701-20231001 20231001-20240101 \
          20240101-20240401 20240401-20240701 20240701-20241001 20241001-20250101 \
          20250101-20250401 20250401-20250701 20250701-20251001 20251001-20260101 \
          20260101-20260401 20260401-20260709 ; do
  echo "=== $TR"
  freqtrade backtesting --config $CFG --timerange $TR --cache none --enable-protections 2>&1 \
    | grep -E "Total profit %|Profit factor|Absolute drawdown|Total/Daily Avg Trades"
done
```

```bash
# Cost sensitivity: 2x fees to model slippage — the honest worst case is
# 2x fees AND 1m-detail exits together
freqtrade backtesting --config $CFG --timerange 20220101-20260709 --fee 0.001 \
  --cache none --enable-protections \
  2>&1 | grep -vE " INFO - " | tail -30

freqtrade backtesting --config $CFG --timerange 20220101-20260709 --fee 0.001 \
  --timeframe-detail 1m --cache none --enable-protections \
  2>&1 | grep -vE " INFO - " | tail -30
```

## Phase 8 — dry run

```bash
freqtrade trade --config configs/strategies/$STRAT.dryrun.json
```

---

## Reading results without re-running

```bash
freqtrade backtesting-show --config $CFG --backtest-directory results/backtests
```

## Dataset (re)build — pre-authorized, use reference commands

```bash
# Full futures dataset restore/top-up. setsid so the tool timeout cannot kill it.
# Fresh 2026.6 downloads auto-include mark + funding_rate in futures mode.
setsid nohup freqtrade download-data \
  --config configs/strategies/SmokeTestStrategy.json \
  --timeframes 1m 5m 15m 30m 1h 4h 8h 1d \
  --timerange 20220101- \
  > results/download.log 2>&1 < /dev/null &
```
Full procedure, gotchas and verification: `.agent/reference/data-download.md`.

## Never run these
```bash
freqtrade backtesting --strategy X            # no --config -> loads config.json. FORBIDDEN.
freqtrade download-data ...                   # only via .agent/reference/data-download.md commands
freqtrade trade ... --dry-run false
rm -rf user_data/data/...
```

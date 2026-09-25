# MultiMATSL — Futures Strategy Plan

Read `.agent/reference/futures-playbook.md` first. This file states the deltas
PLUS every block the building agent needs (see `00-TEMPLATE.md`).

The trend-following member of the collection. Its distinguishing feature is a
**trailing stop as the primary exit** — the entry is a pullback, but the exit
is designed to let winners run.

---

## Hypothesis

In an established higher-timeframe uptrend, a pullback below a moving average
is a discount rather than a reversal. Enter the pullback, then let an ATR-aware
trailing stop capture the trend continuation instead of exiting at a fixed
target.

**Why it should work:** trend persistence. The counterparty is a short-term
trader de-risking into weakness while the dominant flow is still one direction.

## Direction & symmetry claim

**Both directions** — trend has no preferred sign. The 1h EMA50/EMA200 cross is
the regime gate and it flips cleanly: longs only in 1h uptrends, shorts only in
1h downtrends. Never both at once.

## Futures deltas

| Item | Spot original | Futures version |
|------|---------------|-----------------|
| Timeframe | 5m (+1h informative) | **15m (+1h informative)** |
| Direction | long only | **both** |
| `can_short` | False | **True** |
| Stoploss | -0.15 | **-0.18** |
| MA types | 6 (ema/sma/tema/dema/zlema/hma) | **3 (ema/tema/hma)** — see below |
| MA range | 5-80 | **5-80, step 5** |

### Cutting the MA-type sweep

Six MA types x 76 periods = 456 combinations per side, and most MA types are
near-identical. SMA is strictly worse than EMA for this use, and DEMA/ZLEMA are
close cousins of TEMA. Keep three genuinely different smoothing behaviours:
- `ema` — standard exponential
- `tema` — triple-smoothed, much less lag
- `hma` — Hull, lowest lag of the three

If hyperopt strongly prefers one, drop the others in a later iteration.

---

## Data requirements

OHLCV 15m all 10 majors + same-pair **1h informative with a deep warmup**
(read the startup note — the deepest of any plan).

## Indicators (15m)

| Indicator | Method | Column |
|-----------|--------|--------|
| EMA sweep | `ta.EMA(df, N)`, `N in range(5,81,5)` | `ind_ema_{N}` |
| TEMA sweep | `ta.TEMA(df, N)`, same range | `ind_tema_{N}` |
| HMA sweep | `pta.hma(close, length=N)`, same range | `ind_hma_{N}` |
| EWO | `(ta.EMA(df,5) - ta.EMA(df,35)) / close * 100` | `ind_ewo` |
| RSI (14) | `ta.RSI(df, 14)` | `ind_rsi_14` |
| NATR (14) | `ta.NATR(df, 14)` | `ind_natr_14` — required, drives leverage |

### 1h informative (via `merge_informative_pair`)

| Indicator | Column |
|-----------|--------|
| EMA 50 | `ind_1h_ema_50` |
| EMA 200 | `ind_1h_ema_200` |
| RSI 14 | `ind_1h_rsi` |

Column selection at signal time:
```python
ma_col = f"ind_{self.opt_ma_type.value}_{self.opt_ma_period.value}"
ma_sell_col = f"ind_{self.opt_ma_type_sell.value}_{self.opt_ma_period_sell.value}"
```

**Informative warmup sizing (why startup = 900):** the informative pipeline
extends 1h history backwards by `startup_candle_count x strategy_tf_minutes`.
To seed a 1h EMA(200) the strategy needs 200 x 4 = 800 15m candles; EMAs also
need ~1.5x their period to converge, so 800 is a floor, not a comfort margin.
`startup_candle_count = 900` (was 300 — that silently fed an immature EMA200
for the first ~2 months of the IS window; the regime gate would have been
noise there). Validate with `recursive-analysis` in Phase 2 regardless.

---

## Entry Logic

**Long:**
```
close < dataframe[ma_col] * opt_low_offset       # pullback, default 0.968
(ind_ewo > opt_ewo_high) OR (ind_ewo < opt_ewo_low)
ind_rsi_14 < opt_rsi_entry                       # default 35
ind_1h_ema_50 > ind_1h_ema_200                   # 1h trend is UP
volume > 0
```
tag: `ma_pullback_long`

**Short (mirror):**
```
close > dataframe[ma_col] * (2 - opt_low_offset) # rally above MA by the same offset
(ind_ewo > opt_ewo_high) OR (ind_ewo < opt_ewo_low)
ind_rsi_14 > (100 - opt_rsi_entry)
ind_1h_ema_50 < ind_1h_ema_200                   # 1h trend is DOWN
volume > 0
```
tag: `ma_pullback_short`

## Exit Logic

Primary exit is the **trailing stop** (see risk parameters). The signal exit is
a backstop:

**Long:** `close > dataframe[ma_sell_col] * opt_high_offset` — tag `ma_sell_offset`
**Short:** `close < dataframe[ma_sell_col] * (2 - opt_high_offset)`

---

## Hyperopt Parameters

| Parameter | Type | Range/Options | Default | Space |
|-----------|------|---------------|---------|-------|
| opt_ma_type | CategoricalParameter | [ema, tema, hma] | ema | buy |
| opt_ma_period | IntParameter (step=5) | 5-80 | 15 | buy |
| opt_low_offset | DecimalParameter | 0.94-0.99 | 0.968 | buy |
| opt_ewo_high | DecimalParameter | 2.0-12.0 | 4.179 | buy |
| opt_ewo_low | DecimalParameter | -20.0 to -2.0 | -3.97 | buy |
| opt_rsi_entry | IntParameter | 20-50 | 35 | buy |
| opt_ma_type_sell | CategoricalParameter | [ema, tema, hma] | ema | sell |
| opt_ma_period_sell | IntParameter (step=5) | 5-80 | 20 | sell |
| opt_high_offset | DecimalParameter | 1.001-1.05 | 1.012 | sell |

Nine parameters — the most of any plan here. This is a known risk. If Phase 5
flags overfitting, the first cut is `opt_ma_type_sell` (force equal to
`opt_ma_type`), then `opt_ewo_low`.

### Hyperopt execution notes

- `--analyze-per-epoch`: **NOT needed.** All 3 MA types x 17 periods are
  precomputed once; `opt_*` only select columns at signal time.
- Stepped params: `IntParameter(5, 80, default=15, step=5)` with sweeps
  hardcoded as `range(5, 81, 5)` (`.range` ignores `step` — see template).
- 9 params x 300 epochs is the portfolio's widest search — consider
  `--early-stop 40`.

---

## Risk Parameters (hardcoded — never optimise)
```python
stoploss = -0.18
trailing_stop = True
trailing_stop_positive = 0.005
trailing_stop_positive_offset = 0.025
trailing_only_offset_is_reached = True
minimal_roi = {"0": 100}      # disabled — the trailing stop is the exit
startup_candle_count = 900    # 1h EMA200 deep warm-up (see sizing note)
target_vol_pct = 0.4
max_leverage_cap = 2.0        # wide stop -> lower cap
```

A -18% stoploss at 2x is a 9% price move. Intentional: trend trades need room.

### Risk verification (precomputed 2026-09-26; base: ratio 0.5, max_open_trades 5)

| Check | Formula | Value | Verdict |
|-------|---------|-------|---------|
| K2 per-trade risk | 0.10 x 0.18 | **1.8% equity** | <= 2% PASS — closest to the budget of any plan; do not widen the stop without dropping max_open_trades |
| K7 liquidation headroom | 0.18/2 = 9.0% vs 1/2 = 50% | 5.6x margin | PASS |
| K4 trailing giveback | 0.005 <= 0.025/3 = 0.0083 | within 1/3 | PASS |
| ROI precedes trailing | ROI disabled (`{"0": 100}`) | trivially true | PASS |

### Protections (15m candle counts)
```python
@property
def protections(self):
    return [
        {"method": "CooldownPeriod", "stop_duration_candles": 2},
        {"method": "StoplossGuard", "lookback_period_candles": 96,
         "trade_limit": 1, "stop_duration_candles": 96,
         "only_per_pair": False, "only_per_side": False},
        {"method": "MaxDrawdown", "lookback_period_candles": 2000,
         "trade_limit": 5, "max_allowed_drawdown": 0.10,
         "calculation_mode": "equity", "stop_duration_candles": 288},
    ]
```

## Strategy Configuration
```python
INTERFACE_VERSION = 3
timeframe = '15m'
can_short = True
```

Config: `configs/strategies/MultiMATSL.json`

---

## Phase map

- **Phase 2:** deepest warmup of the portfolio (900). If `recursive-analysis`
  flags the 1h EMA columns, raise startup before anything else.
- **Phase 4:** expect low win rate, high average win — judge on profit factor,
  never win rate.
- **Phase 5:** widest parameter surface; edge-pinning and clustering checks
  decide whether 9 params survive.

## Key patterns to learn

**Trailing stop as the exit thesis.** `minimal_roi` disabled plus
`trailing_only_offset_is_reached = True` means: give the trade room until it is
up 2.5%, then protect it with a 0.5% trail.

**Regime-gated symmetry.** The 1h EMA cross is what makes the short side valid.
Copy this pattern to any strategy where you want shorts but the raw signal is
not naturally two-sided.

**CategoricalParameter for structure selection.** Lets hyperopt choose the
smoothing family, not just its period.

---

## Expected behaviour

**Works in:** sustained directional trends on the 1h.
**Struggles in:** chop — the 1h EMA cross whipsaws and pullback entries become
counter-trend entries. Expect the worst drawdowns here.
**Watch for:** the deepest `startup_candle_count` requirement of any plan.
`recursive-analysis` in Phase 2 is not optional.

## Kill criteria
- Profit factor < 1.2 in-sample after one round of tuning
- Phase 5 overfitting flags after cutting to 7 parameters
- More than 2 consecutive losing quarters in Phase 7 (regime fragility)
- Shorts materially worse than longs -> drop shorts, record the asymmetry

## Changelog
- 2026-09-26: Full template restructure. **Fix:** `startup_candle_count`
  300 -> 900 — a 1h EMA(200) informative needs `200 x 4 = 800` 15m candles of
  extended history plus convergence buffer; 300 silently immatured the regime
  gate for the first ~2 months of the IS window. Added the warmup-sizing rule,
  missing `ma_sell_col` selection, risk verification (K2 at 1.8% — nearest the
  budget), protections, hyperopt notes (no analyze-per-epoch; stepped sweep),
  phase map. No parameter changes beyond the startup fix.

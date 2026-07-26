# MultiMATSL — Futures Strategy Plan

Read `.agent/reference/futures-playbook.md` first. This file states only the deltas.

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

---

## Futures deltas

| Item | Spot original | Futures version |
|------|---------------|-----------------|
| Timeframe | 5m (+1h informative) | **15m (+1h informative)** |
| Direction | long only | **both** — trend has no preferred sign |
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
```

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

The 1h EMA cross is the regime gate and it flips cleanly — this is what makes
shorts legitimate here, unlike in `EWODipHunter`. Longs only in 1h uptrends,
shorts only in 1h downtrends. Never both at once.

---

## Exit Logic

Primary exit is the **trailing stop** (see risk parameters). The signal exit is
a backstop:

**Long:** `close > dataframe[ma_sell_col] * opt_high_offset`
**Short:** `close < dataframe[ma_sell_col] * (2 - opt_high_offset)`

---

## Hyperopt Parameters

| Parameter | Type | Range/Options | Default | Space |
|-----------|------|---------------|---------|-------|
| opt_ma_type | CategoricalParameter | [ema, tema, hma] | ema | buy |
| opt_ma_period | IntParameter | 5-80 step 5 | 15 | buy |
| opt_low_offset | DecimalParameter | 0.94-0.99 | 0.968 | buy |
| opt_ewo_high | DecimalParameter | 2.0-12.0 | 4.179 | buy |
| opt_ewo_low | DecimalParameter | -20.0 to -2.0 | -3.97 | buy |
| opt_rsi_entry | IntParameter | 20-50 | 35 | buy |
| opt_ma_type_sell | CategoricalParameter | [ema, tema, hma] | ema | sell |
| opt_ma_period_sell | IntParameter | 5-80 step 5 | 20 | sell |
| opt_high_offset | DecimalParameter | 1.001-1.05 | 1.012 | sell |

Nine parameters — the most of any plan here. This is a known risk. If Phase 5
flags overfitting, the first cut is `opt_ma_type_sell` (force it equal to
`opt_ma_type`), then `opt_ewo_low`.

---

## Risk Parameters (hardcoded — never optimise)
```python
stoploss = -0.18
trailing_stop = True
trailing_stop_positive = 0.005
trailing_stop_positive_offset = 0.025
trailing_only_offset_is_reached = True
minimal_roi = {"0": 100}      # disabled — the trailing stop is the exit
startup_candle_count = 300    # 1h EMA200 needs deep warm-up
target_vol_pct = 0.4
max_leverage_cap = 2.0        # wide stop -> lower cap
```

A -18% stoploss at 2x is a 9% price move. That is intentional: trend trades need
room. Confirm against the leverage table in `futures-playbook.md` §4.

## Strategy Configuration
```python
INTERFACE_VERSION = 3
timeframe = '15m'
can_short = True
```

Config: `configs/strategies/MultiMATSL.json`

---

## Key patterns to learn

**Trailing stop as the exit thesis.** `minimal_roi` disabled plus
`trailing_only_offset_is_reached = True` means: give the trade room until it is
up 2.5%, then protect it with a 0.5% trail. Expect a low win rate and a high
average win. Judge it on profit factor, never on win rate.

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

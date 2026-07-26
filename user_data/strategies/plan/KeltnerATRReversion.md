# KeltnerATRReversion — Futures Strategy Plan

Read `.agent/reference/futures-playbook.md` first. This file states only the deltas.

Distinct from `BBRSIMeanReversion` in two ways that matter: the channel is
**ATR-based** (true range, not close-to-close deviation), and entry requires a
**recovery cross** rather than mere band penetration.

---

## Hypothesis

Price that pierces an ATR-based channel and then *crosses back inside* has
exhausted the move that pushed it out. Entering on the recovery — not on the
penetration — avoids catching a knife that is still falling. A 1h ADX filter
suppresses entries when the higher timeframe is strongly trending, because
channel reversion fails in trends.

**Why it should work:** ATR channels adapt to realised volatility, so the same
multiplier means the same statistical stretch across pairs and regimes. The
`crossed_above` timing means someone has already stepped in to absorb the move.

---

## Futures deltas

| Item | Spot original | Futures version |
|------|---------------|-----------------|
| Timeframe | 5m (+1h informative) | **15m (+1h informative)** |
| Direction | long only | **both** |
| `can_short` | False | **True** |
| Stoploss | -0.05 | **-0.10** |
| `minimal_roi` | {"0":0.05,"30":0.025,...} | **{"0":0.04,"60":0.02,"180":0.01,"360":0}** |

---

## Indicators (15m)

| Indicator | Method | Column |
|-----------|--------|--------|
| EMA (20) | `ta.EMA(df, 20)` | `ind_ema_20` |
| ATR (14) | `ta.ATR(df, 14)` | `ind_atr_14` |
| NATR (14) | `ta.NATR(df, 14)` | `ind_natr_14` — required, drives leverage |
| Keltner upper | `ind_ema_20 + ind_atr_14 * opt_kc_mult` | `ind_kc_upper` |
| Keltner lower | `ind_ema_20 - ind_atr_14 * opt_kc_mult` | `ind_kc_lower` |
| Keltner width | `(ind_kc_upper - ind_kc_lower) / ind_ema_20` | `ind_kc_width` |
| RSI (14) | `ta.RSI(df, 14)` | `ind_rsi_14` |

### 1h informative (via `merge_informative_pair`, never a manual merge)

| Indicator | Column |
|-----------|--------|
| ADX (14) | `ind_1h_adx` |
| EMA (50) | `ind_1h_ema_50` |

**Warning:** `opt_kc_mult` is a hyperopt parameter used *inside*
`populate_indicators`. That is allowed, but it means the channel is recomputed
per epoch — expect slower hyperopt. Do not cache it across epochs.

---

## Entry Logic

**Long:**
```
qtpylib.crossed_above(close, ind_kc_lower)     # recovery cross, NOT close < lower
ind_rsi_14 < opt_rsi_entry                     # default 40
ind_1h_adx < opt_adx_max                       # default 30 — not strongly trending
volume > 0
```
tag: `kc_lower_recovery`

**Short:**
```
qtpylib.crossed_below(close, ind_kc_upper)
ind_rsi_14 > (100 - opt_rsi_entry)
ind_1h_adx < opt_adx_max
volume > 0
```
tag: `kc_upper_recovery`

The cross is the whole point. `close < ind_kc_lower` would enter repeatedly all
the way down a cascade; `crossed_above` fires once, on the turn.

---

## Exit Logic

**Long:** `close > ind_ema_20` OR `ind_rsi_14 > opt_rsi_exit` (default 65)
**Short:** `close < ind_ema_20` OR `ind_rsi_14 < (100 - opt_rsi_exit)`

Exit at the channel midline, not the opposite band. Mean reversion targets the
mean.

---

## Hyperopt Parameters

| Parameter | Type | Range | Default | Space |
|-----------|------|-------|---------|-------|
| opt_kc_mult | DecimalParameter | 1.0-3.0 | 2.0 | buy |
| opt_rsi_entry | IntParameter | 25-50 | 40 | buy |
| opt_adx_max | IntParameter | 15-40 | 30 | buy |
| opt_rsi_exit | IntParameter | 55-80 | 65 | sell |

---

## Risk Parameters (hardcoded — never optimise)
```python
stoploss = -0.10
trailing_stop = True
trailing_stop_positive = 0.01
trailing_stop_positive_offset = 0.02
trailing_only_offset_is_reached = True
minimal_roi = {"0": 0.04, "60": 0.02, "180": 0.01, "360": 0}
startup_candle_count = 300     # 1h informative needs deeper warm-up
target_vol_pct = 0.5
max_leverage_cap = 3.0
```

## Strategy Configuration
```python
INTERFACE_VERSION = 3
timeframe = '15m'
can_short = True
```

Config: `configs/strategies/KeltnerATRReversion.json`

---

## Key patterns to learn

**Recovery cross vs level test.** `crossed_above(close, band)` fires once per
excursion. `close < band` fires every candle of the excursion. The first is a
timing signal; the second is a state description that will overtrade.

**Higher-timeframe regime gate.** The 1h ADX filter encodes "this strategy does
not work in trends" directly, instead of hoping the stoploss handles it.

**startup_candle_count with informatives.** A 1h EMA50 needs 50 hours = 200
15m candles of 1h history. Validate with `recursive-analysis` in Phase 2 —
this plan is the most likely of the nine to fail that check.

---

## Expected behaviour

**Works in:** choppy, high-volatility ranges where ATR expands.
**Struggles in:** persistent trends (ADX filter should block most of these),
and very quiet markets where the channel is too narrow to reach.

## Kill criteria
- Profit factor < 1.2 in-sample after one round of tuning
- The ADX filter blocks so much that trades < 100 over the IS window
- `recursive-analysis` cannot be made clean at a sane `startup_candle_count`
- Profit factor < 1.0 at 2x fees

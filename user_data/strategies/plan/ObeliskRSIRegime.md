# ObeliskRSIRegime — Futures Strategy Plan

Read `.agent/reference/futures-playbook.md` first. This file states only the deltas.

The regime-switching plan. One signal, **two parameter sets**, selected by which
side of the SMA200 price is on. Also the only plan using a custom time-ramped
stoploss.

---

## Hypothesis

RSI oversold means different things in different regimes. Above the SMA200, a
dip to RSI 35 is a buyable pullback. Below it, the same reading is just a
downtrend continuing, so the threshold must be stricter and the exit faster.
Encode the regime explicitly rather than hoping one parameter set fits both.

**Why it should work:** it stops the strategy from applying bull-market
assumptions in bear markets — the single most common way a backtest that looked
great in one regime dies in the next.

---

## Futures deltas

| Item | Spot original | Futures version |
|------|---------------|-----------------|
| Timeframe | 5m | **15m** |
| Direction | long only | **both** — the regime gate flips cleanly |
| `can_short` | False | **True** |
| Stoploss ramp | -10% -> -2% | **-15% -> -4%** (leverage-adjusted) |

In the futures version the regime does more work: above SMA200 take longs on
RSI dips, below SMA200 take shorts on RSI spikes. The bear-regime long is
dropped entirely — it was the weakest part of the original.

---

## Indicators (15m)

| Indicator | Method | Column |
|-----------|--------|--------|
| SMA (200) | `ta.SMA(df, 200)` | `ind_sma_200` |
| RSI (14) | `ta.RSI(df, 14)` | `ind_rsi_14` |
| Bull flag | `(close > ind_sma_200).astype(int)` | `ind_bull` |
| NATR (14) | `ta.NATR(df, 14)` | `ind_natr_14` — required, drives leverage |

Three real indicators. This is the second most frugal plan.

---

## Entry Logic

**BULL regime (`ind_bull == 1`) — long only:**
```
ind_bull == 1
qtpylib.crossed_below(ind_rsi_14, opt_bull_rsi_entry)     # default 35
volume > 0
```
tag: `bull_rsi_dip`

**BEAR regime (`ind_bull == 0`) — short only:**
```
ind_bull == 0
qtpylib.crossed_above(ind_rsi_14, opt_bear_rsi_entry_short)   # default 65
volume > 0
```
tag: `bear_rsi_spike`

`crossed_below` / `crossed_above`, never a bare comparison. We want the moment
RSI passes the threshold, not every candle it stays there. A bare `<` in a
sustained dump would re-enter on every single candle.

**Deliberate omission:** no longs in the bear regime. The original had them with
a stricter threshold; on futures the short side is available and strictly
better than a counter-trend long. If you want to test bear-regime longs, that
is a separate experiment with its own tag — not a default.

---

## Exit Logic

**BULL long:** `qtpylib.crossed_above(ind_rsi_14, opt_bull_rsi_exit)` (default 65)
**BEAR short:** `qtpylib.crossed_below(ind_rsi_14, opt_bear_rsi_exit)` (default 35)

---

## Custom Stoploss — time ramp

The distinguishing mechanism. The stop starts wide (the trade needs room to
work) and tightens linearly (if it has not worked by now, it is not going to).

```python
use_custom_stoploss = True

def custom_stoploss(self, pair, trade, current_time, current_rate,
                    current_profit, after_fill, **kwargs) -> float:
    elapsed = (current_time - trade.open_date_utc).total_seconds() / 60.0
    frac = min(1.0, elapsed / self.opt_ramp_minutes.value)
    # linear ramp from -0.15 to -0.04
    return -0.15 + (0.11 * frac)
```

Rules:
- Return a **negative** ratio. Returning a positive value silently disables it.
- `stoploss = -0.15` must still be declared at class level as the hard floor.
- `opt_ramp_minutes` is the one risk-adjacent value allowed in hyperopt here,
  because it controls *timing*, not loss size. Both ends of the ramp are fixed.
- This interacts with dynamic leverage: at 2x, -15% is a 7.5% price move
  tightening to 2%. Verify against `futures-playbook.md` §4 before changing
  either end.

---

## Hyperopt Parameters

| Parameter | Type | Range | Default | Space |
|-----------|------|-------|---------|-------|
| opt_bull_rsi_entry | IntParameter | 20-45 | 35 | buy |
| opt_bear_rsi_entry_short | IntParameter | 55-80 | 65 | buy |
| opt_bull_rsi_exit | IntParameter | 55-80 | 65 | sell |
| opt_bear_rsi_exit | IntParameter | 20-45 | 35 | sell |
| opt_ramp_minutes | IntParameter | 60-1440 | 360 | sell |

---

## Risk Parameters (hardcoded — never optimise)
```python
stoploss = -0.15               # hard floor; custom_stoploss ramps inside this
trailing_stop = False
minimal_roi = {"0": 0.05, "120": 0.02, "360": 0}
startup_candle_count = 250     # SMA200 + buffer
target_vol_pct = 0.5
max_leverage_cap = 2.0
```

## Strategy Configuration
```python
INTERFACE_VERSION = 3
timeframe = '15m'
can_short = True
use_custom_stoploss = True
```

Config: `configs/strategies/ObeliskRSIRegime.json`

---

## Key patterns to learn

**Explicit regime switching.** Two parameter sets under one roof, selected by a
slow indicator. The most direct defence against anti-pattern #3 (regime
overfitting) available without machine learning.

**Cross vs level.** `crossed_below(rsi, 35)` fires once per excursion;
`rsi < 35` fires continuously. For entries you almost always want the cross.

**Time-ramped stop.** Encodes "this trade had a thesis with a time horizon". If
the move has not happened in six hours, the setup is stale and the remaining
risk is not worth holding.

---

## Expected behaviour

**Works in:** markets with clear regime persistence on the SMA200.
**Struggles in:** price oscillating around the SMA200 — the regime flag flips
constantly and the strategy alternates between long and short setups near the
worst possible prices.
**Watch for:** whether the two regimes have comparable trade counts. If 95% of
trades are bull-regime, the bear logic is untested rather than validated, and
Phase 7 will not have exercised it.

## Kill criteria
- Profit factor < 1.2 in-sample after one round of tuning
- Either regime has < 30 trades over the IS window (untested, not validated)
- The custom stoploss underperforms a plain fixed stop -> delete the ramp,
  keep the simpler version
- More than 2 consecutive losing quarters in Phase 7

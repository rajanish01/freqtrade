# SuperTrendBBCombo — Futures Strategy Plan

Read `.agent/reference/futures-playbook.md` first. This file states only the deltas.

The hybrid: **SuperTrend decides direction, Bollinger decides timing.** It is
the only plan here that combines a trend filter with a mean-reversion entry,
which makes it the natural bridge between the band family and `MultiMATSL`.

---

## Hypothesis

Trade pullbacks only in the direction the trend allows. SuperTrend defines
whether longs or shorts are permitted; the Bollinger position then times the
entry within that direction. Exit either at the opposite band (target reached)
or on a SuperTrend flip (thesis invalidated).

**Why it should work:** it filters out the single worst failure mode of pure
band reversion — buying the lower band during a downtrend, over and over, all
the way down.

---

## Futures deltas

| Item | Spot original | Futures version |
|------|---------------|-----------------|
| Timeframe | 5m | **15m** |
| Direction | long only | **both** — SuperTrend is inherently two-sided |
| `can_short` | False | **True** |
| Stoploss | (per original) | **-0.12** |

SuperTrend already computes a bearish line and a direction flag. The short side
is not an addition here; it is half of an indicator that was being thrown away.

---

## Indicators (15m)

| Indicator | Method | Column |
|-----------|--------|--------|
| SuperTrend | `pta.supertrend(high, low, close, length=opt_st_period, multiplier=opt_st_mult)` | `ind_st_long`, `ind_st_short`, `ind_st_dir` |
| Bollinger (20,2) | `qtpylib.bollinger_bands(qtpylib.typical_price(df), 20, 2)` | `ind_bb_lower`, `ind_bb_mid`, `ind_bb_upper` |
| BB percent | `(close - ind_bb_lower) / (ind_bb_upper - ind_bb_lower)` | `ind_bb_pct` |
| BB width | `(ind_bb_upper - ind_bb_lower) / ind_bb_mid` | `ind_bb_width` |
| RSI (14) | `ta.RSI(df, 14)` | `ind_rsi_14` |
| NATR (14) | `ta.NATR(df, 14)` | `ind_natr_14` — required, drives leverage |

### SuperTrend extraction

`pandas_ta.supertrend` returns a frame with suffixed column names:
```python
st = pta.supertrend(dataframe['high'], dataframe['low'], dataframe['close'],
                    length=period, multiplier=mult)
dataframe['ind_st_long']  = st[f'SUPERTl_{period}_{mult}']
dataframe['ind_st_short'] = st[f'SUPERTs_{period}_{mult}']
dataframe['ind_st_dir']   = st[f'SUPERTd_{period}_{mult}']   # 1 bullish, -1 bearish
```

**Two traps here:**
1. The suffix must match the *exact* float formatting of `mult`. A multiplier
   of `3.0` yields `SUPERTd_10_3.0`, not `SUPERTd_10_3`. Build the key from the
   same variables you passed in, never hardcode it.
2. `opt_st_period` and `opt_st_mult` are used inside `populate_indicators`, so
   SuperTrend is recomputed every hyperopt epoch. This is the slowest plan to
   optimise. Budget accordingly, or fix the period and optimise only the
   multiplier.

---

## Entry Logic

**Long:**
```
ind_st_dir == 1                          # SuperTrend bullish
ind_bb_pct < opt_bb_pct_entry            # near lower band, default 0.15
ind_rsi_14 < opt_rsi_entry               # default 40
ind_bb_width > opt_min_bb_width          # default 0.015, no squeeze
volume > 0
```
tag: `st_bull_bb_dip`

**Short:**
```
ind_st_dir == -1                         # SuperTrend bearish
ind_bb_pct > (1 - opt_bb_pct_entry)      # near upper band
ind_rsi_14 > (100 - opt_rsi_entry)
ind_bb_width > opt_min_bb_width
volume > 0
```
tag: `st_bear_bb_rally`

Use `ind_st_dir` rather than `close > ind_st_long`. The direction flag is
unambiguous; the line comparison is NaN on the inactive side.

---

## Exit Logic

**Long:** `ind_bb_pct > opt_bb_pct_exit` (default 0.85) OR `ind_st_dir == -1`
**Short:** `ind_bb_pct < (1 - opt_bb_pct_exit)` OR `ind_st_dir == 1`

The SuperTrend flip is a **structural exit**: the condition that justified the
entry is gone, so leave regardless of P&L. Tag the two exit reasons separately
so Phase 4 can show which one is doing the work.

---

## Hyperopt Parameters

| Parameter | Type | Range | Default | Space |
|-----------|------|-------|---------|-------|
| opt_st_period | IntParameter | 7-20 | 10 | buy |
| opt_st_mult | DecimalParameter | 1.5-4.0 | 3.0 | buy |
| opt_bb_pct_entry | DecimalParameter | 0.05-0.25 | 0.15 | buy |
| opt_rsi_entry | IntParameter | 25-45 | 40 | buy |
| opt_min_bb_width | DecimalParameter | 0.005-0.04 | 0.015 | buy |
| opt_bb_pct_exit | DecimalParameter | 0.75-0.95 | 0.85 | sell |

---

## Risk Parameters (hardcoded — never optimise)
```python
stoploss = -0.12
trailing_stop = False
minimal_roi = {"0": 0.06, "120": 0.03, "360": 0.015, "720": 0}
startup_candle_count = 200
target_vol_pct = 0.5
max_leverage_cap = 3.0
```

No trailing stop: the SuperTrend flip already serves as the dynamic exit.
Adding a trailing stop on top would double up and cut winners early.

## Strategy Configuration
```python
INTERFACE_VERSION = 3
timeframe = '15m'
can_short = True
```

Config: `configs/strategies/SuperTrendBBCombo.json`

---

## Key patterns to learn

**Direction filter + timing trigger.** The most transferable idea in the whole
collection. One indicator answers "which way am I allowed to trade", another
answers "when". Keeping those jobs separate prevents the trend filter from also
becoming an entry trigger.

**Structural exit vs target exit.** Two exits with different meanings, tagged
separately. If the SuperTrend-flip exit is where all the losses are, the trend
filter is too slow and `opt_st_period` should come down.

**Trap-aware library use.** The pandas-ta column-suffix issue is exactly the
kind of thing that produces a silent `KeyError` mid-hyperopt, hours in.

---

## Expected behaviour

**Works in:** trending markets with regular pullbacks — the sweet spot.
**Struggles in:** rapid trend flips, where SuperTrend whipsaws and every entry
is immediately invalidated by a flip exit.
**Watch for:** a high share of `st_flip` exits with small losses. That means
whipsaw, and the fix is a longer `opt_st_period`, not a wider stoploss.

## Kill criteria
- Profit factor < 1.2 in-sample after one round of tuning
- SuperTrend-flip exits are > 60% of exits and net negative (whipsaw dominates)
- Does not beat `BBRSIMeanReversion` -> the trend filter adds nothing, and the
  extra complexity is not paying for itself
- Profit factor < 1.0 at 2x fees

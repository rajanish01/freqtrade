# VWAPBandReversion — Futures Strategy Plan

Read `.agent/reference/futures-playbook.md` first. This file states the deltas
PLUS every block the building agent needs (see `00-TEMPLATE.md`).

The third band strategy, kept because its anchor is **volume-weighted**. BB
anchors on a simple moving average and Keltner on an EMA — both price-only.
VWAP asks "where did the money actually trade", which is a genuinely different
mean.

---

## Hypothesis

Price deviating from the volume-weighted average by more than a volatility-
scaled band reverts toward it. VWAP is the reference price institutions measure
execution against, so it acts as a magnet in the absence of new information.

**Why it should work:** VWAP is a real benchmark that real desks are graded on.
That creates genuine flow toward it, unlike an arbitrary moving average.

## Direction & symmetry claim

**Both directions.** Deviation from a mean is symmetric by construction. Short
thresholds derived (`-z` / `+z` around the same `opt_band_z`).

## Futures deltas

| Item | Spot original | Futures version |
|------|---------------|-----------------|
| Timeframe | 5m | **15m** |
| Direction | long only ("This is a spot strategy") | **both** |
| `can_short` | False | **True** |
| Stoploss | ATR-based, -0.05 baseline | **-0.10** |

### VWAP on 24/7 perpetuals

True VWAP resets each trading session. Perpetual futures have **no session
boundary**, so a session VWAP is undefined. Use a rolling VWAP with the window
as a hyperopt parameter, and say so explicitly in the strategy docstring.

```python
dataframe['ind_vwap'] = qtpylib.rolling_vwap(dataframe, window=opt_vwap_period)
```

Do not use a cumulative-since-inception VWAP — it drifts and is not stationary.

---

## Data requirements

OHLCV 15m, all 10 majors. No informative timeframes, no funding reads.

## Indicators (15m)

| Indicator | Method | Column |
|-----------|--------|--------|
| Rolling VWAP | `qtpylib.rolling_vwap(df, window=opt_vwap_period)` | `ind_vwap` |
| Deviation | `(close - ind_vwap) / ind_vwap` | `ind_vwap_dev` |
| Rolling stdev of dev | `ind_vwap_dev.rolling(opt_vwap_period).std()` | `ind_vwap_dev_std` |
| Z-score | `ind_vwap_dev / ind_vwap_dev_std` | `ind_vwap_z` |
| ADX (14) | `ta.ADX(df, 14)` | `ind_adx_14` |
| NATR (14) | `ta.NATR(df, 14)` | `ind_natr_14` — required, drives leverage |

Using a **z-score** rather than a raw band multiplier makes the threshold
comparable across pairs and across volatility regimes. That matters here more
than in the BB plan, because VWAP deviation scales with pair volatility.

Warmup: rolling windows up to 200 (max `opt_vwap_period`) x2 stacked
(deviation std reuses the same window) → `startup_candle_count = 250`. The
z-score is NaN until both windows fill; entries must include
`ind_vwap_z.notna()` defensively (NaN comparisons are False anyway, but be
explicit).

---

## Entry Logic

**Long:**
```
ind_vwap_z < -opt_band_z            # default 1.5, stretched below VWAP
ind_adx_14 < opt_adx_max            # default 25, not trending
ind_vwap_z.notna()
volume > 0
```
tag: `vwap_below_band`

**Short:**
```
ind_vwap_z > opt_band_z
ind_adx_14 < opt_adx_max
ind_vwap_z.notna()
volume > 0
```
tag: `vwap_above_band`

## Exit Logic

**Long:** `close > ind_vwap` (crossed back to the mean) — tag `vwap_midline`
**Short:** `close < ind_vwap`

Structural exit — the trade thesis is "return to VWAP", so returning to VWAP
completes it. `minimal_roi` is the backstop, not the plan.

---

## Hyperopt Parameters

| Parameter | Type | Range | Default | Space |
|-----------|------|-------|---------|-------|
| opt_vwap_period | IntParameter | 20-200 | 50 | buy |
| opt_band_z | DecimalParameter | 0.5-3.0 | 1.5 | buy |
| opt_adx_max | IntParameter | 15-40 | 25 | buy |

Only three. This is the most parameter-frugal plan after BBRSI.

### Hyperopt execution notes

- **`--analyze-per-epoch` MANDATORY.** `opt_vwap_period` is used inside
  `populate_indicators` (rolling VWAP + rolling std). Without the flag the
  epochs optimise against default-period columns (gotcha #0c).
- Budget: two stacked rolling computations re-run per epoch — this is the
  second-slowest hyperopt of the 15m plans (SuperTrendBBCombo is worse).

---

## Risk Parameters (hardcoded — never optimise)
```python
stoploss = -0.10
trailing_stop = False
minimal_roi = {"0": 0.05, "120": 0.02, "360": 0.01, "720": 0}
startup_candle_count = 250
target_vol_pct = 0.5
max_leverage_cap = 3.0
```

The original plan specified an ATR-multiple stoploss. That is a **custom
stoploss**, which is a YELLOW change and interacts badly with dynamic leverage
(both scale with volatility, so they compound). Start with the fixed stoploss
above. Only consider `use_custom_stoploss` after Phase 5 passes, and only with
approval.

### Risk verification (precomputed 2026-09-26; base: ratio 0.5, max_open_trades 5)

| Check | Formula | Value | Verdict |
|-------|---------|-------|---------|
| K2 per-trade risk | 0.10 x 0.10 | 1.0% equity | <= 2% PASS |
| K7 liquidation headroom | 0.10/3 = 3.3% vs 1/3 = 33.3% | 10x margin | PASS |
| K4 trailing giveback | trailing disabled | n/a | n/a |

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
use_custom_stoploss = False
```

Config: `configs/strategies/VWAPBandReversion.json`

---

## Note on the existing implementation

`user_data/strategies/VWAPBandReversion.py` previously existed and **crashed
the backtester** — it used the `dataframe.loc[(), [...]] = (...)` empty
scaffold, which creates a `|V0` void column under pandas 3. It has since been
deleted. Rebuild from Phase 1 using the scaffold in
`.agent/phases/01-STRATEGY-SCAFFOLD.md`. Do not restore the old file.

---

## Phase map

- **Phase 3 smoke:** expect a healthy count (10-60/month); 0 trades usually
  means the z-score went NaN — check warmup first.
- **Phase 4:** headline gate is the family comparison — must beat
  `BBRSIMeanReversion` on the same window (see kill criteria).

## Key patterns to learn

**Z-score instead of raw multiplier.** `deviation / rolling_std` is unitless
and comparable across pairs. Any band strategy trading a multi-pair whitelist
should prefer it.

**Volume-weighted anchor.** The reason this earns a slot next to two other band
strategies. If it does not outperform them, that is a real finding: the volume
weighting adds nothing at this timeframe, and the plan should be dropped rather
than tuned.

---

## Expected behaviour

**Works in:** ranging markets with meaningful volume dispersion.
**Struggles in:** trends (ADX gate), and thin/illiquid periods where VWAP is
dominated by a few prints.

## Kill criteria
- Profit factor < 1.2 in-sample after one round of tuning
- Does not beat `BBRSIMeanReversion` on the same window -> the volume weighting
  adds nothing; drop this plan rather than tuning it further
- Profit factor < 1.0 at 2x fees

## Changelog
- 2026-09-26: Full template restructure. Added explicit `.notna()` entry guard
  (stacked rolling windows), **`--analyze-per-epoch` mandatory** note
  (`opt_vwap_period` is inside `populate_indicators` — gotcha #0c), risk
  verification, protections, phase map. No parameter changes.

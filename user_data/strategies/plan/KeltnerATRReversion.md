# KeltnerATRReversion — Futures Strategy Plan

Read `.agent/reference/futures-playbook.md` first. This file states the deltas
PLUS every block the building agent needs (see `00-TEMPLATE.md`).

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
Note this is the *confirmed* entry style that the `BBRSIMeanReversion` prior
run was missing — if BBRSI's fallback succeeds, expect similar behaviour here.

## Direction & symmetry claim

**Both directions.** Channel reversion is symmetric by construction. Short
thresholds derived from longs (`100 - x`).

## Futures deltas

| Item | Spot original | Futures version |
|------|---------------|-----------------|
| Timeframe | 5m (+1h informative) | **15m (+1h informative)** |
| Direction | long only | **both** |
| `can_short` | False | **True** |
| Stoploss | -0.05 | **-0.10** |
| `minimal_roi` | {"0":0.05,"30":0.025,...} | **{"0":0.04,"60":0.02,"180":0.01,"360":0}** |

---

## Data requirements

OHLCV 15m all 10 majors + same-pair 1h informative. No funding/mark reads.

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

**Warmup sizing (verified rule):** an informative Tf-slower indicator needs
`period x (informative_tf / strategy_tf)` strategy candles of history
extension. 1h ADX(14) needs ~2x period stabilisation ≈ 28h → 112 15m candles;
1h EMA(50) needs 50h → 200 15m candles. `startup_candle_count = 300` covers
both with buffer. Validate with `recursive-analysis` in Phase 2.

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

The cross is the whole point. `close < ind_kc_lower` would enter repeatedly
all the way down a cascade; `crossed_above` fires once, on the turn.

## Exit Logic

**Long:** `close > ind_ema_20` OR `ind_rsi_14 > opt_rsi_exit` (default 65)
**Short:** `close < ind_ema_20` OR `ind_rsi_14 < (100 - opt_rsi_exit)`
tags: `kc_midline`, `rsi_exit`

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

### Hyperopt execution notes

- **`--analyze-per-epoch` MANDATORY.** `opt_kc_mult` is used inside
  `populate_indicators` (channel formula). Without the flag, indicators are
  computed ONCE with the default multiplier and all epochs optimise stale
  columns — silently garbage (ENVIRONMENT.md gotcha #0c). The alternative —
  precomputing channels for a stepped multiplier sweep — is rejected here: the
  multiplier interacts with a continuous range, and 4 params x 300 epochs at
  per-epoch recompute is acceptable on 15m x 10 pairs.
- Budget: expect a slow run (channel recompute per epoch). Do not cache the
  channel across epochs.

---

## Risk Parameters (hardcoded — never optimise)
```python
stoploss = -0.10
trailing_stop = True
trailing_stop_positive = 0.01
trailing_stop_positive_offset = 0.03
trailing_only_offset_is_reached = True
minimal_roi = {"0": 0.04, "60": 0.02, "180": 0.01, "360": 0}
startup_candle_count = 300     # 1h informative warm-up covered (see sizing note)
target_vol_pct = 0.5
max_leverage_cap = 3.0
```

### Risk verification (precomputed 2026-09-26; base: ratio 0.5, max_open_trades 5)

| Check | Formula | Value | Verdict |
|-------|---------|-------|---------|
| K2 per-trade risk | 0.10 x 0.10 | 1.0% equity | <= 2% PASS |
| K7 liquidation headroom | 0.10/3 = 3.3% vs 1/3 = 33.3% | 10x margin | PASS |
| K4 trailing giveback | 0.01 <= 0.03/3 = 0.01 | at the boundary | PASS |
| ROI precedes trailing | 0.03 < 0.04 | offset below ROI@0 | PASS |

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

Config: `configs/strategies/KeltnerATRReversion.json`

---

## Phase map

- **Phase 2:** this plan is the most warmup-sensitive of the 15m band plans —
  `recursive-analysis` is the gate that matters here.
- **Phase 4 watch:** if the ADX filter blocks so much that IS trades < 100,
  that is structural, not a tuning issue (see kill criteria).

## Key patterns to learn

**Recovery cross vs level test.** `crossed_above(close, band)` fires once per
excursion; `close < band` fires every candle of the excursion.

**Higher-timeframe regime gate.** The 1h ADX encodes "does not work in trends"
directly, instead of hoping the stoploss handles it.

**In populate_indicators opt_* → analyze-per-epoch.** The canonical example
plan for gotcha #0c.

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

## Changelog
- 2026-09-26: Full template restructure. **Risk fix:** `trailing_stop_positive_offset`
  0.02 -> 0.03 — the old pair (0.01 / 0.02) gave 50% giveback, violating
  Kotegawa K4 (<= offset/3). **Hyperopt note corrected:** the prior text
  implied the channel is recomputed per epoch automatically; it is not —
  `--analyze-per-epoch` is mandatory (gotcha #0c). Added warmup-sizing rule,
  risk verification, protections, phase map. Exit reasons now tagged.

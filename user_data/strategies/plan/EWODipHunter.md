# EWODipHunter — Futures Strategy Plan
## Absorbs: TrueLamboComposite (merged — same EWO + MA-offset dip hypothesis)

Read `.agent/reference/futures-playbook.md` first. This file states the deltas
PLUS every block the building agent needs (see `00-TEMPLATE.md`).

**This plan is LONG-ONLY. That is deliberate. Do not enable shorts.**

---

## Hypothesis

Price dipping a fixed percentage below a moving average, while the Elliott Wave
Oscillator confirms either a healthy uptrend (buy the pullback) or deep
capitulation (buy the panic), reverts upward.

**Why it should work:** two structurally different sellers. In Mode A the
counterparty is a momentum trader taking profit into strength, and the trend
resumes. In Mode B the counterparty is a forced seller — a liquidation or a
margin call — and the price is temporarily below fair value because the seller
had no choice.

---

## Direction & symmetry claim — why long-only (do not "fix" this)

The mirror of "buy capitulation" would be "short euphoria". These are not
symmetric in crypto:
- Downside capitulation is **forced** (liquidations, margin calls) and
  mechanically overshoots.
- Upside euphoria is **voluntary** and can persist far longer than a short can
  survive. Short squeezes have unbounded loss shape.

Mode B in particular has no valid mirror. Enabling `can_short` here would not
be a conversion — it would be an unvalidated new hypothesis wearing a
battle-tested name. See `futures-playbook.md` §3.

Long-only on futures is still worth doing: leverage and no borrow requirement.

---

## Futures deltas

| Item | Spot original | Futures version |
|------|---------------|-----------------|
| Timeframe | 5m | **15m** |
| Direction | long only | **long only (unchanged)** |
| `can_short` | False | **False** |
| Stoploss | -0.10 | **-0.15** (wide by design; capitulation entries need room) |
| MA range | 5-80 | **5-80, step 5** (17 values, not 76 — see below) |

### The MA-range problem

The original pre-computes every EMA and SMA from period 5 to 80 — 152 columns —
then lets hyperopt pick one via `opt_base_nb_candles_buy`. On 15m futures across
10 pairs this is slow and is a large overfitting surface: 76 nearly-identical
choices is 76 chances to fit noise.

Use `range(5, 81, 5)` (17 periods). If hyperopt pins to a range edge, widen
deliberately rather than restoring the full sweep.

---

## Data requirements

OHLCV 15m, all 10 majors. No informatives. Leverage cap is lower (2.0) than the
band plans — funding on long holds is the Phase-4 watch item.

## Indicators (15m)

| Indicator | Method | Column |
|-----------|--------|--------|
| EMA sweep | `ta.EMA(df, N)` for `N in range(5,81,5)` | `ind_ema_{N}` |
| EWO | `(ta.EMA(df,5) - ta.EMA(df,35)) / close * 100` | `ind_ewo` |
| RSI (14) | `ta.RSI(df, 14)` | `ind_rsi_14` |
| NATR (14) | `ta.NATR(df, 14)` | `ind_natr_14` — required, drives leverage |

Select the active MAs at signal time:
```python
ma_col = f"ind_ema_{self.opt_base_nb_candles_buy.value}"
ma_sell_col = f"ind_ema_{self.opt_base_nb_candles_sell.value}"
```

---

## Entry Logic

**Mode A — pullback in an uptrend:**
```
close < dataframe[ma_col] * opt_low_offset      # default 0.968
ind_ewo > opt_ewo_high                          # default 4.179
ind_rsi_14 < opt_rsi_buy                        # default 35
volume > 0
```
tag: `ewo_high_pullback`

**Mode B — capitulation:**
```
close < dataframe[ma_col] * opt_low_offset
ind_ewo < opt_ewo_low                           # default -3.97
volume > 0
```
tag: `ewo_low_capitulation`

Tag them separately. Phase 4's `backtesting-analysis` will say whether both
modes earn their keep — it is common for one to carry the strategy and the
other to bleed. If Mode B loses money, delete it; do not tune it.

## Exit Logic
```
close > dataframe[ma_sell_col] * opt_high_offset     # default 1.012
volume > 0
```
tag: `ma_sell_offset`

---

## Hyperopt Parameters

| Parameter | Type | Range | Default | Space |
|-----------|------|-------|---------|-------|
| opt_base_nb_candles_buy | IntParameter (step=5) | 5-80 | 15 | buy |
| opt_low_offset | DecimalParameter | 0.95-0.99 | 0.968 | buy |
| opt_ewo_high | DecimalParameter | 2.0-12.0 | 4.179 | buy |
| opt_ewo_low | DecimalParameter | -20.0 to -2.0 | -3.97 | buy |
| opt_rsi_buy | IntParameter | 20-50 | 35 | buy |
| opt_base_nb_candles_sell | IntParameter (step=5) | 5-80 | 20 | sell |
| opt_high_offset | DecimalParameter | 1.001-1.05 | 1.012 | sell |

Seven parameters — the highest of the reversion plans. Watch the Phase 5
clustering check closely; this is the plan most likely to noise-fit.

### Hyperopt execution notes

- `--analyze-per-epoch`: **NOT needed.** The full EMA sweep is precomputed once
  in `populate_indicators` and `opt_*` only *select* a column at signal time
  (the stepped-sweep pattern — see `00-TEMPLATE.md`).
- Declare the stepped params as `IntParameter(5, 80, default=15, step=5,
  space="buy")`. The `.range` property ignores `step`, so the precompute loop
  must hardcode `range(5, 81, 5)` — do not iterate `.range`.

---

## Risk Parameters (hardcoded — never optimise)
```python
stoploss = -0.15
trailing_stop = False
minimal_roi = {"0": 100}      # disabled — exits are signal or stoploss only
startup_candle_count = 200
target_vol_pct = 0.4          # lower target: wide stop, so smaller size
max_leverage_cap = 2.0        # capped lower than the band strategies
```

`minimal_roi = {"0": 100}` means no ROI exit at all. Combined with a -15%
stoploss this is a high-conviction, low-turnover profile. Do not add a trailing
stop without approval — it changes the strategy's character entirely.

### Risk verification (precomputed 2026-09-26; base: ratio 0.5, max_open_trades 5)

| Check | Formula | Value | Verdict |
|-------|---------|-------|---------|
| K2 per-trade risk | 0.10 x 0.15 | 1.5% equity | <= 2% PASS |
| K7 liquidation headroom | 0.15/2 = 7.5% vs 1/2 = 50% | 6.7x margin | PASS |
| K4 trailing giveback | trailing disabled; ROI disabled | n/a | n/a |
| Wide-stop consequence | ROI disabled -> losers run to -15% | by design; funding watch applies |

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
can_short = False
```

Config: `configs/strategies/EWODipHunter.json`

---

## Phase map

- **Phase 3 smoke:** expect 5-30 trades/month.
- **Phase 4:** read per-tag breakdown FIRST — `ewo_high_pullback` vs
  `ewo_low_capitulation` as separate sub-strategies. Then funding share (long
  holds).
- **Phase 5:** 7 params — clustering check is the real test here.
- **Phase 7:** sustained-downtrend quarters are the expected losing regime.

## Key patterns to learn

**Two entry modes, separately tagged.** The cleanest way to test two
sub-hypotheses inside one strategy without building two strategies.

**MA-offset entry.** `close < ma * 0.968` is a percentage-stretch trigger. It
adapts to price level but *not* to volatility — which is why NATR-driven
leverage matters here.

**Parameter-count discipline.** Reducing the MA sweep from 76 to 17 choices is
the single highest-value change in this conversion.

---

## Expected behaviour

**Works in:** volatile markets with sharp dips and quick recoveries.
**Struggles in:** sustained downtrends — the wide stoploss and disabled ROI
mean losers run. Expect a low win rate with large winners.
**Watch for:** funding drag. Long-only with no ROI exit means long holds, and
`futures-playbook.md` §2 applies — check funding as a share of gross profit.

## Kill criteria
- Profit factor < 1.2 in-sample after one round of tuning
- Funding > 20% of gross profit (holding period too long)
- Phase 5 top-10 epochs scattered rather than clustered (noise-fitting)
- Either entry mode individually unprofitable -> delete that mode

## Changelog
- 2026-09-26: Full template restructure. **Fix:** added the missing
  `ma_sell_col` selection (`opt_base_nb_candles_sell`) — the prior version
  referenced it in exits without defining it. Risk verification, protections,
  hyperopt notes (stepped-sweep pattern documented; `--analyze-per-epoch` not
  needed), phase map added. No parameter changes.

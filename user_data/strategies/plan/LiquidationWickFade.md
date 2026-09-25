# LiquidationWickFade — Futures Strategy Plan
## FUTURES-NATIVE — has no spot equivalent

Read `.agent/reference/futures-playbook.md` first. This file states the deltas
PLUS every block the building agent needs (see `00-TEMPLATE.md`).

The second futures-native plan, and the **only one that keeps the 5m
timeframe**. That exemption is justified below.

---

## Hypothesis

Leveraged futures positions are liquidated by the exchange at market, without
regard to price. A cluster of liquidations produces a forced, price-insensitive
order flow burst: a long lower wick on huge volume, with price snapping back
within minutes. Fade the wick — take the other side of the forced seller.

**Why it should work:** the counterparty is not choosing to trade. A liquidation
engine has no price opinion and no patience; it must fill immediately. That
temporarily pushes price below any reasonable fair value. This is one of the
few genuinely mechanical, non-behavioural edges in crypto.

---

## Why this needs futures

Liquidation cascades are a consequence of leverage and maintenance margin. Spot
markets have no liquidation engine — a spot holder in drawdown is never forced
to sell. The entire mechanism is futures-specific.

## Direction & symmetry claim

**Both directions.** There is a genuine two-sided mechanism: downside cascades
(long liquidations) and upside short squeezes (short liquidations). Both are
forced flow. The asymmetry risk (squeezes can persist) is handled by the
"recovery already begun" confirmation and the hard time-stop — and by the
kill criterion comparing long vs short performance.

## Why 5m is justified here (and nowhere else)

`futures-playbook.md` §6 sets 15m as the default because fees eat small edges.
This plan is the documented exception:

- Cascades resolve in **minutes**. On 15m the wick and its recovery are often
  the same candle, so the signal is invisible.
- The target move is large (a cascade overshoot is 1-3%, not 0.3%), so the
  0.1% round-trip fee is a much smaller share of the edge than it would be for
  a 5m band strategy.
- Entry frequency is low — this fires on tail events, not continuously.

Data: 5m futures exists for all 10 pairs, 2022-01-01 onward (~475k candles/pair).
Hyperopt on this plan will be the slowest. Consider restricting hyperopt to 4
pairs (`.agent/pair-lists/core-four.json`), then validating on all 10 — propose
that at Phase 5, not before.

---

## Data requirements

OHLCV 5m, all 10 majors. 1m data present (required — the Phase-4
`--timeframe-detail 1m` realism pass is the main arbiter for this plan).

## Indicators (5m)

| Indicator | Method | Column |
|-----------|--------|--------|
| Candle range | `high - low` | `ind_range` |
| Lower wick frac | `(min(open,close) - low) / ind_range` | `ind_wick_lower` |
| Upper wick frac | `(high - max(open,close)) / ind_range` | `ind_wick_upper` |
| Volume SMA (50) | `volume.rolling(50).mean()` | `ind_vol_sma_50` |
| Volume spike | `volume / ind_vol_sma_50` | `ind_vol_spike` |
| ATR (14) | `ta.ATR(df, 14)` | `ind_atr_14` |
| NATR (14) | `ta.NATR(df, 14)` | `ind_natr_14` — required, drives leverage |
| Range vs ATR | `ind_range / ind_atr_14` | `ind_range_atr` |
| RSI (14) | `ta.RSI(df, 14)` | `ind_rsi_14` — required by the exit logic |
| EMA (200) | `ta.EMA(df, 200)` | `ind_ema_200` |

Guard against divide-by-zero: `ind_range` is 0 on a flat candle. Compute wick
fractions with an explicit `where(ind_range > 0, ..., 0)`.

All three event-shape conditions must coincide — that conjunction is what
distinguishes a liquidation cascade from ordinary volatility:
1. a large range relative to ATR,
2. a wick that is most of that range (price rejected the level),
3. volume far above normal (forced flow, not organic).

---

## Entry Logic

**Long (fade a downside cascade):**
```
ind_wick_lower > opt_wick_frac        # default 0.55 — most of the candle is lower wick
ind_range_atr  > opt_range_atr        # default 2.5 — abnormally large candle
ind_vol_spike  > opt_vol_spike        # default 3.0 — volume burst
close > low + (ind_range * 0.5)       # already recovered off the low
volume > 0
```
tag: `liq_cascade_long`

**Short (fade an upside squeeze):**
```
ind_wick_upper > opt_wick_frac
ind_range_atr  > opt_range_atr
ind_vol_spike  > opt_vol_spike
close < high - (ind_range * 0.5)
volume > 0
```
tag: `liq_squeeze_short`

The `close` condition requires the snap-back to have **already begun** on the
signal candle. Entering while price is still falling is catching the cascade
mid-flight — that is how this strategy loses badly.

## Exit Logic

Fast and mechanical. This is a scalp, not a position. Two exit channels:

1. **`minimal_roi` ladder (primary):** {"0": 0.02, "15": 0.012, "45": 0.006,
   "120": 0} — the 120-minute zero ROI is the time-stop: a cascade fade that
   has not worked within two hours was not a cascade.
2. **Momentum-spent signal exit (backstop):** **Long:** `ind_rsi_14 >
   opt_rsi_exit` (default 60) — tag `rsi_spent`. **Short:** `ind_rsi_14 <
   (100 - opt_rsi_exit)`.

The dominant exit should be `minimal_roi`. If signal exits dominate, the ROI
ladder is too slow for the mechanism — report that; do not weaken the entry
conjunction to compensate.

---

## Hyperopt Parameters

| Parameter | Type | Range | Default | Space |
|-----------|------|-------|---------|-------|
| opt_wick_frac | DecimalParameter | 0.40-0.75 | 0.55 | buy |
| opt_range_atr | DecimalParameter | 1.5-5.0 | 2.5 | buy |
| opt_vol_spike | DecimalParameter | 2.0-8.0 | 3.0 | buy |
| opt_rsi_exit | IntParameter | 50-75 | 60 | sell |

Four parameters, all describing the *shape of the event*. None of them are
price levels, which is why this plan should generalise across pairs better
than the band strategies.

### Hyperopt execution notes

- `--analyze-per-epoch`: **NOT needed.** All indicators use fixed periods.
- This is the slowest plan per epoch (5m x ~475k candles x 10 pairs). Keep
  300 epochs on the full whitelist only if runtime allows; otherwise propose
  the core-four pair restriction at Phase 5 (YELLOW).

---

## Risk Parameters (hardcoded — never optimise)
```python
stoploss = -0.08
trailing_stop = False
minimal_roi = {"0": 0.02, "15": 0.012, "45": 0.006, "120": 0}
startup_candle_count = 250
target_vol_pct = 0.4
max_leverage_cap = 2.0
```

Short ROI ladder measured in **minutes** — 120 minutes is the full timeout.

Leverage capped at 2x: entering during peak volatility means NATR is high, so
the volatility-targeting rule will already pull leverage toward 1x. That is
correct and intended.

### Risk verification (precomputed 2026-09-26; base: ratio 0.5, max_open_trades 5)

| Check | Formula | Value | Verdict |
|-------|---------|-------|---------|
| K2 per-trade risk | 0.10 x 0.08 | 0.8% equity | <= 2% PASS — tightest per-trade risk in the portfolio (scalp profile) |
| K7 liquidation headroom | 0.08/2 = 4.0% vs 1/2 = 50% | 12.5x margin | PASS |
| K4 trailing giveback | trailing disabled | n/a | n/a |

### Protections (5m candle counts — 24h = 288)
```python
@property
def protections(self):
    return [
        {"method": "CooldownPeriod", "stop_duration_candles": 2},
        {"method": "StoplossGuard", "lookback_period_candles": 288,
         "trade_limit": 1, "stop_duration_candles": 288,
         "only_per_pair": False, "only_per_side": False},
        {"method": "MaxDrawdown", "lookback_period_candles": 6048,
         "trade_limit": 5, "max_allowed_drawdown": 0.10,
         "calculation_mode": "equity", "stop_duration_candles": 864},
    ]
```

## Strategy Configuration
```python
INTERFACE_VERSION = 3
timeframe = '5m'
can_short = True
```

Config: `configs/strategies/LiquidationWickFade.json`

---

## Key patterns to learn

**Event-shape signals, not level signals.** Every condition describes the
geometry of a candle relative to its own recent history. Nothing references an
absolute price or a pair-specific constant, so the same thresholds should work
across all 10 pairs. Phase 7's per-pair check is the test of that claim.

**Requiring confirmation before entry.** The `close > low + range*0.5` condition
is the difference between "fade the cascade" and "get run over by the cascade".

**Multi-condition coincidence.** Wick alone is noise. Volume alone is noise.
Range alone is noise. The conjunction is the signal. Resist the urge to relax
one of them to get more trades — that is exactly how this becomes a random
volatility strategy.

---

## Serious caveats — read before building

**1. 5m OHLCV understates cascades.** A real cascade may complete inside a
single 5m candle. You see the wick but not the sequence. 1m data exists on disk
if a finer reconstruction is needed later — but that is a YELLOW change.

**2. Backtest fills are optimistic.** During a genuine cascade the order book is
thin and slippage is severe. A backtest fill at the modelled price is
unrealistic. **Phase 7's 2x-fee test is not optional for this plan** — treat
profit factor at 2x fees as the real number, and the 1x number as fiction.

**3. Survivorship of the mechanism.** Exchanges have improved liquidation
engines (partial liquidations, better auto-deleveraging) over the backtest
window. An edge that was strong in 2022 may be materially weaker in 2026.
Phase 7's walk-forward should be read specifically for **decay over time**, not
just regime dependence. A monotonically declining profit factor across the 18
quarters is a kill signal even if the aggregate passes.

---

## Phase map

- **Phase 3 smoke (1 month):** tail-event strategy — a handful of trades is
  expected; 0 trades in a calm month is not automatically a failure. Widen to
  3 months before concluding the conjunction never fires.
- **Phase 4:** the 1m-detail pass IS the headline here (candle-internal wick
  recovery is exactly what 5m candles hide). Main-TF vs detail divergence is
  expected; judge on detail.
- **Phase 7:** read quarterly PF as a time series, not a distribution — decay
  over calendar time is the kill signal (caveat 3).

## Expected behaviour

**Works in:** high-volatility markets with frequent forced deleveraging.
**Struggles in:** calm markets — expect long flat periods, which is correct.
**Watch for:** a low trade count and lumpy returns. Most profit will come from
a handful of days. Check whether removing the single best day destroys the
edge; if it does, this is one lucky event, not a strategy.

## Kill criteria
- Profit factor < 1.0 at **2x fees** (the realistic case here, not the optional one)
- Profit factor declining monotonically across Phase 7 quarters (mechanism decay)
- Removing the best 3 trading days makes profit factor < 1.0
- Fewer than 100 trades across the IS window on all 10 pairs

## Changelog
- 2026-09-26: Full template restructure. **Fixes:** (a) added RSI(14) to the
  indicators table — the exit logic referenced `ind_rsi_14` / `opt_rsi_exit`
  but RSI was never declared (would have crashed Phase 3 or silently deadened
  the exit); (b) removed the stale `opt_target_atr` mention from the exit text
  — it was never a declared parameter; the exit is the minimal_roi ladder plus
  the RSI backstop, now stated explicitly with tags; (c) protections converted
  to 5m candles (24h = 288); (d) risk verification, hyperopt notes (flag not
  needed; core-four hyperopt restriction is a Phase-5 YELLOW proposal), and
  phase map added. No parameter changes.

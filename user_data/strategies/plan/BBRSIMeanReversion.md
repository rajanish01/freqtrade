# BBRSIMeanReversion — Futures Strategy Plan
## Based on: BB_RSI (Leandro Handal) + BbandRsi (Gert Wohlgemuth)
## Absorbs: BollingerDipBuyer (merged — same band-dip hypothesis)

Read `.agent/reference/futures-playbook.md` first. This file states the deltas
PLUS every block the building agent needs (see `00-TEMPLATE.md`).

The simplest strategy in the collection. Fewest parameters, lowest overfitting
risk. It is the **control** against which the band family must justify extra
complexity.

---

## Hypothesis

Price that closes outside a Bollinger Band with momentum confirming exhaustion
reverts to the band mid. The BB-width filter suppresses entries during
squeezes, where "touching the band" only means the bands are tight, not that
price is stretched. MFI adds a volume-weighted second opinion to RSI's
price-only view.

**Why it should work:** short-horizon liquidity provision. The counterparty is
a taker who needs immediate fills and pays the spread to get them. The edge is
small, decays as spreads tighten, and dies in trends.

## Prior run — known failure mode (read before Phase 1)

A build of the v1 knife-catch entry (`close < lower band`, enter immediately)
died at Phase 4: entries fire on the falling knife, grind ~28h into the
stoploss; **70% win rate with inverted payoff (avg loss 3.9x avg win)** — the
K4 gate failed and the run was scrapped. Full diagnosis survives in
`.agent/JOURNAL.md`; the lesson is recorded in
`.agent/reports/PORTFOLIO.md` (lessons ledger).

Standing instruction (pre-approved for this plan only): **build v1 as written
below; if Phase 4 fails on the K4/payoff gate or stoploss-share gate, the
approved Phase-3 iteration is the rejection-confirmed entry**:

```
(long)  low < ind_bb_lower   AND   close > ind_bb_lower    # pierced AND closed back inside
(short) high > ind_bb_upper  AND   close < ind_bb_upper
```

That is "the band rejection happened", not "price is outside the band". It is
derived from the same indicators, adds zero parameters, and directly attacks
the recorded failure mode. Do not invent other fixes before trying this one.

---

## Direction & symmetry claim

**Both directions.** The upper band is the exact mirror of the lower band and
the exhaustion logic is sign-agnostic. Short thresholds are **derived**
(`100 - x`), not separately optimised. If shorts need their own thresholds,
the hypothesis is not actually symmetric — report that rather than adding
params.

## Futures deltas

| Item | Spot original | Futures version |
|------|---------------|-----------------|
| Timeframe | 5m | **15m** |
| Direction | long only | **both** |
| `can_short` | False | **True** |
| Stoploss | -0.065 | **-0.12** (survives up to 3x leverage) |
| `minimal_roi` | {"0":0.4,"335":0.18,...} | **{"0":0.05,"60":0.025,"180":0.01,"360":0}** |

---

## Data requirements

OHLCV 15m only, all 10 majors. No funding/mark data needed by the logic
(funding affects P&L, reported at Phase 4). 1m data present for the
`--timeframe-detail 1m` realism pass.

## Indicators (15m)

| Indicator | Method | Column |
|-----------|--------|--------|
| Bollinger (20, 2) | `qtpylib.bollinger_bands(qtpylib.typical_price(df), 20, 2)` | `ind_bb_lower`, `ind_bb_mid`, `ind_bb_upper` |
| BB width | `(ind_bb_upper - ind_bb_lower) / ind_bb_mid` | `ind_bb_width` |
| BB percent | `(close - ind_bb_lower) / (ind_bb_upper - ind_bb_lower)` | `ind_bb_pct` (diagnostic only — unused by signals; keep for Phase-4 band-position attribution and possible exit experiments) |
| RSI (14) | `ta.RSI(df, 14)` | `ind_rsi_14` |
| MFI (14) | `ta.MFI(df, 14)` | `ind_mfi_14` |
| Volume SMA (20) | `df['volume'].rolling(20).mean()` | `ind_vol_sma_20` |
| NATR (14) | `ta.NATR(df, 14)` | `ind_natr_14` — required, drives leverage |

Max lookback 20 → `startup_candle_count = 200` is comfortably sufficient;
confirm with Phase-2 `recursive-analysis` anyway.

---

## Entry Logic

**Long:**
```
close < ind_bb_lower
ind_rsi_14 < opt_rsi_entry                       # default 30
ind_mfi_14 < opt_mfi_entry                       # default 30
ind_bb_width > opt_min_bb_width                  # default 0.01 — no squeeze
volume > ind_vol_sma_20 * opt_min_vol_ratio      # default 0.5
volume > 0
```
tag: `bb_lower_reversion`

**Short (mirror):**
```
close > ind_bb_upper
ind_rsi_14 > (100 - opt_rsi_entry)
ind_mfi_14 > (100 - opt_mfi_entry)
ind_bb_width > opt_min_bb_width
volume > ind_vol_sma_20 * opt_min_vol_ratio
volume > 0
```
tag: `bb_upper_reversion`

(Deliberate level test, not a cross — a band excursion is a state, and the
width+volume filters limit repetition. The cross-based variant is the
pre-approved fallback above, not the default.)

## Exit Logic

**Long:** `close >= ind_bb_mid` — tag `bb_mid_exit` (reversion to the mid completed)
**Short:** `close <= ind_bb_mid` — tag `bb_mid_exit`

(Current contract after the 2026-09-26 override — the original RSI exit
`ind_rsi_14 > opt_rsi_exit` was removed: it captured nothing, avg -2.4%.)

---

## Hyperopt Parameters

| Parameter | Type | Range | Default | Space |
|-----------|------|-------|---------|-------|
| opt_rsi_entry | IntParameter | 20-40 | 30 | buy |
| opt_mfi_entry | IntParameter | 15-40 | 30 | buy |
| opt_min_bb_width | DecimalParameter | 0.005-0.05 | 0.01 | buy |
| opt_min_vol_ratio | DecimalParameter | 0.3-1.5 | 0.5 | buy |

Four parameters (opt_rsi_exit removed 2026-09-26 — dead param after the
band-mid exit change; sell space is now empty).

### Hyperopt execution notes

- `--analyze-per-epoch`: **NOT needed.** Every indicator uses fixed periods;
  all `opt_*` are thresholds read at signal time.
- 300 epochs default is fine; `--early-stop 40` acceptable.

---

## Risk Parameters (hardcoded — never optimise)
```python
stoploss = -0.12
trailing_stop = True
trailing_stop_positive = 0.01
trailing_stop_positive_offset = 0.03
trailing_only_offset_is_reached = True
minimal_roi = {"0": 0.05, "60": 0.025, "180": 0.01, "360": 0}
startup_candle_count = 200
target_vol_pct = 0.5
max_leverage_cap = 3.0
```

### Risk verification (precomputed 2026-09-26; base: ratio 0.5, max_open_trades 5)

| Check | Formula | Value | Verdict |
|-------|---------|-------|---------|
| K2 per-trade risk | 0.10 x 0.12 | 1.2% equity | <= 2% PASS |
| K7 liquidation headroom | 0.12/3 = 4.0% vs 1/3 = 33.3% | 8x margin | PASS |
| K4 trailing giveback | 0.01 <= 0.03/3 = 0.01 | at the boundary | PASS |
| ROI precedes trailing | 0.03 < 0.05 | offset below ROI@0 | PASS |

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

Config: `configs/strategies/BBRSIMeanReversion.json`

---

## Phase map

- **Phase 3 smoke (1 month, 20250601-20250701):** expect roughly 5-40 trades.
  0 = conditions too tight (check MFI+RSI conjunction); >200 = noise.
- **Phase 4:** compare per-tag P&L (`backtesting-analysis`). Watch stoploss
  share of exits — the prior run failed exactly here. Funding share must stay
  < 20% of gross.
- **Phase 7:** mean reversion is regime-fragile; expect losing quarters in
  trending regimes. The kill criterion on shorts-vs-longs divergence applies.

## Key patterns to learn

**BB width filter.** In a squeeze, price rides the band without being
stretched. Directly reusable in any band strategy (VWAP, Keltner, squeeze
breakout — the squeeze variant inverts it).

**MFI as volume-weighted RSI.** Two momentum reads — one price-only, one
volume-weighted. The one place two "momentum" indicators are justified despite
anti-pattern #7, because their inputs differ.

**Derived short thresholds.** Mirroring is the cheapest overfitting defence.

---

## Expected behaviour

**Works in:** ranging, oscillating markets with stable volatility.
**Struggles in:** strong trends (band-walking), and low-volatility regimes
where the width filter blocks most entries.
**Watch for:** the trend-continuation failure — if stoploss dominates exits,
the "reversion" was actually continuation and the hypothesis is inverted. This
exact mode killed the prior run (see top).

## Kill criteria
- Profit factor < 1.2 in-sample after one round of signal tuning
- Stoploss > 50% of exits
- K4: avg_loss < 3 x avg_win fails (this is what killed v1 the first time)
- Profit factor < 1.0 at 2x fees
- Shorts materially worse than longs -> drop shorts, re-test long-only,
  and record that the symmetry claim failed

## Changelog
- 2026-09-26: Full template restructure. Added prior-failure section +
  pre-approved rejection-confirmed Phase-3 fallback (from `PORTFOLIO.md`
  lessons ledger — the v1 knife-catch run died on inverted payoff). Marked
  `ind_bb_pct` diagnostic-only. Added risk verification, protections,
  hyperopt-flag note (not needed), phase map. No parameter changes.
- 2026-09-26: Exit changed RSI -> band mid (`close >= ind_bb_mid` long /
  `close <= ind_bb_mid` short, tag `bb_mid_exit`); `opt_rsi_exit` removed
  (sell space now empty). Evidence: phase4-iter1 postmortem — the pre-approved
  rejection-confirmed entry improved everything (PF 0.61 -> 0.73, K4
  3.85x -> 3.14x) but kill criteria met (K4 > 3x, PF < 1.2). User approved
  ONE override attempt: rsi_exit cohort loses -486 USDT (avg -2.4%, captures
  nothing) while roi exits +1150 win; the band-mid exit targets the reversion
  directly. If this also fails the gates, DEAD — no further attempts.

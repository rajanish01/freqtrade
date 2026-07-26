# BBRSIMeanReversion — Futures Strategy Plan
## Based on: BB_RSI (Leandro Handal) + BbandRsi (Gert Wohlgemuth)
## Absorbs: BollingerDipBuyer (merged — same band-dip hypothesis)

Read `.agent/reference/futures-playbook.md` first. This file states only the deltas.

The simplest strategy in the collection. Fewest parameters, lowest overfitting
risk. Start here — it is the control against which the others must justify
their extra complexity.

---

## Hypothesis

Price that closes outside a Bollinger Band with momentum confirming exhaustion
reverts to the band mid. The BB-width filter suppresses entries during squeezes,
where "touching the band" only means the bands are tight, not that price is
stretched. MFI adds a volume-weighted second opinion to RSI's price-only view.

**Why it should work:** short-horizon liquidity provision. The counterparty is
a taker who needs immediate fills and pays the spread to get them. The edge is
small, decays as spreads tighten, and dies in trends.

---

## Futures deltas

| Item | Spot original | Futures version |
|------|---------------|-----------------|
| Timeframe | 5m | **15m** |
| Direction | long only | **both** — the band is symmetric |
| `can_short` | False | **True** |
| Stoploss | -0.065 | **-0.12** (survives up to 3x leverage) |
| `minimal_roi` | {"0":0.4,"335":0.18,...} | **{"0":0.05,"60":0.025,"180":0.01,"360":0}** |

Shorts are legitimate here: the upper band is the exact mirror of the lower
band, and the exhaustion logic is sign-agnostic.

---

## Indicators (15m)

| Indicator | Method | Column |
|-----------|--------|--------|
| Bollinger (20, 2) | `qtpylib.bollinger_bands(qtpylib.typical_price(df), 20, 2)` | `ind_bb_lower`, `ind_bb_mid`, `ind_bb_upper` |
| BB width | `(ind_bb_upper - ind_bb_lower) / ind_bb_mid` | `ind_bb_width` |
| BB percent | `(close - ind_bb_lower) / (ind_bb_upper - ind_bb_lower)` | `ind_bb_pct` |
| RSI (14) | `ta.RSI(df, 14)` | `ind_rsi_14` |
| MFI (14) | `ta.MFI(df, 14)` | `ind_mfi_14` |
| Volume SMA (20) | `df['volume'].rolling(20).mean()` | `ind_vol_sma_20` |
| NATR (14) | `ta.NATR(df, 14)` | `ind_natr_14` — required, drives leverage |

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

The short thresholds are **derived** from the long ones (`100 - x`), not
separately optimised. This halves the parameter count and enforces the
symmetry the hypothesis claims. If shorts need their own thresholds, the
hypothesis is not actually symmetric — report that rather than adding params.

---

## Exit Logic

**Long:** `ind_rsi_14 > opt_rsi_exit` (default 70)
**Short:** `ind_rsi_14 < (100 - opt_rsi_exit)`

---

## Hyperopt Parameters

| Parameter | Type | Range | Default | Space |
|-----------|------|-------|---------|-------|
| opt_rsi_entry | IntParameter | 20-40 | 30 | buy |
| opt_mfi_entry | IntParameter | 15-40 | 30 | buy |
| opt_min_bb_width | DecimalParameter | 0.005-0.05 | 0.01 | buy |
| opt_min_vol_ratio | DecimalParameter | 0.3-1.5 | 0.5 | buy |
| opt_rsi_exit | IntParameter | 60-85 | 70 | sell |

Five parameters. Keep it that way.

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

## Strategy Configuration
```python
INTERFACE_VERSION = 3
timeframe = '15m'
can_short = True
use_custom_stoploss = False
```

Config: `configs/strategies/BBRSIMeanReversion.json`

---

## Key patterns to learn

**BB width filter.** In a squeeze, price rides the band without being
stretched. `ind_bb_width > threshold` is directly reusable in any band strategy
(VWAP, Keltner).

**MFI as volume-weighted RSI.** Two momentum reads — one price-only, one
volume-weighted. Agreement is a stronger signal than either alone. This is the
one place two "momentum" indicators are justified despite anti-pattern #7,
because their inputs differ.

**Derived short thresholds.** Mirroring instead of duplicating parameters is
the cheapest overfitting defence available.

---

## Expected behaviour

**Works in:** ranging, oscillating markets with stable volatility.
**Struggles in:** strong trends (band-walking), and low-volatility regimes
where the width filter blocks most entries.
**Watch for:** the trend-continuation failure — if stoploss dominates exits,
the "reversion" was actually continuation and the hypothesis is inverted.

## Kill criteria
- Profit factor < 1.2 in-sample after one round of signal tuning
- Stoploss > 50% of exits
- Profit factor < 1.0 at 2x fees
- Shorts materially worse than longs -> drop shorts, re-test long-only,
  and record that the symmetry claim failed

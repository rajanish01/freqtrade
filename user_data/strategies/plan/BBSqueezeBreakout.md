# BBSqueezeBreakout — Futures Strategy Plan
## Based on: the TTM Squeeze (John Carter) / Bollinger bandwidth squeezes —
## the inverse reading of the BBRSIMeanReversion width filter

Read `.agent/reference/futures-playbook.md` first. This file states the deltas
PLUS every block the building agent needs (see `00-TEMPLATE.md`). New plan,
written to the template on 2026-09-26. Research confidence: **3/5** (squeeze
methods are widely used and mechanistically plausible via crypto's strong
volatility clustering; published standalone expectancy is thin — hence the
hard "must beat the control" kill criterion).

Every band plan so far treats **low width as a no-trade zone**
(`ind_bb_width > opt_min_bb_width` as an entry *blocker*). This plan treats
**low width as the setup** — the compressed spring — and trades the expansion
that follows. It inverts the width filter of the band family on purpose.

---

## Hypothesis

Crypto volatility is strongly clustered: long quiet periods are followed by
expansion, and the direction of the first strong close through a squeezed
Bollinger Band tends to lead the expansion leg. The squeeze alone does not
predict direction; the break + momentum + volume conjunct does.

**Why it should work:** counterparty logic. During the squeeze, carry-traders
and range traders are short volatility. When price leaves the band, their
stops and rehedging fuel the first leg of the expansion. The edge is in the
*transition* from compression to expansion, a regime change the reversion
plans are explicitly filtered out of.

## Direction & symmetry claim

**Both directions.** A band is symmetric and compression carries no
directional information — the direction comes from which band is broken.
Thresholds derived, not duplicated. If the short side materially
underperforms (upside squeezes vs downside liquidation-led breaks), drop
shorts and record the asymmetry finding.

## Futures deltas

| Item | TTM/spot convention | Futures version |
|------|----------------------|-----------------|
| Timeframe | daily / 5m | **15m** |
| Direction | usually long-biased teaching examples | **both** |
| Momentum confirm | TTM momentum histogram | **ROC(6)** (catalog indicator) |
| Stoploss | pattern stop beyond the squeeze | **-0.10 fixed** (Kotegawa layer) |

---

## Data requirements

OHLCV 15m, all 10 majors. No informative timeframes.

## Indicators (15m)

| Indicator | Method | Column |
|-----------|--------|--------|
| Bollinger (20, 2) | `qtpylib.bollinger_bands(qtpylib.typical_price(df), 20, 2)` | `ind_bb_lower`, `ind_bb_mid`, `ind_bb_upper` |
| BB width | `(ind_bb_upper - ind_bb_lower) / ind_bb_mid` | `ind_bb_width` |
| Squeeze floor (sweep) | `ind_bb_width.rolling(N).quantile(0.2)`, N in stepped sweep | `ind_sq_floor_{N}` |
| Squeeze state | `ind_bb_width <= ind_sq_floor_{N}` | computed at signal time |
| ROC (6) | `ta.ROC(df, 6)` | `ind_roc_6` |
| Volume SMA (50) / spike | `volume.rolling(50).mean()` / `volume / sma` | `ind_vol_sma_50`, `ind_vol_spike` |
| RSI (14) | `ta.RSI(df, 14)` | `ind_rsi_14` — direction guard only |
| NATR (14) | `ta.NATR(df, 14)` | `ind_natr_14` — required, drives leverage |

Design decisions the building agent must honour:
- The squeeze quantile **0.2** is a structural constant (`_SQ_QUANTILE`),
  not an `opt_*` — it defines "compressed", it is not a trading threshold.
  Documented here so it is not mistaken for a magic number in a condition.
- Stepped sweep (template pattern), no per-epoch recompute:
  `sq_lengths = range(50, 151, 25)  # 50 75 100 125 150`
- "Squeeze is recent, not necessarily this candle": use
  `squeeze_on.rolling(5).max() > 0` — a window of 5 candles for the break to
  follow the compression. The 5 is the shape of the event (like
  `LiquidationWickFade`); hyperopt may tune it via `opt_sq_recent`.

---

## Entry Logic

**Long:**
```
squeeze_recent(N=opt_sq_recent)               # width was at/below floor within last 5 candles
close > ind_bb_upper                          # first break upward
ind_roc_6 > opt_roc_min                       # default 0.8 — momentum confirming
ind_rsi_14 > 50                               # direction guard (structural, not tuned)
ind_vol_spike > opt_vol_mult                  # default 1.5
volume > 0
```
tag: `squeeze_break_long`

**Short (mirror):**
```
squeeze_recent(N=opt_sq_recent)
close < ind_bb_lower
ind_roc_6 < -opt_roc_min
ind_rsi_14 < 50
ind_vol_spike > opt_vol_mult
volume > 0
```
tag: `squeeze_break_short`

The `ind_rsi_14 > 50` / `< 50` guards are deliberately *untuned* structural
gates (centre-line checks). They exist so a break while momentum is already
fading (RSI on the wrong side of midline) is not taken. If Phase 4 shows they
never filter anything, delete them — do not tune them.

## Exit Logic

**Long:** `close < ind_bb_mid` — tag `bb_midline` (thesis: ride the expansion
while it holds above the mean)
**Short:** `close > ind_bb_mid`

Plus the ROI ladder and trailing stop below — expansions run, so this plan
(unlike the reversion plans) keeps a trailing stop on top of the structural
exit.

---

## Hyperopt Parameters

| Parameter | Type | Range | Default | Space |
|-----------|------|-------|---------|-------|
| opt_sq_lookback | IntParameter (step=25) | 50-150 | 100 | buy |
| opt_sq_recent | IntParameter | 3-8 | 5 | buy |
| opt_roc_min | DecimalParameter | 0.3-2.0 | 0.8 | buy |
| opt_vol_mult | DecimalParameter | 1.0-3.0 | 1.5 | buy |

Four parameters. The squeeze quantile is fixed (0.2) and the RSI midline
guards are structural — both deliberately outside the hyperopt space to keep
the overfit surface small on a plan whose prior is the weakest of the
portfolio.

### Hyperopt execution notes

- `--analyze-per-epoch`: **NOT needed.** The squeeze floor sweep is
  precomputed once per lookback; `opt_sq_lookback` only selects a column, and
  `opt_sq_recent` is a signal-time window.
- Stepped param: `IntParameter(50, 150, default=100, step=25)` with the
  precompute loop hardcoding `range(50, 151, 25)`.

---

## Risk Parameters (hardcoded — never optimise)
```python
stoploss = -0.10
trailing_stop = True
trailing_stop_positive = 0.01
trailing_stop_positive_offset = 0.03
trailing_only_offset_is_reached = True
minimal_roi = {"0": 0.06, "60": 0.03, "180": 0.01, "360": 0}
startup_candle_count = 200    # max sweep 150 + convergence buffer
target_vol_pct = 0.5
max_leverage_cap = 3.0
```

### Risk verification (precomputed 2026-09-26; base: ratio 0.5, max_open_trades 5)

| Check | Formula | Value | Verdict |
|-------|---------|-------|---------|
| K2 per-trade risk | 0.10 x 0.10 | 1.0% equity | <= 2% PASS |
| K7 liquidation headroom | 0.10/3 = 3.3% vs 1/3 = 33.3% | 10x margin | PASS |
| K4 trailing giveback | 0.01 <= 0.03/3 = 0.01 | at the boundary | PASS |
| ROI precedes trailing | 0.03 < 0.06 | offset below ROI@0 | PASS |

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

Config: `configs/strategies/BBSqueezeBreakout.json`

---

## Phase map

- **Phase 3 smoke:** the conjunction (recent squeeze + break + ROC + volume)
  is restrictive — 2-20 trades/month is the sane band; 0 = check the
  `squeeze_recent` window is implemented as a rolling max, not a same-candle
  requirement.
- **Phase 4:** the headline gate is comparative: must beat
  `BBRSIMeanReversion` on the same IS window. A poor absolute showing with a
  complementary losing-quarter profile vs the control is a *portfolio*
  argument for keeping it — state that explicitly rather than quietly passing.
- **Phase 7:** squeeze opportunities are regime-clustered; expect starved
  quarters in sustained trends. Starvation is acceptable; losing quarters are
  not.

## Key patterns to learn

**Inverted filter reuse.** The same `ind_bb_width` column that *blocks* trades
in the reversion plans *enables* them here. One indicator, two hypotheses —
exactly the kind of reuse that keeps the catalogue small.

**Structural constants vs tuned thresholds.** The 0.2 quantile and RSI
midline are definition-of-regime choices, not fitted values; keeping them out
of hyperopt halves the search space for free.

**Regime-transition trades.** The edge is the compression -> expansion
transition itself, a different market state from both "ranging" (reversion
plans) and "trending" (trend plans).

---

## Expected behaviour

**Works in:** markets cycling between quiet drift and explosive repricing —
crypto's volatility-clustering regime.
**Struggles in:** persistently trending or persistently dead markets (no
squeezes to break, or breaks that are grind-outs with no expansion).
**Watch for:** false breaks in choppy ranges — if stoploss share of exits
exceeds 50%, the ROC/volume conjuncts are not filtering enough; that is a
finding about the conjunction, and the correct response is tightening the
event shape, not widening the stop.

## Kill criteria
- Profit factor < 1.2 in-sample after one round of tuning
- Does not beat `BBRSIMeanReversion` on the same IS window -> the squeeze
  reading adds nothing over plain band reversion; drop the plan
- Stoploss share of exits > 50% (false breaks dominate)
- Profit factor < 1.0 at 2x fees

## Changelog
- 2026-09-26: Plan created to `00-TEMPLATE.md`. Family added: volatility
  compression -> expansion. Uses only catalog indicators (BB, ROC, RSI,
  volume, NATR) — no Phase-2 catalog gate triggered.

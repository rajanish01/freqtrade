# RelativeStrengthBTC — Futures Strategy Plan
## Based on: cross-asset relative-strength / lead-lag literature equities->crypto
## (BTC as the crypto market factor) — adapted to freqtrade informative pairs

Read `.agent/reference/futures-playbook.md` first. This file states the deltas
PLUS every block the building agent needs (see `00-TEMPLATE.md`). New plan,
written to the template on 2026-09-26. Research confidence: **3/5** (BTC beta
and alt-vs-BTC relative strength are well documented empirically; the
freqtrade mechanicals of cross-pair informative data are the risk — Phase 0/2
prove them first).

The only plan whose signal comes from **another pair's data**. Every other
plan is self-contained per pair; this one reads BTC to decide about alts.
It is also the template example for the `@informative` cross-pair pattern.

---

## Hypothesis

Alts are high-beta expressions of the crypto market factor (BTC). When BTC is
in a confirmed uptrend, alts whose own price is strengthening *relative to
BTC* outperform alts in general — capital rotates into strength. When BTC is
in a confirmed downtrend, alts that are weak relative to BTC underperform fur-
ther — the same rotation, reversed. Trade the rotation event: the alt/BTC
ratio crossing from falling to rising (or back), gated by the BTC regime.

**Why it should work:** the counterparty is slow capital — allocators and
retail flow that rotate between BTC and alts in waves, not per candle. A
ratio trend is a directly observable footprint of that rotation.

## Direction & symmetry claim

**Both directions.** Long: BTC bull + alt outperforms. Short: BTC bear + alt
underperforms. Both legs are *trend following* (with the factor, with the
relative flow), so the symmetry conditions of `futures-playbook.md` §3 hold.
Thresholds derived from one set.

## Futures deltas (from a generic spot rotation concept)

| Item | Generic spot version | Futures version |
|------|----------------------|-----------------|
| Timeframe | 1h/4h (rotation is slow) | **15m** (fee fraction acceptable, data deep) |
| Direction | long the strong basket | **both** — per-alt rotation, not basket |
| Shorts | impossible on spot | **enabled** — shorting the weak alts in a BTC bear |
| Stoploss | n/a | **-0.12** |

---

## Data requirements — cross-pair (the distinguishing block)

BTC is **data-only**: it is read as an informative pair and is **not** in the
trade whitelist (an alt-vs-itself ratio is constant 1 — dead signal).

```python
def informative_pairs(self):
    return [
        ("BTC/USDT:USDT", "15m"),   # price for the ratio
        ("BTC/USDT:USDT", "1h"),    # regime (EMA50 vs EMA200)
    ]
```

(Equivalently via the `@informative("1h", "BTC/USDT:USDT", fmt=...)` decorator,
verified present in this checkout at `freqtrade/strategy/informative_decorator.py`;
equal-timeframe 15m informative is explicitly allowed.)

The same `populate_indicators` code that computes `ind_ema_50` / `ind_ema_200`
on the strategy pair also runs on the informative frames; merged columns arrive
as `btc_ind_ema_50_1h` etc. under the default `{base}_{column}_{timeframe}`
format — verify the actual names once at Phase 2 with a debug print, then
remove the debug.

Whitelist: the 9 alts (`ETH SOL BNB XRP ADA DOGE AVAX LINK LTC`, all
`/USDT:USDT`). Config: `configs/strategies/RelativeStrengthBTC.json`.

**Informative warmup sizing (why startup = 900):** same rule as
`MultiMATSL.md` — a 1h EMA(200) needs 200 x 4 = 800 15m candles of extended
history plus convergence buffer. `startup_candle_count = 900`. Phase-2
`recursive-analysis` validates.

## Indicators (15m strategy pair + BTC informative)

| Indicator | Method | Column |
|-----------|--------|--------|
| EMA (50) | `ta.EMA(df, 50)` (also produced on BTC 1h informative) | `ind_ema_50` / `btc_ind_ema_50_1h` |
| EMA (200) | `ta.EMA(df, 200)` (idem on BTC 1h) | `ind_ema_200` / `btc_ind_ema_200_1h` |
| BTC close (15m) | via informative merge | `btc_close_15m` |
| RS ratio | `close / btc_close_15m` | `ind_rs` |
| RS EMA fast sweep | `ta.EMA(ind_rs, F)`, F in `range(6, 25, 3)` | `ind_rs_fast_{F}` |
| RS EMA slow sweep | `ta.EMA(ind_rs, S)`, S in `range(24, 97, 12)` | `ind_rs_slow_{S}` |
| RSI (14) | `ta.RSI(df, 14)` | `ind_rsi_14` |
| NATR (14) | `ta.NATR(df, 14)` | `ind_natr_14` — drives leverage (own-pair vol) |

Ratio computed from the merged BTC 15m close (ffilled by the informative
machinery). Guard: `btc_close_15m > 0` and `.notna()` at the merge head.

EMAs on a *ratio* — the ratio is unitless and starts near 1 on every pair, so
fast/slow EMAs comparing it are well-behaved across pairs. This is the "bounded
/ normalised indicators" preference of the indicator catalog applied to a
cross-pair quantity.

---

## Entry Logic

**Long:**
```
btc_ind_ema_50_1h > btc_ind_ema_200_1h        # BTC 1h regime: BULL
qtpylib.crossed_above(rs_fast, rs_slow)       # this alt just started outperforming
ind_rsi_14 < opt_rsi_cap                      # default 65 — do not chase extended
volume > 0
```
tag: `rs_rotate_long`

**Short (mirror):**
```
btc_ind_ema_50_1h < btc_ind_ema_200_1h        # BTC 1h regime: BEAR
qtpylib.crossed_below(rs_fast, rs_slow)       # this alt just started underperforming
ind_rsi_14 > (100 - opt_rsi_cap)
volume > 0
```
tag: `rs_rotate_short`

A cross, not a level: the rotation *event* is the entry. Holding a level
condition would re-enter every candle of a trending ratio.

## Exit Logic

**Long:** `qtpylib.crossed_below(rs_fast, rs_slow)` — tag `rs_unwind`; OR BTC
regime flips bear — tag `regime_flip`
**Short:** `qtpylib.crossed_above(rs_fast, rs_slow)`; OR regime flips bull —
same tag names.

The regime-flip exit is **structural** (the gating condition is gone) — exit
regardless of P&L, same pattern as `SuperTrendBBCombo`'s `st_flip`.

---

## Hyperopt Parameters

| Parameter | Type | Range | Default | Space |
|-----------|------|-------|---------|-------|
| opt_rs_fast | IntParameter (step=3) | 6-24 | 12 | buy |
| opt_rs_slow | IntParameter (step=12) | 24-96 | 48 | buy |
| opt_rsi_cap | IntParameter | 50-70 | 65 | buy |

Three parameters — the most frugal plan in the portfolio alongside
VWAPBandReversion. Invariant asserted: `opt_rs_fast < opt_rs_slow` (ranges
overlap at 24; a Phase-5 epoch violating it means the ratio EMAs are inverted
— record and constrain, do not accept silently).

### Hyperopt execution notes

- `--analyze-per-epoch`: **NOT needed.** Ratio EMA sweeps are precomputed once
  (7 fast + 7 slow columns); `opt_*` select columns at signal time.
- Stepped params per template (`step=3` / `step=12`), loops hardcode the
  matching `range(...)` (`.range` ignores `step`).

---

## Risk Parameters (hardcoded — never optimise)
```python
stoploss = -0.12
trailing_stop = False
minimal_roi = {"0": 0.06, "120": 0.03, "360": 0.01, "720": 0}
startup_candle_count = 900    # BTC 1h EMA200 informative warm-up (rule above)
target_vol_pct = 0.5
max_leverage_cap = 2.0
```

### Risk verification (precomputed 2026-09-26; base: ratio 0.5, max_open_trades 5)

| Check | Formula | Value | Verdict |
|-------|---------|-------|---------|
| K2 per-trade risk | 0.10 x 0.12 | 1.2% equity | <= 2% PASS |
| K7 liquidation headroom | 0.12/2 = 6.0% vs 1/2 = 50% | 8.3x margin | PASS |
| K4 trailing giveback | trailing disabled | n/a | n/a |
| Concentration note | signals on 9 alts correlate with the *same* BTC regime | accepted; review max_open_trades at Phase 8 | recorded |

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

Config: `configs/strategies/RelativeStrengthBTC.json`
(**whitelist is the 9 alts — BTC excluded by design**)

---

## Phase map

- **Phase 0:** extra check — BTC 15m and 1h data cover the full IS+OOS range
  (it does, per `list-data`, but this plan *depends* on it; a BTC data gap is
  a signal gap, not just a missing tradable).
- **Phase 2:** verify merged column names once with a debug print (this
  checkout's fmt semantics), then remove. `recursive-analysis` covers the 900
  warmup.
- **Phase 4:** every trade shares the BTC regime — report the exit-tag split
  (`rs_unwind` vs `regime_flip`). `regime_flip` dominating = the ratio signal
  is noise and the regime is doing all the work.
- **Phase 7:** compare losing quarters against `MultiMATSL` — both are trend
  plans; zero overlap would support the "two different trend bets" argument.

## Key patterns to learn

**Cross-pair informative data.** `informative_pairs` / `@informative` with an
explicit asset — the only pattern for "pair A reads pair B" inside freqtrade
rules. This plan is the reference implementation.

**Unitless ratio features.** `close / btc_close` starts near 1 on every pair
and is stationary-ish — the right way to make a cross-pair quantity comparable
across the whitelist (contrast: raw price or absolute spread).

**Regime gate from an external asset.** The gate (`btc 1h trend`) is not
computable from the traded pair alone — a genuinely new information source,
not a recombination of existing columns.

---

## Expected behaviour

**Works in:** trending crypto markets with clear leadership rotation.
**Struggles in:** market-wide V-chops where every alt moves with BTC and the
ratio mean-reverts — crosses whipsaw.
**Watch for:** (1) regime-flip exit share (see Phase map); (2) whether the
strategy is secretly just "long alts in BTC bull" — if per-tag analysis shows
`rs_rotate_long` entries cluster on the 2-3 highest-beta pairs regardless of
the ratio cross, the RS layer adds nothing over a pure BTC-regime gate.

## Kill criteria
- Profit factor < 1.2 in-sample after one round of tuning
- `regime_flip` exits are > 60% of exits AND net negative (ratio cross useless)
- Single-pair profit share > 50% (not a rotation strategy, a one-alt bet)
- Profit factor < 1.0 at 2x fees
- Shorts materially worse than longs -> drop shorts, record the asymmetry

## Changelog
- 2026-09-26: Plan created to `00-TEMPLATE.md`. Family added: cross-pair
  lead-lag / relative strength. BTC is data-only (excluded from whitelist by
  construction). Reuses the MultiMATSL informative warmup rule (startup 900).

# DonchianATRBreakout — Futures Strategy Plan
## Based on: Turtle Trader Donchian-channel breakouts (Richard Dennis, 1983) +
## freqtrade-strategies `SwingHighToSky` (swing-breakout lineage)

Read `.agent/reference/futures-playbook.md` first. This file states the deltas
PLUS every block the building agent needs (see `00-TEMPLATE.md`). New plan,
written to the template on 2026-09-26. Research confidence: **4/5** (trend
premia and channel breakouts are among the best-documented anomalies in futures
markets, crypto included — see `RESEARCH-BACKLOG.md`).

The only **breakout** plan. Every other plan enters on weakness (pullback,
capitulation, band penetration); this one enters on *strength* — a close beyond
the prior N-candle extreme. It is the missing entry style in the portfolio.

---

## Hypothesis

Markets alternate between drift and consolidation, and the level other traders
watch — the recent high — clusters stop orders and breakout entries behind it.
A confirmed close beyond the N-candle extreme, with trend strength (ADX) and
participation (volume) present, continues more often than it immediately fails,
because the move is being fuelled by forced stop-outs.

**Why it should work:** the counterparty on a failed-ish sideways day is a mean
reversion trader who is *short* the breakout with a stop right above the
recent high. When the level goes, their stops become your tailwind. This is the
structural opposite of the liquidity-provision edge in `BBRSIMeanReversion` —
the two plans are natural complements and their Phase-7 results should be
compared for correlation of losing quarters.

## Direction & symmetry claim

**Both directions.** A breakout is symmetric by construction (prior-high break =
long, prior-low break = short), and trend following has no preferred sign
(`futures-playbook.md` §3). Thresholds derived, not duplicated.

## Futures deltas

| Item | Turtle/spot convention | Futures version |
|------|------------------------|-----------------|
| Timeframe | daily (Turtle), 5m (SwingHighToSky) | **15m** |
| Direction | both (Turtle futures) | **both** |
| Stoploss | 2x ATR (Turtle "N") | **-0.12 fixed** (Kotegawa layer; no custom stops) |
| Exits | 20-in / 10-out channels | **shorter exit channel only (winners run)** |

---

## Data requirements

OHLCV 15m, all 10 majors. No informative timeframes. No funding/mark reads.

**Catalog note (YELLOW pre-approved):** the Donchian channel is not in
`.agent/reference/indicator-catalog.md`. It is two pandas rolling calls
(`high.rolling(N).max()`, `low.rolling(N).min()`) — the same "pandas rolling"
category the catalog already lists for Volume SMA. This plan's approval
constitutes the Phase-2 approval; on implementation, add one catalog row
("Donchian channel | pandas rolling | period | `ind_dc_upper`/`ind_dc_lower`").

## Indicators (15m)

| Indicator | Method | Column |
|-----------|--------|--------|
| Entry-channel high | `high.rolling(N).max().shift(1)`, N in stepped sweep | `ind_dc_high_{N}` |
| Entry-channel low | `low.rolling(N).min().shift(1)` | `ind_dc_low_{N}` |
| Exit-channel low (long) | `low.rolling(M).min().shift(1)`, M in stepped sweep | `ind_dc_exit_low_{M}` |
| Exit-channel high (short) | `high.rolling(M).max().shift(1)` | `ind_dc_exit_high_{M}` |
| ADX (14) | `ta.ADX(df, 14)` | `ind_adx_14` |
| Volume SMA (50) | `volume.rolling(50).mean()` | `ind_vol_sma_50` |
| Volume spike | `volume / ind_vol_sma_50` | `ind_vol_spike` |
| NATR (14) | `ta.NATR(df, 14)` | `ind_natr_14` — required, drives leverage |

**The `shift(1)` is load-bearing and is not lookahead.** Without it the channel
contains the current candle, `close > rolling max` can never be true (close <=
high), and the strategy fires zero trades — a silent all-NaN-adjacent failure
that costs a debugging iteration. `shift(1)` uses only past candles: the signal
is "close exceeds the extreme of the *prior* N candles". This is the canonical
Donchian convention.

Sweep periods (stepped, selected at signal time — see template):
```python
entry_lengths = range(20, 121, 20)   # 20 40 60 80 100 120
exit_lengths  = range(5, 41, 5)      # 5 10 ... 40
dc_hi_col = f"ind_dc_high_{self.opt_dc_entry_len.value}"
# Invariant the plan asserts: opt_dc_exit_len < opt_dc_entry_len
# (wide channel to get in, tight channel to get out). The ranges make the
# inversion possible but unlikely; at the Phase 5 review, if the best epoch
# has exit_len >= entry_len, the trailing logic is inverted — record it and
# constrain rather than silently accepting it.
```

---

## Entry Logic

**Long:**
```
close > dataframe[dc_hi_col]                 # close beyond prior-N high
ind_adx_14 > opt_adx_min                     # default 25 — trend fuel present
ind_vol_spike > opt_vol_mult                 # default 1.5 — participation
volume > 0
```
tag: `dc_breakout_long`

**Short (mirror):**
```
close < dataframe[dc_lo_col]
ind_adx_14 > opt_adx_min
ind_vol_spike > opt_vol_mult
volume > 0
```
tag: `dc_breakout_short`

A level test (`close >`), not a cross: any close beyond the prior extreme is a
valid breakout state; the CooldownPeriod protection prevents immediate re-entry
churn after a stop-out, and `max_open_trades` caps simultaneous exposure.

## Exit Logic

**Long:** `close < dataframe[f"ind_dc_exit_low_{M}"]` — tag `dc_trail_exit`
**Short:** `close > dataframe[f"ind_dc_exit_high_{M}"]` — tag `dc_trail_exit`

The exit channel is the exit thesis (Turtle-style trailing structure): the
trade is held until the shorter channel breaks. `minimal_roi` is disabled and
there is no trailing stop — the channel gives back more than a trail would, by
design, in exchange for not capping winners.

---

## Hyperopt Parameters

| Parameter | Type | Range | Default | Space |
|-----------|------|-------|---------|-------|
| opt_dc_entry_len | IntParameter (step=20) | 20-120 | 40 | buy |
| opt_dc_exit_len | IntParameter (step=5) | 5-40 | 15 | sell |
| opt_adx_min | IntParameter | 15-35 | 25 | buy |
| opt_vol_mult | DecimalParameter | 1.0-3.0 | 1.5 | buy |

Four parameters. If Phase 5 flags instability, fix `opt_dc_entry_len` at 40
first (channel length is the least noise-sensitive of the four).

### Hyperopt execution notes

- `--analyze-per-epoch`: **NOT needed.** Both channel sweeps are precomputed
  once (6 entry + 8 exit columns per side); `opt_*` only select columns at
  signal time.
- Stepped params: `IntParameter(20, 120, default=40, step=20)` etc. — and the
  precompute loops hardcode the matching `range(...)` (the `.range` property
  ignores `step`; see `00-TEMPLATE.md`).

---

## Risk Parameters (hardcoded — never optimise)
```python
stoploss = -0.12
trailing_stop = False
minimal_roi = {"0": 100}      # disabled — the exit channel is the exit
startup_candle_count = 200    # max sweep 120 + buffer (covers ADX convergence)
target_vol_pct = 0.5
max_leverage_cap = 2.0        # breakouts enter at elevated local volatility
```

### Risk verification (precomputed 2026-09-26; base: ratio 0.5, max_open_trades 5)

| Check | Formula | Value | Verdict |
|-------|---------|-------|---------|
| K2 per-trade risk | 0.10 x 0.12 | 1.2% equity | <= 2% PASS |
| K7 liquidation headroom | 0.12/2 = 6.0% vs 1/2 = 50% | 8.3x margin | PASS |
| K4 trailing giveback | trailing disabled; exit channel is the giveback mechanism | n/a (structural) | PASS |
| ROI precedes trailing | ROI disabled (`{"0": 100}`) | trivially true | PASS |

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

Config: `configs/strategies/DonchianATRBreakout.json`

---

## Phase map

- **Phase 3 smoke:** 0 trades over one month is suspicious here — check the
  `shift(1)` is present before touching any threshold (it is the classic bug).
- **Phase 4:** expect a clearly *low* win rate (35-45%): breakout systems are
  payoff-driven. Win rate is not a gate; `avg_loss < 3 x avg_win` is.
- **Phase 7:** the key comparison is vs `MultiMATSL` (the other trend plan) —
  losing-quarter *overlap* tells you whether "trend" is one bet or two.

## Key patterns to learn

**The shift(1) Donchian trap.** The single most common silent failure in
breakout implementations. Canonical example for the catalog note.

**Enter on strength, exit on weakness.** The opposite timing of every reversion
plan — the portfolio's diversification argument rests on this asymmetry.

**Exit channel as structural trail.** A cheaper-to-reason-about alternative to
percent trailing; notably immune to the "trailing giveback" calibration that
K4 gates elsewhere.

---

## Expected behaviour

**Works in:** sustained directional legs after compression or drift — crypto's
signature regime. **Struggles in:** wide, violent chop where prior extremes are
broken and immediately reclaimed (false breakouts) — the ADX + volume
conjuncts are the mitigation, not a guarantee.
**Watch for:** long flat stretches punctuated by few large winners; a quarter
whose profit is one trade is concentrated luck — Phase 7's per-quarter reading
must separate "trend quarters" from "one lucky pair".

## Kill criteria
- Profit factor < 1.2 in-sample after one round of tuning
- Phase 4 stoploss share > 50% (false breakouts dominating = the conjunctions
  are not filtering)
- Does not complement `MultiMATSL` (identical losing quarters AND lower PF) ->
  redundant trend exposure; drop one
- Profit factor < 1.0 at 2x fees

## Changelog
- 2026-09-26: Plan created to `00-TEMPLATE.md`. Family gap filled: breakout
  entry style was absent from the portfolio. Includes the catalog YELLOW pre-
  approval for the Donchian rolling-max/min indicator row.

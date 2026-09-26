# Strategy Portfolio — Index

Twelve futures strategies. All plans follow `00-TEMPLATE.md` and inherit
`.agent/reference/futures-playbook.md`. Candidates beyond the twelve live in
`RESEARCH-BACKLOG.md` (scored, with promotion rules).

**This repo is futures-only.** There is no spot data and no spot config.

---

## The portfolio

| # | Strategy | TF | Short? | Family | Distinguishing idea |
|---|----------|-----|--------|--------|---------------------|
| 1 | `BBRSIMeanReversion` | 15m | yes | band reversion | simplest; the control case (5 params). Known prior failure + pre-approved rejection-entry fallback documented in-plan |
| 2 | `KeltnerATRReversion` | 15m | yes | band reversion | ATR channel + **recovery cross** entry |
| 3 | `VWAPBandReversion` | 15m | yes | band reversion | **volume-weighted** anchor, z-scored |
| 4 | `EWODipHunter` | 15m | **no** | dip buying | two entry modes: pullback + capitulation |
| 5 | `MultiMATSL` | 15m | yes | trend | trailing stop as the exit thesis |
| 6 | `SuperTrendBBCombo` | 15m | yes | trend + band | direction filter + timing trigger |
| 7 | `ObeliskRSIRegime` | 15m | yes | regime | two parameter sets + time-ramped stop |
| 8 | `FundingSkewCarry` | 1h | yes | **futures-native** | funding extremes; carry is *revenue* |
| 9 | `LiquidationWickFade` | 5m | yes | **futures-native** | fade forced liquidation flow |
| 10 | `DonchianATRBreakout` | 15m | yes | **breakout** | enter on strength (prior-N extreme), exit on short channel |
| 11 | `BBSqueezeBreakout` | 15m | yes | **vol compression -> expansion** | the band family's width filter, inverted |
| 12 | `RelativeStrengthBTC` | 15m | yes | **cross-pair lead-lag** | alt/BTC ratio rotation gated by BTC regime; BTC is data-only |

Suggested order of work: **1 first** (control), then 10 and 5/6 (trend family
decision), then the futures-native pair, then the family challengers (2, 3, 11)
which must each beat #1 or a family incumbent to justify their complexity, then
12 last (it needs the cross-pair mechanics proven cheaply at Phase 0-2).

---

## 2026-09-26 blueprint overhaul — what changed

All twelve plans were restructured to `00-TEMPLATE.md`. Every plan now carries
pre-computed **risk verification** (Kotegawa K2/K4/K7 numbers), an explicit
**protections** block with timeframe-correct candle counts (15m / 5m / 1h
conversions), **hyperopt execution notes** (the `--analyze-per-epoch` decision
stated per plan, not rediscovered per run), a **phase map**, and a
**changelog**.

Corrections applied during the overhaul (each recorded in the plan's
changelog):

| Plan | Correction |
|------|-----------|
| KeltnerATRReversion | `trailing_stop_positive_offset` 0.02 -> 0.03 (was a Kotegawa K4 giveback violation: 50% > 33%) |
| MultiMATSL | `startup_candle_count` 300 -> 900 (1h EMA200 informative needs ~800 15m candles of extended history; 300 silently immatured the regime gate) |
| FundingSkewCarry | `startup_candle_count` 600 -> 1100 (z-score lookback up to 1000); explicit `.notna()` entry guard; data facts refreshed |
| LiquidationWickFade | RSI(14) added to the indicator table (exit logic referenced it undeclared); stale `opt_target_atr` exit text removed |
| EWODipHunter | missing `ma_sell_col` selection defined |
| BBRSIMeanReversion | prior-run failure (knife-catch entry, inverted payoff) documented; rejection-confirmed entry pre-approved as the Phase-3 fallback |
| Keltner / VWAP / SuperTrend / FundingSkew | `--analyze-per-epoch` marked **mandatory** (opt_* inside `populate_indicators`, gotcha #0c); BBRSI / EWO / MultiMATSL / Obelisk / LiqWickFade marked **not needed** (signal-time column selection) |

Also repaired: `configs/strategies/BBRSIMeanReversion.json` was missing despite
being referenced as the active config (recreated; Phase 0 Check 0 covers this).

---

## Why these twelve

Started from 9 spot long-only plans. Two were merged away as duplicates, two
futures-native plans added (see history below), and on 2026-09-26 three more
families were added after an external research pass (`RESEARCH-BACKLOG.md`):

| Added | Family it fills |
|-------|-----------------|
| `DonchianATRBreakout` | **breakout** — every prior plan enters on weakness; none entered on strength |
| `BBSqueezeBreakout` | **volatility compression -> expansion** — a regime transition, not a level |
| `RelativeStrengthBTC` | **cross-pair** — the only plan whose signal reads another pair |

Original derivation (2026-09-24):

| Removed | Merged into | Reason |
|---------|-------------|--------|
| `BollingerDipBuyer` | `BBRSIMeanReversion` | same BB-dip + RSI hypothesis |
| `TrueLamboComposite` | `EWODipHunter` / `MultiMATSL` | same EWO + MA-offset dip logic |

Futures-native plans exist because they cannot be expressed on spot:
`FundingSkewCarry` (funding rates are a perpetual-swap mechanism) and
`LiquidationWickFade` (liquidation engines only exist with leverage).

Result: **seven distinct families** rather than near-copies of one.

---

## Shorts: enabled selectively, not by default

`can_short = True` is a claim that the hypothesis is symmetric. Eleven of
twelve qualify. `EWODipHunter` does not, and that is a deliberate finding:

> The mirror of "buy forced capitulation" is "short voluntary euphoria". Those
> are not symmetric. Downside is forced by liquidations and mechanically
> overshoots; upside is voluntary, can persist far longer, and short squeezes
> have unbounded loss shape.

Do not "fix" plan 4 by enabling shorts. See `futures-playbook.md` §3.

Where shorts are enabled, thresholds are **derived** from the long side
(`100 - x`) rather than separately optimised. This enforces the claimed
symmetry and halves the parameter count. If a strategy needs independent short
parameters, the symmetry claim was false — report that rather than adding
parameters.

---

## What changed from the spot originals

| Item | Spot | Futures | Why |
|------|------|---------|-----|
| Timeframe | 5m | **15m** (3 exceptions) | 0.1% round-trip fee vs ~1% target move; 4x faster hyperopt |
| Stoploss | -0.05 to -0.15 | **widened** | `profit_ratio = price_move x leverage`; a -5% stop at 3x is only 1.67% of price |
| `minimal_roi` | up to 40% | **realistic intraday** | 40% targets are spot moonbag logic |
| Leverage | n/a | **dynamic, NATR-targeted** | risk sizing, capped 2-3x, never hyperopt-optimised |
| Funding | n/a | **modelled and reported** | 8h funding is a real cost on every held position |
| Parameter sweeps | 76-456 combos | **cut to 3-9 params / stepped sweeps** | fewer degrees of freedom to overfit |

Timeframe exceptions: `FundingSkewCarry` at 1h (funding updates every 8h, so
15m would be 32 copies of one signal) and `LiquidationWickFade` at 5m
(cascades resolve in minutes and the target move is large enough to absorb
fees). All others — including the three new plans — stay on 15m.

---

## One config per strategy — always

```bash
freqtrade backtesting --config configs/strategies/<Name>.json --timerange ...
```

Each config declares its own `strategy`, so `--strategy` is not needed. Each
inherits `configs/base.futures.json` via `add_config_files`.

**Never use `config.json` or `user_data/config.json`** for development,
backtesting, hyperopt or evaluation. See root `AGENTS.md` §1.

---

## Status

**Plan 1 `BBRSIMeanReversion` is DEAD** (2026-09-26, Phase 4 after 3
measurements — PF 0.79 best of three, kill criteria met; terminal verdict at
`.agent/reports/BBRSIMeanReversion/DEAD.md`). Its lesson binds the remaining
band-family plans: a +0.2% median reversion win cannot clear a 0.1% round-trip
cost floor at 15m frequency.

None of the other plans are implemented yet. They are plans, not strategies.
Every one must pass Phases 0-7 before it means anything, and the honest prior
is that **most will fail**. A plan that dies at Phase 4 with a clean postmortem
is a successful use of this process.

Track run progress in `.agent/STATE.md`; terminal verdicts and the
family scorecard in `.agent/reports/PORTFOLIO.md`.

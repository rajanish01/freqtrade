# Strategy Portfolio — Index

Nine futures strategies. All plans inherit `.agent/reference/futures-playbook.md`.
Every plan states only its deltas from that shared contract.

**This repo is futures-only.** There is no spot data and no spot config.

---

## The portfolio

| # | Strategy | TF | Short? | Family | Distinguishing idea |
|---|----------|-----|--------|--------|---------------------|
| 1 | `BBRSIMeanReversion` | 15m | yes | band reversion | simplest; the control case (5 params) |
| 2 | `KeltnerATRReversion` | 15m | yes | band reversion | ATR channel + **recovery cross** entry |
| 3 | `VWAPBandReversion` | 15m | yes | band reversion | **volume-weighted** anchor, z-scored |
| 4 | `EWODipHunter` | 15m | **no** | dip buying | two entry modes: pullback + capitulation |
| 5 | `MultiMATSL` | 15m | yes | trend | trailing stop as the exit thesis |
| 6 | `SuperTrendBBCombo` | 15m | yes | trend + band | direction filter + timing trigger |
| 7 | `ObeliskRSIRegime` | 15m | yes | regime | two parameter sets + time-ramped stop |
| 8 | `FundingSkewCarry` | 1h | yes | **futures-native** | funding extremes; carry is *revenue* |
| 9 | `LiquidationWickFade` | 5m | yes | **futures-native** | fade forced liquidation flow |

Suggested order of work: **1 first** (it is the control), then 5 or 6, then the
futures-native pair. Plans 2 and 3 must beat plan 1 to justify their existence.

---

## Why these nine

Started from 9 spot long-only plans. Two were merged away as duplicates:

| Removed | Merged into | Reason |
|---------|-------------|--------|
| `BollingerDipBuyer` | `BBRSIMeanReversion` | same BB-dip + RSI hypothesis |
| `TrueLamboComposite` | `EWODipHunter` / `MultiMATSL` | same EWO + MA-offset dip logic |

Two futures-native plans were added, because neither can be expressed on spot:
`FundingSkewCarry` (funding rates are a perpetual-swap mechanism) and
`LiquidationWickFade` (liquidation engines only exist with leverage).

Result: four distinct families rather than four near-copies of one.

---

## Shorts: enabled selectively, not by default

`can_short = True` is a claim that the hypothesis is symmetric. Eight of nine
qualify. `EWODipHunter` does not, and that is a deliberate finding:

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
| Timeframe | 5m | **15m** (2 exceptions) | 0.1% round-trip fee vs ~1% target move; 4x faster hyperopt |
| Stoploss | -0.05 to -0.15 | **widened** | `profit_ratio = price_move x leverage`; a -5% stop at 3x is only 1.67% of price |
| `minimal_roi` | up to 40% | **realistic intraday** | 40% targets are spot moonbag logic |
| Leverage | n/a | **dynamic, NATR-targeted** | risk sizing, capped 2-3x, never hyperopt-optimised |
| Funding | n/a | **modelled and reported** | 8h funding is a real cost on every held position |
| Parameter sweeps | 76-456 combos | **cut to 17-51** | fewer degrees of freedom to overfit |

Timeframe exceptions: `FundingSkewCarry` at 1h (funding updates every 8h, so
15m would be 32 copies of one signal) and `LiquidationWickFade` at 5m
(cascades resolve in minutes and the target move is large enough to absorb fees).

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

None of these are implemented yet. They are plans, not strategies. Every one
must pass Phases 0-7 before it means anything, and the honest prior is that
**most will fail**. A plan that dies at Phase 4 with a clear postmortem is a
successful use of this process.

Track progress in `.agent/STATE.md`.

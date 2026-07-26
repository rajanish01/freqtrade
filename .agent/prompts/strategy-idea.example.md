# Strategy Idea: VWAPBandReversion  (EXAMPLE — do not edit, copy the template)

This is a worked example of a filled-in `strategy-idea.md`. It is deliberately
a *modest* idea, not an ambitious one.

---

## Hypothesis
On liquid perpetual futures, short bursts of one-sided flow push price away
from the volume-weighted average and are then partly retraced as market makers
rebalance inventory. Entering on a stretched deviation and exiting on the
return to VWAP should capture that retracement.

## Why this should work
The counterparty is a market maker who is temporarily short inventory and
widens quotes to attract flow back. The edge is small and decays as spreads
tighten, so it should show up as many small wins with occasional larger losses
when the deviation is the start of a real trend rather than noise.

## Timeframe
15m

## Pairs
BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT, XRP/USDT:USDT

Chosen before seeing any results: the four most liquid pairs with full history.

## Direction
both

## Indicators

| Indicator | Period | Purpose |
|-----------|--------|---------|
| Rolling VWAP | opt_vwap_period | the mean price is reverting to |
| Rolling stdev of close | opt_vwap_period | scales the band to current volatility |
| ADX | 14 | regime filter — suppress entries in strong trends |
| NATR | 14 | normalised volatility, comparable across pairs |

One indicator per concept: mean, dispersion, trend strength, volatility.

## Entry Logic
- **Long:** close below `VWAP - opt_band_std * stdev`, and `ADX < opt_adx_max`,
  and `volume > 0`
- **Short:** close above `VWAP + opt_band_std * stdev`, and `ADX < opt_adx_max`,
  and `volume > 0`

The ADX filter exists because the hypothesis explicitly does not hold in trends.

## Exit Logic
- **Long:** close crosses back above VWAP
- **Short:** close crosses back below VWAP

## Risk Parameters
- **Stoploss:** -0.05
- **ROI table:** {"0": 0.10, "60": 0.05, "120": 0.01}
- **Trailing stop:** no
- **Max open trades:** 4

## What should be optimizable?

| Parameter | Range | Default |
|-----------|-------|---------|
| opt_vwap_period | 20 - 200 | 50 |
| opt_band_std | 0.5 - 3.0 | 1.5 |
| opt_adx_max | 15 - 40 | 25 |

Three parameters only. Every extra one is another way to overfit.

## FreqAI Intent
No. The deterministic version must earn its keep first.

## How will we know this failed?
- Profit factor below 1.2 on the in-sample window after one round of signal
  tuning -> hypothesis not supported, stop.
- Stoploss accounts for more than half of exits -> the "reversion" is really
  trend continuation, and the idea is backwards.
- Profit factor below 1.0 at 2x fees -> the edge is smaller than execution
  cost and is not tradeable regardless of tuning.

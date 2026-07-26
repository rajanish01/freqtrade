# Futures Playbook — Shared Contract for Every Strategy

Every plan in `user_data/strategies/plan/` inherits this file. Read it once per
strategy, at Phase 1. Individual plans state only their **deltas** from it.

This repo is **futures-only**. There is no spot data and no spot config.

---

## 1. Trading mode

Set in `configs/base.futures.json`, never in a strategy file:

```
trading_mode: futures
margin_mode: isolated
exchange:    binanceusdm
pairs:       BTC ETH SOL BNB XRP ADA DOGE AVAX LINK LTC  (all /USDT:USDT)
fee:         0.0005 (0.05% taker, applied twice)
```

Pair notation is always `BTC/USDT:USDT`. A plan that writes `BTC/USDT` is wrong.

---

## 2. Funding costs are real and they are modelled

Perpetual futures charge funding every 8 hours. This repo's backtests **do**
apply it (funding data was repaired — see `ENVIRONMENT.md` gotcha #13).

Consequences you must design around:
- A position held 24h pays funding 3 times.
- Funding is charged on **notional**, so leverage multiplies it.
- Strategies with long average hold times need a bigger per-trade edge.

Report `funding_fees` alongside profit in Phase 4. If total funding exceeds
20% of gross profit, the strategy is renting money to hold its positions and
the holding period needs to come down.

Reading funding inside a strategy (verified working):
```python
fr = self.dp.get_pair_dataframe(pair, "1h", candle_type="funding_rate")
```
Values are `0.0` except at 00:00 / 08:00 / 16:00 UTC. Forward-fill before use.
Mark price is available the same way with `candle_type="mark"`.

---

## 3. Shorts — only where the hypothesis is symmetric

`can_short = True` is a **hypothesis claim**, not a feature toggle. Crypto is
not symmetric: drops are faster and deeper than rallies, and short squeezes
have unbounded loss shape while long liquidations do not.

| Pattern | Shorts? | Why |
|---------|---------|-----|
| Band / channel mean reversion | **Yes** | the band is symmetric by construction |
| Trend following | **Yes** | trend has no preferred sign |
| Regime-gated oscillator | **Yes** | the regime gate flips cleanly |
| Dip buying / capitulation | **No** | "buy panic" has no valid mirror; nobody panic-buys the same way |
| Funding / basis extremes | **Yes** | the mechanism is inherently two-sided |

If a plan says long-only, that is a deliberate finding, not an omission.
Do not "improve" it by enabling shorts.

Every short strategy must additionally require `volume > 0` and should avoid
entering shorts into a vertical move — that is where squeezes happen.

---

## 4. Dynamic leverage — volatility targeting

Leverage is **risk sizing**, not signal. It is deterministic, rule-based, and
**never hyperopt-optimised and never ML-driven**.

The rule: target a constant risk contribution per trade by scaling leverage
inversely with volatility.

```python
# class attributes — tune by hand, never with hyperopt
target_vol_pct: float = 0.5    # desired NATR(14) in percent
max_leverage_cap: float = 3.0  # hard ceiling, never exceeded

def leverage(self, pair: str, current_time, current_rate: float,
             proposed_leverage: float, max_leverage: float,
             entry_tag: str | None, side: str, **kwargs) -> float:
    df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    if df is None or len(df) == 0:
        return 1.0
    natr = df["ind_natr_14"].iat[-1]
    if not isfinite(natr) or natr <= 0:
        return 1.0
    lev = self.target_vol_pct / natr
    return float(max(1.0, min(lev, self.max_leverage_cap, max_leverage)))
```

Notes:
- `.iat[-1]` is correct **here**. The "no `.iloc[-1]`" rule applies to
  `populate_*` methods only — callbacks are evaluated per-candle by design.
- Requires `ind_natr_14` in `populate_indicators`. Every futures plan includes it.
- Floors at 1.0: never below unleveraged.
- Quiet markets get more size, violent markets get less. That is the point.

### Leverage changes what your stoploss means

Freqtrade computes `profit_ratio = price_change * leverage`. So `stoploss` is
expressed in **account risk**, not price distance:

| stoploss | 1x | 2x | 3x |
|----------|-----|-----|-----|
| -0.05 | 5.00% price move | 2.50% | 1.67% |
| -0.10 | 10.00% price move | 5.00% | 3.33% |
| -0.15 | 15.00% price move | 7.50% | 5.00% |

At 3x a `-0.05` stop is only 1.67% of price away — inside normal 15m noise on
most pairs. **This is why every plan below widens its stoploss versus the
original spot version.** Do not port a spot stoploss unchanged.

Isolated-margin liquidation sits near `-1/leverage` (≈ -33% at 3x), so a
stoploss of -0.15 still triggers well before liquidation. Keep it that way.

---

## 5. Risk parameter conversion from the spot originals

The plans were originally spot, long-only, 5m, with ROI targets like `{"0": 0.4}`
(40%). Those are moonbag targets and are meaningless on leveraged 15m futures.

Rules applied to every converted plan:
- `minimal_roi` targets scaled down to realistic intraday magnitudes
- `stoploss` widened to survive leverage (see table above)
- `minimal_roi = {"0": 100}` ("disabled") is retained only where a trailing
  stop or a structural exit does the work
- `startup_candle_count` unchanged at 200 unless the plan needs more, and
  validated by `recursive-analysis` in Phase 2

---

## 6. Timeframe

Default **15m**. Rationale: at 5m the round-trip fee is 0.1% against a target
move of ~1%, so 10% of gross edge is lost to fees before funding — and 5m means
~580k candles per pair, which makes local hyperopt impractically slow.

5m is used only where the edge is genuinely microstructural
(`LiquidationWickFade`). 1h is used where the signal itself is 8-hourly
(`FundingSkewCarry`).

Changing a plan's timeframe is a YELLOW action.

---

## 7. Mandatory indicators for every futures plan

Regardless of the strategy's own signal set:

| Column | Purpose |
|--------|---------|
| `ind_natr_14` | drives the leverage callback; comparable across pairs |

---

## 8. Quality gates

Use the gates in `.agent/CONVENTIONS.md`. Two futures-specific additions:

| Gate | Threshold | Why |
|------|-----------|-----|
| Funding share of gross profit | < 20% | else the holding period is too long |
| Profit factor at 2x fees | > 1.0 | Phase 7 cost sensitivity, covers slippage |

---

## 9. Config — one per strategy, always

Every strategy has exactly one config: `configs/strategies/<Name>.json`.
It inherits `configs/base.futures.json` via `add_config_files`.

```bash
freqtrade backtesting --config configs/strategies/<Name>.json --timerange ...
```

The config declares `strategy`, so `--strategy` is not needed.

**Never use `config.json` or `user_data/config.json` for any development,
backtest, hyperopt or evaluation.** See root `AGENTS.md` §1.

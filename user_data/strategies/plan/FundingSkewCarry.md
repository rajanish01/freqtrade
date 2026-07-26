# FundingSkewCarry — Futures Strategy Plan
## FUTURES-NATIVE — has no spot equivalent

Read `.agent/reference/futures-playbook.md` first. This file states only the deltas.

The first of two plans built on a mechanism that only exists in perpetual
futures. Nothing in this strategy can be expressed on a spot market.

---

## Hypothesis

The funding rate is a direct, public measurement of positioning imbalance. When
funding is strongly positive, longs are crowded and paying shorts to stay in.
Extreme crowding precedes mean reversion, because the crowded side is
leveraged, and leveraged positions are the ones that get liquidated first.

Take the side that **receives** funding, when the imbalance is extreme and
price momentum is not confirming the crowd.

**Why it should work — two independent income sources:**
1. **Carry.** You are paid funding every 8 hours simply for holding the
   unpopular side. This is the only strategy here with positive expected
   holding cost instead of negative.
2. **Reversion.** Crowded positioning is fragile. When it unwinds, it unwinds
   toward you.

**Who is on the other side:** leveraged directional traders who want exposure
badly enough to pay for it, and who will be force-closed if price moves against
them. Their urgency is your edge.

---

## Why this needs futures

Funding rates are a perpetual-swap mechanism. They exist to tether the
perpetual price to spot. There is no spot analogue — on spot you simply own the
asset and pay nothing. This plan is unportable by construction.

---

## Data access (verified working — see `ENVIRONMENT.md` gotcha #13)

```python
fr = self.dp.get_pair_dataframe(pair, "1h", candle_type="funding_rate")
```

Facts confirmed on this machine:
- Returns hourly rows. Values are `0.0` except at **00:00 / 08:00 / 16:00 UTC**.
- Must be **forward-filled** to get "the funding rate currently in force".
- History runs 2021-01-01 to 2026-07-11 for all 10 pairs.
- Mark price is available the same way with `candle_type="mark"`.

Merge it onto the strategy dataframe by date, then forward-fill:
```python
fr = fr[["date", "open"]].rename(columns={"open": "ind_funding_rate"})
dataframe = dataframe.merge(fr, on="date", how="left")
dataframe["ind_funding_rate"] = dataframe["ind_funding_rate"].replace(0.0, nan).ffill()
```

**Do not** use `self.dp.funding_rate(pair)` — that is a live exchange call and
returns nothing in backtest.

---

## Indicators (1h)

| Indicator | Method | Column |
|-----------|--------|--------|
| Funding rate | merged + ffilled as above | `ind_funding_rate` |
| Funding z-score | `(fr - fr.rolling(opt_fund_lookback).mean()) / fr.rolling(opt_fund_lookback).std()` | `ind_funding_z` |
| Funding APR | `ind_funding_rate * 3 * 365 * 100` | `ind_funding_apr` (readability only) |
| RSI (14) | `ta.RSI(df, 14)` | `ind_rsi_14` |
| EMA (50) | `ta.EMA(df, 50)` | `ind_ema_50` |
| NATR (14) | `ta.NATR(df, 14)` | `ind_natr_14` — required, drives leverage |

Use the **z-score**, not the raw rate. Baseline funding differs per pair and
drifts across years; a fixed threshold like `> 0.0001` would fire constantly on
one pair and never on another.

---

## Timeframe: 1h (not 15m)

Funding updates every 8 hours. On 15m the signal would be identical across 32
consecutive candles — no extra information, 4x the compute, and a strong
temptation to overtrade the same signal. 1h is the coarsest timeframe that
still reacts within a funding period.

---

## Entry Logic

**Short (funding strongly positive — longs crowded, shorts get paid):**
```
ind_funding_z > opt_fund_z                  # default 1.8
close > ind_ema_50                          # crowd is long AND price is extended
ind_rsi_14 > opt_rsi_short                  # default 55, momentum not collapsing
volume > 0
```
tag: `funding_crowded_long`

**Long (funding strongly negative — shorts crowded, longs get paid):**
```
ind_funding_z < -opt_fund_z
close < ind_ema_50
ind_rsi_14 < (100 - opt_rsi_short)
volume > 0
```
tag: `funding_crowded_short`

The price filter matters. Extreme funding *with* price already extended in the
crowd's direction is the fragile setup. Extreme funding *against* price
direction usually means the crowd is already being squeezed — too late.

---

## Exit Logic

**Short:** `ind_funding_z < opt_fund_exit_z` (default 0.3) OR `close < ind_ema_50`
**Long:** `ind_funding_z > -opt_fund_exit_z` OR `close > ind_ema_50`

Exit when the imbalance has normalised — the carry has been collected and the
reversion thesis is spent. Tag both exits separately.

---

## Hyperopt Parameters

| Parameter | Type | Range | Default | Space |
|-----------|------|-------|---------|-------|
| opt_fund_lookback | IntParameter | 100-1000 | 500 | buy |
| opt_fund_z | DecimalParameter | 1.0-3.0 | 1.8 | buy |
| opt_rsi_short | IntParameter | 50-70 | 55 | buy |
| opt_fund_exit_z | DecimalParameter | 0.0-1.0 | 0.3 | sell |

Four parameters.

---

## Risk Parameters (hardcoded — never optimise)
```python
stoploss = -0.10
trailing_stop = False
minimal_roi = {"0": 0.06, "480": 0.03, "1440": 0.015, "2880": 0}
startup_candle_count = 600     # funding z-score lookback dominates
target_vol_pct = 0.5
max_leverage_cap = 2.0
```

Deliberately long ROI horizons (480 min = 8h = one funding period). This is the
one strategy where **holding through funding is the point**, so the usual
"reduce holding period" advice is inverted.

## Strategy Configuration
```python
INTERFACE_VERSION = 3
timeframe = '1h'
can_short = True
```

Config: `configs/strategies/FundingSkewCarry.json`

---

## Reporting difference

For this plan only, funding is **revenue, not cost**. In Phase 4, report
`funding_fees` as a positive contribution and check the sign. If total funding
is negative, the strategy is systematically on the paying side and the core
premise has failed — that is an immediate kill, not a tuning problem.

The `futures-playbook.md` §8 gate "funding < 20% of gross profit" does **not**
apply here. Replace it with: "funding_fees must be positive".

---

## Known risk: trade count

Extreme funding on 10 large-cap pairs is not a frequent event. This plan is the
most likely of the nine to fail the `trades >= 100` gate.

If it does, in order of preference:
1. Lower `opt_fund_z` toward 1.0 (more setups, weaker each)
2. Accept a lower trade count and require a correspondingly higher profit factor
3. Report it as structurally low-frequency and unsuitable as a standalone
   strategy — a legitimate finding, not a failure to fix

Do **not** move to 15m to manufacture more trades. That produces 32 copies of
the same signal, not 32 independent observations.

---

## Expected behaviour

**Works in:** euphoric or capitulatory markets where positioning gets extreme.
**Struggles in:** calm, balanced markets — funding hovers near baseline and the
z-score rarely triggers. Long flat periods are normal and correct.
**Watch for:** correlated entries. Funding extremes tend to hit all 10 pairs at
once, so `max_open_trades: 5` may all fire simultaneously in the same
direction. That is concentrated directional risk wearing a diversified costume.

## Kill criteria
- `funding_fees` total is negative (core premise inverted)
- Profit factor < 1.2 in-sample
- Fewer than 50 trades over the IS window even at `opt_fund_z = 1.0`
- All entries cluster into a handful of market-wide events -> not a strategy,
  just a few macro bets

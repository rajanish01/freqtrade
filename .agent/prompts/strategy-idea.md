# Strategy Idea: <StrategyName>

Fill this in before Phase 0. The agent treats this file as the contract for the
whole run — everything it builds must trace back to something written here.
If a section still says `<...>`, the agent must stop and ask.

A worked example is in `strategy-idea.example.md`.

---

## Hypothesis
<One paragraph. What market behaviour are you exploiting, and why should it
persist? "RSI is low so price goes up" is not a hypothesis. "Forced
deleveraging on high-funding days creates short-term overshoot that mean-reverts
within a few hours" is.>

## Why this should work
<What is the mechanism? Who is on the other side of the trade, and why are they
willing to lose? If there is no answer, expect the backtest to disagree with you.>

## Timeframe
<e.g. 15m — must exist on disk; see .agent/ENVIRONMENT.md>

## Pairs
<Use futures notation with the :USDT suffix, e.g. BTC/USDT:USDT.
Decide the whitelist NOW and do not change it to improve results later.>

## Direction
<long only | short only | both — "both" requires can_short = True>

## Indicators
<List each with its role. Only one indicator per concept.
Check against .agent/reference/indicator-catalog.md.

| Indicator | Period | Purpose |
|-----------|--------|---------|
| <e.g. RSI> | <14> | <entry trigger> |
>

## Entry Logic
- **Long:** <plain-English conditions>
- **Short:** <or "n/a">

## Exit Logic
- **Long:** <plain-English conditions>
- **Short:** <or "n/a">

## Risk Parameters
<Deterministic and fixed. Hyperopt will not touch these.>
- **Stoploss:** <e.g. -0.05>
- **ROI table:** <e.g. {"0": 0.10, "60": 0.05, "120": 0.01}>
- **Trailing stop:** <yes/no, and settings>
- **Max open trades:** <e.g. 3>

## What should be optimizable?
<Each becomes an opt_* parameter with a range. Keep this list short —
every extra parameter is another degree of freedom to overfit with.

| Parameter | Range | Default |
|-----------|-------|---------|
| <opt_x> | <1.0 - 3.0> | <1.5> |
>

## FreqAI Intent
<No | Yes. If yes: what is the prediction target, and what will the model gate?
Remember FreqAI can only filter existing signals, never create them.>

## How will we know this failed?
<State the kill criteria up front, before seeing any results. This is the single
best defence against rationalising a bad backtest.
e.g. "If profit factor is below 1.2 on the in-sample window after one round of
signal tuning, the hypothesis is wrong and we stop.">

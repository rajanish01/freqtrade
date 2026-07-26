# FreqAI Feature Engineering

Propose features and justify them. Do NOT write code in this step.

## Given
- The strategy's existing `ind_*` indicators
- The prediction target from the strategy idea
- The base timeframe and `label_period_candles`

## Naming — FreqAI's rules, not ours
- `%-` prefix = feature (e.g. `%-rsi-period`)
- `&-` prefix = target/label (e.g. `&-s_close`)
- Features defined in `feature_engineering_expand_all` are automatically
  expanded across every `indicator_periods_candles` and `include_timeframes`
  entry, then shifted by `include_shifted_candles`.

That expansion multiplies fast. With 5 base features, 2 periods, 2 timeframes
and 2 shifts you already have 60+ columns. Count before you propose.

## Categories worth considering
1. **Normalised momentum** — RSI, ROC, MFI (bounded, model-friendly)
2. **Normalised volatility** — NATR, BB width / price, ATR percentile rank
3. **Relative position** — `close / bb_mid - 1`, distance to VWAP in ATR units
4. **Rate of change of an indicator** — `ind_rsi.diff(3)`
5. **Volume anomaly** — `volume / volume.rolling(50).mean()`
6. **Higher-timeframe context** — via `include_timeframes`, not manual merges
7. **Cross-pair context** — via `include_corr_pairlist` (BTC/ETH as market beta)
8. **Calendar** — hour of day, day of week (in `feature_engineering_standard`)

## Quality rules
- **Past data only.** `.shift(-N)` is legal only in `set_freqai_targets`.
- **Bounded or normalised.** Raw price and raw volume are poor features —
  their distribution shifts over the years and the model cannot generalise.
  Use ratios, percentage changes or percentile ranks.
- **Stationary.** A feature that trends upward over 4 years teaches the model
  the date, not the market.
- **Justified.** One sentence per feature explaining the mechanism. If you
  cannot write it, drop the feature.
- **Max 12 base features** in the first pass, before expansion.
- **No duplicates of the deterministic signal.** If the feature is just the
  entry condition restated, the model learns nothing new.

## Target design
The target must be reachable within the trade's expected holding period.
If `minimal_roi` exits around 60 candles, predicting a 5-candle return is
predicting something the strategy will never act on. State the alignment
explicitly.

## Output Format

Numbered list. For each:
```
<N>. %-<name>
    Calculation:   <pseudo-formula>
    Bounded:       yes/no (<range>)
    Justification: <one sentence — the mechanism>
```

Then:
```
Base features: <N>
After expansion: <N> x <periods> x <timeframes> x <shifts> = <total> columns
Target: &-<name> — <description>, horizon <N> candles
Horizon vs holding period: ALIGNED / MISALIGNED (<explain>)
```

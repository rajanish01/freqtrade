# Anti-Patterns — Known Mistakes

Read before Phase 4, and any time a backtest looks unusually good.

Rule of thumb: a strategy showing a profit factor above ~3 on years of data is
almost always a bug, not an edge. Look here first.

---

## 0. The pandas 3 void-dtype crash (this repo, right now)
**What:** `dataframe.loc[(), ['enter_long','enter_tag']] = (1,'enter_long')`
creates a `|V0` void column when the mask matches nothing.
**Symptom:** `AssertionError: Something has gone wrong, please report a bug at
pandas` from deep inside `backtesting.py`. It looks like a library bug. It is not.
**Fix:** initialise first — `dataframe.loc[:, 'enter_long'] = 0` — then assign
conditionally into the existing column.

## 1. Lookahead bias
**What:** using data the strategy could not have had at decision time.
**Sneaks in via:**
- `.shift(-N)` in `populate_indicators` (legal only in `set_freqai_targets`)
- centred rolling windows (`center=True`)
- resampling that leaks the close of an unfinished higher-timeframe candle
- computing forward returns outside FreqAI targets
**Detect:** `freqtrade lookahead-analysis` — this is a hard gate in Phase 4.
**Fix:** every indicator uses current and past candles only.

## 2. Insufficient warm-up (recursive bias)
**What:** an indicator's value at candle N depends on how much history was
loaded, so backtest and live disagree.
**Detect:** `freqtrade recursive-analysis`.
**Fix:** raise `startup_candle_count` until the analysis is clean. Long-memory
indicators (EMA, ADX, SAR) need far more warm-up than their nominal period.

## 3. Overfitting to a market regime
**What:** great in the 2023 bull run, dead in 2024 chop.
**Detect:** Phase 7 walk-forward — more than 2 consecutive losing quarters.
**Fix:** add a regime filter (ADX for trend strength, ATR percentile for
volatility), or cut parameter count. Do not "fix" it by re-optimising.

## 4. Curve-fitting via hyperopt
**What:** hundreds of epochs on one window produces perfect IS, dead OOS.
**Detect:** Phase 5 overfitting ratios.
**Tell:** the winning parameter sits at the edge of its declared range, or the
top-10 epochs have wildly different parameters for similar profit.
**Fix:** fewer optimised parameters, fewer epochs, wider validation.

## 5. Stop loss too wide
**What:** each loss is 5–10x the average win.
**Symptom:** high win rate, flat or negative return.
**Detect:** Phase 4 exit-reason breakdown — stoploss share of exits.
**Fix:** tighten the stop or widen targets — but this is a YELLOW change.

## 6. Ignoring trading costs
**What:** profitable before fees, unprofitable after.
**Detect:** Phase 7 cost sensitivity (2x fees).
**Note:** this repo is futures — funding rates apply on top of fees, and they
compound on positions held for days.
**Fix:** if the edge dies at 2x fees, it needs fewer, larger trades.

## 7. Indicator redundancy
**What:** RSI + Stochastic RSI + CCI all measure momentum. Hyperopt then fits
noise in their disagreements.
**Fix:** one indicator per concept. Spread across trend / momentum /
volatility / volume.

## 8. Magic numbers
**What:** `if rsi < 32.7` — a value that came from one narrow window.
**Fix:** every threshold is an `opt_*` parameter with a sane range.

## 9. Pair cherry-picking
**What:** choosing the whitelist after seeing which pairs performed well.
**Detect:** Phase 7 per-pair — one pair carrying > 50% of profit.
**Fix:** fix the whitelist in Phase 0 and do not change it to improve results.
Changing the whitelist mid-run is a YELLOW action for exactly this reason.

## 10. Reading the OOS window early
**What:** peeking at out-of-sample results, then adjusting the strategy.
**Why it matters:** once you have tuned against it, it is in-sample. There is
no way to un-see it, and the run's validation is gone.
**Fix:** OOS is touched once, in Phase 5 Step 4, after parameters are frozen.

## 11. Survivorship bias
**What:** backtesting only on pairs that still exist and are liquid today.
**Fix:** acknowledge it. With a fixed 10-pair major whitelist this bias is
present and cannot be removed here — state it in the Phase 8 dossier rather
than pretending it is absent.

## 12. Silent config drift
**What:** a parameter changed for one experiment and never restored, so later
results are not comparable.
**Fix:** record every temporary change in `.agent/JOURNAL.md` and restore it in
the same turn. Phase 7 explicitly requires restoration.

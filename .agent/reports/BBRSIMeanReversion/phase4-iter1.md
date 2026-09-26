# POSTMORTEM — BBRSIMeanReversion, Phase 4 iteration 1

Date: 2026-09-26
Command: `freqtrade backtesting --config configs/strategies/BBRSIMeanReversion.json --timerange 20220101-20250630 --breakdown month --export signals --cache none --enable-protections --backtest-directory results/backtests --notes "phase4 IS baseline"` + lookahead-analysis + recursive-analysis + backtesting-analysis + 1m-detail pass (reduced window)

---

## FAILED GATES

| Gate | Threshold | Actual | Verdict |
|------|-----------|--------|---------|
| Profit factor | > 1.2 | **0.61** | FAIL |
| Max drawdown | < 25% | **81.33%** | FAIL |
| Sharpe (daily) | > 0.5 | **-2.48** | FAIL |
| Profitable pairs | >= 60% | **0/10** (best: LTC -3.87%) | FAIL |
| Payoff (K4) | avg_loss < 3 x avg_win | **avg_loss -1.558% vs avg_win 0.405% = 3.85x** | FAIL |
| Stoploss exits | < 50% | 7.0% by count (318/4567) — but **76% of gross loss** (1602 of 2104 USDT) | PASS by count, FAIL in intent |
| Trades | >= 100 | 4567 | PASS |
| Funding | < 20% of gross | 7.58 USDT total (~0.6% of gross wins), avg lev 1.197x | PASS |

## FAILURE MODE(S)

**Asymmetric risk (primary).** 70.6% win rate (3223/1344) with PF 0.61 and
-81.02% total. The signature is identical to the prior v1 run (PF 0.615, K4
3.9x, same 318 stop-loss trades) — deterministic reproduction on re-downloaded
data.

**No edge (secondary).** 42 of 43 months negative; the two positive months
(May 2023 +10.4 PF 1.44, Jul 2023 +6.0 PF 1.9) are noise, not a regime cluster.
Not pair concentration either — all 10 pairs lose (long -38.50% / short
-42.52%; the symmetry claim holds, the mechanism fails both ways).

## EVIDENCE

- `roi` exits: 3762 trades, **+1238.5 USDT** (median +0.999% ≈ the ROI table's
  1% row) — the reversion-to-mid mechanism demonstrably banks small wins.
- `stop_loss` exits: 318 trades, **-1601.9 USDT**, avg -12.1% per trade, avg
  loser duration 1d 00:59 — entries ride the knife into a full stoploss grind.
- `rsi_exit`: 416 trades, **-497.0 USDT**, avg -1.25% — the RSI-recovery exit
  fires on trades that are already underwater; it captures nothing.
- `trailing_stop_loss`: 66 trades, +55.0 USDT (small, positive).
- 1m-detail pass (reduced: SOL/ETH/DOGE, 6 months): 298 trades, -20.44%,
  DD 20.71%, Sharpe -3.47 — directionally identical to main-TF. Not a
  flattering-main-TF artifact.

## ROOT CAUSE

The v1 knife-catch entry (`close < ind_bb_lower`, level test) fires on the
knife candle itself — it cannot distinguish "exhausted stretch about to revert"
from "start of a trend leg". The 318 stop-loss trades (7% of entries by count)
each average -12.1% over ~25h and cost 76% of gross loss, overwhelming the
+1238 USDT of roi-exit wins from the other 93% of entries. The RSI exit is
structurally late for these entries (avg -1.25% at exit), so nothing cuts the
grind earlier. This is the exact failure mode recorded in the plan's prior-run
section and in `.agent/JOURNAL.md` (2026-09-24 entry).

## HYPOTHESIS STATUS

**UNDETERMINED — the pre-approved fix decides it.** The reversion mechanism
itself exists (roi cohort +1238 USDT), so the parameters are not the whole
story; but the level-test entry cannot separate exhaustion from trend-start.
The plan's standing instruction (pre-approved, and anticipated by the kill
criteria: "K4 ... this is what killed v1 the first time") routes a K4 failure
to the rejection-confirmed entry before the hypothesis is declared dead.
If that fix also fails the PF/K4 gates, the kill criteria are met and the
verdict becomes NOT SUPPORTED (terminal DEAD.md).

## PROPOSED CHANGES (ranked)

1. **Rejection-confirmed entry** | phase 3 | replace the level test with
   `low < ind_bb_lower AND close > ind_bb_lower` (long) and
   `high > ind_bb_upper AND close < ind_bb_upper` (short) — "the band
   rejection happened", not "price is outside the band". Zero new parameters,
   same indicators. Expect: signal count drops (a 70-80% cut still leaves
   >900 trades over 3.5y, above the 100 floor); the knife-catch cohort is
   eliminated at the source, so stoploss trades and avg_loss shrink; K4 should
   move toward passing; PF recovers toward >1.2 if the roi cohort survives.
   Risk: the confirmation adds one candle of lag, so some roi-exit wins shrink
   or vanish; trade count could drop below statistical relevance if the
   filters over-constrain.
2. (only if #1 is insufficient — needs user approval at that point) **Exit at
   band mid instead of RSI** | phase 3 | hypothesis-consistent ("reverts to
   the band mid"); the RSI exit demonstrably captures nothing (avg -1.25%).
   Risk: mid-exit cuts winners that would have run to ROI.
3. Not proposed: hyperopt (forbidden as a fix for a failed Phase 4), risk
   parameter changes (the risk layer is not the problem — funding is 0.6% of
   gross, leverage avg 1.2x).

## RECOMMEND: apply #1 (pre-approved in-plan)

# FINAL VERDICT — BBRSIMeanReversion — 2026-09-26

STATUS: DEAD — hypothesis **not supported**; do not hyperopt or re-run this
strategy again without a new plan.

─────────────────────────────────────────────────
HYPOTHESIS:        Price that closes outside a Bollinger Band with momentum
                   confirming exhaustion reverts to the band mid
                   (short-horizon liquidity provision; the counterparty is a
                   taker paying the spread for immediate fills).
DIED AT:           Phase 4, iteration 2 (three Phase-4 measurements: baseline,
                   rejection-confirmed entry, band-mid exit)
KILL CRITERIA:
- PF < 1.2 in-sample after one round of signal tuning — **MET** (0.79 after
  two rounds; it never crossed 1.0 at any iteration)
- Stoploss > 50% of exits — NOT MET by count (51/3862 = 1.3%; 22% of gross
  loss by value)
- K4: avg_loss < 3 x avg_win fails — NOT MET in final form (2.13x passes;
  it failed at 3.85x and 3.14x in the two earlier iterations)
- PF < 1.0 at 2x fees — not tested (moot: PF 0.79 < 1.0 already at 1x fees)
- Shorts materially worse than longs — NOT MET (symmetric: exp_ratio -0.064
  short vs -0.085 long)
─────────────────────────────────────────────────
WHAT WAS TRIED
- iter 0 (baseline v1 knife-catch entry, plan as written):
  PF 0.61, -81.02%, DD 81.33%, K4 3.85x, 4567 trades, stoploss 318 trades
  = 76% of gross loss, rsi_exit -497 USDT (captures nothing)
- iter 1 (rejection-confirmed entry, pre-approved in-plan):
  PF 0.73, -44.12%, DD 44.53%, K4 3.14x, 2611 trades (-43%), stoploss 137
  = 70% of gross loss, roi exits +1150 (median ~1.0%)
- iter 2 (band-mid exit replacing RSI exit, user-approved override):
  PF 0.79, -43.53%, DD 43.84%, K4 2.13x (passes), 3862 trades (+48% — fast
  exits free slots and re-enter), stoploss 51 = 22% of gross loss
─────────────────────────────────────────────────
FINAL EVIDENCE (last backtest, IS 20220101-20250630, protections on)
- 3862 trades, -43.53%, PF 0.79, DD 43.84%, Sharpe -1.48, CAGR -15.11%,
  win rate 62.7%, avg duration 3:47
- Funding 3.91 USDT total, leverage avg 1.16x; 1/10 pairs profitable
- bb_mid_exit: 3482 trades, -421.5 USDT — median +0.24% but mean -0.203%
  (fee drag plus immediate V-reversal exits at breakeven-minus-fees)
- roi exits: 280 trades, +360.7 USDT; trailing: 47 trades, +100.2 USDT;
  stop_loss: 51 trades, -460.9 USDT
- Bias checks CLEAN on every iteration (lookahead has_bias = No;
  recursive 0.000% at all warm-ups) — the failure is real, not an artifact

FAILURE MODE(S):   **No edge** (primary — PF 0.79 over 3.5y; every fix moved
                   PF toward 1.0 but never across it) + **cost sensitivity**
                   (the surviving wins average +0.2% against a 0.1% round-trip
                   fee; 3862 trades amplify the drag).

ROOT CAUSE CHAIN:  The band-penetration edge exists but is smaller than the
                   cost of harvesting it. Each fix removed one loss cohort
                   (knife-catch, then RSI-exit) and the wins never grew: the
                   reversion-to-mid pays ~+0.2% median, the entry conjunction
                   (RSI<30 & MFI<30 & width>0.01 & vol>0.5x SMA) does not
                   select stretches deep enough to pay more, and the fast-exit
                   structure re-enters into the same shallow edge. After two
                   signal rounds the aggregate is still negative — the edge
                   does not clear the cost floor on 15m futures at 0.05%
                   taker.
─────────────────────────────────────────────────
WHY UNFIXABLE WITHIN THE RULES
- Signal fixes tried: rejection-confirmed entry (iter 1), band-mid exit
  (iter 2) — both improved every metric; neither crossed PF 1.0.
- Hyperopt cannot fix it: tuning 4 thresholds on a PF 0.79 baseline cannot
  create an edge that is not there, and it would spend the IS tuning budget
  on a losing structure.
- Risk changes would only hide the bleed: the risk layer is already
  conservative (funding 0.6% of gross, leverage avg 1.16x) — the problem is
  entry edge vs costs, not the risk layer.
- Whitelist/timeframe changes are YELLOW rewrites of the hypothesis, not
  fixes.
RETRY WOULD REQUIRE
  A new hypothesis with a bigger per-trade target: enter only on extreme
  stretches (deeper than 2 std), aim at moves larger than the fee floor, or
  a higher timeframe where one reversion pays several times the round-trip
  cost. That is a new plan — the user's call, never the agent's.
ARTIFACTS
  Postmortems:  .agent/reports/BBRSIMeanReversion/phase4-iter1.md (+ verdict)
  Journals:     .agent/JOURNAL.md, .agent/reports/BBRSIMeanReversion/journal.md
  Strategy file/config: DELETED after this verdict (user-approved DEAD path)
─────────────────────────────────────────────────
LESSON: A band-penetration edge worth +0.2% median per trade cannot clear a
0.1% round-trip cost floor at 15m frequency — mean reversion on short
timeframes needs a per-trade target several times the cost, and faster exits
that free slots just re-enter into the same shallow edge.

This is a successful outcome of the process: the failure is recorded
precisely, the diagnosis is reproducible, and the lesson transfers to every
other band-family plan in the portfolio (plans 2, 3, 11 — all of which must
now answer this cost-floor question in their own Phase 4).

# Phase 4 — iteration 1 — DonchianATRBreakout

Date: 2026-09-27 · Window: IS 20220101-20250630 · Config: defaults
(entry N=40, exit M=15, ADX>25, vol spike>1.5) · protections ON · `--cache none`

```
PHASE 4 RESULTS — DonchianATRBreakout (iteration 1)
─────────────────────────
BIAS CHECKS
Lookahead analysis:  CLEAN (has_bias=No; 20 signals caught, 0 biased/entry/exit)
Recursive analysis:  CLEAN (ind_adx_14 0.001% at the warm-up edge only,
                     converged to 0.000% by 399; natr/vol_sma 0.000%)
─────────────────────────
IN-SAMPLE 20220101-20250630
Total trades:      3688 (1811 long / 1877 short)
Win rate:          33.5%
Profit factor:     0.91 (0.9068)
Total profit:      -31.02%
Max drawdown:      45.65% (848 days: 2022-02-26 -> 2024-06-23)
Sharpe (daily):    -0.59
Avg duration:      9h16m (winners 14h37m, losers 6h34m)
Funding fees:      -7.47 USDT (2.41% of |gross profit| — net received, shorts)
Avg leverage:      1.182x (max 2.0)
Best pair:         ADA/USDT:USDT +7.18%
Worst pair:        SOL/USDT:USDT -13.17%
Top exit reason:   dc_trail_exit (3682/3688 = 99.8% of exits; stop_loss 6)
─────────────────────────────────
1m-DETAIL PASS (REDUCED: H1 2025, SOL/ETH/BNB — main-TF gates already FAIL)
Profit factor:     1.0621 (main-TF same window: 1.0621)
Max drawdown:      6.59% (main-TF: 6.59%)
Trades:            518 (main-TF: 518)
Divergence:        0.0% — detail flag verified active ("Parameter
                   --timeframe-detail detected"); no trailing stop and no
                   custom stoploss exist, so 1m resolution has nothing to
                   change for this strategy (signals on 15m closes; 15m low =
                   min of 1m lows).
─────────────────────────────────
QUALITY GATES (full-IS main-TF run)
Profit factor > 1.2:        FAIL (0.91)
Max drawdown < 25%:         FAIL (45.65%)
Trades >= 100:              PASS (3688)
Sharpe > 0.5:               FAIL (-0.59)
Profitable pairs >= 60%:    FAIL (3/10 = 30%)
Stoploss share of gross loss < 50%: PASS (2.0% loss-share; count-share 0.16%)
Funding < 20% of gross:     PASS (2.41%)
Payoff: avg_loss < 3x avg_win: PASS (1.33 < 7.33; avg_win 2.44 > avg_loss 1.33)
────────────────────────
VERDICT: FAIL (iterate)
```

## Cost decomposition (computed from the export, fees = 0.05%/side x notional)

| Measure | Value |
|---------|-------|
| Total profit with fees+funding | **-310.20 USDT** |
| Total fees | 339.34 USDT |
| Total funding | -7.47 USDT (net received) |
| Total edge at ZERO costs (price only) | **+36.60 USDT** |
| PF at zero costs | 1.0118 (win rate 35.2%) |
| Fee drag vs raw edge | fees consume ~10x the raw per-trade edge (+0.01%/trade) |

## Monthly breakdown (42 months)

16/42 positive (38%). Best months: 2022-01 +55.5, 2022-02 +70.2 — the only
sustained winning period is the first two months. Then 2022-03 -> 2024-06
persistent bleeding (the 848-day drawdown). 2024-07 onward: small mixed
months. No decay into the present as such — the strategy simply never worked
outside early 2022.

## Entry/exit breakdown

| enter_reason | trades | wl_ratio | avg_win | avg_loss | exp_ratio |
|--------------|--------|----------|---------|----------|-----------|
| dc_breakout_long | 1811 | 34.3% | 2.573 | -1.449 | -0.047 |
| dc_breakout_short | 1877 | 32.7% | 2.312 | -1.270 | -0.079 |

Both sides negative; longs lose less. Median trade: -0.62% — the typical trade
loses small; the big winners (avg 3.1% of stake) carry everything.

## POSTMORTEM — DonchianATRBreakout, Phase 4 iteration 1

```
POSTMORTEM — DonchianATRBreakout, Phase 4 iteration 1
────────────────────────────────
FAILED GATES:      PF 0.91 (<1.2) · DD 45.65% (>25%) · Sharpe -0.59 (<0.5) ·
                   profitable pairs 3/10 (<60%)
FAILURE MODE(S):   No edge at defaults + regime dependence + cost floor
EVIDENCE:          PF 0.91 with fees, 1.0118 at zero costs — the raw price
                   edge is +36.6 USDT over 3.5y (+0.01%/trade) and fees
                   (339.34 USDT) consume it ~10x over. Win rate 33.5% vs the
                   35.7% break-even at the measured payoff 1.81. Profit
                   clustered in 2022-01/02 (+125.7 USDT of a -310 total);
                   848-day drawdown. 16/42 months positive. Both entry sides
                   negative (long exp -0.047, short exp -0.079). Stoploss
                   share 2.0% — the exit channel is NOT the problem; the
                   entry conjuncts admit breakouts that do not continue.
ROOT CAUSE:        `opt_adx_min` default 25 admits breakouts in 25-30 ADX
                   chop (non-trending regime) that immediately revert; at
                   payoff 1.81 the win rate must be >= 35.7% and is 33.5%.
                   Secondary: fee drag (0.12% of stake per round trip at avg
                   1.18x lev) is 10x the raw per-trade edge — fewer, better
                   trades is the only honest lever against it.
HYPOTHESIS STATUS: UNDETERMINED — the plan's kill criterion is "PF < 1.2
                   in-sample AFTER ONE ROUND OF TUNING"; no tuning round has
                   run yet (this is the default-param baseline). The
                   mechanism is partially present (positive payoff structure,
                   functioning exit thesis, near-break-even win rate).
────────────────────────────────
PROPOSED CHANGES (ranked)
1. opt_adx_min default 25 -> 30 | phase 3 (threshold within declared range
   15-35) | expect win rate +2-4pp toward/above the 35.7% break-even, trade
   count -25-40% | risk: fewer trades; may drop early-2022-style winners
2. opt_dc_exit_len default 15 -> 5 | phase 3 (within declared range 5-40) |
   expect less giveback per trade, higher win rate | risk: cuts the
   big-winner tail that carries the strategy (avg win 3.1% of stake vs median
   trade -0.62%) — could LOWER expectancy; violates the "winners run" thesis
3. opt_vol_mult default 1.5 -> 2.0 | phase 3 (within declared range 1.0-3.0) |
   expect higher-quality entries only | risk: trade count down materially
────────────────────────
RECOMMEND: apply #1 (opt_adx_min 25 -> 30, Phase 3)
```

## Notes

- All three proposals are signal-threshold changes within already-declared
  `opt_*` ranges — no risk-parameter changes, no new indicators, no hyperopt
  as a fix (tuning cannot create an edge that is not there).
- The 1m detail pass was REDUCED (H1 2025, 3 most-traded pairs) per the
  phase's scale-to-what-it-can-decide rule; the full 3.5y pass cannot rescue
  a decided verdict. Divergence 0.0% — recorded, not skipped.
- Phase-7 comparison vs MultiMATSL remains deferred (#5 not built).

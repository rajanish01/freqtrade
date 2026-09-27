# BBRSIMeanReversion — Strategy Journal

Append-only. One block per phase completion and per fix iteration. Never edit
or delete past entries.

Plan:    user_data/strategies/plan/BBRSIMeanReversion.md
Config:  configs/strategies/BBRSIMeanReversion.json
Branch:  rj/strategy/BBRSIMeanReversion (forked from rj/develop, 2026-09-26)

---

## 2026-09-26 — SCREENING GATE — PASS
Command:  none (plan + data review against catalog and ENVIRONMENT.md)
Result:   7 indicators, all catalog-listed (BB qtpylib; RSI/MFI/NATR ta-lib;
          vol SMA pandas rolling). 5 params (sane range 3-9). 15m data on disk
          for all 10 whitelist pairs incl. 1m (detail pass safe). Single
          entry-gate plan — no multi-gate starvation risk. Prior-failure
          fallback (rejection-confirmed entry) pre-approved in-plan.
Decision: Plan adoptable on this machine. Proceed to Phase 0.

## 2026-09-26 — Phase 0 DATA-READINESS — PASS
Command:  list-data + list-strategies + canary backtest (SmokeTestStrategy
          config) + funding file count
Result:   10/10 pairs, 15m 20220101-20260923 (165,783 candles/pair), 1m
          present (2.48M candles/pair). Exactly 2 configs loaded (strategy +
          ../base.futures.json; never config.json). Canary: 50 trades, -3.95%,
          exit 0, ZERO funding warnings. Funding files: 10.
          IS 20220101-20250630 / OOS 20250701-20260709 — stated, non-overlapping.
Decision: Phase 0 PASS. All 5 checks explicit. Proceed to Phase 1 (scaffold).

## 2026-09-26 — Phase 1 SCAFFOLD — PASS
Command:  freqtrade list-strategies + backtesting --timerange 20250601-20250701 --cache none
Result:   Strategy OK (4 buy + 1 sell params, hyperoptable). Smoke: 0 trades,
          exit 0, no errors, exactly 2 configs loaded. Scaffold has
          protections @property, leverage callback, empty signals
          (loc[:, col] = 0 form), no indicators, no entry/exit logic.
          Risk-layer re-verification (from plan values):
          - K2: (0.5/5) x 0.12 = 1.2% equity <= 2% PASS
          - K7: 0.12/3 = 4.0% price distance vs liquidation 33.3% at 3x
            (fires at 12% of liquidation distance, <= half) PASS
          - K4: trailing_stop_positive 0.01 <= 0.03/3 = 0.01 (at boundary) PASS
          - ROI precedes trailing: 0.03 < 0.05 PASS
          - Protections (15m): Cooldown 2; StoplossGuard 96/1/96;
            MaxDrawdown 2000/5/10%/288
Decision: Phase 1 PASS. No risk violations. Proceed to Phase 2 (indicators).

## 2026-09-26 — Phase 2 INDICATORS — PASS
Command:  smoke backtest 20250601-20250701 --cache none + recursive-analysis 20250101-20250701
Result:   Smoke: 0 trades (correct pre-signals), exit 0, no errors.
          recursive-analysis: ALL indicators 0.000% drift at every history
          length (199/200/399/499/999/1999), including the strategy's 200.
          Indicators: BB(20,2) qtpylib -> ind_bb_lower/mid/upper; BB width and
          BB pct derived; RSI(14) ta -> ind_rsi_14; MFI(14) ta -> ind_mfi_14;
          Volume SMA(20) rolling -> ind_vol_sma_20; NATR(14) ta -> ind_natr_14.
          startup_candle_count 200 (max lookback 20 -> floor 70; plan value
          200 exceeds floor and validates clean).
Decision: Phase 2 PASS. All indicators catalog-approved, no redundancy
          (NATR is the leverage driver per futures-playbook §7). Entry/exit
          untouched. Proceed to Phase 3 (signals).

## 2026-09-26 — Phase 3 SIGNALS — PASS (iter 1: import bug fixed)
Command:  smoke backtest 20250601-20250701 --cache none (x2)
Result:   First run: 164 trades but leverage callback raised
          NameError('isfinite') per entry — the Phase 2 import edit had
          dropped `from math import isfinite`; freqtrade fell back to 1x.
          Fixed, re-run: 170 trades, -6.76%, 70.0% win, avg duration 15:23,
          DD 9.20%. 0 leverage errors. Tag assignments verified safe on
          pandas 3.0.3 (conditional scalar-assign on new cols with empty
          masks does NOT produce void dtype — only the tuple-assign form
          does; gotcha #1 annotated).
Decision: Trade count in sane band (1-200) though above the plan's rough
          5-40 expectation — the RSI+MFI+width+volume conjunction fires more
          often than the plan author guessed. Not a gate failure; Phase 4
          decides. Phase 3 PASS, proceed to Phase 4.

## 2026-09-26 — Phase 4 BACKTEST — FAIL (iter 1)
Command:  IS 20220101-20250630 --enable-protections --cache none --breakdown
          month + lookahead/recursive + backtesting-analysis + 1m detail
          (reduced: SOL/ETH/DOGE, 6 months)
Result:   PF 0.61, -81.02%, DD 81.33%, Sharpe -2.48, 4567 trades, 0/10 pairs
          profitable. Bias checks CLEAN. 70.6% win rate, K4 3.85x FAIL.
          Stoploss: 318 trades, avg -12.1%, 76% of gross loss (-1602 USDT).
          roi exits: 3762 trades, +1238.5 USDT (median +0.999%). rsi_exit:
          416 trades, -497 USDT (avg -1.25% — captures nothing). Long -38.50%
          / short -42.52%. Funding 7.58 USDT (~0.6% of gross wins), lev avg
          1.197x. 42/43 months negative. 1m detail confirms (-20.44%).
          Reproduces the prior v1 run digit-for-digit (same 318 stop-loss
          count, K4 3.9x). Full analysis: phase4-iter1.md.
Decision: Postmortem: root cause = knife-catch entry fires on the falling
          knife; 7% of entries cost 76% of gross loss. Hypothesis UNDETERMINED
          — the pre-approved rejection-confirmed entry decides it. Re-enter
          Phase 3 with the rejection-confirmed entry (pre-approved in-plan).
          If it fails the gates again, kill criteria met -> DEAD.

## 2026-09-26 — Phase 4 BACKTEST (iter 1 of fix: rejection-confirmed) — FAIL
Command:  bias checks + IS 20220101-20250630 --enable-protections + analysis
Result:   PF 0.73, -44.12%, DD 44.53%, Sharpe -1.48, 2611 trades (-43%),
          K4 3.14x (improved from 3.85x, still > 3x). Stoploss 137 trades =
          70% of gross loss. roi exits +1150. 0/10 pairs. 0/5 gates met in
          full. Bias CLEAN.
Decision: The pre-approved fix moved every metric toward the gates but
          crossed none. User approved ONE override attempt (ranked #2):
          band-mid exit replacing the RSI exit (rsi_exit cohort -486 USDT,
          captures nothing). Final attempt.

## 2026-09-26 — Phase 4 BACKTEST (iter 2: band-mid exit) — FAIL -> DEAD
Command:  bias checks + IS 20220101-20250630 --enable-protections + analysis
Result:   PF 0.79, -43.53%, DD 43.84%, Sharpe -1.48, 3862 trades (+48% —
          fast exits re-enter), K4 2.13x (PASSES), stoploss 51 trades = 22%
          of gross loss. bb_mid_exit 3482 trades -421.5 USDT (median +0.24%,
          mean -0.203% — fee drag + immediate V-reversal exits). roi +360.7.
          1/10 pairs. Funding 3.91 USDT, lev avg 1.16x. Bias CLEAN.
Decision: Gates still fail (PF 0.79 < 1.2, DD 43.84% > 25%, Sharpe -1.48,
          1/10 pairs). User's pre-registered decision: this was the final
          attempt -> DEAD. Terminal verdict at DEAD.md. LESSON: a +0.2%
          median reversion win cannot clear a 0.1% round-trip cost floor at
          15m; faster exits that free slots re-enter into the same shallow
          edge.





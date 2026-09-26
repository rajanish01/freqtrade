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


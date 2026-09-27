# JOURNAL.md — Append-Only Run Log

Append one block per phase completion or fix iteration. Never edit or delete
past entries. Newest at the bottom.

Purpose: this is the agent's long-term memory. When the context window drops
older turns, this file is what stops the agent repeating a failed experiment.

Entry format:

```
## <ISO date> — Phase <N> <PHASE NAME> — <PASS|FAIL|NOTE>
Strategy: <name>
Command:  <the command actually run, or "none">
Result:   <the numbers, or the error>
Decision: <what happens next, and why>
```

Rules:
- Record the numbers, not adjectives. "PF 0.87" not "disappointing".
- Record failed experiments too — especially those. A failed idea recorded here
  is worth more than a passing one.
- If a change was reverted, say so and say why.

---

## 2026-07-26 — Phase -1 SETUP — NOTE
Strategy: n/a
Command:  `freqtrade backtesting --config configs/strategies/$STRAT.json --timerange 20250601-20250701`
Result:   42 trades, -9.11% total profit. Ran clean.
Decision: Infra canary passes. `configs/*.json` were rewritten (exchange
          `binance` -> `binanceusdm`, futures/isolated mode added, real
          `pair_whitelist` added, deprecated `protections` removed, `api_server`
          block restored, order-book pricing forced, FreqAI block rebuilt to
          schema). Baseline for Phase 0 established.

## 2026-07-26 — Phase -1 SETUP — NOTE
Strategy: n/a
Command:  `freqtrade recursive-analysis --config configs/strategies/$STRAT.json --timerange 20250101-20250301`
Result:   `rsi` drifts -4.244% at the strategy's `startup_candle_count = 30`,
          and 0.000% at 199. Confirms the tool works and that 30 is too low.
Decision: Documented as the Phase 2 warm-up validation method.

## 2026-07-26 — Phase -1 SETUP — NOTE
Strategy: n/a
Command:  `freqtrade lookahead-analysis --config configs/strategies/$STRAT.json --timerange 20240101-20250630 --pairs BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT`
Result:   `has_bias = No`, 20 signals analysed. Clean.
Decision: Two blockers found and fixed before this worked, both now in
          ENVIRONMENT.md as gotchas #9-#11:
          (a) the command reads `config["pairs"]`, not the whitelist, so
              `--pairs` is mandatory or it silently analyses nothing;
          (b) `available_capital: 1000` capped the wallet below the
              `stake_amount: 10000` the tool forces internally, yielding 0
              trades — `available_capital` removed from all configs;
          (c) `price_side` had to move from `same` to `other` because the tool
              forces market orders.
          Both bias checks are now hard gates in Phase 4.

## 2026-07-26 — Phase -1 SETUP — NOTE
Strategy: VWAPBandReversion
Command:  `freqtrade backtesting --config configs/strategies/$STRAT.json --strategy VWAPBandReversion --timerange 20250601-20250701`
Result:   Crash. `AssertionError` from pandas inside `backtesting.py:563`.
          Root cause: `dataframe.loc[(), ['enter_long','enter_tag']] = (1,...)`
          creates a `|V0` void-dtype column under pandas 3.0.3.
Decision: NOT a library bug and NOT a config problem — the infra canary passes
          on the same config. Recorded as gotcha #1 and anti-pattern #0. The
          Phase 1 scaffold spec was rewritten to mandate
          `dataframe.loc[:, "enter_long"] = 0` instead, since the old spec is
          what generated this code in the first place.

## 2026-07-26 — Phase -1 SETUP — NOTE (futures conversion)
Strategy: portfolio-wide
Command:  `freqtrade list-data` / `backtesting` across all 10 strategy configs
Result:   All 9 plans in user_data/strategies/plan/ were SPOT, long-only, 5m.
          None were futures. Converted per user direction:
          15m default (5m/1h exceptions), selective shorts (8 of 9),
          NATR-targeted dynamic leverage capped 2-3x.
Decision: Merged 2 duplicate plans (BollingerDipBuyer -> BBRSIMeanReversion,
          TrueLamboComposite -> EWODipHunter/MultiMATSL) and added 2
          futures-native plans (FundingSkewCarry, LiquidationWickFade).
          Nine total. Shared contract extracted to
          .agent/reference/futures-playbook.md so each plan is only a delta.
          EWODipHunter kept long-only deliberately: "buy forced capitulation"
          has no valid mirror in crypto.

## 2026-07-26 — Phase -1 SETUP — NOTE (funding data repair)
Strategy: n/a — affects every futures backtest
Command:  inspection of user_data/data/binanceusdm/futures/*funding_rate*
Result:   Binance funding_fee_timeframe defaults to 1h; disk had only 8h.
          Freqtrade found no funding data and applied ZERO funding fees to
          every futures backtest, overstating any strategy that holds
          positions overnight.
Decision: The two files are structurally identical (both contain only
          8-hourly rows). Copied *-8h-funding_rate.feather ->
          *-1h-funding_rate.feather for all 10 pairs. Nothing deleted.
          Verified after: warnings gone, 39/50 canary trades now carry
          non-zero funding_fees. Recorded as ENVIRONMENT.md gotcha #13 and
          as a Phase 0 exit criterion so it cannot silently regress.

## 2026-07-26 — Phase -1 SETUP — NOTE (config isolation)
Strategy: portfolio-wide
Command:  `freqtrade backtesting --config configs/strategies/<Name>.json`
Result:   Loads exactly 2 configs (strategy + ../base.futures.json). config.json
          and user_data/config.json are never read. Verified for all 10 configs.
Decision: Replaced the three shared configs (backtest/hyperopt/freqai.json) with
          one config per strategy inheriting configs/base.futures.json via
          add_config_files. Each config declares its own `strategy`, so
          --strategy is redundant. Also removed `strategy_path` from configs,
          which had been causing list-strategies to report DUPLICATE NAME.

## 2026-09-24 — FRAMEWORK UPGRADE v2 — NOTE
Strategy: portfolio-wide (driven by freqtrade 2026.6 docs review)
Command:  none (documentation/config changes only)
Result:   Kotegawa risk layer added (tradable_balance_ratio 0.95 -> 0.5,
          per-trade risk <= 2% formula, protections @property template with
          StoplossGuard trade_limit 1 / MaxDrawdown equity 10% / Cooldown,
          position_adjustment_enable=False, payoff gate avg_loss < 3x avg_win).
          Phase 4 gains --timeframe-detail 1m realism pass + --cache none +
          --enable-protections. Phase 5 gains --analyze-per-epoch correctness
          rule (params inside populate_indicators) + --early-stop + loss-fn
          options (YELLOW). Phase 7 walk-forward + 2x-fee runs now with
          protections on; 2x-fee also at 1m detail. Phase 8: reserve ratio
          locked, stoploss_on_exchange off in dry-run. New references:
          kotegawa-risk-layer.md, callbacks-reference.md. New skill:
          .opencode/skills/freqtrade-strategy-productionizer/SKILL.md.
          ENVIRONMENT.md: Python 3.13.11 (was wrongly 3.14.6), 1m-data fact,
          config-architecture + cache + analyze-per-epoch + protections gotchas.
          SmokeTestStrategy.py restored from git (was deleted in worktree;
          RegimeAdaptiveTrend*.py left deleted as found).
Decision: Active strategy = BBRSIMeanReversion (user-approved). Per-strategy
          journal protocol live at .agent/reports/<Name>/journal.md. Proceed
          to Phase 0.

## 2026-09-24 — Phase 0 DATA-READINESS — PASS
Strategy: BBRSIMeanReversion
Command:  download-data (dataset restore, user-authorized) + list-data + list-strategies + canary backtest
Result:   Dataset was FOUND DELETED (user_data/data empty; husk created today).
          Restored via freqtrade 2026.6 download-data, 10 pairs x 8 TFs,
          20220101-20260923, 664MB, funding 1h native (no #13 repair needed).
          Canary: 50 trades, -3.95%, funding on 39/50 trades. Configs: exactly 2 loaded.
Decision: Phase 0 PASS. Data reference written to .agent/reference/data-download.md.
          ENVIRONMENT.md data section re-verified. Extra OOS data (to 2026-09-23)
          noted; split unchanged. Proceed to Phase 1.

## 2026-09-24 — Phase 4 BACKTEST — FAIL (iter 1)
Strategy: BBRSIMeanReversion
Command:  IS backtest 20220101-20250630 --enable-protections (defaults)
Result:   PF 0.615, -81.02%, DD 81.33%, Sharpe -2.48, 4567 trades, 0/10 pairs
          profitable. Bias checks CLEAN. Stoploss bleed = 76% of gross loss
          (318 trades, avg -12.1%, 27.9h grinds); RSI exits cut at -2.6% avg.
          Reversion mechanism itself prints +1238 (ROI exits).
Decision: Postmortem phase4-iter1.md. Proposal: rejection-confirmed entry
          (Phase 3). Await user approval. 1m detail pass still running.

## 2026-09-26 — FRAMEWORK — NOTE (full reset + hardening)
Strategy: BBRSIMeanReversion (reset); portfolio-wide (hardening)
Command:  file edits only — no backtests run
Result:   User-approved full reset of the in-flight run: deleted
          user_data/strategies/BBRSIMeanReversion.py,
          configs/strategies/BBRSIMeanReversion.json,
          .agent/reports/BBRSIMeanReversion/ (journal + postmortem), and the
          two stale backtest zips in results/backtests/. The Phase 4 diagnosis
          above (2026-09-24 entry) survives here — entry-fires-on-knife-candle
          root cause; pre-ranked fix = rejection-confirmed entry.
          Framework hardening on rj/develop: 11 defects fixed (funding-warning
          contradiction in gotcha #12; list-freqaimodels without --config;
          missing --cache none / --enable-protections in phase templates;
          base.futures.json self-serve edits now need approval; journal-split
          documented). New: prompts/final-verdict.md (terminal DEAD verdict),
          reports/PORTFOLIO.md, scripts/framework-check.sh, opencode
          permission deny rules. STATE.md reset to no active strategy.
Decision: Framework is now the focus; portfolio execution (Part 5) starts on
          user go. BBRSIMeanReversion resumes from Phase 1 when picked up.

## 2026-09-26 — FRAMEWORK — NOTE (framework-check verification + parser fixes)
Strategy: portfolio-wide
Command:  bash .agent/scripts/framework-check.sh (twice)
Result:   First run 9 PASS / 1 FAIL — the FAIL was the script's trade-count
          regex, not the env (funding check on the same run found 39/50
          trades; the canary had run fine). freqtrade 2026.6 summary metrics
          use `│` separators and lowercase `Absolute drawdown`. Two defects
          fixed: framework-check.sh regex, and the `Absolute Drawdown` ->
          `Absolute drawdown` grep in COMMANDS.md + phases/07-VALIDATE.md
          walk-forward loops (it had been silently missing the drawdown line).
          Second run: 10 PASS / 0 FAIL. Framework healthy.
Decision: Framework hardening complete and committed to rj/develop
          (67d581e71 + parser-fix commit). Local branches: only rj/develop
          remains; rj/strategy/* deleted per user direction.

## 2026-09-26 — Phase 0 DATA-READINESS — PASS
Strategy: BBRSIMeanReversion
Command:  list-data + list-strategies + canary (SmokeTestStrategy config) + funding count
Result:   10/10 pairs 15m+1m, 20220101-20260923. Exactly 2 configs loaded.
          Canary 50 trades, -3.95%, 0 funding warnings. Funding files 10.
          IS 20220101-20250630 / OOS 20250701-20260709 stated.
Decision: Phase 0 PASS. Branch rj/strategy/BBRSIMeanReversion forked from
          rj/develop. Framework touch-ups applied pre-Phase-0: review
          recommendations R2-R5 + NEW finding F7 — Phase 0 Check 3 canary now
          falls back to SmokeTestStrategy.json on fresh builds (the strategy's
          own config cannot load before Phase 1 scaffolds the .py). Also
          noted: venv activation does not persist across parallel tool calls
          (ENVIRONMENT.md runtime updated). Proceed to Phase 1.

## 2026-09-26 — Phase 1 SCAFFOLD — PASS
Strategy: BBRSIMeanReversion
Command:  list-strategies + smoke backtest 20250601-20250701 --cache none
Result:   OK (4 buy + 1 sell params); smoke 0 trades, exit 0, no errors.
          Risk layer re-verified: K2 1.2% (<=2%), K7 4%/33.3% (PASS),
          K4 0.01<=0.01 (boundary), ROI precedes trailing. Protections 15m.
Decision: Phase 1 PASS. Proceed to Phase 2.

## 2026-09-26 — Phase 2 INDICATORS — PASS
Strategy: BBRSIMeanReversion
Command:  smoke 20250601-20250701 + recursive-analysis 20250101-20250701
Result:   Smoke 0 trades, exit 0. recursive-analysis: 0.000% drift on all
          indicators at every length incl. 200. 9 columns from 7 indicators,
          all catalog-approved.
Decision: Phase 2 PASS. Proceed to Phase 3.

## 2026-09-26 — Phase 3 SIGNALS — PASS (iter 1: import bug fixed)
Strategy: BBRSIMeanReversion
Command:  smoke backtest 20250601-20250701 --cache none (x2)
Result:   First run caught leverage NameError('isfinite') — Phase 2 import
          edit had dropped `from math import isfinite`; freqtrade fell back
          to 1x silently. Fixed, re-run: 170 trades, -6.76%, 70.0% win,
          DD 9.20%, 0 leverage errors.
Decision: Phase 3 PASS (count in sane band 1-200, above plan's rough 5-40).
          Proceed to Phase 4. Gotcha #1 annotated (tuple-assign is the only
          broken form; scalar-assign verified safe on empty masks).

## 2026-09-26 — Phase 4 BACKTEST — FAIL (iter 1)
Strategy: BBRSIMeanReversion
Command:  IS 20220101-20250630 --enable-protections --cache none --breakdown
          month + bias checks + backtesting-analysis + reduced 1m detail
Result:   PF 0.61, -81.02%, DD 81.33%, Sharpe -2.48, 4567 trades, 0/10
          pairs. K4 3.85x FAIL. Stoploss 318 trades avg -12.1% = 76% of
          gross loss; roi exits +1238.5; rsi_exit -497 (captures nothing).
          Funding 7.58 USDT (0.6% of gross wins). Bias CLEAN. Reproduces the
          prior v1 failure digit-for-digit.
Decision: Postmortem phase4-iter1.md: knife-catch entry is the root cause;
          hypothesis UNDETERMINED. Re-enter Phase 3 with the pre-approved
          rejection-confirmed entry. If it fails gates again -> DEAD.

## 2026-09-26 — Phase 4 BACKTEST iters 1-2 — FAIL -> FINAL VERDICT DEAD
Strategy: BBRSIMeanReversion
Command:  bias checks + IS 20220101-20250630 --enable-protections + analysis (x2)
Result:   iter 1 (rejection-confirmed entry): PF 0.73, -44.12%, K4 3.14x.
          iter 2 (band-mid exit, user-approved override): PF 0.79, -43.53%,
          DD 43.84%, K4 2.13x (passes), 3862 trades, 1/10 pairs, Sharpe
          -1.48. Bias CLEAN throughout. Every fix moved metrics toward the
          gates; none crossed PF 1.0.
Decision: Kill criteria met (PF < 1.2 after tuning rounds) + user's
          pre-registered "final attempt" decision -> DEAD. Terminal verdict:
          .agent/reports/BBRSIMeanReversion/DEAD.md. Strategy file + config
          deleted. LESSON: a +0.2% median reversion win cannot clear a 0.1%
          round-trip cost floor at 15m — binds band-family plans 2, 3, 11.

## 2026-09-26 — FRAMEWORK REFINEMENTS (from first strategy run) — NOTE
Strategy: portfolio-wide framework work (no strategy run)
Command:  pip install pyflakes + gh binary install to ~/.local/bin + file edits
Result:   Three refinements applied: (1) Phase-1 lint step — pyflakes 4.0.0
          catches undefined names (the dropped-isfinite class surfaces as a
          silent per-entry NameError + 1x leverage fallback; list-strategies
          and py_compile miss it); (2) Phase-4 1m-detail pass now scales to
          what it can decide — reduced window when main-TF gates already
          FAIL, full window when they PASS (the full 3.5y pass is OOM-prone
          and cannot rescue a decided verdict); (3) stoploss-share gate
          clarified as gross-LOSS share (count 1.3% vs loss 22% read opposite
          ways in the BBRSI run). gh CLI 2.101.0 installed (binary, no sudo).
Decision: Framework tightened from the first run's observations without
          loosening discipline. Next: commit, push branch, PR to rj/develop.

## 2026-09-26 — PR TO rj/develop — DONE
Strategy: portfolio-wide framework work + BBRSIMeanReversion run record
Command:  gh 2.101.0 (binary, ~/.local/bin) auth (user, device flow) + git push -u origin rj/strategy/BBRSIMeanReversion + gh pr create --base rj/develop --body-file
Result:   PR #3: https://github.com/rajanish01/freqtrade/pull/3 —
          "First strategy run: BBRSIMeanReversion DEAD (clean postmortem) +
          framework refinements". Base rj/develop, head rj/strategy/BBRSIMeanReversion,
          8 commits (R2-R5 + canary fallback, phases 0-4 + DEAD verdict,
          3 refinements). First gh pr create failed on shell quoting of the
          long --body; fixed with --body-file.
Decision: Awaiting user review/merge. Next strategy is a separate decision.

## 2026-09-27 — PHASE 0 + 1 PASS — DonchianATRBreakout run started
Strategy: DonchianATRBreakout (plan #10, breakout family, 4/5 confidence)
Branch:   rj/strategy/DonchianATRBreakout forked from rj/develop (user-approved pick)
Result:   Phase 0: framework-check.sh 10/10 PASS (data 10 majors 15m+1m full
          range, canary 50 trades, funding 39/50 non-zero). Phase 1: scaffold
          created, pyflakes clean, list-strategies OK, smoke 0 trades clean.
          Risk layer verified: K2 1.2% equity/trade, K7 8.3x liquidation
          headroom, trailing disabled (exit channel is the exit), lev cap 2.0.
Next:     Phase 2 INDICATORS (Donchian channels with load-bearing shift(1)).

## 2026-09-27 — PHASE 2 PASS — DonchianATRBreakout
Result:  indicators in (Donchian entry/exit channels with load-bearing shift(1),
         ADX, vol SMA/spike, NATR); recursive-analysis 0.000% drift — stable at
         startup 200; smoke clean 0 trades. 1 in-phase fix (talib import alias).
Next:    Phase 3 SIGNALS.

## 2026-09-27 — PHASE 3 PASS — DonchianATRBreakout
Result:  signals in (level-test breakout entries + ADX/volume conjuncts, both
         sides; exit on shorter Donchian channel). Smoke 1-month: 215 trades,
         win 35.8% (plan expected 35-45% for payoffs), avg duration 8h12m.
         Band: marginally above 1-200 guidance, far below 2000 noise FAIL.
Next:    Phase 4 BACKTEST (IS 20220101-20250630, protections on, 1m detail).

## 2026-09-27 — PHASE 4 FAIL (iter 1) — DonchianATRBreakout
Result:  IS baseline (defaults, protections ON): 3688 trades, PF 0.9068,
         -31.02%, DD 45.65%, Sharpe -0.59, win 33.5%. 4 gates FAIL (PF, DD,
         Sharpe, profitable pairs 3/10). Bias checks CLEAN. 1m detail
         (reduced H1 2025, SOL/ETH/BNB): divergence 0.0% vs main-TF (PF
         1.0621 both) — no flattery. Cost decomposition: raw edge +36.6
         USDT at zero costs, fees 339.34 consume it ~10x over (BBRSI
         cost-floor pattern, different entry style). Risk layer NOT the
         problem: stoploss share 2.0% of gross loss, K2/K7 passing, lev avg
         1.18x. Monthly: 16/42 positive, profit clustered 2022-01/02,
         848-day DD. Hypothesis UNDETERMINED (kill criterion = after one
         round of tuning — none yet).
Fix:     proposed opt_adx_min 25 -> 30 (Phase 3, within declared range),
         awaiting user approval. Analysis: phase4-iter1.md.

## 2026-09-28 — FRAMEWORK UPGRADE v3 (MAZE) + RESET — NOTE
Strategy: portfolio-wide (no active strategy run — all prior runs reset)
Command:  none against live strategies (file edits + MazeProbe tooling smoke tests
          only; all MazeProbe artifacts deleted after validation)
Result:   User-directed: "reset all previous plan runs, create a branch from
          rj/develop, start." Branch rj/framework/maze forked from rj/develop
          (5812a4134). Reset: DonchianATRBreakout (Phase-4 FAIL iter 1, PF
          0.9068) and BBRSIMeanReversion (DEAD — verdict stands) reports
          archived to .agent/reports/_archive/pre-maze-2026-09-27/, strategy
          .py as .py.txt, result zips to results/_archive/pre-maze-2026-09-27/.
          Donchian plan file remains live; BBRSI lesson ledger intact.
          Framework v3 built and verified end-to-end:
          - 04M-MAZE.md: tree protocol T0-T5 replacing linear Phase 4-FAIL
            iteration; exhaustion rule; one-shot vault (20260710-20260923).
          - .agent/scripts/maze.py: init/node/run(hyperopt+backtest)/promote/
            mark/status/tree/gates/vault; ledger.csv + tree.md per strategy;
            genome staging via the strategy's params-file slot (staged before,
            restored after every run — verified).
          - .agent/scripts/hyperopt/MazeGateLoss.py: gate-aligned hyperopt
            loss (PF/DD/Sharpe/rate/pair/stoploss-share/funding/K4/K2/K7);
            gate gradient verified live (failing epochs 1001-1036, graduated,
            not cliff).
          - Full lifecycle verified on a throwaway probe: promoted child's
            backtest gate score EXACTLY equals its source hyperopt epoch's
            score (-1001.7425) — inheritance + scoring pipeline self-consistent.
          - Policy change (from the approved MAZE plan): risk NUMBERS
            (stoploss, lev cap, protection values) are a bounded T2 search
            dimension, formula-gated K2/K7, scored per-epoch by MazeGateLoss.
            Risk MECHANISM unchanged, still never ML.
          - Verification finds corrected: config > strategy precedence
            (gotcha #8 was backwards); --enable-protections DOES work with
            hyperopt (old phase-5 assumption wrong); zip stats timestamps are
            ms; max_open_trades display-stat vs setting; nested
            add_config_files chaining; "saved to" line-wrap regex.
Decision: Framework v3 is the focus; next session picks a pilot (Donchian
          ATRBreakout's cost-floor failure mode is the natural first maze
          candidate — T1 = timeframe/confirmation-filter/exit-mechanism moves)
          and starts the tree with maze.py init.

## 2026-09-28 — RESET — BBRSIMeanReversion (user-directed) — NOTE
Strategy: BBRSIMeanReversion (plan 1, band reversion)
Command:  file edits only (no backtests run)
Result:   User-directed reset of the DEAD run, same treatment as DonchianATR
          Breakout's reset. State: strategy .py + config were already deleted
          at the 2026-09-26 DEAD-verdict close (nothing to un-archive); the
          pre-maze record (DEAD.md, journal, phase4-iter1.md) stays archived
          at .agent/reports/_archive/pre-maze-2026-09-27/BBRSIMeanReversion/.
          Ledgers updated: STATE/PORTFOLIO/INDEX row 1 -> RESET (re-enter via
          MAZE, Phase 0/1 rebuild from the plan). DEAD verdict kept, never
          deleted.
Decision: BBRSIMeanReversion re-enters through the MAZE when picked up. The
          T1 candidate set for its cost-floor failure mode: confirmation
          filter before the knife-candle entry + a timeframe step (the two
          responses its lesson called for that the old 3-iteration budget
          never allowed). Both reset runs (plans 1, 10) are now available;
          pilot pick is the user's call.

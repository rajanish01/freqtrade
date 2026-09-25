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

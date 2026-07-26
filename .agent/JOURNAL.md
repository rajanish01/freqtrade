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

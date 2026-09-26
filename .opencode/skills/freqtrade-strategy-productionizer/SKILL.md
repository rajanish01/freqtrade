---
name: freqtrade-strategy-productionizer
description: Use when converting a freqtrade strategy plan from user_data/strategies/plan/ into a production-ready futures strategy — running the gated Phase 0-8 loop (data readiness, scaffold, indicators, signals, backtest, hyperopt, validation, deploy) with Kotegawa risk management, per-strategy journals, and honest kill-criteria reporting. Triggers: "productionize a strategy", "build a strategy from a plan", "iterate backtest/hyperopt", "BBRSIMeanReversion", strategy plan portfolio work.
---

# Freqtrade Strategy Productionizer

Convert one strategy plan from `user_data/strategies/plan/` into a
production-ready, dry-run-validated futures strategy. This skill ORCHESTRATES
the repo's existing framework — it does not replace it.

## Hard boundaries (from AGENTS.md — non-negotiable)

- Write only: `user_data/strategies/`, `configs/strategies/`,
  `configs/base.futures.json`, `.agent/`, `results/`, `.opencode/`
- NEVER read, write, or pass `config.json` or `user_data/config.json`.
  Freqtrade's default config is `config.json` in the cwd — that default is
  deliberately bypassed on every command by passing `--config
  configs/strategies/<Name>.json` (documented freqtrade mechanism, same as
  `add_config_files`). The user's own `config.json` keeps working, untouched.
- Never edit `freqtrade/`, `tests/`, `ft_client/`, `docs/`, `setup.*`,
  `pyproject.toml`. Never set `"dry_run": false`. Never write real API keys.
- All strategy work runs in a dedicated git worktree
  (`git worktree add -b rj/strategy/<Name> ../freqtrade-<name> rj/develop`);
  the main checkout is never blocked — no strategy files, run state edits, or
  long-running freqtrade commands there. See AGENTS.md §3 worktree discipline.
- One strategy at a time, one phase at a time, max 3 fix iterations per phase.

## Session startup — do this before anything else

1. Read `.agent/STATE.md` — where the run is.
2. Read `.agent/ENVIRONMENT.md` — machine facts, IS/OOS split, gotchas.
3. Read `.agent/phases/<current-phase>.md` — the one phase to execute.
4. Read `.agent/reports/<StrategyName>/journal.md` if it exists — what has
   already been tried on this strategy.

Do not pre-read all phases. Context is finite; journals are the memory.

## The loop

```
screen -> Phase 0 DATA -> 1 SCAFFOLD -> 2 INDICATORS -> 3 SIGNALS
       -> 4 BACKTEST -> 5 HYPEROPT (+OOS) -> 6 FREQAI (optional, YELLOW)
       -> 7 VALIDATE -> 8 DEPLOY -> dossier
```

Execute each phase by its own file in `.agent/phases/`. A phase is complete
only when every exit criterion in its file is explicitly marked PASS/FAIL —
no implicit passes. On FAIL: follow `.agent/prompts/iteration-fix.md`, then
`.agent/prompts/backtest-postmortem.md` (Phase 4) or
`.agent/prompts/hyperopt-review.md` (Phase 5). After 3 failed fix iterations,
stop and escalate with a summary of everything tried.

Commands: copy from `.agent/COMMANDS.md` (verified on this machine). Every
command passes `--config configs/strategies/<Name>.json`, `--cache none`, and
from Phase 4 onward `--enable-protections`.

## Screening gate (before Phase 0, once per strategy)

Check the plan is adoptable on this machine:
- every indicator computable from futures OHLCV (+funding where the plan says so)
- timeframe data exists for all whitelist pairs (Phase 0 verifies)
- parameter count sane (plans have 3-9; flag anything higher)
- trade-count risk acknowledged (multi-gate plans may starve)
- for 5m plans: 1m data present (needed for `--timeframe-detail` realism pass)

Record the screening verdict in the strategy journal. A plan that cannot be
adopted is reported as such — that is a legitimate finding.

## Risk layer — Kotegawa "always in control" (mandatory)

`.agent/reference/kotegawa-risk-layer.md` is the contract. At Phase 1 and on
any risk-parameter change, verify and record in the journal:
- `tradable_balance_ratio = 0.5` (base config, half-capital reserve)
- `risk_per_trade = 0.5 / max_open_trades x |stoploss| <= 2%` of equity
- protections `@property` present (StoplossGuard/MaxDrawdown/CooldownPeriod),
  hand-tuned, `--enable-protections` on every backtest from Phase 4
- `position_adjustment_enable = False` (never average down)
- `trailing_stop_positive_offset < minimal_roi["0"]`
- payoff gate at Phase 4: `avg_loss < 3 x avg_win`
- stoploss fires at <= half the liquidation distance at max leverage

Risk parameters change only with explicit user approval (YELLOW). Hyperopt
never touches roi/stoploss/trailing/protection spaces. FreqAI never touches
the risk layer.

## Journals — the memory of this run

- Per-strategy journal: `.agent/reports/<Name>/journal.md` — append one block
  per phase completion AND per fix iteration:
  ```
  ## <ISO date> — Phase <N> <NAME> — <PASS|FAIL|NOTE>
  Command:  <what actually ran, or "none">
  Result:   <the numbers, or the error>
  Decision: <what happens next and why>
  ```
  Append-only. Never edit or delete past entries. Record failures with the
  same fidelity as passes.
- Cross-reference every phase outcome in `.agent/JOURNAL.md` (one line each).
- Temporary config/param changes are logged and restored in the same turn.

## Honesty rules

- Backtest output is the only truth. Report bad numbers plainly; never call a
  failing strategy promising.
- If a command did not run, say it did not run. No placeholder metrics.
- The OOS window (`20250701-20260709`) is never hyperopted or peeked at
  before Phase 5 Step 4.
- Kill criteria in each plan are enforced: a strategy that dies at Phase 4
  with a clean postmortem is a successful use of this process.

## Autonomy

GREEN (act): all read-only freqtrade commands, journal/state writes, advancing
on all-PASS. YELLOW (propose, wait): hypothesis changes, new indicators, risk
parameters, FreqAI, >500 epochs, loss-function change, whitelist/timeframe
change, going back >1 phase. RED (never): `dry_run: false`, live keys, editing
`freqtrade/`, deleting data, git write ops unless explicitly told.

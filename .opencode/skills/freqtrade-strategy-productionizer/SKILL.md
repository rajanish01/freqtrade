---
name: freqtrade-strategy-productionizer
description: Use when converting a freqtrade strategy plan from user_data/strategies/plan/ into a production-ready futures strategy — running the gated Phase 0-8 loop (data readiness, scaffold, indicators, signals, backtest, then the MAZE exhaustive variant search T0-T5) with Kotegawa risk management, per-strategy journals, and honest kill-criteria reporting. Triggers: "productionize a strategy", "build a strategy from a plan", "iterate backtest/hyperopt", "run the maze", "BBRSIMeanReversion", strategy plan portfolio work.
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
- One strategy at a time, one phase at a time. Max 3 fix iterations applies
  to Phases 0-3 only (structural correctness); from Phase 4 onward the MAZE
  (`.agent/phases/04M-MAZE.md`) replaces the fixed iteration budget — its own
  exhaustion rule decides when to stop.

## Session startup — do this before anything else

1. Read `.agent/STATE.md` — where the run is.
2. Read `.agent/ENVIRONMENT.md` — machine facts, IS/OOS split, gotchas.
3. Read `.agent/phases/<current-phase>.md` — the one phase to execute.
4. Read `.agent/reports/<StrategyName>/journal.md` and, if the strategy has
   maze nodes, `.agent/reports/<StrategyName>/maze/ledger.csv` +
   `tree.md` — what has already been tried on this strategy.

Do not pre-read all phases. Context is finite; journals are the memory.

## The loop

```
screen -> Phase 0 DATA -> 1 SCAFFOLD -> 2 INDICATORS -> 3 SIGNALS
        -> 4 BACKTEST (T0 baseline) --FAIL--> 4M MAZE (T0-T5 variant tree)
        -> (T5 survivor) -> 8 DEPLOY -> dossier
```

Phases 5 (hyperopt mechanics) and 7 (walk-forward mechanics) are now
tier-level tools INSIDE the maze — T2 and T4 respectively — not separate
linear gates. Phase 6 FreqAI (optional, YELLOW) sits between T3 and T4.

Execute each phase by its own file in `.agent/phases/`. A phase (or maze
tier) is complete only when every exit criterion in its file is explicitly
marked PASS/FAIL — no implicit passes. On FAIL in Phases 0-3:
`.agent/prompts/iteration-fix.md` (max 3, then escalate). On FAIL in Phase 4
or later: `.agent/prompts/backtest-postmortem.md` (diagnose, emit moves) +
`.agent/phases/04M-MAZE.md` (register the moves as tree nodes) — there is no
fixed iteration count from there on.

Commands: copy from `.agent/COMMANDS.md` (verified on this machine). Every
command passes `--config configs/strategies/<Name>.json`, `--cache none`, and
from Phase 4 onward `--enable-protections`. Once a strategy has maze nodes,
all its runs go through `python .agent/scripts/maze.py run ...` — never a
bare freqtrade call (genome-slot staging, see `maze.py`'s docstring).

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
any risk-mechanism change, verify and record in the journal:
- `tradable_balance_ratio = 0.5` (base config, half-capital reserve)
- `risk_per_trade = 0.5 / max_open_trades x |stoploss| <= 2%` of equity
- protections `@property` present (StoplossGuard/MaxDrawdown/CooldownPeriod),
  `--enable-protections` on every backtest from Phase 4 (also during hyperopt)
- `position_adjustment_enable = False` (never average down)
- `trailing_stop_positive_offset < minimal_roi["0"]`
- payoff gate at Phase 4: `avg_loss < 3 x avg_win`
- stoploss fires at <= half the liquidation distance at max leverage

The risk MECHANISM (sizing structure, reserve, which protection methods
exist) changes only with explicit user approval (YELLOW). From MAZE tier T2,
the risk NUMBERS (stoploss, leverage cap, protection values) are a bounded
search dimension scored every epoch by
`.agent/scripts/hyperopt/MazeGateLoss.py` against the K2/K4/K7 formulas —
see `04M-MAZE.md`. FreqAI never touches the risk layer, ever.

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
- MAZE ledger: `.agent/reports/<Name>/maze/ledger.csv` + `tree.md` (owned by
  `.agent/scripts/maze.py` — never hand-edit) — one row per tree node, pass
  or fail, from Phase 4 onward. The per-node record; the journal carries the
  tier-level narrative only.
- Cross-reference every phase outcome in `.agent/JOURNAL.md` (one line each).
- Temporary config/param changes are logged and restored in the same turn
  (maze nodes make this mostly obsolete — node configs are permanent files,
  the genome slot is staged/restored automatically).

## Honesty rules

- Backtest output is the only truth. Report bad numbers plainly; never call a
  failing strategy promising.
- If a command did not run, say it did not run. No placeholder metrics.
- The OOS window (`20250701-20260709`) is never touched before a maze T5
  finalist; the vault window (`20260710-20260923`) is spent once, ever —
  `maze.py vault` enforces this mechanically (refuses a second call without
  `--force`, which itself is YELLOW).
- The maze ledger's total node count is disclosed in every final verdict
  (`anti-patterns.md` #13) — a search whose breadth is hidden is not
  evidence.
- Kill criteria in each plan are enforced: a strategy that dies at Phase 4
  with a clean postmortem is a successful use of this process.

## Autonomy

GREEN (act): all read-only freqtrade commands, `maze.py` node runs covered by
an approved T1 candidate set / T2 spaces list, pruning failed nodes (record,
don't delete), journal/state writes, advancing on all-PASS. YELLOW (propose,
wait): hypothesis changes, new indicators, risk-mechanism changes, risk
STARTING values at Phase 1, naming/widening a T1 candidate set or T2 spaces
list, FreqAI, >500 epochs, loss-function change, whitelist change, opening a
PRUNED line, `maze.py vault --force`. RED (never): `dry_run: false`, live
keys, editing `freqtrade/`, deleting data, git write ops unless explicitly
told.

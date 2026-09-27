# AGENTS.md — Freqtrade Strategy Development

You are a **strategy development companion**. You build, test and refine one
Freqtrade strategy at a time through a fixed, gated, iterative workflow.

This repo is a **checkout of the Freqtrade library itself**. Read the
boundaries below before touching anything.

---

## 1. FILE BOUNDARIES (hard rule)

| Path | Permission |
|------|-----------|
| `user_data/strategies/` | READ + WRITE |
| `configs/strategies/` | READ + WRITE (one config per strategy) |
| `configs/base.futures.json` | READ + WRITE (shared base — change affects all strategies) |
| `.agent/` | READ + WRITE |
| `results/` | WRITE (artifacts only, gitignored) |
| `config.json`, `user_data/config.json` | **NEVER READ, NEVER WRITE, NEVER PASS TO A COMMAND** |
| `freqtrade/`, `tests/`, `ft_client/`, `docs/`, `setup.*`, `pyproject.toml` | **READ ONLY — NEVER EDIT** |

If a task seems to require editing `freqtrade/`, you are wrong about the task. Stop and ask.

### The config rule

**Every command must pass an explicit `--config configs/strategies/<Name>.json`.**

Freqtrade silently falls back to `user_data/config.json` or `config.json` when
`--config` is omitted. Those are the user's own files. Touching them corrupts
their setup and makes results non-reproducible. A command without `--config` is
a bug, always.

Every strategy gets its own config. Never share one config between two
strategies, and never edit a config to "temporarily" point at a different
strategy.

This repo is **futures-only** (`binanceusdm`, isolated margin). There is no spot
data and no spot config. Pairs are always `BTC/USDT:USDT` notation.

---

## 2. START HERE, EVERY SESSION

Do these three reads before your first action. Nothing else.

1. `.agent/STATE.md` — where the run currently is.
2. `.agent/ENVIRONMENT.md` — verified facts about this machine (data, pairs, gotchas).
3. `.agent/phases/<current-phase>.md` — the one phase you are executing.

Then act. Do **not** pre-read all phases, all prompts, or the `freqtrade/` source.

---

## 3. THE LOOP

| # | Phase | File to open | Produces |
|---|-------|--------------|----------|
| 0 | DATA-READINESS | `.agent/phases/00-DATA-READINESS.md` | verified data + infra canary |
| 1 | SCAFFOLD | `.agent/phases/01-STRATEGY-SCAFFOLD.md` | strategy file, no logic |
| 2 | INDICATORS | `.agent/phases/02-INDICATORS.md` | `populate_indicators` only |
| 3 | SIGNALS | `.agent/phases/03-SIGNALS.md` | entry/exit only |
| 4 | BACKTEST | `.agent/phases/04-BACKTEST.md` | bias checks + T0 baseline measurement |
| 4M | MAZE | `.agent/phases/04M-MAZE.md` | exhaustive, gate-scored variant tree (T0-T5) — entered on a Phase 4 FAIL, supersedes the old linear Phase 5/7 |
| 5 | HYPEROPT | `.agent/phases/05-HYPEROPT.md` | mechanics reference for MAZE tier T2 (tuned params + OOS validation) |
| 6 | FREQAI | `.agent/phases/06-FREQAI.md` | optional ML overlay |
| 7 | VALIDATE | `.agent/phases/07-VALIDATE.md` | mechanics reference for MAZE tier T4 (walk-forward + sensitivity) |
| 8 | DEPLOY | `.agent/phases/08-DEPLOY.md` | dry-run config + dossier |

Rules:
- **One phase at a time.** Never skip. Never merge two phases. (4M is one
  phase with sub-tiers T0-T5, not six phases — do not treat a tier change as
  a phase change for the "name the file before you edit it" rule below.)
- **One file edited per turn.** Name the file before you edit it.
- A phase (or maze tier) is complete only when **every** exit criterion in
  its file is explicitly listed with PASS/FAIL. No implicit passes.
- On FAIL in Phases 0-3: follow `.agent/prompts/iteration-fix.md`. Max 3 fix
  iterations per phase; on the 4th failure, stop and escalate to the user
  with a summary of what was tried. Do not improvise.
- On FAIL in Phase 4 or later: enter/continue the maze
  (`.agent/phases/04M-MAZE.md`) — there is no fixed iteration count from here
  on; the maze's own exhaustion rule decides when to stop trying variants.

---

## 4. AUTONOMY CONTRACT (companion mode)

You run the mechanical loop yourself. You stop for judgement calls.

**GREEN — act without asking:**
- Any read-only command (`backtesting`, `hyperopt`, `lookahead-analysis`,
  `recursive-analysis`, `list-data`, `backtesting-analysis`)
- Writing to `.agent/STATE.md`, `.agent/JOURNAL.md`, `.agent/reports/`, `results/`
- Advancing to the next phase (or maze tier) when all exit criteria PASS
- Applying a fix the user already approved this iteration
- Re-running a failed command after fixing a syntax/typo error
- Running any `maze.py` node whose move type and parameter spaces were
  already covered by an approved T1 candidate set / T2 spaces list
- Pruning a maze node whose gate table failed (recording it, not deleting it)

**YELLOW — propose, then wait for "yes":**
- Changing the strategy hypothesis or adding an indicator not in the strategy idea
- Changing any risk parameter's STARTING value at Phase 1, or the risk
  MECHANISM itself (adding/removing a protection method, changing
  `position_adjustment_enable`, changing `tradable_balance_ratio`) — the
  bounded T2 search of risk NUMBERS within the K2/K7 formula is already
  covered by `04M-MAZE.md` and does not need a separate ask per node
- Enabling FreqAI (Phase 6) or changing the FreqAI model/target
- Hyperopt beyond 500 epochs, or changing `--hyperopt-loss`
- Changing the pair whitelist
- Naming or widening a maze T1 candidate set (timeframe options, filter
  moves, exit-mechanism swaps) or a T2 `--spaces` list beyond
  `buy sell protection risk stoploss`
- Using `maze.py vault --force` a second time on the same strategy
- Going back more than one phase (or reopening a `PRUNED` maze line)

**RED — never, even if asked implicitly:**
- Setting `"dry_run": false`, or running `freqtrade trade` against live keys
- Writing real API keys/secrets into any file
- Editing anything under `freqtrade/` (see §1)
- Deleting anything in `user_data/data/`
- `git commit`, `git push`, or any git write op unless explicitly told

---

## 5. NON-NEGOTIABLES

1. **Backtest output is the only truth.** Your opinion of a strategy is
   irrelevant. Report the numbers, including bad ones. Never describe a
   failing strategy as promising.
2. **Risk layer is deterministic.** Stoploss, position sizing and max
   drawdown are hardcoded. FreqAI never sets them.
3. **Never invent numbers.** If a command did not run, say it did not run.
   Do not fabricate metrics, and do not fill an output template with
   placeholder values.
4. **Out-of-sample is sacred.** Never hyperopt on the OOS window
   (see `.agent/ENVIRONMENT.md` for the split).
5. **No new .py files** beyond the single strategy file. No utils, no helpers.
   Scope: this governs `user_data/strategies/`. Framework tooling under
   `.agent/scripts/` (the maze ledger tool and its hyperopt loss function —
   `.agent/phases/04M-MAZE.md`) is infrastructure, not strategy code, and is
   exempt — it lives under `.agent/`, already READ+WRITE per §1.

---

## 6. CONTEXT DISCIPLINE (local model — small context window)

- Read one phase file at a time; drop it from mind when the phase ends.
- Never `cat` a file under `freqtrade/`. Use `grep` with a narrow pattern.
- Pipe long command output: `... 2>&1 | grep -vE " INFO - " | tail -40`.
- Keep replies under ~40 lines unless printing a required report block.
- Record durable findings in `.agent/JOURNAL.md`, not in the chat.

---

## 7. REFERENCE INDEX (load on demand only)

| File | Read when |
|------|-----------|
| `.agent/COMMANDS.md` | you need an exact command |
| `.agent/CONVENTIONS.md` | writing/editing strategy code |
| `.agent/reference/anti-patterns.md` | a backtest looks too good, or before Phase 4 |
| `.agent/reference/indicator-catalog.md` | choosing an indicator |
| `.agent/prompts/iteration-fix.md` | Phases 0-3 failed |
| `.agent/prompts/backtest-postmortem.md` | a maze node's backtest verdict = FAIL |
| `.agent/prompts/hyperopt-review.md` | a MAZE tier-T2 hyperopt run is in |
| `.agent/prompts/freqai-feature-eng.md` | Phase 6 feature design |
| `.agent/prompts/final-verdict.md` | kill criteria met, or the maze is exhausted — the terminal "why it failed" verdict |
| `.agent/scripts/framework-check.sh` | Phase 0, or any result looks wrong — one-shot infra verification |
| `.agent/phases/04M-MAZE.md` | a Phase 4 T0 baseline FAILs — the tree-search protocol that replaces linear Phase 5/7 from there on |
| `.agent/scripts/maze.py` | running/scoring any maze node (`--help` for the command surface) |
| `.agent/scripts/hyperopt/MazeGateLoss.py` | T2 hyperopt — the gate-aligned loss function, default from `04M-MAZE.md` |

Orchestrator skill: `.opencode/skills/freqtrade-strategy-productionizer/SKILL.md`
wraps this entire workflow (boundaries, loop, screening gate, risk layer,
journals, autonomy) — opencode loads it automatically on strategy-production
tasks. The user's global `~/.config/opencode/opencode.json` (not a repo file —
verified 2026-09-27, there is no `opencode.json`/`.jsonc` in this repo)
enforces the RED list mechanically: config.json and `user_data/config.json`
are deny-read/deny-edit, library dirs are deny-edit, `freqtrade trade` asks
unless it targets a `.dryrun.json`, `rm` of data is denied, git writes ask.
Do not weaken these rules, and do not assume they travel with this repo —
they are this machine's own opencode setup, ask before relying on them
existing elsewhere.

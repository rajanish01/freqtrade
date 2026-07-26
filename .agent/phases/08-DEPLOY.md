# Phase 8: Dry-Run Preparation

## Prerequisite
Phase 7 VERDICT = ROBUST.

## Your Task
Prepare the strategy for paper trading. Live trading is out of scope for the
agent entirely — see the RED list in the root `AGENTS.md`.

---

### Step 1 — Create `configs/strategies/<Name>.dryrun.json`

Copy the strategy's own config `configs/strategies/<Name>.json` to
`configs/strategies/<Name>.dryrun.json` and change only what deployment requires.
It keeps `add_config_files: ["../base.futures.json"]`, so all the environment
gotchas stay handled.

```json
{
  "_comment": "Dry-run config for <Name>. Inherits all futures/exchange settings.",
  "add_config_files": ["../base.futures.json"],
  "strategy": "<Name>",
  "timeframe": "<tf>",
  "dry_run": true,
  "dry_run_wallet": 1000,
  "max_open_trades": 3,
  "stake_amount": "unlimited",
  "cancel_open_orders_on_exit": true,
  "exchange": {
    "pair_whitelist": ["<only pairs that were profitable in Phase 7>"]
  }
}
```

Must be true of the finished file:
- `"dry_run": true` — non-negotiable
- `add_config_files` still points at `../base.futures.json`, so the
  `api_server`, order-book pricing and futures-mode gotchas stay handled.
  Do not inline-copy the base and then diverge from it.
- No `exchange.key` / `exchange.secret` written here.
  **Never** write a real key into a config file. The environment already
  supplies `FREQTRADE__EXCHANGE__KEY` / `__SECRET`.
- Pair whitelist = only the pairs that were profitable in Phase 7
- No `protections` key in any config (gotcha #3) — protections belong in the
  strategy class
- Leverage cap unchanged from what Phase 7 validated. Raising leverage at
  deploy time invalidates every number in the dossier.

### Step 2 — Pre-flight checklist

Verify in the strategy file:
- [ ] No `print()` calls and no debug-level logging
- [ ] No hardcoded dates or timeranges
- [ ] `startup_candle_count` matches what Phase 2 validated
- [ ] No imports outside the freqtrade runtime
- [ ] Single self-contained file, no helper modules
- [ ] Parameter source is unambiguous — either the `.json` next to the
      strategy or the class defaults, and you have stated which

### Step 3 — Start check

```bash
freqtrade trade --config configs/strategies/$STRAT.dryrun.json
```
Let it reach "Bot heartbeat" or the first pair-refresh, then stop it with
Ctrl-C. You are proving it starts, not running it.

If this machine is offline, this step will fail at the exchange handshake.
That is expected — record it as SKIPPED (offline) rather than FAIL.

### Step 4 — Write the strategy dossier

Create `.agent/reports/<strategy>/FINAL.md`:
- Hypothesis in plain English, and whether the backtests supported it
- Final parameters and where they live
- IS and OOS headline numbers, side by side
- Known regime vulnerabilities from Phase 7, stated bluntly
- Expected performance envelope: best / typical / worst quarter observed
- Risk parameters and the reasoning behind each
- Monitoring checklist: what would tell the user to switch it off
  (e.g. "3 consecutive losing weeks", "drawdown > 20%", "trade rate halves")

Be honest in this document. It is the artifact the user will rely on when
deciding whether to risk money. Include the failure modes.

## DO NOT
- Set `"dry_run": false`
- Write real API keys or secrets into any file
- Modify the strategy logic
- Claim live-readiness — the deliverable is a dry-run candidate

## Exit Criteria
- [ ] `configs/strategies/<Name>.dryrun.json` created, `dry_run: true` verified by reading it back
- [ ] No secrets present in any config
- [ ] Pre-flight checklist all pass
- [ ] Start check PASS or SKIPPED (offline)
- [ ] `.agent/reports/<strategy>/FINAL.md` written
- [ ] `.agent/STATE.md` marked complete

## Output Format

```
PHASE 8 COMPLETE — <StrategyName>
─────────────────────────
Config:            configs/strategies/<Name>.dryrun.json
dry_run:           true (verified)
Secrets in config: NONE (verified)
Pairs:             <list>
Max open trades:   <N>
Start check:       PASS / SKIPPED (offline)
Dossier:           .agent/reports/<strategy>/FINAL.md
─────────────────────────
Expected envelope: best <N>% / typical <N>% / worst <N>% per quarter
Known weaknesses:  <list>
─────────────────────────
STATUS: READY FOR DRY RUN
```

## Handoff
Tell the user, in plain terms: run it in dry-run for at least one month and
compare live trade frequency and win rate to the backtest before considering
anything further. Divergence in trade *frequency* is the earliest sign that
backtest assumptions do not hold.

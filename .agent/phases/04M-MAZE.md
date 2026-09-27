# Phase 4M: The Maze — Exhaustive Variant Search

## Prerequisite
Phase 3 exit criteria all PASS. Strategy produces trades. This phase REPLACES
the old linear ending of Phase 4/5/7 ("3 fix iterations, then postmortem,
then DEAD"). Phases 0-3 are unchanged — one strategy file, built up linearly,
scaffold -> indicators -> signals, same as before. The maze starts once that
file produces its first trade and needs to be *measured*.

## Why this phase exists

The old rule was: measure the strategy once (Phase 4), get 3 fix attempts
(one change each, `iteration-fix.md`), and if the gates still fail, write it
off (`final-verdict.md`). That is fast, but it confuses "this exact parameter
set fails" with "this hypothesis is dead" — and both `BBRSIMeanReversion`
(3 iterations, PF crept 0.61 -> 0.73 -> 0.79, never crossed 1.0) and
`DonchianATRBreakout` (FAIL iteration 2/3, PF 0.9068) died without ever
trying an obvious next move (a different timeframe, a confirmation filter, a
volatility-scaled exit) because the budget was spent on parameter nudges.

MAZE explores the SAME hypothesis across a bounded tree of structural
variants — timeframe, entry filters, exit mechanism, and (this is the policy
change from the old framework) risk/leverage knobs — before concluding
"not supported." It is still bounded: every move is logged, every node is
scored the same way, and two hard stops close it out (a frozen vault window
spent once, and an exhaustion rule below) so this cannot become unbounded
fishing.

**Read `.agent/reference/anti-patterns.md` #13 before running a single node.**
Trying many variants and keeping the best one is the textbook setup for
finding noise instead of an edge if you do not correct for it. The
corrections this phase relies on (in order of how much they actually
protect you, most to least):

1. **OOS is still sacred.** No node's hyperopt ever touches
   `20250701-20260709`. A node that only looks good in-sample is not
   promoted, full stop.
2. **The vault window is spent once, on the whole run, not once per node.**
   `20260710-20260923` — see "The vault" below. This is the actual firewall.
3. **Every node is logged, survivors and failures alike**
   (`.agent/reports/<Name>/maze/ledger.csv`). The final dossier states the
   total node count. A result obtained by quietly trying 200 things and
   reporting the one that worked is not reported here — the ledger makes
   that impossible to hide, including from yourself.
4. A soft, heuristic trial-count margin (`maze.py status`) — nice to have,
   not load-bearing. Do not treat it as a rigorous p-value.

## The model

```
Node = a specific config overlay + parameter genome, at a specific tier,
       measured once against the gate table.
Edge = a "move": one categorical change from a parent node (timeframe,
       a new filter, a different exit mechanism, a risk/leverage knob).
Tree = root (T0, the plan's default build) + every node reachable from it.
```

Nodes are NOT separate strategy files. One strategy = one `.py` file, same
rule as before (`CONVENTIONS.md`). A node is a `configs/strategies/_maze/
<Name>/<node_id>.json` overlay (inherits the strategy's own config via
`add_config_files`, overrides only what its move changes) plus, if the move
is a hyperopted parameter set, a genome snapshot
(`.agent/reports/<Name>/maze/params/<node_id>.json`) staged into the
strategy's params-file slot for exactly the duration of that node's run.
**This is why config-level moves (timeframe, stoploss, ROI, trailing,
max_open_trades) never require touching the strategy file at all** —
verified empirically 2026-09-27: Configuration beats Strategy beats default
for these attributes (`freqtrade/resolvers/strategy_resolver.py
:_override_attribute_helper`; `ENVIRONMENT.md` gotcha #8 is corrected to say
this). Only a genuinely new INDICATOR or SIGNAL CONDITION requires editing
the one `.py` file, and that is still Phase 2/3 work, still one file.

All of this bookkeeping is done by `.agent/scripts/maze.py` — read its module
docstring once (`python .agent/scripts/maze.py --help` for the command
surface). Do not hand-roll ledger rows or config overlays; the genome-staging
step in particular is easy to get subtly wrong by hand (one shared mutable
file per strategy, not per node — see the script's docstring).

## Tiers

| Tier | Question it answers | Typical move | Window | Budget |
|------|---------------------|--------------|--------|--------|
| T0 | Does the plan's default build produce a scoreable baseline? | none (root) | IS (or a fast slice of it) | 1 node |
| T1 | Does a structural change fix the failure mode the postmortem named? | timeframe, entry filter, exit mechanism, informative-pair confirmation | IS | small, fixed candidate set (see below) |
| T2 | Within a surviving structural shape, what do buy/sell/protection/risk parameters want to be? | hyperopt over `buy sell protection risk stoploss` spaces | IS | epochs per `.agent/phases/05-HYPEROPT.md` |
| T3 | Does the best T2 epoch hold up at full realism (1m detail, protections, full IS)? | promote + confirm | IS | 1 node per T2 survivor worth promoting |
| T4 | Is it robust (walk-forward, sensitivity, cost, pair concentration)? | none — measurement only, per `.agent/phases/07-VALIDATE.md` methodology | IS (all quarters) | 1 pass per T3 survivor |
| T5 | Does the single remaining finalist hold up out-of-sample, and (once, ever) in the vault? | none — measurement only | OOS, then vault | 1 node |

A node is only worth advancing a tier if it **passes every gate** in
`.agent/CONVENTIONS.md` "Quality gates" (the same table `MazeGateLoss.py`
scores against — see that file's docstring for the exact formulas,
rate-scaled trade-count included). A node that fails gates is `PRUNED`
(recorded, not deleted) unless its failure pattern suggests a specific T1
move, in which case spawn that move as a new sibling and prune the parent
line.

### T1 — the fixed candidate set (name it once, at maze init, not per-node)

T1 is deliberately not open-ended. At `maze.py init` time (or immediately
after the T0 baseline fails), name the T1 candidate set from the plan's own
"kill criteria" / postmortem, and record it as a YELLOW decision (root
`AGENTS.md` §4 still applies — the CANDIDATE SET is the YELLOW moment now,
not each individual timeframe/config change within it). A reasonable default
set, adjust to the actual failure mode:

- **Timeframe**: the plan's native timeframe, plus one step up and down from
  `futures-playbook.md` §6 (e.g. 15m native -> also try 1h; try 5m only if
  the plan's edge is genuinely microstructural, same rule as before).
- **Confirmation filter**: one candle of confirmation before the entry tag
  fires (fixes "knife-catch" failure modes — this is exactly what
  `BBRSIMeanReversion`'s lesson ledger entry called for and never got tried).
- **Exit mechanism swap**: ROI ladder <-> trailing-stop-only <-> structural
  exit (opposite-band / channel-mid / ATR-multiple), gated behind a single
  categorical `opt_exit_mode` parameter if the strategy file already has one,
  else a config-level ROI/trailing override (no `.py` edit needed for the
  ROI-vs-trailing shape, since both are config-resolved attributes).
- **Regime filter**: add or widen an ADX/ATR-percentile gate if the
  postmortem named regime-dependence.

Do not add candidates beyond what the specific failure mode motivates. Four
or five T1 nodes is normal; twenty is not exploring, it is fishing (anti
-pattern #13).

### T2 — hyperopt, with the risk layer now a bounded search dimension

**Policy change from the old framework (read this before objecting that it
contradicts something you remember):** the old rule was "hyperopt never
touches roi/stoploss/trailing/protection; risk is hand-tuned once." That
conflated two different things: the RISK **mechanism** (fixed-fractional
sizing, half-capital reserve, circuit breakers, K4 payoff floor) and the risk
**numbers** (the exact stoploss magnitude, leverage cap, protection
lookback). The mechanism stays exactly as deterministic as before — nothing
here is ML, nothing here removes a protection or the half-capital reserve.
What changes is that the *numbers* are chosen by a classical, deterministic
optimizer within a range **bounded by the same K2/K7 formulas that used to
be a one-time hand check** (`.agent/reference/kotegawa-risk-layer.md`), via
`.agent/scripts/hyperopt/MazeGateLoss.py`, which scores every epoch against
those formulas directly — an epoch that violates K2 or K7 fails exactly like
one that fails profit factor. See that file's docstring for the exact gate
set. This is a wider search, not a looser risk layer.

Spaces now available (all four now genuinely usable — verified 2026-09-27
that `--enable-protections` works during hyperopt, correcting the old
"epochs run without protections" assumption baked into
`.agent/phases/05-HYPEROPT.md`; see that file for the mechanics):

```
--spaces buy sell protection risk stoploss
```

`risk` is a **custom space** — not a freqtrade builtin. Declare it the same
way the probe test in this framework's build history did:
```python
opt_lev_cap = DecimalParameter(1.0, 3.0, default=1.0, decimals=1, space="risk")
```
and read it in `leverage()`. `protection` is builtin but was previously
excluded by house rule; it is now in scope, still only the VALUES
(`stop_duration_candles`, `trade_limit`, `lookback_period_candles`,
`max_allowed_drawdown`) — the set of protection METHODS
(CooldownPeriod/StoplossGuard/MaxDrawdown) is fixed in the class `@property`,
not searched.

**`--hyperopt-loss MazeGateLoss --hyperopt-path .agent/scripts/hyperopt`**
is the default for T2. It will report "No good result found" when no epoch
clears every gate — that is a real, informative maze result (this move's
parameter space does not contain a passing point), not a bug; see the loss
file's docstring before treating it as an error. Reviewing a T2 run still
follows `.agent/prompts/hyperopt-review.md` (range-edge / clustering /
convergence checks are unchanged and still matter — a scattered top-10 is
still a warning sign, gate-aligned loss or not).

Epoch budget: same defaults as before (300, `--early-stop 40` optional,
`>500` still YELLOW) — MazeGateLoss changes what is rewarded, not the search
budget discipline.

### T3 — promote and confirm

`maze.py promote <Name> <T2-node> --epoch N --tier T3` composes the child's
full genome (the epoch's optimized values plus everything the parent already
had fixed — inheritance, not a fresh guess) and registers a new node. Run it
with `--detail-1m` for the full-realism pass (same reasoning as the old
Phase 4 Step 2b: 15m candles hide intra-candle exits).

### T4 — robustness

Apply `.agent/phases/07-VALIDATE.md` Tests 1-4 (walk-forward, sensitivity,
per-pair, cost) to every T3 survivor, not just a single final candidate. The
thresholds in that file are unchanged. A node that fails T4 is `PRUNED` with
the specific failing test recorded — do not average it away.

### T5 — OOS, then the vault

Standard OOS backtest (`20250701-20260709`) on whichever node(s) survive T4.
If more than one node is still alive here, that is a real finding (state it),
but only the single best-scoring survivor proceeds to the vault — the vault
is spent once for the whole run, not once per finalist.

## The vault

`20260710-20260923` is data that exists on disk (`ENVIRONMENT.md`) and that
NOTHING — no node's backtest, hyperopt, or walk-forward — touches before T5.
`maze.py vault <Name> --node <id>` runs it and permanently marks
`.agent/reports/<Name>/maze/vault.json` as opened; a second attempt refuses
without `--force`, and `--force` requires the same explicit user approval as
any other YELLOW action, recorded in the journal with a stated reason. If the
vault result contradicts OOS (gates that passed OOS fail the vault), the
verdict is the vault's — it is the more recent, more independent data — and
that contradiction itself is the headline finding, not a footnote.

## Exhaustion — when the maze is genuinely done, not just tired

Old rule: 3 fix iterations, then stop. New rule — stop and write the verdict
(`.agent/prompts/final-verdict.md`) when **any** of:

- A node reaches T5 and passes the vault -> **not DEAD**, proceed to Phase 8.
- Every T1 candidate has a T2 hyperopt run that reported "no good result"
  (no epoch clears every gate) AND the T1 candidates were the specific,
  named responses to the T0/postmortem failure mode (not a truncated
  attempt) -> DEAD. State which failure modes were addressed and how.
- A kill criterion from the strategy's plan is met at any tier -> DEAD
  immediately, do not keep exploring past a stated kill criterion.
- The user says stop.

"We haven't tried a randomly wider stoploss yet" is not a reason to keep
going forever — the T1 candidate set was named up front for exactly this
reason. If a genuinely new structural idea occurs to you mid-maze that was
not in the original T1 set, that is a new YELLOW proposal (name it, get
approval, add it as a new T1 sibling with its own budget), not silent scope
creep on the existing budget.

## Journals and the ledger

Everything `CONVENTIONS.md` says about journals still applies — this phase
adds one thing: `.agent/reports/<Name>/maze/ledger.csv` and `tree.md` (via
`maze.py status` / `maze.py tree`) ARE the per-node record; the per-strategy
`journal.md` records tier-level narrative (why the T1 set was chosen, why a
node was pruned instead of iterated, the T4/T5 headline numbers) — do not
duplicate every node's numbers into prose, point at the ledger.

## Output format (per tier, append to the journal)

```
MAZE TIER <T1-T5> — <StrategyName>
─────────────────────────
Nodes this tier: <N>   Survivors: <N>   Pruned: <N>
Best node: <id>  score=<N>  gates <passed>/<total>
Move that produced it: <move_type> — <desc>
─────────────────────────
GATE TABLE (best node)
<the 10-row table from `maze.py run` / `maze.py gates`>
─────────────────────────
DECISION: advance <id> to <next tier> / prune all, propose new T1 sibling / DEAD
```

## DO NOT
- Run a node without going through `maze.py run` (genome-slot staging is not
  optional — see the script's docstring on why a bare `freqtrade` invocation
  can silently reuse a different node's parameters)
- Touch the OOS window before T5, or the vault window before the single T5
  finalist
- Grow the T1 candidate set past what the named failure mode motivates
- Report a node's IS numbers as the strategy's expected live performance
- Skip logging a failing node — a pruned branch is evidence, not noise
- Delete a node's config overlay or genome file after pruning (leave it;
  the ledger row is the record, and `configs/strategies/_maze/` /
  `.agent/reports/<Name>/maze/params/` are cheap to keep)

## Exit Criteria
- [ ] T0 baseline measured, gate table recorded
- [ ] T1 candidate set named explicitly and approved (or T0 already passed,
      making T1 unnecessary)
- [ ] Every T1/T2 node's result in the ledger, PASS or FAIL
- [ ] T3 confirmation run (1m detail) on any promoted epoch
- [ ] T4 robustness run on every T3 survivor
- [ ] T5 OOS run on the T4 survivor(s); vault spent at most once, on the
      single best finalist
- [ ] `.agent/STATE.md`, `.agent/JOURNAL.md`, the strategy journal, and
      `.agent/reports/PORTFOLIO.md` updated
- [ ] If DEAD: `.agent/prompts/final-verdict.md` written, stating the total
      node count and the ledger path as evidence

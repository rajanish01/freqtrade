# Framework Review — 2026-09-26

Scope: consistency review of the agent framework (`AGENTS.md`, `.agent/phases/*`,
`.agent/reference/*`, `.agent/prompts/*`, `COMMANDS.md`, `CONVENTIONS.md`,
`STATE.md`, `ENVIRONMENT.md`, configs) against the strategy-plan portfolio in
`user_data/strategies/plan/`. Triggered by the blueprint overhaul of the same
date. Written as an *observations* report: anything that edits `.agent/` files
with uncommitted user changes pending is listed as a recommendation, not done.

---

## Findings — defects found and FIXED (in the plan overhaul)

| # | Finding | Fix |
|---|---------|-----|
| F1 | Plans carried no protections block, but Phase 1 requires one with timeframe-correct candles — guaranteed per-build improvisation of the risk layer | All 12 plans now embed the exact `@property protections` block with converted candle counts (15m: 96/2000/288; 5m: 288/6048/864; 1h: 24/500/72) |
| F2 | Plans carried no precomputed risk math, but Phase 1 requires recording K2/K4/K7 numbers | All 12 plans carry a filled risk-verification table; Keltner's trailing offsets were an actual K4 violation (fixed 0.02 -> 0.03) |
| F3 | `--analyze-per-epoch` rule lived in ENVIRONMENT gotcha #0c and Phase 5 text but was never named in any plan; Keltner/SuperTrend text even falsely claimed per-epoch recompute happens automatically | Mandatory-flag decision now stated explicitly in every plan's "Hyperopt execution notes" |
| F4 | `BBRSIMeanReversion`'s recorded terminal failure (PORTFOLIO lessons ledger) had never flowed back into the plan — a rebuild would have repeated the exact knife-catch mistake | Plan now documents the failure and the pre-approved rejection-confirmed fallback |
| F5 | `configs/strategies/BBRSIMeanReversion.json` did not exist, though STATE.md pointed at it as the active config and COMMANDS.md assumes it for `STRAT=BBRSIMeanReversion` | Recreated (Phase 0 already sanctions config creation) |
| F6 | No plan template existed; `.agent/prompts/strategy-idea.md` is a thinner intake format that doesn't match real plans (STATE.md open issue) | `plan/00-TEMPLATE.md` created; supersedes strategy-idea for full plans |

## Findings — defects found, NOT fixed (need user decision)

| # | Finding | Recommendation |
|---|---------|----------------|
| R1 | **STATE.md is stale**: says branch `rj/strategy/BBRSIMeanReversion` (actual: `rj/develop`), says Phase 4 FAIL for BBRSI but the reports dir is gone (run was scrapped per PORTFOLIO.md), portfolio ledger predates PORTFOLIO.md numbering | Resynced minimally in this same change set (ledger -> 12 plans, branch corrected). Verify it matches intent. |
| R2 | `.agent/reference/indicator-catalog.md` lacks a Donchian/rolling-extreme row; Phase 2 halts on any uncatalogued indicator | `DonchianATRBreakout.md` carries its own YELLOW pre-approval note. Optionally append the catalog row (not done here because `.agent` reference edits overlap the user's uncommitted work — say the word and it is one line). |
| R3 | `.agent/prompts/strategy-idea.md` should point at `plan/00-TEMPLATE.md` as the promotion target | Same reason as R2 — deferred, one-line edit. |
| R4 | `ENVIRONMENT.md` gotcha #13 says fresh downloads make the 8h->1h funding copy unnecessary, but the legacy instructions remain; new agents may "repair" needlessly | Cosmetic; next ENVIRONMENT edit should annotate, not now (user-modified files hands-off). |
| R5 | Phase files reference "the nine plans" (00-DATA-READINESS Check list) | Cosmetic wording; update to "plans in `plan/INDEX.md`" when next touched. |

## Consistency checks that PASSED

- Phase 4 gate table == CONVENTIONS quality gates (identical thresholds). ✓
- Kotegawa K5 template == what Phase 1 requires == what plans now carry. ✓
- COMMANDS.md templates == Phase 4/5/7 commands (cache none, enable-protections,
  backtest-directory). ✓
- FreqAI constraint set (LightGBM/XGBoost/SKLearnRF only) consistent across
  ENVIRONMENT gotcha #7 and Phase 6 Step 0. ✓
- Phase 7 walk-forward list == ENVIRONMENT IS/OOS split; 19th-quarter
  extension correctly gated behind user approval in both places. ✓
- Phase 0 config-creation step == what F5's fix did. ✓

## Structural assessment

The framework is sound. The gaps found were all of one kind: **information
that lived in exactly one place got silently depended on from another**
(risk math in the reference doc but needed at Phase 1; the failure lesson in
PORTFOLIO but needed by the plan; the analyze-per-epoch rule in ENVIRONMENT but
needed at hyperopt recipe time). The overhaul's fixes follow one rule: *every
document now carries the facts its reader needs, rather than relying on the
reader having read everything.*

That is the property to check on any future framework edit.

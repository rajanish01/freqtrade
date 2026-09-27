"""
MazeGateLoss — a hyperopt loss function that scores an epoch against the
framework's actual pass/fail gates (`.agent/CONVENTIONS.md` "Quality gates",
Kotegawa K2/K4/K7 — `.agent/reference/kotegawa-risk-layer.md`) instead of a
generic risk-adjusted return metric.

WHY THIS FILE EXISTS
--------------------
`SharpeHyperOptLossDaily` (the framework's old default) and the other builtin
loss functions optimise a return/risk ratio that does not correlate 1:1 with
the gates a strategy is actually judged on at Phase 4. Hyperopt can and does
converge on a high-Sharpe epoch that fails profit factor, drawdown, payoff
(K4) or the pair-concentration gate — the epoch "wins" the search and then
fails the very next command. `MultiMetricHyperOptLoss` (freqtrade builtin) is
closer but still does not know about this framework's specific thresholds,
the stoploss-share-of-loss gate, the funding gate, or the K2/K7 risk formulas.

The built-in `hyperopt_min_trades` mechanism is also a cliff, not a gradient:
below the minimum every epoch scores the same flat `MAX_LOSS`, so the
optimiser gets zero signal about *which* under-trading epoch is closer to
viable. This file replaces that cliff with a proportional shortfall for
every gate at once, so the search always has a gradient to follow, and an
epoch that passes every gate always outranks one that does not (however good
its raw return looks).

SCORING
-------
For every gate, a "shortfall" is computed: 0.0 if the gate passes, and a
positive number scaling roughly 0..1+ for how far it fails (as a fraction of
the threshold). Shortfalls are summed. If the sum is 0 (every gate passes),
the loss is `-reward` (a Calmar-style return/drawdown score, so the search
still prefers the best strategy among gate-passing candidates). If the sum is
> 0, the loss is `GATE_FAIL_BASE + shortfall_sum`, which is always worse than
any passing epoch's loss (reward is bounded well below `GATE_FAIL_BASE`), and
still ranks failing epochs against each other by how close they are.

Gates mirror `.agent/CONVENTIONS.md` exactly, with the trade-count gate
rate-scaled to the epoch's own window (CONVENTIONS.md's ">= 100 trades" is
defined over the 3.5y / 1277-day IS window; a maze node measured on a shorter
window needs a proportionally lower count, not the same absolute number):

    profit_factor              > 1.2
    max_drawdown_account       < 0.25
    sharpe (daily)             > 0.5
    trade rate                 >= 100 trades / 1277 days, scaled to the window
    profitable pair fraction   >= 0.6
    stoploss share of gross loss < 0.5
    funding share of gross profit < 0.2   (or "revenue" mode, see below)
    payoff K4: avg_loss        < 3 x avg_win
    risk K2:  (tradable_balance_ratio / max_open_trades) * |stoploss| <= 0.02
    liquidation K7: |stoploss| <= 0.5
        (the literal K7 check is |stoploss|/leverage <= 0.5/leverage; leverage
        cancels algebraically, so this is leverage-independent by construction
        — see kotegawa-risk-layer.md K7. Kept as a named, separate gate so a
        future change to the liquidation-buffer fraction only touches one
        constant, and so it stays visible in the ledger.)

CONFIG OVERRIDES (optional, all under a top-level `"maze_gates"` object in
the strategy's config or a node's overlay config — plain extra keys, ignored
by freqtrade itself, read only by this file):

    "maze_gates": {
        "funding_mode": "cost" | "revenue",   # default "cost"; FundingSkewCarry-style
                                                # strategies set "revenue"
        "min_trades_per_1277d": 100,           # default 100 (matches CONVENTIONS.md)
        "profit_factor_threshold": 1.2,
        "max_drawdown_threshold": 0.25,
        "sharpe_threshold": 0.5,
        "pair_profitable_frac_threshold": 0.6,
        "stoploss_share_threshold": 0.5,
        "funding_share_threshold": 0.2,
        "payoff_multiple": 3.0,
        "risk_per_trade_cap": 0.02,
        "liquidation_stoploss_cap": 0.5
    }

Any key not present uses the default shown. This lets one strategy (e.g.
FundingSkewCarry) flip the funding gate without editing this file.

USAGE
-----
    freqtrade hyperopt --config <node-config> \\
      --hyperopt-path .agent/scripts/hyperopt \\
      --hyperopt-loss MazeGateLoss \\
      ...

Used by `.agent/scripts/maze.py` for T2/T3 tier hyperopt runs (see
`.agent/phases/04M-MAZE.md`). Nothing here is ML — it is a fixed, documented
formula, exactly as deterministic as the loss functions it replaces; this
file does not change what freqtrade optimises (still the declared `--spaces`),
only how epochs within that space are ranked.

READING THE CLI OUTPUT — "No good result found for given optimization
function in N epochs" (verified against `hyperopt.py`): freqtrade's live
"Best result" printout and its own `<Strategy>.json` auto-export only fire
when an epoch's loss beats an internal starting threshold **hard-coded to
100** (`self.current_best_loss = 100`, not `inf` and not `MAX_LOSS`). Every
gate-failing epoch here scores `>= GATE_FAIL_BASE` (1000) by design, so if
*no* epoch passes every gate, freqtrade prints that message and exports
nothing — this is correct, not a bug, and it is itself the maze result for
that node ("no point in this move's parameter space clears every gate").
`.agent/scripts/maze.py` reads every epoch straight out of the `.fthypt`
results file, so it does not depend on that printout or the auto-export.
"""

from datetime import datetime
from typing import Any

import numpy as np
from pandas import DataFrame

from freqtrade.constants import Config
from freqtrade.optimize.hyperopt import IHyperOptLoss


GATE_FAIL_BASE = 1000.0
IS_WINDOW_DAYS = 1277.0  # 20220101-20250630, the framework's documented IS window
STOPLOSS_EXIT_REASONS = {"stop_loss", "stoploss_on_exchange", "trailing_stop_loss"}


def _shortfall_above(value: float, threshold: float, scale: float) -> float:
    """Gate of the form `value < threshold`. 0 if it passes."""
    if not np.isfinite(value):
        return 0.0
    return max(0.0, (value - threshold) / scale) if scale > 0 else 0.0


def _shortfall_below(value: float, threshold: float, scale: float) -> float:
    """Gate of the form `value > threshold`. 0 if it passes."""
    if not np.isfinite(value):
        # e.g. profit_factor = inf because there were no losing trades -> trivially passes
        return 0.0
    return max(0.0, (threshold - value) / scale) if scale > 0 else 0.0


class MazeGateLoss(IHyperOptLoss):
    @staticmethod
    def hyperopt_loss_function(
        *,
        results: DataFrame,
        trade_count: int,
        min_date: datetime,
        max_date: datetime,
        config: Config,
        backtest_stats: dict[str, Any],
        starting_balance: float,
        **kwargs,
    ) -> float:
        gates = config.get("maze_gates", {}) or {}

        pf_threshold = gates.get("profit_factor_threshold", 1.2)
        dd_threshold = gates.get("max_drawdown_threshold", 0.25)
        sharpe_threshold = gates.get("sharpe_threshold", 0.5)
        min_trades_rate = gates.get("min_trades_per_1277d", 100)
        pair_frac_threshold = gates.get("pair_profitable_frac_threshold", 0.6)
        stoploss_share_threshold = gates.get("stoploss_share_threshold", 0.5)
        funding_share_threshold = gates.get("funding_share_threshold", 0.2)
        funding_mode = gates.get("funding_mode", "cost")
        payoff_multiple = gates.get("payoff_multiple", 3.0)
        risk_cap = gates.get("risk_per_trade_cap", 0.02)
        liq_cap = gates.get("liquidation_stoploss_cap", 0.5)

        shortfalls: dict[str, float] = {}

        # ---- profit factor ----
        winning = results.loc[results["profit_abs"] > 0, "profit_abs"].sum()
        losing = results.loc[results["profit_abs"] < 0, "profit_abs"].sum()
        profit_factor = winning / abs(losing) if losing != 0 else float("inf")
        shortfalls["profit_factor"] = _shortfall_below(profit_factor, pf_threshold, pf_threshold)

        # ---- max drawdown (account) ----
        max_dd = backtest_stats.get("max_drawdown_account")
        if max_dd is None:
            max_dd = 0.0
        shortfalls["max_drawdown"] = _shortfall_above(max_dd, dd_threshold, dd_threshold)

        # ---- sharpe (daily) ----
        sharpe = backtest_stats.get("sharpe", 0.0) or 0.0
        shortfalls["sharpe"] = _shortfall_below(sharpe, sharpe_threshold, max(sharpe_threshold, 1e-6))

        # ---- trade rate, scaled to this window ----
        days = max((max_date - min_date).total_seconds() / 86400.0, 1.0)
        required_trades = min_trades_rate * (days / IS_WINDOW_DAYS)
        shortfalls["trade_rate"] = _shortfall_below(
            trade_count, required_trades, max(required_trades, 1.0)
        )

        # ---- profitable pair fraction ----
        per_pair = backtest_stats.get("results_per_pair", [])
        pair_rows = [r for r in per_pair if r.get("key") not in (None, "TOTAL")]
        if pair_rows:
            profitable = sum(1 for r in pair_rows if r.get("profit_total_abs", 0) > 0)
            pair_frac = profitable / len(pair_rows)
        else:
            pair_frac = 0.0
        shortfalls["pair_profitable_frac"] = _shortfall_below(
            pair_frac, pair_frac_threshold, pair_frac_threshold
        )

        # ---- stoploss share of gross loss ----
        gross_loss = abs(losing)
        if gross_loss > 0 and "exit_reason" in results.columns:
            sl_loss = abs(
                results.loc[
                    (results["profit_abs"] < 0) & (results["exit_reason"].isin(STOPLOSS_EXIT_REASONS)),
                    "profit_abs",
                ].sum()
            )
            stoploss_share = sl_loss / gross_loss
        else:
            stoploss_share = 0.0
        shortfalls["stoploss_share"] = _shortfall_above(
            stoploss_share, stoploss_share_threshold, stoploss_share_threshold
        )

        # ---- funding share of gross profit (or revenue mode) ----
        gross_profit = winning
        funding_total = (
            results["funding_fees"].sum() if "funding_fees" in results.columns else 0.0
        )
        if funding_mode == "revenue":
            # funding must be net non-negative; penalise any net cost, scaled by gross profit
            shortfalls["funding"] = max(0.0, -funding_total) / max(gross_profit, 1e-6)
        else:
            funding_cost = abs(min(funding_total, 0.0))
            funding_share = funding_cost / gross_profit if gross_profit > 0 else 0.0
            shortfalls["funding"] = _shortfall_above(
                funding_share, funding_share_threshold, funding_share_threshold
            )

        # ---- payoff K4: avg_loss < payoff_multiple x avg_win ----
        n_win = (results["profit_abs"] > 0).sum()
        n_loss = (results["profit_abs"] < 0).sum()
        avg_win = winning / n_win if n_win > 0 else 0.0
        avg_loss = abs(losing) / n_loss if n_loss > 0 else 0.0
        if avg_win > 0:
            shortfalls["payoff_k4"] = _shortfall_above(
                avg_loss, payoff_multiple * avg_win, max(payoff_multiple * avg_win, 1e-6)
            )
        else:
            shortfalls["payoff_k4"] = 1.0 if avg_loss > 0 else 0.0

        # ---- risk K2: (tradable_balance_ratio / max_open_trades) * |stoploss| <= cap ----
        # `config["max_open_trades"]` here is the live, hyperopt-updated value
        # `hyperopt_optimizer.py` sets on `self.config` before backtesting each
        # epoch — the true position-sizing cap, not the pairlist-capped display
        # stat `backtest_stats["max_open_trades"]` (see `maze.py::compute_gates`
        # for the post-hoc-scoring equivalent of this same gate, which has to
        # read a zip export instead and needs `max_open_trades_setting` for the
        # same reason). Do not swap this for `backtest_stats[...]`.
        stoploss = abs(backtest_stats.get("stoploss", config.get("stoploss", 0.0)) or 0.0)
        tbr = config.get("tradable_balance_ratio", 0.5)
        moc = config.get("max_open_trades", 1) or 1
        moc = moc if (isinstance(moc, int | float) and moc > 0) else 1
        risk_per_trade = (tbr / moc) * stoploss
        shortfalls["risk_k2"] = _shortfall_above(risk_per_trade, risk_cap, risk_cap)

        # ---- liquidation K7: |stoploss| <= liq_cap (leverage-independent, see docstring) ----
        shortfalls["liquidation_k7"] = _shortfall_above(stoploss, liq_cap, liq_cap)

        total_shortfall = sum(shortfalls.values())

        if total_shortfall > 0:
            return GATE_FAIL_BASE + total_shortfall

        # All gates pass — reward the best return/drawdown profile among survivors.
        calmar = backtest_stats.get("calmar")
        if calmar is None or not np.isfinite(calmar):
            total_profit_pct = backtest_stats.get("profit_total", 0.0) or 0.0
            calmar = total_profit_pct / max(max_dd, 1e-4)
        return -float(calmar)

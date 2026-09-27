#!/usr/bin/env python3
"""
maze.py — node/tree bookkeeping and gate scoring for the MAZE strategy-search
protocol (`.agent/phases/04M-MAZE.md`). This is framework tooling, not a
strategy file — see `AGENTS.md` NON-NEGOTIABLES for the scope this is
carved out of ("no new .py files" applies to strategy code; this lives under
`.agent/`, which is READ+WRITE per the file-boundary table).

WHAT THIS DOES
--------------
The old linear framework measured ONE strategy file through a fixed phase
sequence, with a 3-fix-iteration budget before declaring DEAD. MAZE instead
explores a bounded TREE of variants of the same hypothesis (timeframe,
filters, exit mechanism, risk/leverage knobs, hyperopted buy/sell/protection
spaces) and only declares DEAD when the tree is genuinely exhausted, not when
a fix counter runs out. This script is the bookkeeping substrate that makes
that tractable by hand:

  - every node (a specific config + parameter genome, at a specific tier) is
    identified, scored against the SAME gate table every time
    (`.agent/reference/... ` mirrors `MazeGateLoss.py`), and recorded in a
    CSV ledger — so "what have we already tried" is a `grep`, not a memory
  - node genomes are composed by INHERITANCE (a child keeps its parent's
    fixed parameters and only overrides what its move changes), via the
    params-file mechanism (`freqtrade/strategy/hyper.py`) and config overlays
    (`add_config_files` chaining — see `ENVIRONMENT.md`)
  - one frozen "vault" window may be spent at most once, on the final
    finalist(s) — see the `vault` subcommand
  - nothing here is ML or a black box: every formula is the same gate table
    used everywhere else in this framework, just applied uniformly and
    recorded instead of eyeballed per run

STRATEGY GENOME MECHANISM (read before using `node`/`promote`)
----------------------------------------------------------------
freqtrade resolves a strategy's optional params file at a FIXED path next to
the .py file: `user_data/strategies/<StrategyName>.json` (see
`load_params_from_file` in `freqtrade/strategy/hyper.py` — it is derived from
`self.__file__`, not from `--config` or `--strategy-path`). Because every
node of the same strategy shares the same .py file, that path is a single
MUTABLE SLOT, not a per-node file. `maze.py run` stages the correct genome
into that slot immediately before invoking freqtrade and restores whatever
was there immediately after — every invocation is atomic with respect to that
slot. Never run freqtrade directly against a strategy that has maze nodes
without going through `maze.py run`, or a stale genome can silently leak into
an unrelated command.

Config-level attributes (`timeframe`, `stoploss`, `minimal_roi`,
`trailing_stop*`, `max_open_trades`, ...) do NOT go through that slot — they
are resolved with Configuration > Strategy > default precedence
(`freqtrade/resolvers/strategy_resolver.py:_override_attribute_helper`,
empirically verified 2026-09-27 — see `ENVIRONMENT.md` gotcha #8, corrected).
Those are set via the node's config overlay
(`configs/strategies/_maze/<Name>/<node_id>.json`), not the genome file.

LAYOUT
------
  configs/strategies/_maze/<Name>/<node_id>.json   node config overlay
  .agent/reports/<Name>/maze/ledger.csv            one row per node
  .agent/reports/<Name>/maze/tree.md               regenerated human view
  .agent/reports/<Name>/maze/vault.json            one-shot frozen-window guard
  .agent/reports/<Name>/maze/params/<node_id>.json genome snapshot (if any)
  .agent/reports/<Name>/maze/runs/<node_id>_*.json full metrics blob per run
  results/backtests/maze/<Name>/<node_id>/         freqtrade backtest export

USAGE (see `.agent/phases/04M-MAZE.md` for the full protocol)
--------------------------------------------------------------
  maze.py init NAME [--config PATH] [--is-window R] [--oos-window R] [--vault-window R]
  maze.py node NAME --parent ID --tier T1 --type filter --desc "..." \\
                     [--set key=value ...] [--genome-from ID|PATH] [--timerange R]
  maze.py run NAME NODE_ID --cmd backtest|hyperopt [--timerange R] [--epochs N] \\
                     [--spaces buy sell ...] [--jobs N] [--min-trades N] \\
                     [--detail-1m] [--loss NAME] [--no-protections]
  maze.py promote NAME HYPEROPT_NODE_ID --epoch N --tier T3 [--desc "..."]
  maze.py mark NAME NODE_ID STATUS [--note "..."]
  maze.py status NAME
  maze.py tree NAME
  maze.py gates NAME --zip PATH --config PATH
  maze.py vault NAME --node ID [--force]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_FAIL_BASE = 1000.0
IS_WINDOW_DAYS = 1277.0
STOPLOSS_EXIT_REASONS = {"stop_loss", "stoploss_on_exchange", "trailing_stop_loss"}

LEDGER_FIELDS = [
    "node_id", "parent_id", "tier", "status", "move_type", "move_desc",
    "created_at", "config_path", "genome_path", "cmd", "timerange",
    "trades", "profit_factor", "max_drawdown_pct", "sharpe", "calmar",
    "pair_profitable_frac", "stoploss_share", "funding_share",
    "payoff_avg_loss_over_win", "risk_k2", "gates_passed", "gates_failed",
    "score", "artifact", "run_blob", "notes",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def maze_dir(name: str) -> Path:
    return REPO_ROOT / ".agent/reports" / name / "maze"


def ledger_path(name: str) -> Path:
    return maze_dir(name) / "ledger.csv"


def strategy_config_path(name: str) -> Path:
    return REPO_ROOT / "configs/strategies" / f"{name}.json"


def strategy_py_path(name: str) -> Path:
    return REPO_ROOT / "user_data/strategies" / f"{name}.py"


def strategy_params_path(name: str) -> Path:
    return REPO_ROOT / "user_data/strategies" / f"{name}.json"


def node_config_dir(name: str) -> Path:
    return REPO_ROOT / "configs/strategies/_maze" / name


def node_config_path(name: str, node_id: str) -> Path:
    return node_config_dir(name) / f"{node_id}.json"


def backtest_dir(name: str, node_id: str) -> Path:
    return REPO_ROOT / "results/backtests/maze" / name / node_id


# --------------------------------------------------------------------------
# Ledger I/O
# --------------------------------------------------------------------------

def read_ledger(name: str) -> list[dict]:
    p = ledger_path(name)
    if not p.exists():
        return []
    with p.open(newline="") as f:
        return list(csv.DictReader(f))


def write_ledger(name: str, rows: list[dict]) -> None:
    p = ledger_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in LEDGER_FIELDS})


def append_ledger_row(name: str, row: dict) -> None:
    rows = read_ledger(name)
    rows.append({k: row.get(k, "") for k in LEDGER_FIELDS})
    write_ledger(name, rows)


def update_ledger_row(name: str, node_id: str, updates: dict) -> None:
    rows = read_ledger(name)
    found = False
    for r in rows:
        if r["node_id"] == node_id:
            r.update({k: str(v) for k, v in updates.items()})
            found = True
            break
    if not found:
        raise SystemExit(f"node {node_id} not found in ledger for {name}")
    write_ledger(name, rows)


def next_node_id(name: str) -> str:
    rows = read_ledger(name)
    return f"N{len(rows) + 1:04d}"


# --------------------------------------------------------------------------
# Value parsing for --set key=value
# --------------------------------------------------------------------------

def parse_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


def parse_set_args(pairs: list[str]) -> dict:
    out: dict = {}
    for p in pairs:
        if "=" not in p:
            raise SystemExit(f"--set expects key=value, got: {p}")
        k, v = p.split("=", 1)
        out[k] = parse_value(v)
    return out


# --------------------------------------------------------------------------
# Gate scoring — MUST mirror .agent/scripts/hyperopt/MazeGateLoss.py exactly.
# Kept as a separate implementation deliberately (hyperopt's --hyperopt-path
# resolver loads that file in isolation); if you change one, change both and
# update the "last synced" note in both docstrings.
# --------------------------------------------------------------------------

def _shortfall_below(value: float, threshold: float, scale: float) -> float:
    if value is None or not math.isfinite(value):
        return 0.0
    return max(0.0, (threshold - value) / scale) if scale > 0 else 0.0


def _shortfall_above(value: float, threshold: float, scale: float) -> float:
    if value is None or not math.isfinite(value):
        return 0.0
    return max(0.0, (value - threshold) / scale) if scale > 0 else 0.0


def compute_gates(trades: list[dict], stats: dict, config: dict, gates_cfg: dict | None = None) -> dict:
    """Returns {"shortfalls": {...}, "detail": {name: (actual, threshold, passed)},
    "total_shortfall": float, "loss": float, "gate_pass": bool}."""
    g = gates_cfg or config.get("maze_gates", {}) or {}
    pf_threshold = g.get("profit_factor_threshold", 1.2)
    dd_threshold = g.get("max_drawdown_threshold", 0.25)
    sharpe_threshold = g.get("sharpe_threshold", 0.5)
    min_trades_rate = g.get("min_trades_per_1277d", 100)
    pair_frac_threshold = g.get("pair_profitable_frac_threshold", 0.6)
    stoploss_share_threshold = g.get("stoploss_share_threshold", 0.5)
    funding_share_threshold = g.get("funding_share_threshold", 0.2)
    funding_mode = g.get("funding_mode", "cost")
    payoff_multiple = g.get("payoff_multiple", 3.0)
    risk_cap = g.get("risk_per_trade_cap", 0.02)
    liq_cap = g.get("liquidation_stoploss_cap", 0.5)

    trade_count = len(trades)
    profit_abs = [t.get("profit_abs", 0.0) or 0.0 for t in trades]
    winning = sum(p for p in profit_abs if p > 0)
    losing = sum(p for p in profit_abs if p < 0)
    profit_factor = (winning / abs(losing)) if losing != 0 else float("inf")

    max_dd = stats.get("max_drawdown_account") or 0.0
    sharpe = stats.get("sharpe") or 0.0

    # backtest_start_ts / backtest_end_ts are epoch MILLISECONDS (verified against
    # a real export — do not assume seconds, that silently inflates this 1000x).
    min_date = stats.get("backtest_start_ts")
    max_date = stats.get("backtest_end_ts")
    if min_date and max_date:
        days = max((max_date - min_date) / 86400000.0, 1.0)
    else:
        days = IS_WINDOW_DAYS
    required_trades = min_trades_rate * (days / IS_WINDOW_DAYS)

    per_pair = stats.get("results_per_pair", [])
    pair_rows = [r for r in per_pair if r.get("key") not in (None, "TOTAL")]
    pair_frac = (
        sum(1 for r in pair_rows if r.get("profit_total_abs", 0) > 0) / len(pair_rows)
        if pair_rows else 0.0
    )

    gross_loss = abs(losing)
    if gross_loss > 0:
        sl_loss = abs(sum(
            p for t, p in zip(trades, profit_abs)
            if p < 0 and t.get("exit_reason") in STOPLOSS_EXIT_REASONS
        ))
        stoploss_share = sl_loss / gross_loss
    else:
        stoploss_share = 0.0

    gross_profit = winning
    funding_total = sum(t.get("funding_fees", 0.0) or 0.0 for t in trades)
    if funding_mode == "revenue":
        funding_shortfall = max(0.0, -funding_total) / max(gross_profit, 1e-6)
        funding_actual = funding_total
        funding_threshold_display = "> 0 (revenue mode)"
    else:
        funding_cost = abs(min(funding_total, 0.0))
        funding_share = funding_cost / gross_profit if gross_profit > 0 else 0.0
        funding_shortfall = _shortfall_above(funding_share, funding_share_threshold, funding_share_threshold)
        funding_actual = funding_share
        funding_threshold_display = f"< {funding_share_threshold}"

    n_win = sum(1 for p in profit_abs if p > 0)
    n_loss = sum(1 for p in profit_abs if p < 0)
    avg_win = winning / n_win if n_win > 0 else 0.0
    avg_loss = abs(losing) / n_loss if n_loss > 0 else 0.0
    if avg_win > 0:
        payoff_shortfall = _shortfall_above(avg_loss, payoff_multiple * avg_win, max(payoff_multiple * avg_win, 1e-6))
    else:
        payoff_shortfall = 1.0 if avg_loss > 0 else 0.0
    payoff_ratio = (avg_loss / avg_win) if avg_win > 0 else float("inf") if avg_loss > 0 else 0.0

    stoploss = abs(stats.get("stoploss", config.get("stoploss", 0.0)) or 0.0)
    tbr = config.get("tradable_balance_ratio", 0.5)
    # `stats["max_open_trades"]` is `min(configured, len(pairlist))` — a display
    # stat (optimize_reports.py), NOT the value freqtrade actually divides
    # available balance by when sizing a trade (backtesting.py uses
    # `self.strategy.max_open_trades`, the true configured cap). Position
    # sizing — and therefore K2 — must use the true cap:
    # `stats["max_open_trades_setting"]` (-1 sentinel means "infinite", i.e.
    # config `max_open_trades: -1`; not used by any plan in this framework —
    # falls through to the config/default lookup). Verified gap, 2026-09-27,
    # via a 3-pair test whitelist with `max_open_trades: 5`.
    moc_setting = stats.get("max_open_trades_setting")
    if moc_setting is not None and moc_setting != -1:
        moc = moc_setting
    else:
        moc = stats.get("max_open_trades") or config.get("max_open_trades", 1) or 1
    moc = moc if isinstance(moc, int | float) and moc > 0 else 1
    risk_per_trade = (tbr / moc) * stoploss

    shortfalls = {
        "profit_factor": _shortfall_below(profit_factor, pf_threshold, pf_threshold),
        "max_drawdown": _shortfall_above(max_dd, dd_threshold, dd_threshold),
        "sharpe": _shortfall_below(sharpe, sharpe_threshold, max(sharpe_threshold, 1e-6)),
        "trade_rate": _shortfall_below(trade_count, required_trades, max(required_trades, 1.0)),
        "pair_profitable_frac": _shortfall_below(pair_frac, pair_frac_threshold, pair_frac_threshold),
        "stoploss_share": _shortfall_above(stoploss_share, stoploss_share_threshold, stoploss_share_threshold),
        "funding": funding_shortfall,
        "payoff_k4": payoff_shortfall,
        "risk_k2": _shortfall_above(risk_per_trade, risk_cap, risk_cap),
        "liquidation_k7": _shortfall_above(stoploss, liq_cap, liq_cap),
    }
    detail = {
        "profit_factor": (round(profit_factor, 4) if math.isfinite(profit_factor) else "inf", f"> {pf_threshold}", shortfalls["profit_factor"] == 0),
        "max_drawdown": (round(max_dd, 4), f"< {dd_threshold}", shortfalls["max_drawdown"] == 0),
        "sharpe": (round(sharpe, 4), f"> {sharpe_threshold}", shortfalls["sharpe"] == 0),
        "trade_rate": (trade_count, f">= {round(required_trades, 1)} (window-scaled)", shortfalls["trade_rate"] == 0),
        "pair_profitable_frac": (round(pair_frac, 4), f">= {pair_frac_threshold}", shortfalls["pair_profitable_frac"] == 0),
        "stoploss_share": (round(stoploss_share, 4), f"< {stoploss_share_threshold}", shortfalls["stoploss_share"] == 0),
        "funding": (round(funding_actual, 4), funding_threshold_display, shortfalls["funding"] == 0),
        "payoff_k4": (round(payoff_ratio, 4) if math.isfinite(payoff_ratio) else "inf", f"< {payoff_multiple}", shortfalls["payoff_k4"] == 0),
        "risk_k2": (round(risk_per_trade, 5), f"<= {risk_cap}", shortfalls["risk_k2"] == 0),
        "liquidation_k7": (round(stoploss, 4), f"<= {liq_cap}", shortfalls["liquidation_k7"] == 0),
    }
    total_shortfall = sum(shortfalls.values())
    gate_pass = total_shortfall == 0
    if gate_pass:
        calmar = stats.get("calmar")
        if calmar is None or not math.isfinite(calmar):
            calmar = (stats.get("profit_total", 0.0) or 0.0) / max(max_dd, 1e-4)
        loss = -float(calmar)
    else:
        loss = GATE_FAIL_BASE + total_shortfall
    return {
        "shortfalls": shortfalls,
        "detail": detail,
        "total_shortfall": total_shortfall,
        "loss": loss,
        "score": -loss,
        "gate_pass": gate_pass,
        "trade_count": trade_count,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_dd * 100,
        "sharpe": sharpe,
        "calmar": stats.get("calmar"),
        "pair_profitable_frac": pair_frac,
        "stoploss_share": stoploss_share,
        "funding_share": funding_actual,
        "payoff_ratio": payoff_ratio,
        "risk_k2": risk_per_trade,
    }


def load_zip_stats(zip_path: Path) -> tuple[dict, list[dict], dict]:
    """Returns (stats, trades, resolved_config). `resolved_config` is read from
    the zip's own `*_config.json` member — the config freqtrade actually
    resolved and used (post `add_config_files` chaining and CLI overrides) —
    NOT a raw re-read of the node's overlay file, which will be missing any
    key it inherits rather than sets directly (e.g. `max_open_trades`,
    `tradable_balance_ratio` when the node doesn't override them). Verified
    gap, 2026-09-27: scoring `risk_k2` from the raw overlay file silently
    used this module's `max_open_trades` fallback default instead of the
    node's real, inherited value."""
    zf = zipfile.ZipFile(zip_path)
    cfg_name = next((n for n in zf.namelist() if n.endswith("_config.json")), None)
    resolved_config = json.loads(zf.read(cfg_name)) if cfg_name else {}
    names = [n for n in zf.namelist() if n.endswith(".json") and n != cfg_name and "meta" not in n]
    d = json.loads(zf.read(names[0]))
    strat_name = next(iter(d["strategy"]))
    stats = d["strategy"][strat_name]
    return stats, stats.get("trades", []), resolved_config


def gate_table_text(name: str, node_id: str, g: dict) -> str:
    lines = [f"GATES — {name} {node_id}", "─" * 50]
    for gname, (actual, threshold, passed) in g["detail"].items():
        lines.append(f"{gname:22s} {str(actual):>12s}  {threshold:<28s} {'PASS' if passed else 'FAIL'}")
    lines.append("─" * 50)
    if g["gate_pass"]:
        verdict = "ALL GATES PASS"
    else:
        verdict = f"FAIL (shortfall {g['total_shortfall']:.3f})"
    lines.append(f"VERDICT: {verdict}  score={g['score']:.4f}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Config overlay writer
# --------------------------------------------------------------------------

def write_node_config(name: str, node_id: str, overrides: dict) -> Path:
    d = node_config_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    cfg = {
        "_comment": f"MAZE node {node_id} for {name}. Generated by maze.py — do not hand-edit.",
        "add_config_files": [f"../../{name}.json"],
        **overrides,
    }
    p = node_config_path(name, node_id)
    p.write_text(json.dumps(cfg, indent=2) + "\n")
    return p


# --------------------------------------------------------------------------
# Genome (params-file) staging
# --------------------------------------------------------------------------

class GenomeStage:
    """Context manager: stage a node's genome into the strategy's fixed
    params-file slot, restore whatever was there afterward. See module
    docstring — this slot is shared across every node of one strategy."""

    def __init__(self, name: str, genome_path: Path | None):
        self.target = strategy_params_path(name)
        self.genome_path = genome_path
        self.backup: bytes | None = None
        self.existed = False

    def __enter__(self):
        if self.target.exists():
            self.existed = True
            self.backup = self.target.read_bytes()
        if self.genome_path and self.genome_path.exists():
            self.target.write_bytes(self.genome_path.read_bytes())
        elif self.target.exists():
            self.target.unlink()
        return self

    def __exit__(self, *exc):
        if self.existed and self.backup is not None:
            self.target.write_bytes(self.backup)
        elif self.target.exists():
            self.target.unlink()
        return False


def compose_genome(params_details: dict, params_not_optimized: dict, strategy_name: str) -> dict:
    merged: dict = {}
    for space, values in params_not_optimized.items():
        merged.setdefault(space, {}).update(values)
    for space, values in params_details.items():
        merged.setdefault(space, {}).update(values)
    return {
        "strategy_name": strategy_name,
        "params": merged,
        "ft_stratparam_v": 1,
        "export_time": now_iso(),
    }


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def cmd_init(args):
    name = args.name
    d = maze_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    (d / "params").mkdir(exist_ok=True)
    (d / "runs").mkdir(exist_ok=True)
    if not ledger_path(name).exists():
        write_ledger(name, [])
    vault_path = d / "vault.json"
    if not vault_path.exists():
        vault_path.write_text(json.dumps({
            "window": args.vault_window,
            "opened": False,
            "opened_by_node": None,
            "opened_at": None,
        }, indent=2) + "\n")
    tree_path = d / "tree.md"
    if not tree_path.exists():
        tree_path.write_text(f"# MAZE tree — {name}\n\nRegenerate with `maze.py tree {name}`.\n")
    root_id = next_node_id(name)
    cfg_overrides = {}
    if args.timeframe:
        cfg_overrides["timeframe"] = args.timeframe
    cfg_path = write_node_config(name, root_id, cfg_overrides) if cfg_overrides else strategy_config_path(name)
    append_ledger_row(name, {
        "node_id": root_id, "parent_id": "", "tier": "T0", "status": "QUEUED",
        "move_type": "root", "move_desc": "baseline (plan defaults)",
        "created_at": now_iso(), "config_path": str(cfg_path.relative_to(REPO_ROOT)),
        "genome_path": "", "cmd": "", "timerange": args.is_window,
    })
    print(f"Initialized maze for {name}. Root node: {root_id}")
    print(f"IS window:    {args.is_window}")
    print(f"OOS window:   {args.oos_window}")
    print(f"Vault window: {args.vault_window} (one-shot; see `maze.py vault`)")
    print(f"Ledger:       {ledger_path(name).relative_to(REPO_ROOT)}")


def cmd_node(args):
    name = args.name
    node_id = next_node_id(name)
    overrides = parse_set_args(args.set or [])
    genome_path = None
    if args.genome_from:
        src = Path(args.genome_from)
        if not src.is_absolute():
            candidate = maze_dir(name) / "params" / f"{args.genome_from}.json"
            src = candidate if candidate.exists() else src
        if not src.exists():
            raise SystemExit(f"genome source not found: {args.genome_from}")
        genome_path = maze_dir(name) / "params" / f"{node_id}.json"
        genome_path.write_bytes(src.read_bytes())

    parent_rows = [r for r in read_ledger(name) if r["node_id"] == args.parent]
    if not parent_rows:
        raise SystemExit(f"parent node {args.parent} not found")

    cfg_path = write_node_config(name, node_id, overrides) if overrides else strategy_config_path(name)
    append_ledger_row(name, {
        "node_id": node_id, "parent_id": args.parent, "tier": args.tier, "status": "QUEUED",
        "move_type": args.type, "move_desc": args.desc,
        "created_at": now_iso(), "config_path": str(cfg_path.relative_to(REPO_ROOT)),
        "genome_path": str(genome_path.relative_to(REPO_ROOT)) if genome_path else "",
        "cmd": "", "timerange": args.timerange or "",
    })
    print(f"Created node {node_id} (parent {args.parent}, tier {args.tier}): {args.desc}")
    print(f"Config: {cfg_path.relative_to(REPO_ROOT)}")
    if genome_path:
        print(f"Genome: {genome_path.relative_to(REPO_ROOT)}")


def _run_freqtrade(cmd: list[str]) -> str:
    print("+ " + " ".join(cmd))
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    out = proc.stdout + "\n" + proc.stderr
    tail = "\n".join(l for l in out.splitlines() if " INFO - " not in l)[-4000:]
    print(tail)
    if proc.returncode != 0:
        raise SystemExit(f"freqtrade exited {proc.returncode}")
    return out


def cmd_run(args):
    name = args.name
    node_id = args.node_id
    rows = read_ledger(name)
    row = next((r for r in rows if r["node_id"] == node_id), None)
    if row is None:
        raise SystemExit(f"node {node_id} not found")

    config_path = REPO_ROOT / row["config_path"]
    genome_path = REPO_ROOT / row["genome_path"] if row["genome_path"] else None
    timerange = args.timerange or row.get("timerange") or ""
    strategy_name = json.loads(config_path.read_text()).get("strategy") or name
    if strategy_name == name and "strategy" not in json.loads(config_path.read_text()):
        pass  # inherited from base strategy config, fine

    venv_python = REPO_ROOT / ".venv/bin/python"
    ft_bin = REPO_ROOT / ".venv/bin/freqtrade"
    ft = str(ft_bin) if ft_bin.exists() else "freqtrade"

    update_ledger_row(name, node_id, {"status": "RUNNING", "cmd": args.cmd, "timerange": timerange})

    with GenomeStage(name, genome_path):
        if args.cmd == "backtest":
            bdir = backtest_dir(name, node_id)
            bdir.mkdir(parents=True, exist_ok=True)
            cmd = [ft, "backtesting", "--config", str(config_path),
                   "--timerange", timerange, "--cache", "none",
                   "--export", "signals", "--backtest-directory", str(bdir)]
            if not args.no_protections:
                cmd.append("--enable-protections")
            if args.detail_1m:
                cmd += ["--timeframe-detail", "1m"]
            if args.extra:
                cmd += args.extra.split()
            _run_freqtrade(cmd)
            zips = sorted(bdir.glob("*.zip"))
            if not zips:
                update_ledger_row(name, node_id, {"status": "DONE", "notes": "NO EXPORT FOUND"})
                raise SystemExit("no backtest export found")
            zpath = zips[-1]
            stats, trades, config = load_zip_stats(zpath)
            g = compute_gates(trades, stats, config)
            blob = {
                "node_id": node_id, "cmd": "backtest", "timerange": timerange,
                "zip": str(zpath.relative_to(REPO_ROOT)), "gates": g["detail"],
                "gate_pass": g["gate_pass"], "score": g["score"], "run_at": now_iso(),
            }
            run_blob = maze_dir(name) / "runs" / f"{node_id}_backtest_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
            run_blob.write_text(json.dumps(blob, indent=2, default=str))
            update_ledger_row(name, node_id, {
                "status": "DONE", "trades": g["trade_count"],
                "profit_factor": round(g["profit_factor"], 4) if math.isfinite(g["profit_factor"]) else "inf",
                "max_drawdown_pct": round(g["max_drawdown_pct"], 3),
                "sharpe": round(g["sharpe"], 4), "calmar": g["calmar"],
                "pair_profitable_frac": round(g["pair_profitable_frac"], 3),
                "stoploss_share": round(g["stoploss_share"], 3),
                "funding_share": round(g["funding_share"], 4),
                "payoff_avg_loss_over_win": round(g["payoff_ratio"], 3) if math.isfinite(g["payoff_ratio"]) else "inf",
                "risk_k2": round(g["risk_k2"], 5),
                "gates_passed": sum(1 for v in g["shortfalls"].values() if v == 0),
                "gates_failed": sum(1 for v in g["shortfalls"].values() if v > 0),
                "score": round(g["score"], 4),
                "artifact": str(zpath.relative_to(REPO_ROOT)),
                "run_blob": str(run_blob.relative_to(REPO_ROOT)),
            })
            print(gate_table_text(name, node_id, g))

        elif args.cmd == "hyperopt":
            cmd = [ft, "hyperopt", "--config", str(config_path),
                   "--hyperopt-path", ".agent/scripts/hyperopt",
                   "--hyperopt-loss", args.loss or "MazeGateLoss",
                   "--timerange", timerange,
                   "--epochs", str(args.epochs),
                   "-j", str(args.jobs),
                   "--min-trades", str(args.min_trades),
                   "--disable-param-export",
                   "--spaces", *(args.spaces or ["buy", "sell"])]
            if not args.no_protections:
                cmd.append("--enable-protections")
            if args.analyze_per_epoch:
                cmd.append("--analyze-per-epoch")
            if args.extra:
                cmd += args.extra.split()
            out = _run_freqtrade(cmd)
            # freqtrade's logger wraps this line and inserts a hard newline right
            # after "saved to" when the path is long (verified 2026-09-27) — do
            # not assume it is on one line.
            m = re.search(r"saved to\s*\n?\s*'([^']+)'", out)
            if not m:
                update_ledger_row(name, node_id, {"status": "DONE", "notes": "NO FTHYPT FOUND"})
                raise SystemExit("could not locate .fthypt output path in freqtrade output")
            fthypt = Path(m.group(1))
            epochs = [json.loads(line) for line in fthypt.read_text().splitlines() if line.strip()]
            # Hyperopt has no zip export, so there is no resolved-config sidecar to
            # read here (unlike the backtest branch) — this is the raw overlay file.
            # compute_gates() covers the one field this usually matters for
            # (max_open_trades) via a stats-first fallback; tradable_balance_ratio
            # is a K1 structural invariant this framework never overrides per-node,
            # so the 0.5 default is safe. If a node ever DOES override it, pass
            # `--set tradable_balance_ratio=...` so it lands in this same file.
            config = json.loads(config_path.read_text())
            best = None
            for e in epochs:
                metrics = e["results_metrics"]
                g = compute_gates(metrics.get("trades", []), metrics, config)
                e["_gate_score"] = g["score"]
                e["_gate_pass"] = g["gate_pass"]
                e["_gate_detail"] = g["detail"]
                if best is None or g["score"] > best["_gate_score"]:
                    best = e
            csv_path = maze_dir(name) / "runs" / f"{node_id}_epochs.csv"
            with csv_path.open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["epoch", "loss", "gate_pass", "score", "trades", "params_dict"])
                for e in epochs:
                    w.writerow([e["current_epoch"], e["loss"], e["_gate_pass"], round(e["_gate_score"], 4),
                                e["results_metrics"].get("total_trades"), json.dumps(e["params_dict"])])
            update_ledger_row(name, node_id, {
                "status": "DONE", "trades": best["results_metrics"].get("total_trades"),
                "score": round(best["_gate_score"], 4),
                "gates_passed": sum(1 for v in best["_gate_detail"].values() if v[2]),
                "gates_failed": sum(1 for v in best["_gate_detail"].values() if not v[2]),
                "artifact": str(fthypt.relative_to(REPO_ROOT)),
                "run_blob": str(csv_path.relative_to(REPO_ROOT)),
                "notes": f"best_epoch={best['current_epoch']} of {len(epochs)}"
                         + ("" if best["_gate_pass"] else " (no epoch passed every gate)"),
            })
            print(f"{len(epochs)} epochs. Best (by gate score): epoch {best['current_epoch']}"
                  f" score={best['_gate_score']:.4f} gate_pass={best['_gate_pass']}")
            print(f"Params: {json.dumps(best['params_dict'])}")
            print(f"Top-20 CSV: {csv_path.relative_to(REPO_ROOT)}")
            print("Promote a specific epoch with:")
            print(f"  maze.py promote {name} {node_id} --epoch {best['current_epoch']} --tier <T3> --desc '...'")
        else:
            raise SystemExit(f"unknown --cmd {args.cmd}")


def cmd_promote(args):
    name = args.name
    hyperopt_node = args.node_id
    rows = read_ledger(name)
    row = next((r for r in rows if r["node_id"] == hyperopt_node), None)
    if row is None:
        raise SystemExit(f"node {hyperopt_node} not found")
    fthypt = REPO_ROOT / row["artifact"]
    if not fthypt.exists() or fthypt.suffix != ".fthypt":
        raise SystemExit(f"node {hyperopt_node} has no .fthypt artifact (was it a hyperopt run?)")
    epochs = [json.loads(line) for line in fthypt.read_text().splitlines() if line.strip()]
    epoch = next((e for e in epochs if e["current_epoch"] == args.epoch), None)
    if epoch is None:
        raise SystemExit(f"epoch {args.epoch} not found in {fthypt}")

    strategy_name = json.loads((REPO_ROOT / row["config_path"]).read_text()).get("strategy", name)
    genome = compose_genome(epoch["params_details"], epoch.get("params_not_optimized", {}), strategy_name)
    node_id = next_node_id(name)
    genome_path = maze_dir(name) / "params" / f"{node_id}.json"
    genome_path.write_text(json.dumps(genome, indent=2))

    overrides = parse_set_args(args.set or [])
    cfg_path = write_node_config(name, node_id, overrides) if overrides else REPO_ROOT / row["config_path"]
    append_ledger_row(name, {
        "node_id": node_id, "parent_id": hyperopt_node, "tier": args.tier, "status": "QUEUED",
        "move_type": "hyperopt-epoch",
        "move_desc": args.desc or f"epoch {args.epoch} of {hyperopt_node}",
        "created_at": now_iso(), "config_path": str(cfg_path.relative_to(REPO_ROOT)),
        "genome_path": str(genome_path.relative_to(REPO_ROOT)),
        "cmd": "", "timerange": args.timerange or row.get("timerange", ""),
    })
    print(f"Promoted epoch {args.epoch} of {hyperopt_node} -> node {node_id}")
    print(f"Genome: {genome_path.relative_to(REPO_ROOT)}")
    print(f"Config: {cfg_path.relative_to(REPO_ROOT)}")


def cmd_mark(args):
    update_ledger_row(args.name, args.node_id, {"status": args.status, "notes": args.note or ""})
    print(f"{args.node_id} -> {args.status}" + (f" ({args.note})" if args.note else ""))


def cmd_status(args):
    rows = read_ledger(args.name)
    if not rows:
        print(f"No nodes for {args.name} yet. Run `maze.py init {args.name}` first.")
        return
    by_tier: dict[str, list[dict]] = {}
    for r in rows:
        by_tier.setdefault(r["tier"], []).append(r)
    print(f"MAZE STATUS — {args.name}")
    print("─" * 60)
    print(f"Total nodes evaluated: {len(rows)}")
    trial_note = math.sqrt(2 * math.log(max(len(rows), 2)))
    print(f"Trial-inflation note (heuristic, see 04M-MAZE.md 'Anti-overfitting'):")
    print(f"  expected max-Z at this trial count ~= {trial_note:.2f}."
          f" Treat any single node's margin over a gate as noise unless it")
    print(f"  clears by more than that many standard errors. The real firewall is OOS + vault, not this number.")
    print("─" * 60)
    for tier in sorted(by_tier):
        trows = by_tier[tier]
        statuses = {}
        for r in trows:
            statuses[r["status"]] = statuses.get(r["status"], 0) + 1
        best = max((r for r in trows if r.get("score")), key=lambda r: float(r["score"]), default=None)
        print(f"{tier}: {len(trows)} nodes | " + ", ".join(f"{k}={v}" for k, v in statuses.items()))
        if best:
            print(f"   best: {best['node_id']} score={best['score']} gates {best['gates_passed']}/"
                  f"{int(best['gates_passed'] or 0) + int(best['gates_failed'] or 0)} "
                  f"({best['move_desc']})")
    vault = json.loads((maze_dir(args.name) / "vault.json").read_text())
    print("─" * 60)
    print(f"Vault ({vault['window']}): "
          + (f"OPENED by {vault['opened_by_node']} at {vault['opened_at']}" if vault["opened"] else "untouched"))


def cmd_tree(args):
    rows = read_ledger(args.name)
    children: dict[str, list[dict]] = {}
    for r in rows:
        children.setdefault(r["parent_id"], []).append(r)

    lines = [f"# MAZE tree — {args.name}", "", "Regenerated by `maze.py tree`. Do not hand-edit.", ""]

    def walk(node_id: str, depth: int):
        for r in children.get(node_id, []):
            gp = f"{r['gates_passed']}/{int(r['gates_passed'] or 0) + int(r['gates_failed'] or 0)}" if r["gates_passed"] != "" else "-"
            lines.append(
                f"{'  ' * depth}- **{r['node_id']}** [{r['tier']}/{r['status']}] "
                f"{r['move_type']}: {r['move_desc']} "
                f"(score={r['score'] or '-'}, gates={gp})"
            )
            walk(r["node_id"], depth + 1)

    walk("", 0)
    (maze_dir(args.name) / "tree.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def cmd_gates(args):
    stats, trades, resolved_config = load_zip_stats(Path(args.zip))
    # Resolved config from the zip is authoritative for what freqtrade actually
    # used; --config is layered on top only for ad-hoc gate-threshold overrides
    # (e.g. testing a different maze_gates block against an existing export).
    config = {**resolved_config, **json.loads(Path(args.config).read_text())}
    g = compute_gates(trades, stats, config)
    print(gate_table_text(args.name, args.zip, g))


def cmd_vault(args):
    name = args.name
    vpath = maze_dir(name) / "vault.json"
    vault = json.loads(vpath.read_text())
    if vault["opened"] and not args.force:
        print(f"REFUSING: vault already opened by {vault['opened_by_node']} at {vault['opened_at']}.")
        print("The vault window is one-shot by design (anti-overfitting firewall — see 04M-MAZE.md).")
        print("Pass --force only with explicit user approval, and record why in the journal.")
        raise SystemExit(1)
    rows = read_ledger(name)
    row = next((r for r in rows if r["node_id"] == args.node), None)
    if row is None:
        raise SystemExit(f"node {args.node} not found")
    config_path = REPO_ROOT / row["config_path"]
    genome_path = REPO_ROOT / row["genome_path"] if row["genome_path"] else None
    ft_bin = REPO_ROOT / ".venv/bin/freqtrade"
    ft = str(ft_bin) if ft_bin.exists() else "freqtrade"
    bdir = backtest_dir(name, args.node) / "vault"
    bdir.mkdir(parents=True, exist_ok=True)
    with GenomeStage(name, genome_path):
        cmd = [ft, "backtesting", "--config", str(config_path), "--timerange", args.window,
               "--cache", "none", "--enable-protections", "--export", "signals",
               "--backtest-directory", str(bdir)]
        _run_freqtrade(cmd)
    zips = sorted(bdir.glob("*.zip"))
    if not zips:
        raise SystemExit("vault run produced no export")
    stats, trades, config = load_zip_stats(zips[-1])
    g = compute_gates(trades, stats, config)
    vault.update({"opened": True, "opened_by_node": args.node, "opened_at": now_iso(),
                  "result_zip": str(zips[-1].relative_to(REPO_ROOT)), "gate_pass": g["gate_pass"],
                  "score": g["score"]})
    vpath.write_text(json.dumps(vault, indent=2, default=str))
    update_ledger_row(name, args.node, {"status": "VAULTED", "notes": f"vault score={g['score']:.4f}"})
    print(gate_table_text(name, args.node, g))
    print(f"\nVAULT CONSUMED. {vpath.relative_to(REPO_ROOT)} now permanently marked opened=true.")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="subcommand", required=True)

    s = sub.add_parser("init", help="initialize the maze workspace for a strategy")
    s.add_argument("name")
    s.add_argument("--is-window", default="20220101-20250630")
    s.add_argument("--oos-window", default="20250701-20260709")
    s.add_argument("--vault-window", default="20260710-20260923")
    s.add_argument("--timeframe", default=None)
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("node", help="register a new node")
    s.add_argument("name")
    s.add_argument("--parent", required=True)
    s.add_argument("--tier", required=True)
    s.add_argument("--type", required=True, help="move category: timeframe|filter|exit_mode|risk|config")
    s.add_argument("--desc", required=True)
    s.add_argument("--set", action="append", help="key=value config override, repeatable")
    s.add_argument("--genome-from", default=None, help="node id or path to a genome json to copy")
    s.add_argument("--timerange", default=None)
    s.set_defaults(func=cmd_node)

    s = sub.add_parser("run", help="execute a node (backtest or hyperopt)")
    s.add_argument("name")
    s.add_argument("node_id")
    s.add_argument("--cmd", required=True, choices=["backtest", "hyperopt"])
    s.add_argument("--timerange", default=None)
    s.add_argument("--epochs", type=int, default=300)
    s.add_argument("--spaces", nargs="+", default=None)
    s.add_argument("--jobs", type=int, default=-1)
    s.add_argument("--min-trades", type=int, default=50)
    s.add_argument("--loss", default=None)
    s.add_argument("--detail-1m", action="store_true")
    s.add_argument("--no-protections", action="store_true")
    s.add_argument("--analyze-per-epoch", action="store_true")
    s.add_argument("--extra", default=None, help="raw extra CLI args, space-separated")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("promote", help="materialize a hyperopt epoch as a new child node")
    s.add_argument("name")
    s.add_argument("node_id", help="the hyperopt node to promote an epoch from")
    s.add_argument("--epoch", type=int, required=True)
    s.add_argument("--tier", required=True)
    s.add_argument("--desc", default=None)
    s.add_argument("--set", action="append")
    s.add_argument("--timerange", default=None)
    s.set_defaults(func=cmd_promote)

    s = sub.add_parser("mark", help="set a node's status")
    s.add_argument("name")
    s.add_argument("node_id")
    s.add_argument("status", choices=["QUEUED", "RUNNING", "DONE", "PROMOTED", "PRUNED", "DEAD", "VAULTED"])
    s.add_argument("--note", default=None)
    s.set_defaults(func=cmd_mark)

    s = sub.add_parser("status", help="summarize the tree")
    s.add_argument("name")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("tree", help="regenerate tree.md")
    s.add_argument("name")
    s.set_defaults(func=cmd_tree)

    s = sub.add_parser("gates", help="score an arbitrary backtest zip against the gate table")
    s.add_argument("name")
    s.add_argument("--zip", required=True)
    s.add_argument("--config", required=True)
    s.set_defaults(func=cmd_gates)

    s = sub.add_parser("vault", help="one-shot frozen-window confirmation run")
    s.add_argument("name")
    s.add_argument("--node", required=True)
    s.add_argument("--window", default="20260710-20260923")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_vault)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

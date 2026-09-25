#!/usr/bin/env bash
# framework-check.sh — one-shot infra verification for the agentic strategy framework.
#
# Verifies: config isolation (never config.json), strategy discovery, dataset
# presence (OHLCV + funding + mark), no stray strategy files, and the infra
# canary backtest with funding fees actually applied.
#
# Usage:  bash .agent/scripts/framework-check.sh
# Exit:   0 = all checks PASS, 1 = at least one FAIL. Read the output either way.
# Run at Phase 0, and any time a result looks wrong (rule out infra first).

set -u
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 1

CANARY=SmokeTestStrategy
CFG=configs/strategies/$CANARY.json
CHECKDIR=results/checks
PASS=0; FAIL=0
ok()  { echo "PASS  $1"; PASS=$((PASS+1)); }
bad() { echo "FAIL  $1"; FAIL=$((FAIL+1)); }

echo "FRAMEWORK CHECK — $(date -u +%Y-%m-%dT%H:%MZ)"
echo "──────────────────────────────────────────────────"

# 0. freqtrade binary
if [ -x .venv/bin/freqtrade ]; then FT=.venv/bin/freqtrade
elif command -v freqtrade >/dev/null 2>&1; then FT=freqtrade
else
  echo "FAIL  freqtrade not found (activate .venv: source .venv/bin/activate)"
  exit 1
fi
ok "freqtrade binary: $FT"

# 1. Config isolation — the resolved config set must never contain config.json
CONF_LINES=$("$FT" list-strategies --config "$CFG" 2>&1 | grep -iE "using.*config" || true)
echo "$CONF_LINES" | sed 's/^/      /'
if echo "$CONF_LINES" | grep -qE "(^|/|[^a-z])config\.json"; then
  bad "config isolation — config.json was loaded (FORBIDDEN, see gotcha #0)"
else
  ok "config isolation — config.json not in the resolved set"
fi

# 2. Strategy discovery — no DUPLICATE NAME (gotcha 6b)
if "$FT" list-strategies --config "$CFG" 2>&1 | grep -q "DUPLICATE NAME"; then
  bad "list-strategies reports DUPLICATE NAME (strategy_path in a config?)"
else
  ok "strategy discovery OK"
fi

# 3. Dataset presence — 10 pairs x (1h OHLCV + funding_rate + mark)
for kind in "1h-futures" "1h-funding_rate" "1h-mark"; do
  N=$(ls user_data/data/binanceusdm/futures/*-"$kind".feather 2>/dev/null | wc -l)
  if [ "$N" -eq 10 ]; then ok "dataset: 10 x $kind files"
  else bad "dataset: $N x $kind files (expected 10)"; fi
done

# 4. No stray strategy files — only the canary, plan/ and __pycache__ belong there
STRAYS=$(find user_data/strategies -maxdepth 1 -name "*.py" ! -name "$CANARY.py" 2>/dev/null)
if [ -z "$STRAYS" ]; then
  ok "no stray strategy .py files in user_data/strategies/"
else
  bad "stray strategy files: $STRAYS (dead/in-progress strategies must be removed)"
fi

# 5. Infra canary backtest — proves configs + data + engine work end to end
mkdir -p "$CHECKDIR"
CANARY_OUT=$("$FT" backtesting --config "$CFG" --timerange 20250601-20250701 \
  --cache none --export signals --backtest-directory "$CHECKDIR" 2>&1 || true)
TRADES=$(echo "$CANARY_OUT" | grep -oE "Total/Daily Avg Trades[^0-9]*[0-9]+" | grep -oE "[0-9]+" | tail -1)
if [ -n "$TRADES" ] && [ "$TRADES" -gt 0 ]; then
  ok "infra canary: $TRADES trades on 20250601-20250701"
else
  bad "infra canary: no trades parsed (env broken — diagnose against ENVIRONMENT.md gotchas)"
fi

# 6. Funding warnings must be ABSENT — their presence means fees are silently zero
if echo "$CANARY_OUT" | grep -q "No history for.*funding_rate"; then
  bad "funding warnings PRESENT — fees are silently zero (data-download.md, funding section)"
else
  ok "no funding warnings in canary run"
fi

# 7. Funding fees actually applied — non-zero on canary trades
Z=$(ls -t "$CHECKDIR"/*.zip 2>/dev/null | head -1)
if [ -n "$Z" ]; then
  FUND=$(.venv/bin/python -c "
import zipfile, json
zf = zipfile.ZipFile('$Z')
names = [n for n in zf.namelist() if n.endswith('.json') and 'config' not in n and 'meta' not in n]
d = json.loads(zf.read(names[0]))
s = list(d['strategy'])[0]
t = d['strategy'][s]['trades']
nz = sum(1 for x in t if x.get('funding_fees', 0) != 0)
tot = round(sum(x.get('funding_fees', 0) for x in t), 4)
print(f'{nz}/{len(t)} {tot}')
" 2>/dev/null)
  NZ=${FUND%% *}
  if [ -n "$NZ" ] && [ "${NZ%%/*}" -gt 0 ]; then
    ok "funding fees applied: $NZ canary trades carry non-zero funding"
  else
    bad "funding fees ZERO on canary trades — every futures result would be optimistic"
  fi
else
  bad "no backtest export found in $CHECKDIR — funding check not possible"
fi

echo "──────────────────────────────────────────────────"
echo "RESULT: $PASS PASS / $FAIL FAIL"
[ "$FAIL" -eq 0 ] || echo "Infra is broken. Do NOT write or trust strategy code until fixed — see .agent/ENVIRONMENT.md gotchas."
exit $(( FAIL > 0 ? 1 : 0 ))

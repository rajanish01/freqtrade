# Custom Indicators

Indicators that are **not** in `indicator-catalog.md` but have been explicitly
approved by the user for this repo.

Adding to this file requires user approval (YELLOW). The agent may not add an
entry here on its own initiative.

Each entry must record: what it measures, why a catalog indicator would not do,
the implementation, and confirmation that it passed `lookahead-analysis` and
`recursive-analysis`.

---

## Template

### <IndicatorName>
- **Measures:** <what market property>
- **Why not a catalog indicator:** <justification>
- **Column(s):** `ind_<name>`
- **Lookback:** <N candles — must be covered by startup_candle_count>
- **Approved by user:** <date>
- **lookahead-analysis:** CLEAN / not yet run
- **recursive-analysis:** CLEAN / not yet run

```python
# implementation
```

---

*No custom indicators approved yet.*

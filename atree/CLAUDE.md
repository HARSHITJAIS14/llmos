# atree

Read [AGENTS.md](AGENTS.md) — all project rules live there (single source of
truth, host-agnostic). This file intentionally adds nothing.

Working on the plugin itself: run tests with `.venv/bin/python -m pytest tests/ -q`.
The token table in `test_axdiff.py` is the Phase 1 exit check — it must print
and pass on every change to `core/axdiff.py`.

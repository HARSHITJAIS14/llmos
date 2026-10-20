"""SQLite schema (implementation.md §14.2). Local only; denylisted apps never get rows."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS apps(
  bundle_id TEXT PRIMARY KEY, name TEXT, version TEXT, build TEXT, framework TEXT, stack TEXT,
  profile_json TEXT, menu_json TEXT, card_md TEXT, updated_at REAL);
CREATE TABLE IF NOT EXISTS routes(
  id INTEGER PRIMARY KEY, bundle_ids TEXT, template TEXT, regex TEXT, slots_json TEXT, plan_json TEXT,
  status TEXT CHECK(status IN ('candidate','trusted','stale','disabled')),
  runs INTEGER DEFAULT 0, passes INTEGER DEFAULT 0, fails INTEGER DEFAULT 0,
  consecutive_fails INTEGER DEFAULT 0, median_ms INTEGER, app_versions_json TEXT, os_version TEXT,
  version INTEGER DEFAULT 1, prev_plan_json TEXT, created_at REAL, last_pass_at REAL, source_trace TEXT,
  literal_len INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS route_aliases(route_id INTEGER REFERENCES routes(id) ON DELETE CASCADE,
  template TEXT, regex TEXT);
CREATE TABLE IF NOT EXISTS anchors(
  bundle_id TEXT, selector TEXT, role TEXT, label TEXT, purpose TEXT,
  hits INTEGER DEFAULT 0, misses INTEGER DEFAULT 0, last_seen REAL, PRIMARY KEY(bundle_id, selector));
CREATE TABLE IF NOT EXISTS outcomes(
  id INTEGER PRIMARY KEY, ts REAL, task_hash TEXT, route_id INTEGER, status TEXT, total_ms INTEGER,
  opus_calls INTEGER, jev_calls INTEGER, tokens_in INTEGER, tokens_out INTEGER, cost_usd REAL, trace_path TEXT);
CREATE TABLE IF NOT EXISTS law_events(ts REAL, law TEXT, bundle_id TEXT, detail TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS routes_template ON routes(template);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    return con

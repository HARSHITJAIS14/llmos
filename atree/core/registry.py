"""Per-app episodic memory (pitch §5): SQLite + FTS5, queried, never loaded.

Primary key for elements is the structural identity path computed by
core.axdiff — stable across snapshots, sessions, and restarts, unlike
snapshot-scoped ref_ids.

Privacy rules are enforced here, not documented elsewhere:
  * denylisted apps take no deposits, ever
  * content-region names are stored as pattern + salted hash, never literally
  * the database is local-only (registry/ is git-ignored)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[1]))
DB_PATH = _ROOT / "registry" / "registry.db"

DENYLIST = frozenset({
    "com.apple.MobileSMS",          # Messages
    "com.apple.Passwords",
    "com.1password.1password",
    "com.agilebits.onepassword7",
    "com.bitwarden.desktop",
    "com.apple.keychainaccess",
})
DENYLIST_NAMES = frozenset({"messages", "passwords", "keychain access", "1password", "bitwarden"})

CONFIDENCE_FLOOR = 0.30
DECAY_HALF_LIFE_DAYS = 90.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS apps(
  id INTEGER PRIMARY KEY,
  bundle_id TEXT UNIQUE,
  name TEXT,
  archetype TEXT,
  version TEXT,
  os_version TEXT,
  last_seen REAL
);
CREATE TABLE IF NOT EXISTS elements(
  id INTEGER PRIMARY KEY,
  app_id INTEGER REFERENCES apps(id),
  identity_path TEXT,
  role TEXT,
  name_pattern TEXT,
  surface TEXT,
  reach_strategy TEXT,
  verify_strategy TEXT DEFAULT 'ax',
  hit_count INTEGER DEFAULT 0,
  miss_count INTEGER DEFAULT 0,
  last_confirmed REAL,
  UNIQUE(app_id, identity_path)
);
CREATE TABLE IF NOT EXISTS routes(
  id INTEGER PRIMARY KEY,
  app_id INTEGER REFERENCES apps(id),
  task_signature TEXT,
  steps_json TEXT,
  run_count INTEGER DEFAULT 0,
  success_count INTEGER DEFAULT 0,
  median_turns REAL,
  last_success REAL,
  UNIQUE(app_id, task_signature)
);
CREATE TABLE IF NOT EXISTS outcomes(
  id INTEGER PRIMARY KEY,
  route_id INTEGER,
  element_id INTEGER,
  ts REAL,
  verdict TEXT,
  postcondition TEXT,
  turns INTEGER,
  tokens INTEGER
);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    try:
        con.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS routes_fts "
            "USING fts5(task_signature, content='routes', content_rowid='id')"
        )
        con.execute("""
            CREATE TRIGGER IF NOT EXISTS routes_ai AFTER INSERT ON routes BEGIN
              INSERT INTO routes_fts(rowid, task_signature) VALUES (new.id, new.task_signature);
            END""")
    except sqlite3.OperationalError:
        pass  # FTS5 unavailable -> LIKE fallback in find_route
    return con


def denied(app_name: str, bundle_id: str = "") -> bool:
    return bundle_id in DENYLIST or app_name.strip().lower() in DENYLIST_NAMES


def sanitize_name(name: str, is_content: bool) -> str:
    """Selectors, not content. UI chrome is stored verbatim; anything from a
    content region becomes a shape-pattern plus a salted hash."""
    if not is_content:
        return name
    salt = os.environ.get("ATREE_REGISTRY_SALT", "atree-local")
    digest = hashlib.sha256((salt + name).encode()).hexdigest()[:12]
    pattern = re.sub(r"[A-Za-z]+", "w", re.sub(r"\d+", "9", name))
    return f"content:{pattern}#{digest}"


def normalize_signature(task: str) -> str:
    sig = task.strip().lower()
    sig = re.sub(r'"[^"]*"|\'[^\']*\'', "{arg}", sig)   # quoted args -> placeholder
    sig = re.sub(r"\d+", "{n}", sig)
    return re.sub(r"\s+", " ", sig)


def confidence(hits: int, misses: int, last_confirmed: float | None) -> float:
    base = (hits + 1) / (hits + misses + 2)             # Laplace-smoothed
    if last_confirmed:
        age_days = max(0.0, (time.time() - last_confirmed) / 86400.0)
        base *= 0.5 ** (age_days / DECAY_HALF_LIFE_DAYS)
    return base


# ---------------------------------------------------------------- deposits

def get_or_create_app(con, name: str, bundle_id: str = "", archetype: str = "",
                      version: str = "", os_version: str = "") -> int | None:
    if denied(name, bundle_id):
        return None
    row = con.execute(
        "SELECT id FROM apps WHERE name=? OR (bundle_id!='' AND bundle_id=?)",
        (name, bundle_id),
    ).fetchone()
    if row:
        con.execute("UPDATE apps SET last_seen=? WHERE id=?", (time.time(), row["id"]))
        con.commit()
        return row["id"]
    cur = con.execute(
        "INSERT INTO apps(bundle_id,name,archetype,version,os_version,last_seen) VALUES(?,?,?,?,?,?)",
        (bundle_id or None, name, archetype, version, os_version, time.time()),
    )
    con.commit()
    return cur.lastrowid


def upsert_element(con, app_id: int, identity_path: str, role: str, name: str,
                   surface: str = "window", reach_strategy: str = "",
                   is_content: bool = False) -> int:
    name_pattern = sanitize_name(name, is_content)
    con.execute(
        """INSERT INTO elements(app_id, identity_path, role, name_pattern, surface, reach_strategy, last_confirmed)
           VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(app_id, identity_path) DO UPDATE SET
             role=excluded.role, name_pattern=excluded.name_pattern,
             surface=excluded.surface,
             reach_strategy=CASE WHEN excluded.reach_strategy!='' THEN excluded.reach_strategy
                                 ELSE elements.reach_strategy END""",
        (app_id, identity_path, role, name_pattern, surface, reach_strategy, time.time()),
    )
    con.commit()
    return con.execute(
        "SELECT id FROM elements WHERE app_id=? AND identity_path=?",
        (app_id, identity_path),
    ).fetchone()["id"]


def save_route(con, app_id: int, task: str, steps: list[dict], turns: int | None = None) -> int:
    sig = normalize_signature(task)
    row = con.execute(
        "SELECT id, run_count, success_count FROM routes WHERE app_id=? AND task_signature=?",
        (app_id, sig),
    ).fetchone()
    now = time.time()
    if row:
        con.execute(
            "UPDATE routes SET steps_json=?, run_count=run_count+1, "
            "success_count=success_count+1, median_turns=?, last_success=? WHERE id=?",
            (json.dumps(steps), turns, now, row["id"]),
        )
        con.commit()
        return row["id"]
    cur = con.execute(
        "INSERT INTO routes(app_id,task_signature,steps_json,run_count,success_count,median_turns,last_success) "
        "VALUES(?,?,?,1,1,?,?)",
        (app_id, sig, json.dumps(steps), turns, now),
    )
    con.commit()
    return cur.lastrowid


def record_outcome(con, verdict: str, element_id: int | None = None,
                   route_id: int | None = None, postcondition: str = "",
                   turns: int | None = None, tokens: int | None = None) -> None:
    """One write, three consumers: registry confidence, ledger evidence stream,
    and — on failure — immediate invalidation of the entry that was used."""
    con.execute(
        "INSERT INTO outcomes(route_id,element_id,ts,verdict,postcondition,turns,tokens) VALUES(?,?,?,?,?,?,?)",
        (route_id, element_id, time.time(), verdict, postcondition, turns, tokens),
    )
    if element_id is not None:
        if verdict == "pass":
            con.execute(
                "UPDATE elements SET hit_count=hit_count+1, last_confirmed=? WHERE id=?",
                (time.time(), element_id),
            )
        else:
            con.execute("UPDATE elements SET miss_count=miss_count+1 WHERE id=?", (element_id,))
    if route_id is not None and verdict != "pass":
        con.execute("UPDATE routes SET success_count=MAX(success_count-1,0) WHERE id=?", (route_id,))
    con.commit()


def invalidate_app(con, app_id: int) -> int:
    """Version-stamped bulk invalidation: zero confidence, force revalidation."""
    cur = con.execute("UPDATE elements SET last_confirmed=NULL WHERE app_id=?", (app_id,))
    con.commit()
    return cur.rowcount


# ----------------------------------------------------------------- lookups

def find_route(con, task: str, app_name: str | None = None) -> dict | None:
    sig = normalize_signature(task)
    base = ("SELECT r.*, a.name AS app_name FROM routes r JOIN apps a ON a.id=r.app_id ")
    row = con.execute(
        base + "WHERE r.task_signature=?" + (" AND a.name=?" if app_name else ""),
        (sig, app_name) if app_name else (sig,),
    ).fetchone()
    if not row:
        try:
            match = con.execute(
                "SELECT rowid FROM routes_fts WHERE routes_fts MATCH ? LIMIT 1",
                (" OR ".join(re.findall(r"[a-z]+", sig)) or sig,),
            ).fetchone()
            if match:
                row = con.execute(base + "WHERE r.id=?", (match["rowid"],)).fetchone()
        except sqlite3.OperationalError:
            row = con.execute(
                base + "WHERE r.task_signature LIKE ?", (f"%{sig.split(' ')[0]}%",)
            ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["steps"] = json.loads(d.pop("steps_json") or "[]")
    return d


def find_elements(con, app_name: str, role: str | None = None,
                  name_like: str | None = None) -> list[dict]:
    q = ("SELECT e.* FROM elements e JOIN apps a ON a.id=e.app_id WHERE a.name=?")
    params: list = [app_name]
    if role:
        q += " AND e.role=?"
        params.append(role)
    if name_like:
        q += " AND e.name_pattern LIKE ?"
        params.append(f"%{name_like}%")
    out = []
    for row in con.execute(q, params):
        d = dict(row)
        d["confidence"] = confidence(d["hit_count"], d["miss_count"], d["last_confirmed"])
        if d["confidence"] >= CONFIDENCE_FLOOR:
            out.append(d)
    return sorted(out, key=lambda d: -d["confidence"])


def app_profile(con, app_name: str) -> dict | None:
    row = con.execute("SELECT * FROM apps WHERE name=?", (app_name,)).fetchone()
    if not row:
        return None
    n_el = con.execute("SELECT COUNT(*) c FROM elements WHERE app_id=?", (row["id"],)).fetchone()["c"]
    n_rt = con.execute("SELECT COUNT(*) c FROM routes WHERE app_id=?", (row["id"],)).fetchone()["c"]
    return {**dict(row), "elements": n_el, "routes": n_rt}


if __name__ == "__main__":
    con = connect()
    if len(sys.argv) > 2 and sys.argv[1] == "app":
        print(json.dumps(app_profile(con, sys.argv[2]) or {"error": "unknown app"}, indent=2, default=str))
    elif len(sys.argv) > 2 and sys.argv[1] == "forget":
        row = con.execute("SELECT id FROM apps WHERE name=?", (sys.argv[2],)).fetchone()
        if row:
            for t in ("elements", "routes"):
                con.execute(f"DELETE FROM {t} WHERE app_id=?", (row["id"],))
            con.execute("DELETE FROM apps WHERE id=?", (row["id"],))
            con.commit()
            print(f"forgot {sys.argv[2]}")
    else:
        for r in con.execute("SELECT name, archetype, last_seen FROM apps ORDER BY last_seen DESC"):
            print(f"{r['name']:30} {r['archetype'] or '?':10} last seen {time.strftime('%Y-%m-%d', time.localtime(r['last_seen']))}")

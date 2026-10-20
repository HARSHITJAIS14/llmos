"""Per-app profiles (implementation.md §14.7): framework, learned press modes, AX speed, opaque flag.

Seeded from the codex app files. Learned keys reset when the app's version changes.
"""
from __future__ import annotations

import json
import sqlite3
import time

from ..plan.cards import seed_for

LEARNED_KEYS = ("press_mode", "type_mode", "slow_ax", "opaque", "anchors")


class Profiles:
    def __init__(self, con: sqlite3.Connection) -> None:
        self.con = con
        self._cache: dict[str, dict] = {}

    def get(self, bundle_id: str, version: str | None = None) -> dict:
        prof = self._cache.get(bundle_id)
        if prof is None:
            row = self.con.execute("SELECT profile_json, version FROM apps WHERE bundle_id=?", (bundle_id,)).fetchone()
            seed = seed_for(bundle_id)
            prof = {"seed_framework": seed.get("framework"), "codex_quirks": seed.get("quirks", [])}
            if row and row["profile_json"]:
                try:
                    prof.update(json.loads(row["profile_json"]))
                except ValueError:
                    pass
                prof["_version"] = row["version"] or ""
            self._cache[bundle_id] = prof
        if version and prof.get("_version") and prof["_version"] != version:
            for k in LEARNED_KEYS:                             # new app version: relearn
                prof.pop(k, None)
            prof["_version"] = version
            self._save(bundle_id, prof)
        return prof

    def update(self, bundle_id: str, **values) -> None:
        prof = self.get(bundle_id)
        prof.update(values)
        self._save(bundle_id, prof)

    def _save(self, bundle_id: str, prof: dict) -> None:
        body = {k: v for k, v in prof.items() if not k.startswith("_")}
        self.con.execute(
            "INSERT INTO apps(bundle_id, profile_json, version, updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(bundle_id) DO UPDATE SET profile_json=excluded.profile_json, "
            "version=COALESCE(excluded.version, apps.version), updated_at=excluded.updated_at",
            (bundle_id, json.dumps(body), prof.get("_version") or None, time.time()))
        self.con.commit()

    def forget(self) -> None:
        self.con.execute("DELETE FROM apps")
        self.con.commit()
        self._cache.clear()

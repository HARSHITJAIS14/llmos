"""Build planner app cards + profile seeds from the AX codex (implementation.md §13.2).

    python scripts/build_cards.py [../Ax_analysis/codex/apps]

Writes src/lsfg/data/codex/profiles.json and src/lsfg/data/codex/cards/<bundle_id>.md.
Cards hold UI function only: no names, messages or file names (codex privacy rule).
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT.parent / "Ax_analysis" / "codex" / "apps"
OUT = ROOT / "src" / "lsfg" / "data" / "codex"
TIER_ORDER = {"high": 0, "session": 1, "low": 2}
SEV_ORDER = {"high": 0, "medium": 1, "low": 2}
INVISIBLE = dict.fromkeys(map(ord, "‎‏‪‫‬‭‮⁦⁧⁨⁩​‌‍⁠﻿"), None)


def clean(s: str) -> str:
    return " ".join(unicodedata.normalize("NFC", str(s or "").translate(INVISIBLE)).split())


sys.path.insert(0, str(ROOT / "src"))
from lsfg.resolve.selector import fmt_clause, parse  # noqa: E402
from lsfg.types import Clause  # noqa: E402


def selector_for(anchor: dict) -> str | None:
    kind, value, role = anchor.get("kind"), anchor.get("value") or "", anchor.get("role") or None
    if not value:
        return None
    prefix = anchor.get("match") == "prefix" or value.endswith(("=", "?", ":"))
    if kind == "ax_identifier":
        c = Clause(role=role, ident=value, ident_prefix=prefix)
    elif kind == "ax_dom_identifier":
        c = Clause(role=role, dom_id=value)
    else:
        return None
    text = fmt_clause(c)
    parse(text)                                                 # every card selector must parse
    return text


def build(src: Path) -> None:
    (OUT / "cards").mkdir(parents=True, exist_ok=True)
    profiles: dict[str, dict] = {}
    for f in sorted(src.glob("*.json")):
        d = json.loads(f.read_text())
        ident = d.get("identity") or {}
        bid = ident.get("bundle_id")
        if not bid:
            continue
        name = clean(ident.get("name") or d.get("app_key"))
        fw = ident.get("framework") or "unknown"
        anchors = sorted(d.get("stable_anchors") or [], key=lambda a: (TIER_ORDER.get(a.get("tier"), 3),
                                                                       -int(a.get("seen_in_captures") or 0)))
        sels = []
        for a in anchors:
            if a.get("tier") == "low":
                continue                                        # _NS:<n> ids are build-scoped (LAW-ID-2)
            sel = selector_for(a)
            if sel:
                sels.append({"selector": sel, "purpose": clean(a.get("purpose"))[:60]})
        quirks = sorted(d.get("quirks") or [], key=lambda q: SEV_ORDER.get(q.get("severity"), 3))
        readiness = d.get("readiness") or {}
        acts = d.get("action_capability") or {}
        profiles[bid] = {
            "name": name, "framework": fw, "match": ident.get("bundle_id_match", "exact"),
            "anchors": sels[:20], "quirks": [q.get("kind") for q in quirks],
            "act_needs_activation": bool((readiness.get("needs_activation") or {}).get("act")),
            "text_entry": acts.get("text_entry"),
        }
        lines = [f"## {name} ({bid}) · {fw}"]
        if sels:
            lines.append("Anchors: " + " · ".join(f"{a['selector']} {a['purpose']}" for a in sels[:12]))
        for q in quirks[:5]:
            lines.append(f"Quirk {q.get('kind')}: {clean(q.get('workaround'))[:140]}")
        if profiles[bid]["act_needs_activation"]:
            lines.append("Its window is often hidden: the executor activates it before typing or pointer clicks.")
        (OUT / "cards" / f"{bid}.md").write_text("\n".join(lines) + "\n")
    (OUT / "profiles.json").write_text(json.dumps(profiles, indent=1, ensure_ascii=False))
    print(f"{len(profiles)} app cards → {OUT}")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC)

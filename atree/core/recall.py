"""The L1→L2→L3 lookup chain (pitch §5.3) — the pre-flight for every task.

Every task begins with a lookup, not a snapshot:

  L1  route hit    this exact task has been done   -> replay, 1 turn
  L2  element hit  app mapped, target known        -> resolve path, 2-3 turns
  L3  archetype    app unseen, class understood    -> informed discovery
  miss             cold                            -> full discovery

Every run promotes downward: cold discovery populates L2; an L2 path walked
twice the same way compiles into an L1 route.
"""
from __future__ import annotations

import json
import re
import sys

from . import registry


def recall(task: str, app_name: str | None = None, con=None) -> dict:
    con = con or registry.connect()

    route = registry.find_route(con, task, app_name)
    if route:
        return {
            "level": "L1",
            "route_id": route["id"],
            "app": route["app_name"],
            "task_signature": route["task_signature"],
            "steps": route["steps"],
            "stats": {"runs": route["run_count"], "successes": route["success_count"],
                      "median_turns": route["median_turns"]},
            "advice": "Replay these steps in order via `agent-desktop batch`; "
                      "declare each step's postcondition first. On any postcondition "
                      "failure, stop replay and fall back to discovery for that step.",
        }

    if app_name:
        keywords = [w for w in re.findall(r"[A-Za-z]{3,}", task)][:5]
        elements: list[dict] = []
        seen = set()
        for kw in keywords:
            for el in registry.find_elements(con, app_name, name_like=kw):
                if el["id"] not in seen:
                    seen.add(el["id"])
                    elements.append(el)
        profile = registry.app_profile(con, app_name)
        if elements:
            return {
                "level": "L2",
                "app": app_name,
                "archetype": (profile or {}).get("archetype", ""),
                "elements": [
                    {"identity_path": e["identity_path"], "role": e["role"],
                     "name": e["name_pattern"], "reach_strategy": e["reach_strategy"],
                     "verify_strategy": e["verify_strategy"],
                     "confidence": round(e["confidence"], 2)}
                    for e in elements[:10]
                ],
                "advice": "Known elements listed with their working reach strategies. "
                          "Resolve each identity_path against ONE fresh skeleton "
                          "snapshot to get live refs — do not re-explore.",
            }
        if profile:
            return {
                "level": "L3",
                "app": app_name,
                "archetype": profile.get("archetype", ""),
                "advice": f"App is known ({profile['elements']} elements, "
                          f"{profile['routes']} routes) but nothing matches this task. "
                          f"Run `ax guide {app_name}` for the {profile.get('archetype') or 'relevant'} "
                          "archetype's quirks, then discover; deposits will fill L2.",
            }

    return {
        "level": "miss",
        "app": app_name,
        "advice": "Cold. Run `ax guide <App>` (or `ax guide index`) for the "
                  "archetype's quirks and strategies, then skeleton-first discovery.",
    }


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else ""
    app = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(recall(task, app), indent=2))

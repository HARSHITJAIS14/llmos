"""JEV latency vs option count and question count. Sends ONLY synthetic, non-personal data.
Result on 2026-09-30: cold 613 ms; warm 342-410 ms (10-200 options, 1 question);
406-505 ms (4 questions x 100 options); ~42 input tokens per option; model jev-1.13.0.
Key: $TYPESAFE_API_KEY, else ~/.lsfg/.env, else ../../../arc-cua/.env. The key is never printed."""
import os
import pathlib
import time

import httpx


def load_key():
    if os.environ.get("TYPESAFE_API_KEY"):
        return os.environ["TYPESAFE_API_KEY"]
    here = pathlib.Path(__file__).resolve()
    for p in (pathlib.Path.home() / ".lsfg" / ".env", here.parents[3] / "arc-cua" / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith("TYPESAFE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("TYPESAFE_API_KEY not found")


KEY = load_key()
URL = "https://api.typesafe.ai/v1/systemone"
client = httpx.Client(http2=True, timeout=10)


def call(n_opts, n_q):
    crit = {f"e{i}": {"role": "button", "label": f"Item number {i}", "where": "list"} for i in range(n_opts)}
    crit["e7"] = {"role": "button", "label": "New Tab", "where": "toolbar"}
    crit["NONE"] = "No listed element matches."
    qs = {f"q{j}": {"type": "choice", "instructions": "Pick the element that opens a new browser tab.",
                    "criteria": crit} for j in range(n_q)}
    body = {"model": "jev-latest", "state": {"task": "open a new tab in the browser", "app": "Browser"},
            "questions": qs}
    t0 = time.perf_counter()
    r = client.post(URL, json=body, headers={"Authorization": f"Bearer {KEY}"})
    ms = (time.perf_counter() - t0) * 1000
    j = r.json() if r.status_code == 200 else {}
    a = j.get("answers", {}).get("q0", {})
    return ms, r.status_code, a.get("choice"), a.get("confidence"), j.get("usage"), j.get("model")


for label, args in [("cold 10x1", (10, 1)), ("10x1", (10, 1)), ("10x1", (10, 1)), ("100x1", (100, 1)),
                    ("100x1", (100, 1)), ("200x1", (200, 1)), ("200x1", (200, 1)), ("100x4", (100, 4)),
                    ("100x4", (100, 4))]:
    ms, st, ch, conf, usage, model = call(*args)
    print(f"{label:10} {ms:6.0f} ms  status={st} choice={ch} conf={conf} usage={usage} model={model}")

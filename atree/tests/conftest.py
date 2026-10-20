import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    data = json.loads((FIXTURES / name).read_text())
    if "data" in data and isinstance(data["data"], dict) and "tree" in data["data"]:
        return data["data"]["tree"]
    return data.get("tree", data)


@pytest.fixture
def fixture_pairs():
    """Consecutive-state pairs salvaged from real ATree_tool runs."""
    return [
        ("whatsapp step1->2", load_fixture("whatsapp_step1.json"), load_fixture("whatsapp_step2.json")),
        ("whatsapp step3->4", load_fixture("whatsapp_step3.json"), load_fixture("whatsapp_step4.json")),
        ("calendar step2->5", load_fixture("calendar_step2.json"), load_fixture("calendar_step5.json")),
    ]

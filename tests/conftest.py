import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "contributions.json"


@pytest.fixture
def data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))

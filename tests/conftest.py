import json
from pathlib import Path
import pytest


@pytest.fixture
def tmp_canon(tmp_path: Path) -> Path:
    """A throwaway canon root with the real schemas copied in."""
    root = tmp_path / "canon"
    (root / "_schema").mkdir(parents=True)
    repo_schema = Path(__file__).parent.parent / "canon" / "_schema"
    for f in repo_schema.glob("*.json"):
        (root / "_schema" / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    return root

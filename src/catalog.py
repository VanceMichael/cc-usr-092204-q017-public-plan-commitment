import json
from pathlib import Path

from src.validation import require_valid

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
CONTRACTS = ROOT / "contracts"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_context(path: Path | None = None) -> dict:
    source = path or FIXTURES / "context.json"
    data = _read_json(source)
    require_valid(data, _read_json(CONTRACTS / "context.schema.json"))
    return data


def load_domain(path: Path | None = None, *, validate: bool = True) -> dict:
    """载入领域包；默认按契约校验，保证交换语义一致。"""
    source = path or FIXTURES / "domain.json"
    data = _read_json(source)
    if validate:
        require_valid(data, _read_json(CONTRACTS / "domain.schema.json"))
    return data


def load_feedback(path: Path | None = None, *, validate: bool = True) -> dict:
    source = path or FIXTURES / "feedback.json"
    data = _read_json(source)
    if validate:
        require_valid(data, _read_json(CONTRACTS / "feedback.schema.json"))
    return data

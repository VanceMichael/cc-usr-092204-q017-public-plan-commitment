"""证据快照的规范序列化与哈希：监督人员据此复核快照未被篡改。"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def evidence_fingerprint(evidence: dict) -> str:
    """重算证据快照哈希（取排除 sha256 字段后的规范序列化）。"""
    body = {k: v for k, v in evidence.items() if k != "sha256"}
    return canonical_sha256(body)

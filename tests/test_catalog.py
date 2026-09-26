import unittest

from src.catalog import load_context, load_domain, load_feedback
from src.validation import SchemaError, validate


class CatalogTest(unittest.TestCase):
    def test_context_has_domain_facts(self) -> None:
        context = load_context()
        self.assertTrue(context["project"])
        self.assertGreaterEqual(len(context["facts"]), 3)
        self.assertGreaterEqual(len(context["actors"]), 3)
        self.assertTrue(context["sample_id"])

    def test_domain_package_contract(self) -> None:
        domain = load_domain()
        self.assertEqual(len(domain["targets"]), 6)
        self.assertEqual(domain["rules_version"], "status-rules-v1.0")
        # 19.6 万公营房屋目标按首发口径锁定
        hs = next(t for t in domain["targets"] if t["target_id"] == "T-HS-01")
        self.assertEqual(hs["target_value"], 196000)
        self.assertTrue(hs["locked"])
        # 每条证据都有完整性哈希
        for e in domain["evidence"]:
            self.assertRegex(e["sha256"], r"^[0-9a-f]{64}$")

    def test_feedback_package_contract(self) -> None:
        pack = load_feedback()
        self.assertGreaterEqual(len(pack["organizations"]), 3)
        for case in pack["cases"]:
            self.assertTrue(case["consent"]["grant"])

    def test_invalid_payload_rejected(self) -> None:
        from pathlib import Path
        import json
        from src.validation import require_valid
        schema = json.loads(
            (Path(__file__).resolve().parents[1]
             / "contracts" / "context.schema.json").read_text(encoding="utf-8"))
        with self.assertRaises(SchemaError):
            require_valid({"project": "x"}, schema)

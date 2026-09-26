import unittest
from copy import deepcopy

from src.catalog import load_domain
from src.governance import Governance, GovernanceError


def revision(**overrides) -> dict:
    base = {
        "revision_id": "REV-TEST",
        "at": "2026-09-20T10:00:00+08:00",
        "plan_id": "PLAN-2627",
        "target_id": "T-HS-01",
        "milestone_id": "MS-HS01-Q6",
        "kind": "reschedule",
        "touches_five_year_target": False,
        "reason": "测试用路径调整",
        "evidence_ids": [],
        "by_org": "HB",
        "decided_by": "测试会议",
        "old": {},
        "new": {"forecast_date": "2026-12-20"},
    }
    base.update(overrides)
    return base


class GovernanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.gov = Governance(load_domain())

    def test_path_reschedule_accepted_and_does_not_alter_target(self) -> None:
        before = self.gov.targets["T-HS-01"]["target_value"]
        result = self.gov.apply_revision(revision())
        self.assertTrue(result["accepted"])
        self.assertEqual(self.gov.targets["T-HS-01"]["target_value"], before)

    def test_locked_target_value_rewrite_rejected_and_logged(self) -> None:
        bad = revision(new={"target_value": 180000},
                       reason="以建造能力不足为由下调")
        with self.assertRaises(GovernanceError):
            self.gov.apply_revision(bad)
        history = self.gov.targets["T-HS-01"]["history"]
        self.assertEqual(history[-1]["event"], "rewrite_rejected")
        self.assertIn("180000", history[-1]["detail"])
        # 被拒绝的修订不得进入修订流水
        self.assertNotIn("REV-TEST",
                         {r["revision_id"] for r in self.gov.domain["revisions"]})

    def test_path_change_cannot_claim_five_year_target(self) -> None:
        bad = revision(kind="path_change", touches_five_year_target=True)
        with self.assertRaises(GovernanceError):
            self.gov.apply_revision(bad)

    def test_rebaseline_requires_bridge(self) -> None:
        bad = revision(
            revision_id="REV-TEST2", target_id="T-DH-01",
            milestone_id="MS-DH01-Q6", kind="metric_rebaseline",
            touches_five_year_target=True,
            new={"metric_version": "v2"})  # 无 bridge_id
        with self.assertRaises(GovernanceError) as ctx:
            self.gov.apply_revision(bad)
        self.assertIn("桥接", str(ctx.exception))

    def test_rebaseline_equivalent_target_must_match_bridge(self) -> None:
        # 800000(v1) × 1.25 = 1000000(v2)；虚报 900000 必须被拒
        bad = revision(
            revision_id="REV-TEST3", target_id="T-DH-01",
            milestone_id="MS-DH01-Q6", kind="metric_rebaseline",
            touches_five_year_target=True,
            new={"metric_version": "v2", "bridge_id": "BR-DHC-01",
                 "target_value_equivalent": 900000})
        with self.assertRaises(GovernanceError):
            self.gov.apply_revision(bad)

    def test_rebaseline_with_correct_equivalent_accepted(self) -> None:
        ok = revision(
            revision_id="REV-TEST4", target_id="T-DH-01",
            milestone_id="MS-DH01-Q6", kind="metric_rebaseline",
            touches_five_year_target=True,
            new={"metric_version": "v2", "bridge_id": "BR-DHC-01",
                 "target_value_equivalent": 1000000})
        self.assertTrue(self.gov.apply_revision(ok)["accepted"])

    def test_duplicate_revision_rejected(self) -> None:
        with self.assertRaises(GovernanceError):
            self.gov.apply_revision(revision(revision_id="REV-001"))


if __name__ == "__main__":
    unittest.main()

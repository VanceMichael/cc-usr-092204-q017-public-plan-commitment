import copy
import unittest
from datetime import date
from pathlib import Path

from src import assess
from src.catalog import (
    DataIntegrityError,
    Registry,
    feedback_authorized,
    load_registry,
    oversight_pledge_view,
    pledge_statuses,
    public_pledge_view,
    public_site,
)

AS_OF = date(2026, 9, 26)


def fixture_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures"


def _read_json(name: str) -> dict:
    import json

    return json.loads((fixture_dir() / name).read_text(encoding="utf-8"))


def registry_with(**overrides) -> Registry:
    """从磁盘构造资料，可替换任一文档，用于负面用例。"""
    docs = {
        "context": _read_json("context.json"),
        "pledges_doc": _read_json("pledges.json"),
        "initiatives_doc": _read_json("initiatives.json"),
        "progress_doc": _read_json("progress.json"),
        "governance_doc": _read_json("governance.json"),
    }
    docs.update(overrides)
    return Registry(**docs)


class RegistryLoadingTest(unittest.TestCase):
    def test_fixtures_load_and_validate(self) -> None:
        reg = load_registry()
        self.assertEqual(len(reg.pledges), 5)
        self.assertEqual(reg.pledge("P-HOUSING")["five_year_target"], 196000)

    def test_context_has_domain_facts(self) -> None:
        reg = load_registry()
        self.assertTrue(reg.context["project"])
        self.assertGreaterEqual(len(reg.context["facts"]), 3)


class ClassificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = load_registry()
        self.housing = self.reg.pledge("P-HOUSING")

    def test_housing_watch_with_provisional_data(self) -> None:
        # 截至 2026-09-26：插值应完成约 89,616，初步实测 84,200，缺口约 6%（预警区间）。
        result = assess.assess_pledge(
            self.housing, self.reg.measurements, self.reg.bases_by_id, AS_OF
        )
        self.assertEqual(result["confidence"], assess.PROVISIONAL)
        self.assertEqual(result["status"], assess.WATCH)
        self.assertGreater(result["gap_pct"], self.housing["warning_pct"])
        self.assertLess(result["gap_pct"], self.housing["breach_pct"])

    def test_subdivided_on_track(self) -> None:
        pledge = self.reg.pledge("P-SUBDIVIDED")
        result = assess.assess_pledge(
            pledge, self.reg.measurements, self.reg.bases_by_id, AS_OF
        )
        self.assertEqual(result["status"], assess.ON_TRACK)
        self.assertEqual(result["confidence"], assess.VERIFIED)
        self.assertIsNotNone(result["next_milestone"])

    def test_beds_off_track_with_overdue_cross_agency_data(self) -> None:
        pledge = self.reg.pledge("P-HOSP-BEDS")
        result = assess.assess_pledge(
            pledge, self.reg.measurements, self.reg.bases_by_id, AS_OF
        )
        # 数据截止 2025-12-31，滞后 120 天后早已超期 -> 迟到待报
        self.assertEqual(result["confidence"], assess.OVERDUE_PENDING)
        self.assertEqual(result["status"], assess.OFF_TRACK)

    def test_no_measurement_yields_watch_and_overdue(self) -> None:
        pledge = copy.deepcopy(self.housing)
        result = assess.assess_pledge(pledge, [], self.reg.bases_by_id, AS_OF)
        self.assertIsNone(result["actual"])
        self.assertEqual(result["confidence"], assess.OVERDUE_PENDING)
        self.assertEqual(result["status"], assess.WATCH)

    def test_threshold_boundaries(self) -> None:
        self.assertEqual(assess.classify(0.039, 0.04, 0.10), assess.ON_TRACK)
        self.assertEqual(assess.classify(0.04, 0.04, 0.10), assess.WATCH)
        self.assertEqual(assess.classify(0.10, 0.04, 0.10), assess.OFF_TRACK)


class InterpolationTest(unittest.TestCase):
    def test_milestone_anchor_values(self) -> None:
        reg = load_registry()
        pledge = reg.pledge("P-HOUSING")
        self.assertEqual(
            assess.interpolate_expected(pledge, date(2026, 3, 31)), 70000.0
        )
        self.assertEqual(
            assess.interpolate_expected(pledge, date(2029, 3, 31)), 196000.0
        )
        self.assertEqual(
            assess.interpolate_expected(pledge, date(2024, 4, 1)), 0.0
        )
        self.assertEqual(
            assess.interpolate_expected(pledge, date(2030, 1, 1)), 196000.0
        )

    def test_linear_midpoint(self) -> None:
        reg = load_registry()
        pledge = reg.pledge("P-HOUSING")
        # M2(70,000@2026-03-31) 与 M3(110,000@2027-03-31) 之间插值
        mid = assess.interpolate_expected(pledge, date(2026, 9, 30))
        fraction = 183 / 365
        self.assertAlmostEqual(mid, 70000 + 40000 * fraction, places=1)
        # 判定基准日 2026-09-26 的应完成量介于 M2 与 M3 之间
        expected = assess.interpolate_expected(pledge, AS_OF)
        self.assertTrue(70000 < expected < 110000)


class BasisBridgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = load_registry()

    def test_old_basis_value_bridged_to_current(self) -> None:
        value, chain = assess.bridge_to_current(
            86000, "B-DHC-A", "B-DHC-B", self.reg.bases_by_id
        )
        self.assertAlmostEqual(value, 86000 * 0.82 - 3000)  # 67,520
        self.assertEqual(chain, ["B-DHC-A", "B-DHC-B"])

    def test_health_assessment_uses_bridged_history(self) -> None:
        pledge = self.reg.pledge("P-HEALTH-DHC")
        at_old = date(2026, 2, 28)  # 只有旧口径数据
        result = assess.assess_pledge(
            pledge, self.reg.measurements, self.reg.bases_by_id, at_old
        )
        self.assertEqual(result["bridged_from"], "B-DHC-A")
        self.assertEqual(result["basis_chain"], ["B-DHC-A", "B-DHC-B"])
        self.assertEqual(result["actual"], 67520)

    def test_missing_bridge_raises(self) -> None:
        bases = {"B-X": {"basis_id": "B-X"}}
        with self.assertRaises(ValueError):
            assess.bridge_to_current(1, "B-X", "B-Y", bases)


class DeterminismTest(unittest.TestCase):
    def test_same_inputs_same_hash_and_result(self) -> None:
        reg = load_registry()
        pledge = reg.pledge("P-SUBDIVIDED")
        r1 = assess.assess_pledge(pledge, reg.measurements, reg.bases_by_id, AS_OF)
        r2 = assess.assess_pledge(pledge, reg.measurements, reg.bases_by_id, AS_OF)
        self.assertEqual(r1, r2)
        self.assertEqual(len(r1["basis_hash"]), 16)

    def test_timeline_replays_historical_status(self) -> None:
        reg = load_registry()
        pledge = reg.pledge("P-HOSP-BEDS")
        timeline = assess.status_timeline(
            pledge,
            reg.measurements,
            reg.bases_by_id,
            [date(2025, 6, 1), date(2026, 4, 30), AS_OF],
        )
        self.assertEqual([row["as_of"] for row in timeline],
                         ["2025-06-01", "2026-04-30", "2026-09-26"])
        # 2025-06-01 病床尚未有数据 -> 迟到待报
        self.assertEqual(timeline[0]["confidence"], assess.OVERDUE_PENDING)


class GovernanceValidationTest(unittest.TestCase):
    def test_pathway_revision_cannot_silently_change_target(self) -> None:
        initiatives = copy.deepcopy(_read_json("initiatives.json"))
        for item in initiatives["initiatives"]:
            if item["initiative_id"] == "I-H3":
                item["target_altered"] = True  # 路径重排却声称改目标
        with self.assertRaises(DataIntegrityError):
            registry_with(initiatives_doc=initiatives)

    def test_target_change_requires_revision_chain(self) -> None:
        # 删掉正式目标修订，但保留项目上的 target_altered 标记
        governance = copy.deepcopy(_read_json("governance.json"))
        governance["revisions"] = [
            r for r in governance["revisions"] if r["revision_id"] != "R-2025-TG1"
        ]
        with self.assertRaises(DataIntegrityError):
            registry_with(governance_doc=governance)

    def test_rewritten_history_target_detected(self) -> None:
        # 偷偷把修订的 old_target 改掉，制造历史断链
        governance = copy.deepcopy(_read_json("governance.json"))
        for r in governance["revisions"]:
            if r["revision_id"] == "R-2025-TG1":
                r["old_target"] = 59000
        with self.assertRaises(DataIntegrityError):
            registry_with(governance_doc=governance)

    def test_current_target_must_equal_chain_end(self) -> None:
        pledges = copy.deepcopy(_read_json("pledges.json"))
        for p in pledges["pledges"]:
            if p["pledge_id"] == "P-YOUTH":
                p["five_year_target"] = 60000  # 与修订链末端 54,000 不符
                p["milestones"][-1]["cumulative_target"] = 60000
        with self.assertRaises(DataIntegrityError):
            registry_with(pledges_doc=pledges)

    def test_measurement_requires_existing_basis_and_evidence(self) -> None:
        progress = copy.deepcopy(_read_json("progress.json"))
        progress["measurements"][0]["evidence_ids"] = ["EV-DOES-NOT-EXIST"]
        with self.assertRaises(DataIntegrityError):
            registry_with(progress_doc=progress)

    def test_unknown_feedback_case_rejected(self) -> None:
        governance = copy.deepcopy(_read_json("governance.json"))
        governance["feedback"][0]["case_ref"] = "CASE-SD-2026-9999"
        with self.assertRaises(DataIntegrityError):
            registry_with(governance_doc=governance)

    def test_expired_authorization_rejected(self) -> None:
        governance = copy.deepcopy(_read_json("governance.json"))
        governance["feedback"][0]["authorization"]["granted_until"] = "2026-01-01"
        with self.assertRaises(DataIntegrityError):
            registry_with(governance_doc=governance)

    def test_embargoed_site_address_must_be_absent(self) -> None:
        governance = copy.deepcopy(_read_json("governance.json"))
        for site in governance["sites"]:
            if site["site_id"] == "S-HSE-EMB1":
                site["address"] = "某乡事会路某号（未刊宪）"
        with self.assertRaises(DataIntegrityError):
            registry_with(governance_doc=governance)

    def test_dangling_site_reference_rejected(self) -> None:
        initiatives = copy.deepcopy(_read_json("initiatives.json"))
        initiatives["initiatives"][0]["site_ids"].append("S-GHOST")
        with self.assertRaises(DataIntegrityError):
            registry_with(initiatives_doc=initiatives)


class AuthorizationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fb = load_registry().feedback[0]

    def test_authorized_within_window(self) -> None:
        self.assertTrue(feedback_authorized(self.fb, date(2026, 9, 26)))
        self.assertFalse(feedback_authorized(self.fb, date(2027, 8, 1)))


class ViewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = load_registry()

    def test_status_board_covers_all_pledges(self) -> None:
        board = pledge_statuses(self.reg, AS_OF)
        self.assertEqual({row["pledge_id"] for row in board},
                         {p["pledge_id"] for p in self.reg.pledges})

    def test_public_view_hides_embargoed_location(self) -> None:
        view = public_pledge_view(self.reg, "P-HOUSING", AS_OF)
        embargoed = [s for s in view["sites"] if s["disclosure_status"] == "embargoed"]
        self.assertTrue(embargoed)
        self.assertIsNone(embargoed[0]["address"])
        public = [s for s in view["sites"] if s["disclosure_status"] == "public"]
        self.assertIsNotNone(public[0]["address"])
        # 公众视图不含任何个案反馈
        self.assertNotIn("authorized_case_feedback", view)

    def test_public_site_helper(self) -> None:
        site = next(s for s in self.reg.sites if s["site_id"] == "S-BED-EMB1")
        self.assertIsNone(public_site(site)["address"])

    def test_delay_explanation_exposed_for_rephased_pathway(self) -> None:
        view = public_pledge_view(self.reg, "P-HOUSING", AS_OF)
        self.assertEqual(view["delay_explanation"]["revision_id"], "R-2025-PW1")
        self.assertIn("196,000", view["delay_explanation"]["explanation"])

    def test_youth_target_revision_visible_with_original_and_current(self) -> None:
        view = public_pledge_view(self.reg, "P-YOUTH", AS_OF)
        self.assertEqual(view["original_target"], 60000)
        self.assertEqual(view["five_year_target"], 54000)

    def test_oversight_view_exposes_chain_timeline_and_feedback(self) -> None:
        view = oversight_pledge_view(self.reg, "P-SUBDIVIDED", AS_OF)
        self.assertIn("basis_hash", view["decision_basis"])
        self.assertIn("rule", view["decision_basis"])
        self.assertTrue(view["status_timeline"])
        fb = view["authorized_case_feedback"]
        self.assertEqual(len(fb), 1)
        self.assertTrue(fb[0]["authorized_now"])
        # 反馈仅含去标识栏位，不含姓名与地址
        self.assertNotIn("address", fb[0])
        # 监督视图可见未公开选址但带敏感标记（未公开选址挂在房屋目标下）
        housing_internal = oversight_pledge_view(self.reg, "P-HOUSING", AS_OF)["sites_internal"]
        self.assertTrue(any(s["sensitivity"] == "embargoed-internal" for s in housing_internal))
        # 劏房目标无选址关联，监督视图给出空列表而非泄漏任何地址
        self.assertEqual(view["sites_internal"], [])

    def test_oversight_timeline_reproduces_why_status_was_assigned(self) -> None:
        view = oversight_pledge_view(self.reg, "P-HOSP-BEDS", AS_OF)
        rows = view["status_timeline"]
        # 每个时点都带独立 basis_hash，可逐点复核判定依据
        self.assertTrue(all(len(r["basis_hash"]) == 16 for r in rows))
        self.assertEqual(rows[-1]["status"], "off_track")


if __name__ == "__main__":
    unittest.main()

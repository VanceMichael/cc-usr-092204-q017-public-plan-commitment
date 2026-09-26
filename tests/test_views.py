import unittest
from datetime import datetime

from src.catalog import load_domain, load_feedback
from src import views
from src.engine import StatusEngine

AT_NOW = datetime.fromisoformat("2026-09-26T12:00:00+08:00")


class ViewsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.domain = load_domain()
        self.feedback = load_feedback()
        self.engine = StatusEngine(self.domain)

    # ---------- 空间项目脱敏 ----------

    def test_classified_site_never_leaks(self) -> None:
        rows = views.public_spatial_projects(self.domain["spatial_projects"])
        serialized = str(rows)
        self.assertNotIn("site_location_classified", serialized)
        self.assertNotIn("SECRET", serialized)
        secret = next(r for r in rows if r["spatial_project_id"] == "SP-HS-02")
        self.assertEqual(secret["granularity"], "district_only")
        self.assertFalse(secret["site_public"])
        public = next(r for r in rows if r["spatial_project_id"] == "SP-HS-01")
        self.assertEqual(public["granularity"], "site")

    # ---------- 市民 / 监督视图 ----------

    def test_public_view_has_latest_delay_and_next_node(self) -> None:
        ev = self.engine.evaluate_target("T-HC-01", AT_NOW)
        view = views.public_target(ev)
        self.assertIn("latest_result", view)
        self.assertEqual(view["delay_explanation"]["revision_id"], "REV-003")
        self.assertIn("顺延", view["delay_explanation"]["reason"])
        self.assertTrue(view["next_milestone"])
        # 市民视图不附内部判定输入，但保留可引用的证据编号
        self.assertNotIn("oversight", view)
        self.assertTrue(view["latest_result"]["evidence_id"])
        for m in view["milestones"]:
            self.assertNotIn("inputs", m)

    def test_oversight_view_contains_verifiable_inputs(self) -> None:
        ev = self.engine.evaluate_target("T-HS-01", AT_NOW)
        view = views.oversight_target(ev)
        inputs = view["oversight"]["milestone_inputs"]["MS-HS01-Q5"]
        self.assertTrue(inputs["hash_ok"])
        self.assertIn("RULE-DATA-LATE", inputs["rule_codes"])

    # ---------- 社区组织鉴权 ----------

    def test_org_reads_only_own_cases(self) -> None:
        rows = views.cases_for_org(self.feedback, "CSO-KT", "TOKEN-KT-DEMO-001")
        self.assertEqual({c["case_ref"] for c in rows}, {"CASE-2026-0001"})

    def test_bad_token_denied(self) -> None:
        with self.assertRaises(views.AccessDenied):
            views.cases_for_org(self.feedback, "CSO-KT", "WRONG")

    def test_public_case_feed_is_pseudonymous(self) -> None:
        rows = views.public_cases(self.feedback)
        text = str(rows)
        self.assertNotIn("record_ref_hash", text)
        self.assertNotIn("access_token", text)
        self.assertNotIn("PSN-", text)  # 公开视图不展示假名令牌原值
        for r in rows:
            self.assertNotIn("consent", r)

    # ---------- 提交校验 ----------

    def _payload(self, **over) -> dict:
        base = {
            "case_ref": "CASE-2026-0100",
            "target_id": "T-SF-01",
            "issue_domain": "subdivided_flats",
            "consent": {
                "grant": True,
                "scope_codes": ["subdivided_flats"],
                "granted_at": "2026-09-20T10:00:00+08:00",
                "record_ref_hash": "a" * 64,
                "expires_at": None,
            },
            "resident": {"pseudonym": "PSN-ABC12345", "district": "观塘"},
            "summary": "单位水渠渗漏，业主拒绝维修，请求转介。",
        }
        base.update(over)
        return base

    def test_valid_submission_normalized(self) -> None:
        rec = views.validate_submission(
            self.feedback, self._payload(), "CSO-KT", "TOKEN-KT-DEMO-001",
            now=AT_NOW)
        self.assertEqual(rec["status"], "received")
        self.assertEqual(rec["org_code"], "CSO-KT")

    def test_submission_without_consent_rejected(self) -> None:
        payload = self._payload()
        payload["consent"]["grant"] = False
        with self.assertRaises(views.SubmissionError):
            views.validate_submission(
                self.feedback, payload, "CSO-KT", "TOKEN-KT-DEMO-001")

    def test_submission_outside_org_scope_rejected(self) -> None:
        # CSO-KT 不获授权处理 district_health
        payload = self._payload(
            target_id="T-DH-01", issue_domain="district_health",
            consent={
                "grant": True, "scope_codes": ["district_health"],
                "granted_at": "2026-09-20T10:00:00+08:00",
                "record_ref_hash": "a" * 64, "expires_at": None})
        with self.assertRaises(views.SubmissionError):
            views.validate_submission(
                self.feedback, payload, "CSO-KT", "TOKEN-KT-DEMO-001")

    def test_submission_outside_district_rejected(self) -> None:
        payload = self._payload(
            resident={"pseudonym": "PSN-ABC12345", "district": "中环"})
        with self.assertRaises(views.SubmissionError):
            views.validate_submission(
                self.feedback, payload, "CSO-KT", "TOKEN-KT-DEMO-001")

    def test_submission_with_pii_rejected(self) -> None:
        payload = self._payload(summary="联络电话 9123 4567，身份证 A123456(7)")
        with self.assertRaises(views.SubmissionError) as ctx:
            views.validate_submission(
                self.feedback, payload, "CSO-KT", "TOKEN-KT-DEMO-001")
        self.assertIn("个人信息", str(ctx.exception))

    def test_expired_consent_rejected(self) -> None:
        payload = self._payload()
        payload["consent"]["expires_at"] = "2026-01-01T00:00:00+08:00"
        with self.assertRaises(views.SubmissionError):
            views.validate_submission(
                self.feedback, payload, "CSO-KT", "TOKEN-KT-DEMO-001", now=AT_NOW)


if __name__ == "__main__":
    unittest.main()

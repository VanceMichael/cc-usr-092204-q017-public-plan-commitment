import unittest
from datetime import datetime

from src.catalog import load_domain
from src.engine import RULES_VERSION, StatusEngine

AT_NOW = datetime.fromisoformat("2026-09-26T12:00:00+08:00")
AT_AUG = datetime.fromisoformat("2026-08-01T12:00:00+08:00")
AT_SEP01 = datetime.fromisoformat("2026-09-01T12:00:00+08:00")
AT_JUL15 = datetime.fromisoformat("2026-07-15T12:00:00+08:00")


def ms(evaluation, milestone_id: str) -> dict:
    return next(m for m in evaluation["milestones"]
                if m["milestone_id"] == milestone_id)


class EngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = StatusEngine(load_domain())

    # ---------- 当前判定 ----------

    def test_housing_units_on_track_provisional_after_late_data(self) -> None:
        row = ms(self.engine.evaluate_target("T-HS-01", AT_NOW), "MS-HS01-Q5")
        self.assertEqual(row["status"], "on_track")
        self.assertEqual(row["confidence"], "provisional")  # 覆盖率 0.85、迟到
        self.assertTrue(row["inputs"]["hash_ok"])

    def test_waiting_time_off_track_minimize_metric(self) -> None:
        # 轮候 4.9 年 vs 计划 4.8 年（越小越好）：达成率 0.8 → 偏离
        row = ms(self.engine.evaluate_target("T-HS-02", AT_NOW), "MS-HS02-Q5")
        self.assertEqual(row["status"], "off_track")
        self.assertAlmostEqual(row["inputs"]["attainment_ratio"], 0.8)

    def test_subdivided_flats_missing_data_past_grace_with_revision(self) -> None:
        row = ms(self.engine.evaluate_target("T-SF-01", AT_NOW), "MS-SF01-Q5")
        self.assertEqual(row["status"], "off_track")
        self.assertEqual(row["confidence"], "missing")
        self.assertIsNone(row["observed_value"])
        self.assertIn("RULE-DATA-MISSING-REV-ACK", row["inputs"]["rule_codes"])

    def test_within_grace_is_pending_data(self) -> None:
        row = ms(self.engine.evaluate_target("T-SF-01", AT_JUL15), "MS-SF01-Q5")
        self.assertEqual(row["status"], "pending_data")
        self.assertEqual(row["confidence"], "missing")

    def test_beds_at_risk_and_future_reschedule_flagged(self) -> None:
        ev = self.engine.evaluate_target("T-HC-01", AT_NOW)
        self.assertEqual(ms(ev, "MS-HC01-Q5")["status"], "at_risk")  # 700/750
        q6 = ms(ev, "MS-HC01-Q6")
        self.assertEqual(q6["status"], "at_risk")  # 未到期但已预测顺延
        self.assertEqual(q6["forecast_date"], "2027-01-31")
        self.assertIn("REV-003", q6["inputs"]["applied_revision_ids"])

    def test_youth_done(self) -> None:
        row = ms(self.engine.evaluate_target("T-YT-01", AT_NOW), "MS-YT01-Q5")
        self.assertEqual(row["status"], "done")

    # ---------- 口径桥接进入判定 ----------

    def test_observed_bridged_to_locked_target_version(self) -> None:
        ev = self.engine.evaluate_target("T-DH-01", AT_NOW)
        latest = ev["latest_result"]
        # v2 实测 251000 人次，换算回锁定的 v1 口径应为 200800
        self.assertEqual(latest["metric_version"], "v2")
        self.assertEqual(latest["value_observed"], 251000)
        self.assertAlmostEqual(latest["value_in_locked_version"], 200800)
        self.assertTrue(latest["conversion_to_locked"])

    # ---------- 时点重放 ----------

    def test_replay_excludes_late_evidence_within_grace(self) -> None:
        # 8 月 1 日：HD 数据未送达，尚在宽限 → 待数据/缺报
        row = ms(self.engine.evaluate_target("T-HS-01", AT_AUG), "MS-HS01-Q5")
        self.assertEqual(row["status"], "pending_data")
        self.assertIsNone(row["inputs"]["evidence_id"])

    def test_replay_excludes_late_evidence_past_grace_no_revision(self) -> None:
        # 9 月 1 日：宽限已过、数据仍缺、且无修订确认 → 预警
        ev = self.engine.evaluate_target("T-HS-01", AT_SEP01)
        row = ms(ev, "MS-HS01-Q5")
        self.assertEqual(row["status"], "at_risk")
        self.assertIn("RULE-DATA-MISSING-GRACE", row["inputs"]["rule_codes"])
        # 数据迟到通知在该时点生效
        self.assertTrue(ev["data_notices"])

    def test_replay_future_revision_does_not_change_past(self) -> None:
        before = datetime.fromisoformat("2026-08-19T12:00:00+08:00")
        row = ms(self.engine.evaluate_target("T-HS-02", before), "MS-HS02-Q6")
        self.assertEqual(row["status"], "planned")  # REV-001（8-20）尚未发生
        self.assertIsNone(row["forecast_date"])

    def test_replay_rules_version_reported(self) -> None:
        ev = self.engine.evaluate_target("T-HS-01", AT_NOW)
        self.assertEqual(ev["rules_version"], RULES_VERSION)

    # ---------- 目标汇总 ----------

    def test_target_overall_is_worst_due_milestone(self) -> None:
        self.assertEqual(
            self.engine.evaluate_target("T-HS-02", AT_NOW)["status"], "off_track")
        self.assertEqual(
            self.engine.evaluate_target("T-YT-01", AT_NOW)["status"], "done")

    def test_next_milestone_points_to_future_node(self) -> None:
        ev = self.engine.evaluate_target("T-HS-01", AT_NOW)
        self.assertEqual(ev["next_milestone"]["milestone_id"], "MS-HS01-Q6")
        self.assertEqual(ev["next_milestone"]["due_date"], "2026-09-30")

    # ---------- 证据完整性 ----------

    def test_tampered_evidence_hash_detected(self) -> None:
        domain = load_domain()
        e = next(x for x in domain["evidence"] if x["evidence_id"] == "EV-YT01-Q5")
        e["observed_value"] = 99999  # 篡改数字但不重算哈希
        engine = StatusEngine(domain)
        row = ms(engine.evaluate_target("T-YT-01", AT_NOW), "MS-YT01-Q5")
        self.assertFalse(row["inputs"]["hash_ok"])


if __name__ == "__main__":
    unittest.main()

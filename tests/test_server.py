import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib import request as urlrequest
from urllib.error import HTTPError

from src import server
from src import views


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()

    def _get(self, path: str, headers: dict | None = None) -> tuple[int, dict]:
        req = urlrequest.Request(f"http://127.0.0.1:{self.port}{path}",
                                 headers=headers or {})
        with urlrequest.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _get_error(self, path: str, headers: dict | None = None) -> tuple[int, dict]:
        req = urlrequest.Request(f"http://127.0.0.1:{self.port}{path}",
                                 headers=headers or {})
        try:
            urlrequest.urlopen(req)
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        raise AssertionError("应返回错误状态")

    def _post(self, path: str, payload: dict, headers: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(payload).encode("utf-8")
        hdrs = {"Content-Type": "application/json"}
        hdrs.update(headers or {})
        req = urlrequest.Request(f"http://127.0.0.1:{self.port}{path}",
                                 data=data, headers=hdrs, method="POST")
        try:
            with urlrequest.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    # ---------- 公开接口 ----------

    def test_health(self) -> None:
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")

    def test_dashboard_has_six_targets(self) -> None:
        _, body = self._get("/dashboard")
        self.assertEqual(len(body["targets"]), 6)
        self.assertIn("status_counts_zh", body)

    def test_target_detail_and_replay_query(self) -> None:
        _, body = self._get("/targets/T-SF-01?at=2026-09-26T12:00:00%2B08:00")
        self.assertEqual(body["status"], "off_track")
        self.assertEqual(body["delay_explanation"]["revision_id"], "REV-002")

    def test_spatial_projects_redacted(self) -> None:
        _, body = self._get("/spatial-projects")
        self.assertNotIn("SECRET", json.dumps(body, ensure_ascii=False))
        undisclosed = next(r for r in body if r["spatial_project_id"] == "SP-HC-02")
        self.assertEqual(undisclosed["granularity"], "district_only")

    def test_consultation_mentions_17k_submissions(self) -> None:
        _, body = self._get("/consultations/CON-001")
        self.assertGreater(body["submissions_total"], 17000)

    # ---------- 监督接口 ----------

    def test_oversight_requires_role(self) -> None:
        code, body = self._get_error("/targets/T-HS-01/oversight")
        self.assertEqual(code, 403)
        self.assertEqual(body["error"], "forbidden")

    def test_oversight_replay_is_deterministic_and_verifiable(self) -> None:
        headers = {"X-Role": "oversight"}
        _, body = self._get(
            "/targets/T-HS-01/replay/MS-HS01-Q5?at=2026-09-26T12:00:00%2B08:00",
            headers)
        self.assertEqual(body["verdict"]["status"], "on_track")
        self.assertEqual(body["evidence"]["sha256"], body["evidence"]["sha256"])
        self.assertTrue(body["evidence"]["hash_ok"])
        self.assertIn("RULE-DATA-LATE", body["basis"]["rule_codes"])
        # 同一时点重跑结果一致（可重现）
        _, again = self._get(
            "/targets/T-HS-01/replay/MS-HS01-Q5?at=2026-09-26T12:00:00%2B08:00",
            headers)
        self.assertEqual(again["basis"], body["basis"])

    # ---------- 社区组织接口 ----------

    def test_org_cases_with_token(self) -> None:
        _, body = self._get("/cases/org", {
            "X-Org-Code": "CSO-KT", "X-Org-Token": "TOKEN-KT-DEMO-001"})
        self.assertEqual(len(body), 1)

    def test_submit_case_accepted(self) -> None:
        payload = {
            "case_ref": "CASE-2026-0200",
            "target_id": "T-YT-01",
            "issue_domain": "youth",
            "consent": {"grant": True, "scope_codes": ["youth"],
                        "granted_at": "2026-09-25T10:00:00+08:00",
                        "record_ref_hash": "b" * 64, "expires_at": None},
            "resident": {"pseudonym": "PSN-ZZZ99999", "district": "元朗"},
            "summary": "查询下一轮青年实习资助的行业范围。",
        }
        code, body = self._post("/cases", payload, {
            "X-Org-Code": "CSO-NW", "X-Org-Token": "TOKEN-NW-DEMO-003"})
        self.assertEqual(code, 201)
        self.assertEqual(body["status"], "received")

    def test_submit_case_with_pii_rejected(self) -> None:
        payload = {
            "case_ref": "CASE-2026-0201",
            "target_id": "T-SF-01",
            "issue_domain": "subdivided_flats",
            "consent": {"grant": True, "scope_codes": ["subdivided_flats"],
                        "granted_at": "2026-09-25T10:00:00+08:00",
                        "record_ref_hash": "c" * 64},
            "resident": {"pseudonym": "PSN-AAA11111", "district": "观塘"},
            "summary": "申请人编号 HD-998877 住户求助。",
        }
        code, body = self._post("/cases", payload, {
            "X-Org-Code": "CSO-KT", "X-Org-Token": "TOKEN-KT-DEMO-001"})
        self.assertEqual(code, 422)
        self.assertEqual(body["error"], "submission_rejected")

    def test_submit_without_token_forbidden(self) -> None:
        code, _ = self._post("/cases", {"case_ref": "x"})
        self.assertEqual(code, 403)


if __name__ == "__main__":
    unittest.main()

"""承诺兑现服务 HTTP 入口（标准库，零第三方依赖）。

市民侧：
  GET /health
  GET /context
  GET /dashboard[?at=ISO]
  GET /targets/<id>[?at=ISO]
  GET /consultations            GET /consultations/<id>
  GET /spatial-projects         （未公开选址自动脱敏到地区）
  GET /plans                    GET /revisions
  GET /cases/public

监督侧（须带请求头 X-Role: oversight；演示用边界，生产应接真实鉴权）：
  GET /targets/<id>/oversight[?at=ISO]
  GET /targets/<id>/replay/<milestone_id>[?at=ISO]

社区组织（请求头 X-Org-Code / X-Org-Token）：
  GET /cases/org                只返回本组织授权范围内的个案
  POST /cases                   提交获居民授权的去标识个案

时点重放：任何判定接口都可加 ?at=2026-08-01T00:00:00+08:00，
返回该时点「本应看到」的状态（迟到数据与未来修订不计入）。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from src.service import DEFAULT_AT, PledgeService
from src import views

SERVICE = PledgeService()
OVERSIGHT_ROLE = "oversight"


def _parse_at(query: dict[str, list[str]]) -> datetime:
    raw = query.get("at", [DEFAULT_AT])[0]
    return datetime.fromisoformat(raw)


class Handler(BaseHTTPRequestHandler):
    server_version = "PledgeService/1.0"

    def _send(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, code: str, message: str) -> None:
        self._send({"error": code, "message": message}, status)

    def log_message(self, fmt, *args) -> None:  # 安静一点
        pass

    # ---------- GET ----------

    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        query = parse_qs(parts.query)
        path = parts.path
        try:
            if path == "/health":
                self._send({"status": "ok", "rules_version": SERVICE.domain["rules_version"]})
            elif path == "/context":
                self._send(SERVICE.context)
            elif path == "/dashboard":
                self._send(SERVICE.dashboard(_parse_at(query)))
            elif path == "/consultations":
                self._send(SERVICE.consultations())
            elif path.startswith("/consultations/"):
                cid = path.rsplit("/", 1)[1]
                self._send(SERVICE.consultation(cid))
            elif path == "/spatial-projects":
                self._send(SERVICE.spatial_projects())
            elif path == "/plans":
                self._send(SERVICE.plans())
            elif path == "/revisions":
                self._send(SERVICE.revisions())
            elif path == "/cases/public":
                self._send(SERVICE.public_cases())
            elif path == "/cases/org":
                self._handle_org_cases()
            elif m := re.fullmatch(r"/targets/([\w-]+)", path):
                self._send(SERVICE.target_public(m.group(1), _parse_at(query)))
            elif m := re.fullmatch(r"/targets/([\w-]+)/oversight", path):
                self._require_oversight()
                self._send(SERVICE.target_oversight(m.group(1), _parse_at(query)))
            elif m := re.fullmatch(r"/targets/([\w-]+)/replay/([\w-]+)", path):
                self._require_oversight()
                tid, mid = m.group(1), m.group(2)
                self._send(SERVICE.replay_basis(tid, mid, _parse_at(query)))
            else:
                self._send_error_json(404, "not_found", f"无此路径：{path}")
        except KeyError:
            self._send_error_json(404, "not_found", "目标或节点不存在")
        except ValueError as exc:
            self._send_error_json(400, "bad_request", str(exc))
        except PermissionError as exc:
            self._send_error_json(403, "forbidden", str(exc))

    def _require_oversight(self) -> None:
        if self.headers.get("X-Role") != OVERSIGHT_ROLE:
            raise PermissionError("监督接口需要请求头 X-Role: oversight")

    def _handle_org_cases(self) -> None:
        org_code = self.headers.get("X-Org-Code", "")
        token = self.headers.get("X-Org-Token", "")
        self._send(SERVICE.org_cases(org_code, token))

    # ---------- POST ----------

    def do_POST(self) -> None:
        parts = urlsplit(self.path)
        if parts.path != "/cases":
            self._send_error_json(404, "not_found", "无此路径")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            org_code = self.headers.get("X-Org-Code", "")
            token = self.headers.get("X-Org-Token", "")
            record = SERVICE.submit_case(payload, org_code, token)
            self._send(record, 201)
        except json.JSONDecodeError:
            self._send_error_json(400, "bad_request", "请求体须为 JSON")
        except views.AccessDenied as exc:
            self._send_error_json(403, "forbidden", str(exc))
        except views.SubmissionError as exc:
            self._send_error_json(422, "submission_rejected", str(exc))


if __name__ == "__main__":
    print("承诺兑现服务监听 http://127.0.0.1:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()

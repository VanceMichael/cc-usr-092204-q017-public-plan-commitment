"""承诺兑现服务门面：组合领域包、判定引擎、治理与视图。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from src import views
from src.catalog import load_context, load_domain, load_feedback
from src.engine import STATUS_ZH, StatusEngine
from src.governance import Governance

DEFAULT_AT = "2026-09-26T12:00:00+08:00"


def parse_at(raw: str | None) -> datetime:
    return datetime.fromisoformat(raw) if raw else datetime.fromisoformat(DEFAULT_AT)


class PledgeService:
    def __init__(self, domain_path: Path | None = None,
                 feedback_path: Path | None = None):
        self.context = load_context()
        self.domain = load_domain(domain_path)
        self.feedback_pack = load_feedback(feedback_path)
        self.engine = StatusEngine(self.domain)
        self.governance = Governance(self.domain)

    # ---------- 市民 ----------

    def dashboard(self, at: datetime) -> dict[str, Any]:
        report = self.engine.evaluate_all(at)
        return {
            "evaluated_at": report["evaluated_at"],
            "rules_version": report["rules_version"],
            "status_counts": report["status_counts"],
            "status_counts_zh": {STATUS_ZH.get(k, k): v
                                 for k, v in report["status_counts"].items()},
            "targets": [{
                "target_id": r["target_id"],
                "title": r["title"],
                "domain": r["domain"],
                "status": r["status"],
                "status_zh": r["status_zh"],
                "confidence": r["confidence"],
                "confidence_zh": r["confidence_zh"],
                "latest_result": r["latest_result"],
                "next_milestone": r["next_milestone"],
            } for r in report["targets"]],
        }

    def target_public(self, target_id: str, at: datetime) -> dict:
        return views.public_target(self.engine.evaluate_target(target_id, at))

    def target_oversight(self, target_id: str, at: datetime) -> dict:
        return views.oversight_target(self.engine.evaluate_target(target_id, at))

    def replay_basis(self, target_id: str, milestone_id: str, at: datetime) -> dict:
        """监督专用：解释某时点某节点为何被判为按期/预警/偏离。"""
        evaluation = self.engine.evaluate_target(target_id, at)
        row = next((m for m in evaluation["milestones"]
                    if m["milestone_id"] == milestone_id), None)
        if row is None:
            raise KeyError(milestone_id)
        inp = row["inputs"]
        return {
            "query": {"target_id": target_id, "milestone_id": milestone_id,
                      "at": at.isoformat()},
            "verdict": {"status": row["status"], "status_zh": row["status_zh"],
                        "confidence": row["confidence"],
                        "confidence_zh": row["confidence_zh"]},
            "rules_version": evaluation["rules_version"],
            "basis": {
                "rule_codes": inp["rule_codes"],
                "due_date": inp["due_date"],
                "planned_value": inp["planned_value"],
                "observed_value_original": inp["observed_value_original"],
                "observed_version": inp["observed_version"],
                "observed_value_common": inp["observed_value_common"],
                "conversion": inp["conversion"],
                "attainment_ratio": inp["attainment_ratio"],
                "effective_forecast_date": inp["effective_forecast_date"],
                "applied_revision_ids": inp["applied_revision_ids"],
            },
            "evidence": None if not inp["evidence_id"] else {
                "evidence_id": inp["evidence_id"],
                "recorded_at": inp["recorded_at"],
                "received_at": inp["received_at"],
                "coverage": inp["coverage"],
                "sha256": inp["evidence_sha256"],
                "hash_ok": inp["hash_ok"],
            },
        }

    # ---------- 配套公开资料 ----------

    def consultations(self) -> list[dict]:
        return self.domain["consultations"]

    def consultation(self, consultation_id: str) -> dict:
        return next(c for c in self.domain["consultations"]
                    if c["consultation_id"] == consultation_id)

    def spatial_projects(self) -> list[dict]:
        return views.public_spatial_projects(self.domain["spatial_projects"])

    def plans(self) -> list[dict]:
        return self.domain["plans"]

    def revisions(self) -> list[dict]:
        return [self.engine._public_revision(r) for r in self.domain["revisions"]]

    # ---------- 社区反馈 ----------

    def org_cases(self, org_code: str, token: str) -> list[dict]:
        return views.cases_for_org(self.feedback_pack, org_code, token)

    def public_cases(self) -> list[dict]:
        return views.public_cases(self.feedback_pack)

    def submit_case(self, payload: dict, org_code: str, token: str,
                    *, now: datetime | None = None) -> dict:
        record = views.validate_submission(
            self.feedback_pack, payload, org_code, token, now=now)
        self.feedback_pack["cases"].append(record)
        return record

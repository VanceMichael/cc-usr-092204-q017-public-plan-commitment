"""对外视图与访问控制。

- 市民视图：每个目标的最新结果、延期解释、下一节点，置信状态可见；
- 监督视图：在市民视图之外附完整判定输入（证据编号、哈希、规则码、口径换算轨迹）；
- 空间项目：未公开选址只到地区粒度，内部选址标识在任何视图中剥离；
- 社区反馈：组织凭令牌只能读取/提交其授权范围个案；提交须有居民授权且不得含个人信息。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

# 个人信息探测：香港身份证号、电话号码、公屋/福利申请编号
PII_PATTERNS = [
    ("hkid", re.compile(r"\b[A-Z]{1,2}\d{6}\(?\d\)?\b")),
    ("phone", re.compile(r"(?:(?:\+?852[-\s]?)?\d{4}[-\s]?\d{4})")),
    ("application_no", re.compile(r"(?:公屋|申请|申請|編號|编号|档案|檔案)\s*[A-Z0-9\-]{5,}")),
]

CLASSIFIED_SPATIAL_FIELDS = ("site_location_classified",)


class AccessDenied(PermissionError):
    pass


class SubmissionError(ValueError):
    pass


# ---------- 目标视图 ----------

def _public_milestone(row: dict) -> dict:
    inp = row["inputs"]
    return {
        "milestone_id": row["milestone_id"],
        "sequence": row["sequence"],
        "title": row["title"],
        "plan_id": row["plan_id"],
        "due_date": row["due_date"],
        "forecast_date": row["forecast_date"],
        "planned_value": row["planned_value"],
        "observed_value": row["observed_value"],
        "unit": row["unit"],
        "metric_version": row["metric_version"],
        "status": row["status"],
        "status_zh": row["status_zh"],
        "confidence": row["confidence"],
        "confidence_zh": row["confidence_zh"],
        "is_due": row["is_due"],
        "responsible_org_code": row["responsible_org_code"],
        # 市民可见判定理由码（不含内部证据哈希）
        "reasons": inp["rule_codes"],
        "applied_revision_ids": inp["applied_revision_ids"],
    }


def public_target(evaluation: dict[str, Any]) -> dict[str, Any]:
    """市民视图：最新结果、延期解释、下一节点。"""
    return {
        "target_id": evaluation["target_id"],
        "title": evaluation["title"],
        "domain": evaluation["domain"],
        "metric_name": evaluation["metric_name"],
        "unit": evaluation["unit"],
        "target_value": evaluation["target_value"],
        "period_end": evaluation["period_end"],
        "locked": evaluation["locked"],
        "status": evaluation["status"],
        "status_zh": evaluation["status_zh"],
        "confidence": evaluation["confidence"],
        "confidence_zh": evaluation["confidence_zh"],
        "responsible_orgs": evaluation["responsible_orgs"],
        "budget": evaluation["budget"],
        "latest_result": evaluation["latest_result"],
        "delay_explanation": evaluation["latest_revision"],
        "data_notices": evaluation["data_notices"],
        "next_milestone": evaluation["next_milestone"],
        "linked_spatial_project_ids": evaluation["linked_spatial_project_ids"],
        "linked_consultation_ids": evaluation["linked_consultation_ids"],
        "milestones": [_public_milestone(r) for r in evaluation["milestones"]],
        "evaluated_at": evaluation["evaluated_at"],
        "rules_version": evaluation["rules_version"],
    }


def oversight_target(evaluation: dict[str, Any]) -> dict[str, Any]:
    """监督视图：市民视图 + 每节点完整判定输入，可重算复核。"""
    view = public_target(evaluation)
    view["oversight"] = {
        "milestone_inputs": {
            row["milestone_id"]: row["inputs"] for row in evaluation["milestones"]
        },
    }
    return view


# ---------- 空间项目脱敏 ----------

def public_spatial_projects(projects: list[dict]) -> list[dict]:
    out = []
    for p in projects:
        if p.get("site_public"):
            row = {k: v for k, v in p.items() if k not in CLASSIFIED_SPATIAL_FIELDS}
        else:
            # 未公开选址：只暴露地区粒度的事实
            row = {
                "spatial_project_id": p["spatial_project_id"],
                "name": f"{p['district']}区内规划项目（选址待公布）",
                "project_type": p["project_type"],
                "district": p["district"],
                "site_public": False,
                "granularity": "district_only",
                "status": p["status"],
                "linked_target_ids": p["linked_target_ids"],
            }
        out.append(row)
    return out


# ---------- 社区组织与反馈 ----------

def _org_index(feedback_pack: dict) -> dict[str, dict]:
    return {o["org_code"]: o for o in feedback_pack["organizations"]}


def authenticate_org(feedback_pack: dict, org_code: str, token: str) -> dict:
    org = _org_index(feedback_pack).get(org_code)
    if org is None or org["access_token"] != token:
        raise AccessDenied("组织代码或令牌无效")
    return org


def cases_for_org(feedback_pack: dict, org_code: str, token: str) -> list[dict]:
    """组织只能读取自己提交的个案；授权内部字段不外显给其他角色。"""
    authenticate_org(feedback_pack, org_code, token)
    return [_org_case_view(c) for c in feedback_pack["cases"] if c["org_code"] == org_code]


def _org_case_view(case: dict) -> dict:
    return {
        "case_ref": case["case_ref"],
        "target_id": case["target_id"],
        "milestone_id": case["milestone_id"],
        "issue_domain": case["issue_domain"],
        "status": case["status"],
        "resident": case.get("resident"),
        "summary": case.get("summary"),
        "created_at": case["created_at"],
        "events": case["events"],
        "consent_scope": case["consent"]["scope_codes"],
        "consent_expires_at": case["consent"].get("expires_at"),
    }


def public_cases(feedback_pack: dict) -> list[dict]:
    """公众可见：假名、地区、议题、状态与公开事件；不附任何授权凭据。"""
    out = []
    for c in feedback_pack["cases"]:
        out.append({
            "case_ref": c["case_ref"],
            "target_id": c["target_id"],
            "issue_domain": c["issue_domain"],
            "status": c["status"],
            "district": c.get("resident", {}).get("district"),
            "created_at": c["created_at"],
            "events": [
                {"at": e["at"], "action": e["action"], "by_org": e["by_org"],
                 "note_public": e.get("note_public")}
                for e in c["events"]
            ],
        })
    return out


def detect_pii(text: str) -> list[str]:
    hits = []
    for label, pattern in PII_PATTERNS:
        if pattern.search(text or ""):
            hits.append(label)
    return hits


def validate_submission(feedback_pack: dict, payload: dict, org_code: str,
                        token: str, *, now: datetime | None = None) -> dict:
    """校验社区组织提交的反馈个案，返回规范化记录。"""
    now = now or datetime.now().astimezone()
    org = authenticate_org(feedback_pack, org_code, token)

    consent = payload.get("consent") or {}
    if not consent.get("grant"):
        raise SubmissionError("未取得居民明确授权，个案不予接收")
    scope = consent.get("scope_codes") or []
    if not scope or any(s not in org["scope_codes"] for s in scope):
        raise SubmissionError(
            f"授权范围 {scope} 超出组织被授权范围 {org['scope_codes']}")
    expires = consent.get("expires_at")
    if expires and datetime.fromisoformat(expires) < now:
        raise SubmissionError("授权已过期")
    if not re.fullmatch(r"[0-9a-f]{64}", consent.get("record_ref_hash", "")):
        raise SubmissionError("须提供授权书档号的 SHA-256 哈希，不得上传原件")

    issue = payload.get("issue_domain")
    if issue not in org["scope_codes"]:
        raise SubmissionError(f"议题 {issue} 不在组织授权范围内")

    resident = payload.get("resident") or {}
    district = resident.get("district")
    if district and district not in org["districts"]:
        raise SubmissionError(f"组织不获授权处理 {district} 区个案")
    if not re.fullmatch(r"PSN-[A-Z0-9]{8,}", resident.get("pseudonym", "")):
        raise SubmissionError("须提供假名化令牌（PSN- 前缀），不得填写真实身份")

    summary = payload.get("summary", "")
    pii = detect_pii(summary)
    if pii:
        raise SubmissionError(f"描述疑似含个人信息 {pii}，请去标识后重新提交")

    return {
        "case_ref": payload["case_ref"],
        "target_id": payload["target_id"],
        "milestone_id": payload.get("milestone_id"),
        "org_code": org_code,
        "issue_domain": issue,
        "status": "received",
        "consent": {
            "grant": True,
            "scope_codes": scope,
            "granted_at": consent["granted_at"],
            "record_ref_hash": consent["record_ref_hash"],
            "expires_at": consent.get("expires_at"),
        },
        "resident": {"pseudonym": resident["pseudonym"], "district": district},
        "summary": summary,
        "created_at": now.isoformat(),
        "events": [{"at": now.isoformat(), "action": "submitted", "by_org": org_code}],
    }

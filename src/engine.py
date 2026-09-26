"""进度判定引擎（规则版本 status-rules-v1.0）。

对外判定不采信机构自报状态，而由本引擎结合证据快照重算，保证任一历史时点
的「按期 / 预警 / 偏离」判定可重现：

- 证据以 received_at 为准进入判定（跨部门数据迟到/未送达时不计入）；
- 修订事件按 at 重放，未来的路径调整不影响历史判定；
- 实测先经口径桥接换算到节点承诺口径再与计划值比较；
- 覆盖率、迟到、陈旧度折算为置信状态 confirmed/provisional/estimated/stale/missing。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from src import bridging
from src.canonical import evidence_fingerprint

RULES_VERSION = "status-rules-v1.0"

GRACE_DAYS = 45            # 节点到期后等待跨部门数据的宽限（日）
STALE_DAYS = 120           # 实测超过此时长视为陈旧
COVERAGE_PROVISIONAL = 0.9
COVERAGE_ESTIMATED = 0.5
BAND_DONE = 0.99
BAND_ON_TRACK = 0.95
BAND_AT_RISK = 0.85

CONFIDENCE_RANK = {
    "confirmed": 0,
    "provisional": 1,
    "estimated": 2,
    "stale": 3,
    "missing": 4,
}
STATUS_RANK = {
    "done": 0,
    "on_track": 1,
    "pending_data": 2,
    "at_risk": 2,
    "off_track": 3,
}

STATUS_ZH = {
    "done": "达标",
    "on_track": "按期",
    "at_risk": "预警",
    "off_track": "偏离",
    "pending_data": "待数据",
    "planned": "未到期",
}
CONFIDENCE_ZH = {
    "confirmed": "定稿",
    "provisional": "初步",
    "estimated": "估算",
    "stale": "陈旧",
    "missing": "缺报",
}


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_d(value: str) -> date:
    return date.fromisoformat(value)


@dataclass
class JudgmentInputs:
    """供监督复核的判定输入快照。"""
    milestone_id: str
    at: str
    due_date: str
    planned_value: float
    observed_value_original: float | None
    observed_version: str | None
    observed_value_common: float | None
    conversion: list[dict]
    attainment_ratio: float | None
    confidence: str
    coverage: float | None
    evidence_id: str | None
    evidence_sha256: str | None
    hash_ok: bool | None
    recorded_at: str | None
    received_at: str | None
    effective_forecast_date: str | None
    applied_revision_ids: list[str]
    rule_codes: list[str]

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class StatusEngine:
    def __init__(self, domain: dict[str, Any]):
        self.domain = domain
        self.targets = {t["target_id"]: t for t in domain["targets"]}
        self.milestones = {m["milestone_id"]: m for m in domain["milestones"]}
        self.evidence_by_ms: dict[str, list[dict]] = {}
        for e in domain["evidence"]:
            self.evidence_by_ms.setdefault(e["milestone_id"], []).append(e)
        self.revisions_by_ms: dict[str, list[dict]] = {}
        for r in sorted(domain["revisions"], key=lambda x: x["at"]):
            self.revisions_by_ms.setdefault(r["milestone_id"], []).append(r)
        self.notices_by_target: dict[str, list[dict]] = {}
        for n in domain["data_notices"]:
            self.notices_by_target.setdefault(n["target_id"], []).append(n)

    # ---------- 时点重放的有效状态 ----------

    def _known_revisions(self, milestone_id: str, at: datetime) -> list[dict]:
        return [r for r in self.revisions_by_ms.get(milestone_id, [])
                if _parse_dt(r["at"]) <= at]

    def effective_forecast(self, milestone: dict, at: datetime) -> tuple[str | None, list[str]]:
        """重放截至 at 的 reschedule 修订，得出有效预测日期。"""
        forecast = milestone.get("forecast_date")
        applied: list[str] = []
        for rev in self._known_revisions(milestone["milestone_id"], at):
            if rev["kind"] == "reschedule":
                forecast = rev["new"].get("forecast_date", forecast)
                applied.append(rev["revision_id"])
        return forecast, applied

    def _admissible_evidence(self, milestone_id: str, at: datetime) -> list[dict]:
        out = []
        for e in self.evidence_by_ms.get(milestone_id, []):
            received = e.get("received_at")
            if received is not None and _parse_dt(received) <= at:
                out.append(e)
        return sorted(out, key=lambda e: (e["recorded_at"], e["received_at"]))

    def _active_notices(self, target_id: str, at: datetime) -> list[dict]:
        active = []
        for n in self.notices_by_target.get(target_id, []):
            if _parse_dt(n["expected_by"]) > at:
                continue
            received = n.get("received_at")
            if received is None or _parse_dt(received) > at:
                active.append(n)
        return active

    # ---------- 口径换算 ----------

    def _to_milestone_version(self, value: float, metric_code: str,
                              from_version: str, to_version: str
                              ) -> tuple[float, list[dict]]:
        converted, steps = bridging.convert(
            value, metric_code, from_version, to_version,
            self.domain["metric_bridges"])
        return converted, [s.as_dict() for s in steps]

    # ---------- 置信状态 ----------

    def _confidence(self, evidence: dict, at: datetime) -> tuple[str, list[str]]:
        codes: list[str] = []
        conf = evidence["confidence"]
        age = at - _parse_dt(evidence["recorded_at"])
        if age > timedelta(days=STALE_DAYS):
            conf = "stale"
            codes.append("RULE-CONF-STALE")
        coverage = evidence.get("coverage", 1.0)
        if coverage < COVERAGE_ESTIMATED:
            conf = "estimated"
            codes.append("RULE-CONF-COVERAGE-EST")
        elif coverage < COVERAGE_PROVISIONAL:
            conf = {"estimated": "estimated"}.get(conf, "provisional")
            codes.append("RULE-CONF-COVERAGE-PROV")
        if evidence.get("is_late"):
            codes.append("RULE-DATA-LATE")
        return conf, codes

    # ---------- 单节点判定 ----------

    def evaluate_milestone(self, milestone_id: str, at: datetime) -> dict[str, Any]:
        m = self.milestones[milestone_id]
        target = self.targets[m["target_id"]]
        due = _parse_d(m["due_date"])
        forecast, applied_rev = self.effective_forecast(m, at)
        rule_codes: list[str] = []
        rule_codes.extend(f"RULE-REV-APPLIED:{rid}" for rid in applied_rev)

        conversion: list[dict] = []
        observed_common: float | None = None
        observed_original: float | None = None
        observed_version: str | None = None
        coverage: float | None = None
        confidence = "missing"
        evidence_id = sha = recorded_at = received_at = None
        hash_ok: bool | None = None

        evidences = self._admissible_evidence(milestone_id, at)
        due_by = datetime.combine(due, datetime.max.time(), tzinfo=at.tzinfo)
        is_due = due_by <= at
        grace_deadline = due_by + timedelta(days=GRACE_DAYS)

        ratio: float | None = None
        band_status: str | None = None
        if evidences:
            e = evidences[-1]
            evidence_id = e["evidence_id"]
            sha = e["sha256"]
            hash_ok = evidence_fingerprint(e) == e["sha256"]
            recorded_at = e["recorded_at"]
            received_at = e["received_at"]
            observed_original = e["observed_value"]
            observed_version = e["metric_version"]
            coverage = e.get("coverage", 1.0)
            confidence, conf_codes = self._confidence(e, at)
            rule_codes.extend(conf_codes)
            if observed_version != m["metric_version"]:
                observed_common, conversion = self._to_milestone_version(
                    observed_original, m["metric_code"],
                    observed_version, m["metric_version"])
                rule_codes.append("RULE-METRIC-BRIDGED")
            else:
                observed_common = float(observed_original)
            ratio = self._attainment(target, m, observed_common)
            if ratio >= BAND_DONE:
                band_status = "done"
            elif ratio >= BAND_ON_TRACK:
                band_status = "on_track"
            elif ratio >= BAND_AT_RISK:
                band_status = "at_risk"
            else:
                band_status = "off_track"
            # 季度已达标：该节点的定稿数字即最终结果，不因查询日推移而变陈旧
            if band_status == "done" and confidence == "stale" \
                    and e["confidence"] in ("confirmed", "provisional"):
                confidence = e["confidence"]
                rule_codes = [c for c in rule_codes if c != "RULE-CONF-STALE"]

        status: str
        if not is_due:
            # 未到期：只看修订事件是否已预告延期
            if forecast and _parse_d(forecast) > due:
                status = "at_risk"
                rule_codes.append("RULE-SCHED-FORECAST-SLIP")
            else:
                status = "planned"
        elif observed_common is None:
            # 到期但无可用实测
            if at <= grace_deadline:
                status = "pending_data"
                rule_codes.append("RULE-DATA-AWAITING")
            else:
                revisions = self._known_revisions(milestone_id, at)
                if any(r["kind"] in ("reschedule", "path_change") for r in revisions):
                    status = "off_track"
                    rule_codes.append("RULE-DATA-MISSING-REV-ACK")
                else:
                    status = "at_risk"
                    rule_codes.append("RULE-DATA-MISSING-GRACE")
        else:
            status = band_status
            if ratio < BAND_ON_TRACK:
                rule_codes.append(
                    "RULE-VALUE-BAND:AT_RISK" if ratio >= BAND_AT_RISK
                    else "RULE-VALUE-BAND:OFF_TRACK")
            if forecast and _parse_d(forecast) > due and status in ("on_track", "done"):
                rule_codes.append("RULE-SCHED-FORECAST-NOTE")

        inputs = JudgmentInputs(
            milestone_id=milestone_id, at=at.isoformat(), due_date=m["due_date"],
            planned_value=m["planned_value"], observed_value_original=observed_original,
            observed_version=observed_version, observed_value_common=observed_common,
            conversion=conversion, attainment_ratio=ratio, confidence=confidence,
            coverage=coverage, evidence_id=evidence_id, evidence_sha256=sha,
            hash_ok=hash_ok, recorded_at=recorded_at, received_at=received_at,
            effective_forecast_date=forecast, applied_revision_ids=applied_rev,
            rule_codes=rule_codes,
        )
        return {
            "milestone_id": milestone_id,
            "sequence": m["sequence"],
            "title": m["title"],
            "plan_id": m["plan_id"],
            "due_date": m["due_date"],
            "forecast_date": forecast,
            "planned_value": m["planned_value"],
            "observed_value": observed_common,
            "unit": m["unit"],
            "metric_version": m["metric_version"],
            "status": status,
            "status_zh": STATUS_ZH[status],
            "confidence": confidence,
            "confidence_zh": CONFIDENCE_ZH[confidence],
            "is_due": is_due,
            "responsible_org_code": m["responsible_org_code"],
            "spatial_project_id": m.get("spatial_project_id"),
            "inputs": inputs.as_dict(),
        }

    @staticmethod
    def _attainment(target: dict, milestone: dict, observed: float) -> float:
        """实测相对节点计划轨迹的达成率（>=1 达标，越小越差）。"""
        planned = milestone["planned_value"]
        if target["direction"] == "maximize":
            return observed / planned if planned else 0.0
        baseline = target["baseline"]["value"]
        planned_move = baseline - planned
        if planned_move == 0:
            return 1.0 if observed <= planned else 0.0
        return (baseline - observed) / planned_move

    # ---------- 目标级汇总 ----------

    def evaluate_target(self, target_id: str, at: datetime) -> dict[str, Any]:
        target = self.targets[target_id]
        ms_rows = [self.evaluate_milestone(m["milestone_id"], at)
                   for m in self.domain["milestones"] if m["target_id"] == target_id]
        ms_rows.sort(key=lambda r: r["sequence"])
        due_rows = [r for r in ms_rows if r["is_due"]]

        # 总体状态：到期节点取最差（排名越大越差）
        judged = [r for r in due_rows if r["status"] in STATUS_RANK]
        overall = max((r["status"] for r in judged),
                      key=lambda s: STATUS_RANK[s], default="planned")

        # 当前进度的置信度：以最近到期节点为准，避免历史已定稿节点干扰
        confidence = "confirmed"
        if due_rows:
            confidence = max(due_rows, key=lambda r: r["sequence"])["inputs"]["confidence"]

        latest = self._latest_result(target, ms_rows)
        next_node = next((
            {"milestone_id": r["milestone_id"], "title": r["title"],
             "due_date": r["due_date"], "forecast_date": r["forecast_date"],
             "planned_value": r["planned_value"], "unit": r["unit"]}
            for r in ms_rows
            if _parse_d(r["due_date"]) >= at.date() and r["status"] != "done"
        ), None)

        revs = [r for r in self.domain["revisions"]
                if r["target_id"] == target_id and _parse_dt(r["at"]) <= at]
        latest_revision = revs[-1] if revs else None
        active_notices = self._active_notices(target_id, at)

        return {
            "target_id": target_id,
            "title": target["title"],
            "domain": target["domain"],
            "metric_name": target["metric_name"],
            "unit": target["unit"],
            "direction": target["direction"],
            "baseline": target["baseline"],
            "target_value": target["target_value"],
            "period_end": target["period_end"],
            "locked": target["locked"],
            "status": overall,
            "status_zh": STATUS_ZH[overall],
            "confidence": confidence,
            "confidence_zh": CONFIDENCE_ZH[confidence],
            "data_notices": active_notices,
            "latest_result": latest,
            "latest_revision": self._public_revision(latest_revision) if latest_revision else None,
            "next_milestone": next_node,
            "responsible_orgs": target["responsible_orgs"],
            "budget": target["budget"],
            "linked_spatial_project_ids": target["linked_spatial_project_ids"],
            "linked_consultation_ids": target["linked_consultation_ids"],
            "milestones": ms_rows,
            "evaluated_at": at.isoformat(),
            "rules_version": RULES_VERSION,
        }

    def _latest_result(self, target: dict, ms_rows: list[dict]) -> dict | None:
        candidates = [r for r in ms_rows if r["inputs"]["evidence_id"]]
        if not candidates:
            return None
        latest = max(candidates, key=lambda r: r["inputs"]["recorded_at"])
        inp = latest["inputs"]
        # 换算到目标锁定口径，便于与五年目标值直接比较
        locked_version = target["baseline"]["metric_version"]
        value_locked, steps = inp["observed_value_common"], []
        if inp["observed_value_common"] is not None and latest["metric_version"] != locked_version:
            value_locked, conv_steps = bridging.convert(
                inp["observed_value_common"], target["metric_code"],
                latest["metric_version"], locked_version, self.domain["metric_bridges"])
            steps = [s.as_dict() for s in conv_steps]
        return {
            "value_observed": inp["observed_value_common"],
            "metric_version": latest["metric_version"],
            "value_in_locked_version": value_locked,
            "locked_metric_version": locked_version,
            "conversion_to_locked": steps,
            "unit": latest["unit"],
            "as_of_recorded_at": inp["recorded_at"],
            "received_at": inp["received_at"],
            "confidence": inp["confidence"],
            "confidence_zh": CONFIDENCE_ZH[inp["confidence"]],
            "coverage": inp["coverage"],
            "evidence_id": inp["evidence_id"],
            "evidence_sha256": inp["evidence_sha256"],
            "hash_ok": inp["hash_ok"],
            "milestone_id": latest["milestone_id"],
        }

    @staticmethod
    def _public_revision(rev: dict) -> dict:
        return {
            "revision_id": rev["revision_id"],
            "at": rev["at"],
            "kind": rev["kind"],
            "touches_five_year_target": rev["touches_five_year_target"],
            "reason": rev["reason"],
            "by_org": rev["by_org"],
            "decided_by": rev["decided_by"],
            "old": rev["old"],
            "new": rev["new"],
            "evidence_ids": rev["evidence_ids"],
        }

    def evaluate_all(self, at: datetime) -> dict[str, Any]:
        rows = [self.evaluate_target(tid, at) for tid in self.targets]
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        return {
            "evaluated_at": at.isoformat(),
            "rules_version": RULES_VERSION,
            "status_counts": counts,
            "targets": rows,
        }

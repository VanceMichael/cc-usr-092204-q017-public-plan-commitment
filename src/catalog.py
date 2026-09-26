"""资料仓储：载入、一致性校验、目标不可偷改核对、授权校验与双重视图。

- 公众视图：最新结果、延期解释、下一节点；未公开选址与个案资料一律脱敏。
- 监督视图：额外给出修订链、口径桥接轨迹、证据快照与时间线重放。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from src.assess import (
    assess_pledge,
    status_timeline,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"

PUBLIC = "public"
OVERSIGHT = "oversight"


class DataIntegrityError(ValueError):
    """资料之间引用不一致或治理规则被破坏（如偷偷改写五年目标）。"""


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_context(path: Path | None = None) -> dict:
    source = path or FIXTURES / "context.json"
    return _read(source)


@dataclass
class Registry:
    context: dict
    pledges_doc: dict
    initiatives_doc: dict
    progress_doc: dict
    governance_doc: dict

    pledges: list[dict] = field(init=False)
    initiatives: list[dict] = field(init=False)
    measurements: list[dict] = field(init=False)
    bases: list[dict] = field(init=False)
    sites: list[dict] = field(init=False)
    evidence: list[dict] = field(init=False)
    opinions: list[dict] = field(init=False)
    feedback: list[dict] = field(init=False)
    revisions: list[dict] = field(init=False)

    def __post_init__(self) -> None:
        self.pledges = self.pledges_doc["pledges"]
        self.initiatives = self.initiatives_doc["initiatives"]
        self.measurements = self.progress_doc["measurements"]
        self.bases = self.progress_doc["bases"]
        self.sites = self.governance_doc["sites"]
        self.evidence = self.governance_doc["evidence"]
        self.opinions = self.governance_doc["opinions"]
        self.feedback = self.governance_doc["feedback"]
        self.revisions = self.governance_doc["revisions"]
        validate(self)

    # ---- 索引 ----
    def pledge(self, pledge_id: str) -> dict:
        return self._by_id(self.pledges, pledge_id, "pledge_id")

    def revisions_for(self, pledge_id: str) -> list[dict]:
        return sorted(
            (r for r in self.revisions if r.get("pledge_id") == pledge_id),
            key=lambda r: r["date"],
        )

    def initiatives_for(self, pledge_id: str) -> list[dict]:
        return [i for i in self.initiatives if i["pledge_id"] == pledge_id]

    def measurements_for(self, pledge_id: str) -> list[dict]:
        return [m for m in self.measurements if m["pledge_id"] == pledge_id]

    @property
    def bases_by_id(self) -> dict[str, dict]:
        return {b["basis_id"]: b for b in self.bases}

    @staticmethod
    def _by_id(rows: list[dict], key: str, id_field: str) -> dict:
        for row in rows:
            if row[id_field] == key:
                return row
        raise DataIntegrityError(f"引用了不存在的记录：{id_field}={key}")


# ---------------------------------------------------------------------------
# 载入与校验
# ---------------------------------------------------------------------------

def load_registry(data_dir: Path | None = None) -> Registry:
    base = data_dir or FIXTURES
    registry = Registry(
        context=load_context(base / "context.json"),
        pledges_doc=_read(base / "pledges.json"),
        initiatives_doc=_read(base / "initiatives.json"),
        progress_doc=_read(base / "progress.json"),
        governance_doc=_read(base / "governance.json"),
    )
    return registry


def _unique(rows: list[dict], id_field: str, label: str) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for row in rows:
        key = row[id_field]
        if key in index:
            raise DataIntegrityError(f"{label}编号重复：{key}")
        index[key] = row
    return index


def validate(reg: Registry) -> None:
    pledge_ids = _unique(reg.pledges, "pledge_id", "承诺")
    init_index = _unique(reg.initiatives, "initiative_id", "年度项目")
    basis_index = _unique(reg.bases, "basis_id", "统计口径")
    site_index = _unique(reg.sites, "site_id", "空间项目")
    evidence_index = _unique(reg.evidence, "evidence_id", "证据快照")
    opinion_index = _unique(reg.opinions, "opinion_id", "咨询意见")
    revision_index = _unique(reg.revisions, "revision_id", "修订记录")

    _validate_pledges(reg, pledge_ids)
    _validate_initiatives(reg, pledge_ids, init_index, site_index, opinion_index, revision_index)
    _validate_progress(reg, pledge_ids, basis_index, evidence_index)
    _validate_revision_chain(reg, pledge_ids, init_index, revision_index)
    _validate_feedback(reg, pledge_ids)
    _validate_sites(reg, site_index)


def _validate_pledges(reg: Registry, pledge_ids: dict[str, dict]) -> None:
    for pledge in reg.pledges:
        milestones = pledge["milestones"]
        if not milestones:
            raise DataIntegrityError(f"{pledge['pledge_id']} 缺少里程碑")
        if milestones[-1]["cumulative_target"] != pledge["five_year_target"]:
            raise DataIntegrityError(
                f"{pledge['pledge_id']} 末个里程碑累计值与五年目标不一致："
                f"{milestones[-1]['cumulative_target']} != {pledge['five_year_target']}"
            )
        previous = -1.0
        for m in milestones:
            if m["cumulative_target"] < previous:
                raise DataIntegrityError(f"{pledge['pledge_id']} 里程碑累计值倒退")
            previous = m["cumulative_target"]
        if pledge["measurement_basis"] not in {
            b["basis_id"] for b in reg.bases if b["pledge_id"] == pledge["pledge_id"]
        }:
            raise DataIntegrityError(
                f"{pledge['pledge_id']} 现行口径 {pledge['measurement_basis']} 不存在"
            )


def _validate_initiatives(
    reg: Registry,
    pledge_ids: dict[str, dict],
    init_index: dict[str, dict],
    site_index: dict[str, dict],
    opinion_index: dict[str, dict],
    revision_index: dict[str, dict],
) -> None:
    for item in reg.initiatives:
        if item["pledge_id"] not in pledge_ids:
            raise DataIntegrityError(f"{item['initiative_id']} 关联了不存在的承诺")
        for site_id in item["site_ids"]:
            if site_id not in site_index:
                raise DataIntegrityError(f"{item['initiative_id']} 引用不存在的空间项目 {site_id}")
        for ref in item["consultation_refs"]:
            if ref not in opinion_index:
                raise DataIntegrityError(f"{item['initiative_id']} 引用不存在的咨询意见 {ref}")
        if item["status"] == "rephased" and not item.get("revision_id"):
            raise DataIntegrityError(f"{item['initiative_id']} 已重排但缺少修订记录")
        if item.get("revision_id"):
            revision = revision_index.get(item["revision_id"])
            if revision is None:
                raise DataIntegrityError(
                    f"{item['initiative_id']} 引用不存在的修订 {item['revision_id']}"
                )
            if revision.get("initiative_id") and revision["initiative_id"] != item["initiative_id"]:
                raise DataIntegrityError(
                    f"{item['initiative_id']} 的修订记录挂接了其他项目"
                )
        if item.get("superseded_by") and item["superseded_by"] not in init_index:
            raise DataIntegrityError(f"{item['initiative_id']} 的替代项目不存在")
        if item["target_altered"] and not item.get("revision_id"):
            raise DataIntegrityError(
                f"{item['initiative_id']} 标记改变目标却无正式修订，年度方案不得自行改写五年目标"
            )


def _validate_progress(
    reg: Registry,
    pledge_ids: dict[str, dict],
    basis_index: dict[str, dict],
    evidence_index: dict[str, dict],
) -> None:
    _unique(reg.measurements, "measure_id", "进度量度")
    for m in reg.measurements:
        if m["pledge_id"] not in pledge_ids:
            raise DataIntegrityError(f"{m['measure_id']} 关联了不存在的承诺")
        basis = basis_index.get(m["basis_id"])
        if basis is None:
            raise DataIntegrityError(f"{m['measure_id']} 使用了不存在的口径")
        if basis["pledge_id"] != m["pledge_id"]:
            raise DataIntegrityError(f"{m['measure_id']} 口径属于其他承诺")
        for ev in m["evidence_ids"]:
            if ev not in evidence_index:
                raise DataIntegrityError(f"{m['measure_id']} 引用不存在的证据快照 {ev}")
    for basis in reg.bases:
        bridge = basis.get("bridge")
        if bridge and bridge["from_basis"] not in basis_index:
            raise DataIntegrityError(f"{basis['basis_id']} 的桥接来源口径不存在")


def _validate_revision_chain(
    reg: Registry,
    pledge_ids: dict[str, dict],
    init_index: dict[str, dict],
    revision_index: dict[str, dict],
) -> None:
    """核对修订链：路径修订不得改变目标；目标修订必须链式衔接并等于现行目标。"""
    for pledge in reg.pledges:
        target_revisions = [
            r for r in reg.revisions_for(pledge["pledge_id"]) if r["kind"] == "target"
        ]
        expected = pledge["original_target"]
        for revision in target_revisions:
            if revision.get("old_target") != expected:
                raise DataIntegrityError(
                    f"{revision['revision_id']} 的旧目标 {revision.get('old_target')} "
                    f"与修订链应处值 {expected} 不符，历史目标被改写"
                )
            expected = revision["new_target"]
            item = init_index.get(revision.get("initiative_id", ""), None)
            if item is None or not item.get("target_altered"):
                raise DataIntegrityError(
                    f"目标修订 {revision['revision_id']} 必须由标记 target_altered 的年度项目承载"
                )
        if expected != pledge["five_year_target"]:
            raise DataIntegrityError(
                f"{pledge['pledge_id']} 修订链末端目标 {expected} 与现行五年目标 "
                f"{pledge['five_year_target']} 不符"
            )
        # 路径修订明确不得改目标：挂接项目必须声明 target_altered=false。
        for revision in reg.revisions_for(pledge["pledge_id"]):
            if revision["kind"] == "pathway":
                item = init_index.get(revision.get("initiative_id", ""))
                if item and item.get("target_altered"):
                    raise DataIntegrityError(
                        f"{revision['revision_id']} 是路径调整，却被标记为改变目标"
                    )


def _validate_feedback(reg: Registry, pledge_ids: dict[str, dict]) -> None:
    _unique(reg.feedback, "feedback_id", "社区反馈")
    for fb in reg.feedback:
        if fb["pledge_id"] not in pledge_ids:
            raise DataIntegrityError(f"{fb['feedback_id']} 关联了不存在的承诺")
        auth = fb["authorization"]
        if auth["scope"] != "case":
            raise DataIntegrityError(f"{fb['feedback_id']} 授权范围必须逐案授予")
        if fb["case_ref"] not in auth["case_ids_authorized"]:
            raise DataIntegrityError(
                f"{fb['feedback_id']} 涉及未获授权的个案 {fb['case_ref']}，社区组织只能反馈授权个案"
            )
        if date.fromisoformat(auth["granted_until"]) < date.fromisoformat(fb["received_date"]):
            raise DataIntegrityError(f"{fb['feedback_id']} 提交时授权已过期")


def _validate_sites(reg: Registry, site_index: dict[str, dict]) -> None:
    for site in reg.sites:
        if site["disclosure_status"] == "embargoed" and site.get("address"):
            raise DataIntegrityError(
                f"{site['site_id']} 属未公开选址，地址不得入库外泄"
            )


# ---------------------------------------------------------------------------
# 授权与脱敏
# ---------------------------------------------------------------------------

def feedback_authorized(fb: dict, on_date: date | None = None) -> bool:
    today = on_date or date.today()
    auth = fb["authorization"]
    return (
        auth["scope"] == "case"
        and fb["case_ref"] in auth["case_ids_authorized"]
        and date.fromisoformat(fb["received_date"]) <= today <= date.fromisoformat(auth["granted_until"])
    )


def public_site(site: dict) -> dict:
    view = {
        "district": site["district"],
        "public_name": site["public_name"],
        "disclosure_status": site["disclosure_status"],
    }
    if site["disclosure_status"] == "public":
        view["address"] = site.get("address")
    else:
        view["address"] = None
        view["location_note"] = "选址尚未刊宪，公开前不披露具体位置"
    return view


# ---------------------------------------------------------------------------
# 视图
# ---------------------------------------------------------------------------

def pledge_statuses(reg: Registry, as_of: date | None = None) -> list[dict]:
    today = as_of or date.today()
    rows = []
    for pledge in reg.pledges:
        result = assess_pledge(pledge, reg.measurements, reg.bases_by_id, today)
        rows.append(
            {
                "pledge_id": pledge["pledge_id"],
                "title": pledge["title"],
                "domain": pledge["domain"],
                "status": result["status"],
                "status_label": result["status_label"],
                "confidence": result["confidence"],
                "confidence_label": result["confidence_label"],
                "actual": result["actual"],
                "expected": result["expected"],
                "five_year_target": result["five_year_target"],
                "unit": pledge["unit"],
                "next_milestone": (result["next_milestone"] or {}).get("label"),
            }
        )
    return rows


def _delay_explanation(reg: Registry, pledge_id: str) -> dict | None:
    explanations = [
        {
            "revision_id": r["revision_id"],
            "date": r["date"],
            "kind": r["kind"],
            "explanation": r.get("public_explanation") or r["rationale"],
        }
        for r in reg.revisions_for(pledge_id)
        if r.get("public_explanation")
    ]
    return explanations[-1] if explanations else None


def public_pledge_view(reg: Registry, pledge_id: str, as_of: date | None = None) -> dict:
    pledge = reg.pledge(pledge_id)
    today = as_of or date.today()
    result = assess_pledge(pledge, reg.measurements, reg.bases_by_id, today)

    initiatives = [
        {
            "fiscal_year": i["fiscal_year"],
            "title": i["title"],
            "agency": i["agency"],
            "budget_hkd": i["budget_hkd"],
            "status": i["status"],
            "pathway": i["pathway"],
        }
        for i in reg.initiatives_for(pledge_id)
        if i["status"] != "rephased" or i.get("superseded_by")
    ]
    sites = [
        public_site(reg._by_id(reg.sites, sid, "site_id"))
        for sid in {s for i in reg.initiatives_for(pledge_id) for s in i["site_ids"]}
    ]
    opinions = [
        {
            "theme": o["theme"],
            "summary": o["summary"],
            "aggregate_count": o.get("aggregate_count"),
            "received_date": o["received_date"],
        }
        for o in reg.opinions
        if o.get("pledge_id") == pledge_id
    ]
    evidence = [
        {
            "evidence_id": eid,
            "title": reg._by_id(reg.evidence, eid, "evidence_id")["title"],
            "captured_at": reg._by_id(reg.evidence, eid, "evidence_id")["captured_at"],
            "sha256": reg._by_id(reg.evidence, eid, "evidence_id")["sha256"],
        }
        for eid in result["evidence_ids"]
    ]

    return {
        "audience": PUBLIC,
        "as_of": today.isoformat(),
        "pledge_id": pledge_id,
        "title": pledge["title"],
        "domain": pledge["domain"],
        "lead_agency": pledge["lead_agency"],
        "five_year_target": pledge["five_year_target"],
        "original_target": pledge["original_target"],
        "unit": pledge["unit"],
        "latest_result": {
            "actual": result["actual"],
            "expected_by_now": result["expected"],
            "gap_pct": result["gap_pct"],
            "data_as_of": result["data_as_of"],
            "confidence": result["confidence"],
            "confidence_label": result["confidence_label"],
            "basis_note": (
                "数字已按口径桥接折算为现行口径" if result["bridged_from"] else None
            ),
            "measurement_note": result["measurement_note"],
        },
        "status": result["status"],
        "status_label": result["status_label"],
        "delay_explanation": _delay_explanation(reg, pledge_id),
        "next_milestone": result["next_milestone"],
        "last_due_milestone": result["last_due_milestone"],
        "budget_envelope_hkd": pledge["budget_envelope"]["amount_hkd"],
        "annual_initiatives": initiatives,
        "sites": sites,
        "public_opinions": opinions,
        "evidence_snapshots": evidence,
    }


def oversight_pledge_view(
    reg: Registry, pledge_id: str, as_of: date | None = None
) -> dict:
    """监督视图：在公众视图之上附加内部判定依据、修订链与可重放时间线。"""
    view = public_pledge_view(reg, pledge_id, as_of)
    pledge = reg.pledge(pledge_id)
    today = as_of or date.today()
    result = assess_pledge(pledge, reg.measurements, reg.bases_by_id, today)

    # 未公开选址对监督人员可见，但仍显式标注敏感级别。
    sites = [
        {
            **reg._by_id(reg.sites, sid, "site_id"),
            "sensitivity": (
                "embargoed-internal"
                if reg._by_id(reg.sites, sid, "site_id")["disclosure_status"] == "embargoed"
                else "public"
            ),
        }
        for sid in {s for i in reg.initiatives_for(pledge_id) for s in i["site_ids"]}
    ]

    # 个案反馈只列授权仍有效的去标识记录；个人资料从未入库。
    authorized_feedback = [
        {
            "feedback_id": fb["feedback_id"],
            "org_id": fb["org_id"],
            "case_ref": fb["case_ref"],
            "category": fb["category"],
            "summary": fb["summary"],
            "received_date": fb["received_date"],
            "authorization_valid_until": fb["authorization"]["granted_until"],
            "authorized_now": feedback_authorized(fb, today),
        }
        for fb in reg.feedback
        if fb["pledge_id"] == pledge_id and feedback_authorized(fb, today)
    ]

    # 时间线重放：以量度截止日、里程碑到期日与今天为检查点。
    checkpoints = sorted(
        {
            date.fromisoformat(m["as_of_date"])
            for m in reg.measurements_for(pledge_id)
        }
        | {date.fromisoformat(ms["due_date"]) for ms in pledge["milestones"]}
        | {today}
    )
    timeline = status_timeline(
        pledge, reg.measurements, reg.bases_by_id, checkpoints
    )

    view.update(
        {
            "audience": OVERSIGHT,
            "decision_basis": {
                "warning_pct": pledge["warning_pct"],
                "breach_pct": pledge["breach_pct"],
                "reporting_lag_days": pledge["reporting_lag_days"],
                "expected_interpolated": result["expected"],
                "actual_bridged": result["actual"],
                "gap_pct": result["gap_pct"],
                "basis_chain": result["basis_chain"],
                "measurement_id": result["measurement_id"],
                "basis_hash": result["basis_hash"],
                "rule": "缺口率=(应完成−实完成)/应完成；达预警阈值=预警，达偏离阈值=偏离；无数据或缺报送=预警并标注迟到",
            },
            "revision_chain": [
                {
                    "revision_id": r["revision_id"],
                    "kind": r["kind"],
                    "date": r["date"],
                    "initiative_id": r.get("initiative_id"),
                    "rationale": r["rationale"],
                    "approved_by": r["approved_by"],
                    "old_target": r.get("old_target"),
                    "new_target": r.get("new_target"),
                }
                for r in reg.revisions_for(pledge_id)
            ],
            "sites_internal": sites,
            "authorized_case_feedback": authorized_feedback,
            "status_timeline": [
                {
                    "as_of": row["as_of"],
                    "status": row["status"],
                    "status_label": row["status_label"],
                    "confidence": row["confidence"],
                    "expected": row["expected"],
                    "actual": row["actual"],
                    "basis_hash": row["basis_hash"],
                }
                for row in timeline
            ],
        }
    )
    return view

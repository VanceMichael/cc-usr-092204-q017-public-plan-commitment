#!/usr/bin/env python3
"""生成去标识的领域样例数据（确定性运行：无随机源，哈希自动计算）。

运行：python3 fixtures/build_fixtures.py
产出：
  fixtures/domain.json    —— 规划目标/节点/证据/修订/口径桥接/通知/空间/咨询
  fixtures/feedback.json  —— 社区组织授权登记与授权反馈个案

所有人物、选址、档号均为合成代号；个人信息不以任何形式进入样例。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures"

QUARTER_DUES = [
    "2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31",
    "2026-06-30", "2026-09-30", "2026-12-31", "2027-03-31",
]
PLAN_BY_QUARTER = {
    1: "PLAN-2526", 2: "PLAN-2526", 3: "PLAN-2526", 4: "PLAN-2526",
    5: "PLAN-2627", 6: "PLAN-2627", 7: "PLAN-2728", 8: "PLAN-2728",
}
GENERATED_AT = "2026-09-26T09:00:00+08:00"


def canonical_hash(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def ev(recorded_date: str, days_to_receive: int | None = 20) -> tuple[str, str | None]:
    rec = datetime.fromisoformat(recorded_date + "T18:00:00+08:00")
    if days_to_receive is None:
        return rec.isoformat(), None
    rcv = rec + timedelta(days=days_to_receive)
    return rec.isoformat(), rcv.replace(hour=10, minute=0, second=0).isoformat()


# ---------- 目标定义 ----------

TARGETS = [
    {
        "target_id": "T-HS-01",
        "domain": "public_housing",
        "title": "五年内建成公营房屋单位",
        "metric_code": "HS-UNIT",
        "metric_name": "期内建成公营房屋单位（累计）",
        "direction": "maximize",
        "baseline": {"value": 0, "as_of": "2025-03-31", "metric_version": "v1"},
        "target_value": 196000,
        "unit": "个",
        "period_start": "2025-04-01",
        "period_end": "2030-03-31",
        "responsible_orgs": [
            {"org_code": "HB", "name": "房屋局（样例）", "role": "lead"},
            {"org_code": "HD", "name": "房屋署（样例）", "role": "supporting"},
        ],
        "budget": [
            {"amount_hkd_million": 42000, "fiscal_year": "2025-26", "status": "approved"},
            {"amount_hkd_million": 39800, "fiscal_year": "2025-26", "status": "spent"},
            {"amount_hkd_million": 45500, "fiscal_year": "2026-27", "status": "approved"},
        ],
        "linked_spatial_project_ids": ["SP-HS-01", "SP-HS-02"],
        "linked_consultation_ids": ["CON-001"],
        "locked": True,
        "history": [
            {"at": "2025-04-01T09:00:00+08:00", "event": "published",
             "detail": "随五年规划公布：196000 个公营房屋单位", "by_org": "HB"},
            {"at": "2025-04-01T09:05:00+08:00", "event": "locked",
             "detail": "五年目标值锁定，年度方案只能调整实现路径", "by_org": "HB"},
        ],
    },
    {
        "target_id": "T-HS-02",
        "domain": "public_housing",
        "title": "缩短公屋一般申请者平均轮候时间",
        "metric_code": "HS-LTM",
        "metric_name": "一般申请者平均轮候时间",
        "direction": "minimize",
        "baseline": {"value": 5.3, "as_of": "2025-03-31", "metric_version": "v1"},
        "target_value": 3.0,
        "unit": "年",
        "period_start": "2025-04-01",
        "period_end": "2030-03-31",
        "responsible_orgs": [
            {"org_code": "HB", "name": "房屋局（样例）", "role": "lead"},
            {"org_code": "HD", "name": "房屋署（样例）", "role": "supporting"},
        ],
        "budget": [
            {"amount_hkd_million": 320, "fiscal_year": "2025-26", "status": "spent"},
            {"amount_hkd_million": 360, "fiscal_year": "2026-27", "status": "approved"},
        ],
        "linked_spatial_project_ids": [],
        "linked_consultation_ids": ["CON-001"],
        "locked": True,
        "history": [
            {"at": "2025-04-01T09:00:00+08:00", "event": "published",
             "detail": "五年末平均轮候时间降至 3.0 年", "by_org": "HB"},
            {"at": "2025-04-01T09:05:00+08:00", "event": "locked",
             "detail": "目标锁定", "by_org": "HB"},
        ],
    },
    {
        "target_id": "T-SF-01",
        "domain": "subdivided_flats",
        "title": "完成劣质劏房处所治理（合规或取缔）",
        "metric_code": "SF-PRM",
        "metric_name": "完成治理的不合标准处所（累计）",
        "direction": "maximize",
        "baseline": {"value": 0, "as_of": "2025-03-31", "metric_version": "v1"},
        "target_value": 20000,
        "unit": "处",
        "period_start": "2025-04-01",
        "period_end": "2030-03-31",
        "responsible_orgs": [
            {"org_code": "HB", "name": "房屋局（样例）", "role": "lead"},
            {"org_code": "BD", "name": "屋宇署（样例）", "role": "supporting"},
            {"org_code": "FEHD", "name": "食物环境衞生署（样例）", "role": "supporting"},
        ],
        "budget": [
            {"amount_hkd_million": 180, "fiscal_year": "2025-26", "status": "spent"},
            {"amount_hkd_million": 180, "fiscal_year": "2026-27", "status": "approved"},
            {"amount_hkd_million": 120, "fiscal_year": "2026-27", "status": "revised"},
        ],
        "linked_spatial_project_ids": [],
        "linked_consultation_ids": ["CON-001", "CON-002"],
        "locked": True,
        "history": [
            {"at": "2025-04-01T09:00:00+08:00", "event": "published",
             "detail": "已识别约 20000 处不合标准处所，五年内完成治理", "by_org": "HB"},
            {"at": "2025-04-01T09:05:00+08:00", "event": "locked",
             "detail": "目标锁定", "by_org": "HB"},
            {"at": "2026-05-18T15:00:00+08:00", "event": "rewrite_rejected",
             "detail": "2026-27 年度方案草拟稿拟以「已视察处所」替换「完成治理处所」口径并下调分母，"
                       "被目标治理机制拒绝：在未附口径桥接的情况下径换分母等同改写五年目标",
             "by_org": "HB"},
        ],
    },
    {
        "target_id": "T-HC-01",
        "domain": "healthcare_beds",
        "title": "五年内净增公立医院病床",
        "metric_code": "HC-BED",
        "metric_name": "公立医院病床净增数目（累计）",
        "direction": "maximize",
        "baseline": {"value": 0, "as_of": "2025-03-31", "metric_version": "v1"},
        "target_value": 3000,
        "unit": "张",
        "period_start": "2025-04-01",
        "period_end": "2030-03-31",
        "responsible_orgs": [
            {"org_code": "HHB", "name": "医务衞生局（样例）", "role": "lead"},
            {"org_code": "HA", "name": "医院管理局（样例）", "role": "supporting"},
        ],
        "budget": [
            {"amount_hkd_million": 8600, "fiscal_year": "2025-26", "status": "spent"},
            {"amount_hkd_million": 9200, "fiscal_year": "2026-27", "status": "approved"},
        ],
        "linked_spatial_project_ids": ["SP-HC-01", "SP-HC-02"],
        "linked_consultation_ids": ["CON-001"],
        "locked": True,
        "history": [
            {"at": "2025-04-01T09:00:00+08:00", "event": "published",
             "detail": "五年净增 3000 张公立医院病床", "by_org": "HHB"},
            {"at": "2025-04-01T09:05:00+08:00", "event": "locked",
             "detail": "目标锁定", "by_org": "HHB"},
        ],
    },
    {
        "target_id": "T-DH-01",
        "domain": "district_health",
        "title": "扩展地区康健中心网络受惠规模",
        "metric_code": "DHC-SVC",
        "metric_name": "康健中心累计服务（口径见桥接 BR-DHC-01）",
        "direction": "maximize",
        "baseline": {"value": 0, "as_of": "2025-03-31", "metric_version": "v1"},
        "target_value": 800000,
        "unit": "人（v1 登记会员）",
        "period_start": "2025-04-01",
        "period_end": "2030-03-31",
        "responsible_orgs": [
            {"org_code": "HHB", "name": "医务衞生局（样例）", "role": "lead"},
            {"org_code": "DH", "name": "衞生署（样例）", "role": "supporting"},
        ],
        "budget": [
            {"amount_hkd_million": 740, "fiscal_year": "2025-26", "status": "spent"},
            {"amount_hkd_million": 910, "fiscal_year": "2026-27", "status": "approved"},
        ],
        "linked_spatial_project_ids": ["SP-DH-01"],
        "linked_consultation_ids": ["CON-001", "CON-003"],
        "locked": True,
        "history": [
            {"at": "2025-04-01T09:00:00+08:00", "event": "published",
             "detail": "v1 口径：登记会员 800000 人", "by_org": "HHB"},
            {"at": "2025-04-01T09:05:00+08:00", "event": "locked",
             "detail": "目标按 v1 口径锁定", "by_org": "HHB"},
            {"at": "2026-04-01T00:00:00+08:00", "event": "clarified",
             "detail": "口径经 REV-004 改为 v2 服务人次，附桥接 BR-DHC-01 并重述历史；"
                       "五年目标 v1 等效值 800000 不变",
             "by_org": "HHB"},
        ],
    },
    {
        "target_id": "T-YT-01",
        "domain": "youth",
        "title": "青年实习、交流与住屋项目受惠人数",
        "metric_code": "YTH-CNT",
        "metric_name": "青年项目受惠人数（累计）",
        "direction": "maximize",
        "baseline": {"value": 0, "as_of": "2025-03-31", "metric_version": "v1"},
        "target_value": 80000,
        "unit": "人",
        "period_start": "2025-04-01",
        "period_end": "2030-03-31",
        "responsible_orgs": [
            {"org_code": "HAB", "name": "民政及青年事务局（样例）", "role": "lead"},
        ],
        "budget": [
            {"amount_hkd_million": 260, "fiscal_year": "2025-26", "status": "spent"},
            {"amount_hkd_million": 300, "fiscal_year": "2026-27", "status": "approved"},
        ],
        "linked_spatial_project_ids": ["SP-YT-01"],
        "linked_consultation_ids": ["CON-001"],
        "locked": True,
        "history": [
            {"at": "2025-04-01T09:00:00+08:00", "event": "published",
             "detail": "五年 80000 名青年受惠", "by_org": "HAB"},
            {"at": "2025-04-01T09:05:00+08:00", "event": "locked",
             "detail": "目标锁定", "by_org": "HAB"},
        ],
    },
]

# 每目标八个季度节点的计划值与口径
PLANNED = {
    "T-HS-01": {"code": "HS-UNIT", "unit": "个", "org": "HD", "spatial": None,
                "versions": ["v1"] * 8,
                "values": [9800, 19600, 29400, 39200, 49000, 58800, 68600, 78400]},
    "T-HS-02": {"code": "HS-LTM", "unit": "年", "org": "HD", "spatial": None,
                "versions": ["v1"] * 8,
                "values": [5.2, 5.1, 5.0, 4.9, 4.8, 4.7, 4.6, 4.5]},
    "T-SF-01": {"code": "SF-PRM", "unit": "处", "org": "BD", "spatial": None,
                "versions": ["v1"] * 8,
                "values": [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000]},
    "T-HC-01": {"code": "HC-BED", "unit": "张", "org": "HA", "spatial": "SP-HC-01",
                "versions": ["v1"] * 8,
                "values": [150, 300, 450, 600, 750, 900, 1050, 1200]},
    "T-DH-01": {"code": "DHC-SVC", "unit": "人次", "org": "DH", "spatial": "SP-DH-01",
                "versions": ["v1", "v1", "v1", "v1", "v2", "v2", "v2", "v2"],
                "values": [50000, 100000, 150000, 200000, 250000, 300000, 350000, 400000]},
    "T-YT-01": {"code": "YTH-CNT", "unit": "人", "org": "HAB", "spatial": None,
                "versions": ["v1"] * 8,
                "values": [4000, 8000, 12000, 16000, 20000, 24000, 28000, 32000]},
}

# 截至 2026-06-30 季度（前五个节点）的实测；None 表示数据尚未送达
OBSERVED = {
    "T-HS-01": [
        dict(v=9600), dict(v=19400), dict(v=29100), dict(v=39300),
        dict(v=48500, confidence="provisional", coverage=0.85, is_late=True,
             received=datetime.fromisoformat("2026-09-12T09:00:00+08:00"),
             note="房屋署季度落成数字延误，余约 15% 项目资料待补，暂以初步数字汇报"),
    ],
    "T-HS-02": [
        dict(v=5.2), dict(v=5.05), dict(v=5.05), dict(v=4.95), dict(v=4.9),
    ],
    "T-SF-01": [
        dict(v=900), dict(v=1700), dict(v=2400), dict(v=3000),
        dict(v=None, confidence="estimated", coverage=0.0, is_late=True, received=None,
             note="屋宇署巡查与执法记录尚未送达，当前无可用实测"),
    ],
    "T-HC-01": [
        dict(v=150), dict(v=300), dict(v=460), dict(v=610), dict(v=700),
    ],
    "T-DH-01": [
        dict(v=48000), dict(v=97000), dict(v=146000), dict(v=196000), dict(v=251000),
    ],
    "T-YT-01": [
        dict(v=4100), dict(v=8200), dict(v=12400), dict(v=16800), dict(v=20900),
    ],
}

# 节点层面的机构自报状态覆盖（预测延期只通过修订事件引入，保证时点重放可重现）
MILESTONE_OVERRIDES = {
    ("T-HS-02", 6): {"status": "at_risk"},
    ("T-SF-01", 5): {"status": "off_track"},
    ("T-HC-01", 6): {"status": "deferred"},
}

SELF_STATUS_BY_GAP = {  # 若无覆盖，按实测与计划的关系给机构自报值
    "T-HS-01": ["on_track", "on_track", "on_track", "on_track", "on_track"],
    "T-HS-02": ["on_track", "on_track", "on_track", "at_risk", "at_risk"],
    "T-SF-01": ["at_risk", "at_risk", "off_track", "off_track", "off_track"],
    "T-HC-01": ["done", "done", "done", "on_track", "at_risk"],
    "T-DH-01": ["on_track", "on_track", "on_track", "on_track", "on_track"],
    "T-YT-01": ["done", "done", "done", "done", "done"],
}


def build_milestones_and_evidence():
    milestones, evidence = [], []
    for tid, spec in PLANNED.items():
        slug = tid.removeprefix("T-").replace("-", "")
        for q in range(1, 9):
            due = QUARTER_DUES[q - 1]
            mid = f"MS-{slug}-Q{q}"
            ms = {
                "milestone_id": mid,
                "target_id": tid,
                "plan_id": PLAN_BY_QUARTER[q],
                "sequence": q,
                "title": f"{due[:4]}年第{((q - 1) % 4) + 1}季度量化节点",
                "metric_code": spec["code"],
                "metric_version": spec["versions"][q - 1],
                "planned_value": spec["values"][q - 1],
                "unit": spec["unit"],
                "due_date": due,
                "forecast_date": None,
                "responsible_org_code": spec["org"],
                "budget_refs": [f"{spec['org']}-{PLAN_BY_QUARTER[q]}"],
                "spatial_project_id": spec["spatial"] if q >= 3 else None,
                "status": "on_track",
            }
            if q <= 5:
                ms["status"] = SELF_STATUS_BY_GAP[tid][q - 1]
            ms.update(MILESTONE_OVERRIDES.get((tid, q), {}))
            milestones.append(ms)

            if q <= 5:
                obs = OBSERVED[tid][q - 1]
                recorded, default_received = ev(due)
                received = obs.get("received", default_received)
                received_iso = received.isoformat() if isinstance(received, datetime) else received
                eid = f"EV-{slug}-Q{q}"
                base = {
                    "evidence_id": eid,
                    "milestone_id": mid,
                    "observed_value": obs["v"] if obs["v"] is not None else 0,
                    "metric_version": spec["versions"][q - 1],
                    "recorded_at": recorded,
                    "received_at": received_iso,
                    "source_org_code": spec["org"],
                    "source_ref": f"RPT-{spec['code']}-2026Q{q}-样例",
                    "confidence": obs.get("confidence", "confirmed"),
                    "coverage": obs.get("coverage", 1.0),
                    "is_late": obs.get("is_late", False),
                }
                if obs["v"] is None:
                    base["observed_value"] = 0
                    base["source_ref"] = f"RPT-{spec['code']}-PENDING-样例"
                if "note" in obs:
                    base["note"] = obs["note"]
                base["sha256"] = canonical_hash(base)
                evidence.append(base)
    return milestones, evidence


PLANS = [
    {"plan_id": "PLAN-2526", "fiscal_year": "2025-26", "title": "2025-26 年度施政方案（样例）",
     "published_at": "2025-02-26", "status": "published", "consultation_ids": ["CON-001"]},
    {"plan_id": "PLAN-2627", "fiscal_year": "2026-27", "title": "2026-27 年度施政方案（样例）",
     "published_at": "2026-02-25", "status": "published",
     "consultation_ids": ["CON-002", "CON-003"]},
    {"plan_id": "PLAN-2728", "fiscal_year": "2027-28", "title": "2027-28 年度施政方案（草拟咨询，样例）",
     "published_at": "2026-09-10", "status": "consultation", "consultation_ids": []},
]

REVISIONS = [
    {
        "revision_id": "REV-001",
        "at": "2026-08-20T11:00:00+08:00",
        "plan_id": "PLAN-2627",
        "target_id": "T-HS-02",
        "milestone_id": "MS-HS02-Q6",
        "kind": "reschedule",
        "touches_five_year_target": False,
        "reason": "建造业人力紧张与个别用地交收滞后，2026 年第三季节点预测由 9 月底顺延约 11 周；"
                  "已加推组装合成法合约与补地价加快安排，五年末降至 3.0 年的目标不变。",
        "evidence_ids": ["EV-HS02-Q5"],
        "by_org": "HB",
        "decided_by": "年度方案跨部门会议通过并公开",
        "old": {"due_date": "2026-09-30", "forecast_date": None},
        "new": {"due_date": "2026-09-30", "forecast_date": "2026-12-15"},
    },
    {
        "revision_id": "REV-002",
        "at": "2026-08-05T10:30:00+08:00",
        "plan_id": "PLAN-2627",
        "target_id": "T-SF-01",
        "milestone_id": "MS-SF01-Q5",
        "kind": "path_change",
        "touches_five_year_target": False,
        "reason": "首年合规进度落后：旧楼业主维修需时、复核程序排期长。2026-27 年度方案增拨 1.2 亿港元，"
                  "加设屋宇署/食环署联合专责小组，在观塘试行「一站式合规支援」，五年治理 20000 处的目标不变。",
        "evidence_ids": ["EV-SF01-Q4"],
        "by_org": "HB",
        "decided_by": "年度方案修订经立法会事务委员会简报后公开",
        "old": {"teams": 4, "annual_budget_hkd_million": 180},
        "new": {"teams": 9, "annual_budget_hkd_million": 300, "pilot_district": "观塘"},
    },
    {
        "revision_id": "REV-003",
        "at": "2026-09-02T16:00:00+08:00",
        "plan_id": "PLAN-2627",
        "target_id": "T-HC-01",
        "milestone_id": "MS-HC01-Q6",
        "kind": "reschedule",
        "touches_five_year_target": False,
        "reason": "东区分院大楼机电工程因主要承建商重组需重新招标，第三季 150 张病床节点顺延至 2027 年 1 月；"
                  "医管局已按合约追讨档期损失，五年净增 3000 张病床目标不变。",
        "evidence_ids": ["EV-HC01-Q5"],
        "by_org": "HHB",
        "decided_by": "医管局董事局工程委员会核准并公开",
        "old": {"due_date": "2026-09-30", "forecast_date": None},
        "new": {"due_date": "2026-09-30", "forecast_date": "2027-01-31"},
    },
    {
        "revision_id": "REV-004",
        "at": "2026-04-01T00:00:00+08:00",
        "plan_id": "PLAN-2627",
        "target_id": "T-DH-01",
        "milestone_id": "MS-DH01-Q5",
        "kind": "metric_rebaseline",
        "touches_five_year_target": True,
        "reason": "v1「登记会员人数」未能反映实际服务量，自 2026-04-01 起改用 v2「累计接受评估或服务人次」；"
                  "经平行统计三个月验证换算系数 1.25，历史值已按桥接 BR-DHC-01 重述，五年目标 v1 等效值维持 800000。",
        "evidence_ids": ["EV-DH01-Q4"],
        "by_org": "HHB",
        "decided_by": "统计口径变更经审计协作组登记并随方案公开",
        "old": {"metric_version": "v1", "metric_name": "登记会员人数"},
        "new": {"metric_version": "v2", "metric_name": "累计接受评估或服务人次",
                "bridge_id": "BR-DHC-01"},
    },
]

BRIDGES = [
    {
        "bridge_id": "BR-DHC-01",
        "metric_code": "DHC-SVC",
        "from_version": "v1",
        "to_version": "v2",
        "effective_at": "2026-04-01",
        "method": "factor",
        "factor": 1.25,
        "additive": None,
        "restated_from_values": {
            "2025-06-30": 60000,
            "2025-09-30": 121250,
            "2025-12-31": 182500,
            "2026-03-31": 245000,
        },
        "rationale": "v2 覆盖健康评估、慢性护理及复康服务人次；三个月平行统计对 v1 的平均比率为 1.25。",
    }
]

DATA_NOTICES = [
    {
        "notice_id": "NTC-001",
        "target_id": "T-HS-01",
        "org_code": "HD",
        "expected_by": "2026-07-31T12:00:00+08:00",
        "received_at": "2026-09-12T09:00:00+08:00",
        "severity": "recovered",
        "impact": "2026 年第二季落成数字延误 43 日；送达前相关判定以 provisional、覆盖率 0.85 显示。",
    },
    {
        "notice_id": "NTC-002",
        "target_id": "T-SF-01",
        "org_code": "BD",
        "expected_by": "2026-09-15T12:00:00+08:00",
        "received_at": None,
        "severity": "delayed",
        "impact": "屋宇署 2026 年第二季巡查与执法记录尚未送达；劏房治理当前进度无实测，按低置信显示。",
    },
]

SPATIAL_PROJECTS = [
    {
        "spatial_project_id": "SP-HS-01", "name": "东涌新市镇扩展公屋发展（样例）",
        "project_type": "housing_development", "district": "离岛",
        "site_public": True, "granularity": "site",
        "site_location_classified": None,
        "status": "works", "linked_target_ids": ["T-HS-01", "T-HS-02"],
    },
    {
        "spatial_project_id": "SP-HS-02", "name": "北区新增公屋用地（代号，样例）",
        "project_type": "housing_development", "district": "北区",
        "site_public": False, "granularity": "district_only",
        "site_location_classified": "LOT-NTM-SECRET-0124（样例，严禁外泄）",
        "status": "planning", "linked_target_ids": ["T-HS-01"],
    },
    {
        "spatial_project_id": "SP-HC-01", "name": "东区分院扩建大楼（样例）",
        "project_type": "healthcare_facility", "district": "东区",
        "site_public": True, "granularity": "site",
        "site_location_classified": None,
        "status": "works", "linked_target_ids": ["T-HC-01"],
    },
    {
        "spatial_project_id": "SP-HC-02", "name": "新界西北医院新大楼（代号，样例）",
        "project_type": "healthcare_facility", "district": "元朗",
        "site_public": False, "granularity": "district_only",
        "site_location_classified": "SITE-YL-SECRET-0077（样例，严禁外泄）",
        "status": "planning", "linked_target_ids": ["T-HC-01"],
    },
    {
        "spatial_project_id": "SP-DH-01", "name": "深水埗地区康健中心（样例）",
        "project_type": "dchc", "district": "深水埗",
        "site_public": True, "granularity": "site",
        "site_location_classified": None,
        "status": "completed", "linked_target_ids": ["T-DH-01"],
    },
    {
        "spatial_project_id": "SP-YT-01", "name": "青年共享空间试验点（样例）",
        "project_type": "youth_space", "district": "油尖旺",
        "site_public": True, "granularity": "site",
        "site_location_classified": None,
        "status": "works", "linked_target_ids": ["T-YT-01"],
    },
]

CONSULTATIONS = [
    {
        "consultation_id": "CON-001",
        "title": "五年民生规划公众咨询（样例）",
        "period_start": "2025-01-08", "period_end": "2025-03-31",
        "submissions_total": 17234,
        "themes": [
            {"theme": "加快公屋落成、缩短轮候", "count": 8412,
             "disposition": "adopted",
             "response_summary": "纳入 T-HS-01/02 量化路径，按季公开节点。"},
            {"theme": "加强劣质劏房治理与安置配套", "count": 5603,
             "disposition": "partly_adopted",
             "response_summary": "强制登记与联合执法纳入 T-SF-01；过渡性安置供应受场地限制需分年推进。"},
            {"theme": "基层医疗可及性与地区康健中心", "count": 2110,
             "disposition": "adopted",
             "response_summary": "康健中心网络扩展与服务人次口径优化纳入 T-DH-01。"},
            {"theme": "青年就业、实习与住屋支援", "count": 1109,
             "disposition": "partly_adopted",
             "response_summary": "纳入 T-YT-01；宿舍名额按可用物业逐年增加。"},
        ],
        "linked_target_ids": ["T-HS-01", "T-HS-02", "T-SF-01", "T-HC-01",
                              "T-DH-01", "T-YT-01"],
    },
    {
        "consultation_id": "CON-002",
        "title": "不合标准处所规管制度咨询（样例）",
        "period_start": "2025-09-01", "period_end": "2025-11-30",
        "submissions_total": 3108,
        "themes": [
            {"theme": "整改资助与技术支援", "count": 1420, "disposition": "adopted",
             "response_summary": "REV-002 增拨资源并设观塘一站式试点。"},
            {"theme": "执法时限与上诉安排", "count": 980, "disposition": "partly_adopted",
             "response_summary": "承诺复核时限公开，上诉机制维持现行法定程序。"},
        ],
        "linked_target_ids": ["T-SF-01"],
    },
    {
        "consultation_id": "CON-003",
        "title": "地区康健中心网络扩展地区咨询（样例）",
        "period_start": "2026-02-02", "period_end": "2026-03-15",
        "submissions_total": 862,
        "themes": [
            {"theme": "夜间及周末服务", "count": 433, "disposition": "adopted",
             "response_summary": "新签约中心须提供最少两晚晚间服务。"},
        ],
        "linked_target_ids": ["T-DH-01"],
    },
]


def build_feedback():
    orgs = [
        {"org_code": "CSO-KT", "name": "观塘友里基层协会（样例）",
         "scope_codes": ["subdivided_flats", "public_housing"],
         "districts": ["观塘", "黄大仙", "西贡"],
         "access_token": "TOKEN-KT-DEMO-001"},
        {"org_code": "CSO-MK", "name": "油尖旺健康互助组（样例）",
         "scope_codes": ["district_health", "healthcare"],
         "districts": ["油尖旺"],
         "access_token": "TOKEN-MK-DEMO-002"},
        {"org_code": "CSO-NW", "name": "新界西北青年连线（样例）",
         "scope_codes": ["youth"],
         "districts": ["元朗", "屯门"],
         "access_token": "TOKEN-NW-DEMO-003"},
    ]

    def consent_hash(ref: str) -> str:
        return hashlib.sha256(ref.encode("utf-8")).hexdigest()

    cases = [
        {
            "case_ref": "CASE-2026-0001",
            "target_id": "T-SF-01",
            "milestone_id": "MS-SF01-Q5",
            "org_code": "CSO-KT",
            "issue_domain": "subdivided_flats",
            "status": "referred",
            "consent": {
                "grant": True,
                "scope_codes": ["subdivided_flats"],
                "granted_at": "2026-07-02T14:00:00+08:00",
                "record_ref_hash": consent_hash("CONSENT-KT-0001（样例档号）"),
                "expires_at": "2027-07-02T14:00:00+08:00",
            },
            "resident": {"pseudonym": "PSN-7F3A9K2Q", "district": "观塘"},
            "summary": "住户反映单位内消防通风设施欠妥，业主长期未维修，希望转介联合专责小组跟进。",
            "created_at": "2026-07-03T10:20:00+08:00",
            "events": [
                {"at": "2026-07-03T10:20:00+08:00", "action": "submitted",
                 "by_org": "CSO-KT"},
                {"at": "2026-07-08T11:00:00+08:00", "action": "triaged",
                 "by_org": "HB", "note_public": "已核对授权范围，归类为消防设施合规个案。"},
                {"at": "2026-07-15T09:30:00+08:00", "action": "referred",
                 "by_org": "BD", "note_public": "转介屋宇署联合专责小组排期视察。"},
            ],
        },
        {
            "case_ref": "CASE-2026-0002",
            "target_id": "T-DH-01",
            "milestone_id": None,
            "org_code": "CSO-MK",
            "issue_domain": "district_health",
            "status": "resolved",
            "consent": {
                "grant": True,
                "scope_codes": ["district_health"],
                "granted_at": "2026-05-11T09:00:00+08:00",
                "record_ref_hash": consent_hash("CONSENT-MK-0002（样例档号）"),
                "expires_at": None,
            },
            "resident": {"pseudonym": "PSN-2D9L4QRT", "district": "油尖旺"},
            "summary": "长者反映康健中心健康评估转介专科轮候时间不清晰，希望收到书面进度通知。",
            "created_at": "2026-05-12T15:40:00+08:00",
            "events": [
                {"at": "2026-05-12T15:40:00+08:00", "action": "submitted",
                 "by_org": "CSO-MK"},
                {"at": "2026-05-20T10:00:00+08:00", "action": "responded",
                 "by_org": "DH", "note_public": "中心已增设转候进度短讯，并在网页公布各区分区轮候概览。"},
                {"at": "2026-06-02T10:00:00+08:00", "action": "resolved",
                 "by_org": "CSO-MK"},
            ],
        },
        {
            "case_ref": "CASE-2026-0003",
            "target_id": "T-YT-01",
            "milestone_id": None,
            "org_code": "CSO-NW",
            "issue_domain": "youth",
            "status": "received",
            "consent": {
                "grant": True,
                "scope_codes": ["youth"],
                "granted_at": "2026-09-18T18:00:00+08:00",
                "record_ref_hash": consent_hash("CONSENT-NW-0003（样例档号）"),
                "expires_at": None,
            },
            "resident": {"pseudonym": "PSN-9B2X7HME", "district": "元朗"},
            "summary": "在职青年查询实习资助计划下一轮申请时间与行业范围。",
            "created_at": "2026-09-19T12:05:00+08:00",
            "events": [
                {"at": "2026-09-19T12:05:00+08:00", "action": "submitted",
                 "by_org": "CSO-NW"},
            ],
        },
    ]
    return {"organizations": orgs, "cases": cases}


def main() -> None:
    milestones, evidence = build_milestones_and_evidence()
    package = {
        "package_id": "PLG-2026-09-26-01",
        "generated_at": GENERATED_AT,
        "rules_version": "status-rules-v1.0",
        "targets": TARGETS,
        "milestones": milestones,
        "evidence": evidence,
        "plans": PLANS,
        "revisions": REVISIONS,
        "metric_bridges": BRIDGES,
        "data_notices": DATA_NOTICES,
        "spatial_projects": SPATIAL_PROJECTS,
        "consultations": CONSULTATIONS,
    }
    (OUT / "domain.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "feedback.json").write_text(
        json.dumps(build_feedback(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(milestones)} milestones, {len(evidence)} evidence, "
          f"{len(TARGETS)} targets, {len(REVISIONS)} revisions")


if __name__ == "__main__":
    main()

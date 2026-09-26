"""承诺兑现判定：纯函数，无文件与网络依赖。

判定规则对公众与监督人员完全一致，且只依赖输入数据；同一组输入在任一时点
重算都得到相同结果与相同的 basis_hash，便于复核"为何被判定为按期/预警/偏离"。
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Iterable

ON_TRACK = "on_track"
WATCH = "watch"
OFF_TRACK = "off_track"

VERIFIED = "verified"
PROVISIONAL = "provisional"
OVERDUE_PENDING = "overdue_pending"

STATUS_LABELS = {
    ON_TRACK: "按期",
    WATCH: "预警",
    OFF_TRACK: "偏离",
}

CONFIDENCE_LABELS = {
    VERIFIED: "已核实",
    PROVISIONAL: "初步数字",
    OVERDUE_PENDING: "跨部门数据迟到，待报送",
}


def _d(value: str) -> date:
    return date.fromisoformat(value)


def interpolate_expected(pledge: dict, as_of: date) -> float:
    """按规划起点(0)至各里程碑的累计目标做分段线性插值，求 as_of 的应完成量。"""
    anchors: list[tuple[date, float]] = [
        (_d(pledge["plan_start_date"]), 0.0)
    ]
    anchors.extend(
        (_d(m["due_date"]), float(m["cumulative_target"]))
        for m in pledge["milestones"]
    )
    anchors.sort(key=lambda p: p[0])

    if as_of <= anchors[0][0]:
        return 0.0
    if as_of >= anchors[-1][0]:
        return float(pledge["five_year_target"])
    for (d0, v0), (d1, v1) in zip(anchors, anchors[1:]):
        if d0 <= as_of <= d1:
            span = (d1 - d0).days
            return v0 + (v1 - v0) * ((as_of - d0).days / span)
    return 0.0


def bridge_to_current(
    value: float,
    measurement_basis_id: str,
    target_basis_id: str,
    bases_by_id: dict[str, dict],
) -> tuple[float, list[str]]:
    """把按旧口径记录的数值沿桥接链折算到承诺现行口径。

    新口径 basis 上的 bridge 表示：新口径值 = 旧口径值 × factor + constant。
    返回折算值与途经的口径编号（审计轨迹）。
    """
    chain = [measurement_basis_id]
    current_basis = measurement_basis_id
    current_value = float(value)
    # 桥接链理论上很短；上限防止循环引用。
    for _ in range(len(bases_by_id) + 1):
        if current_basis == target_basis_id:
            return current_value, chain
        nxt = None
        for basis in bases_by_id.values():
            bridge = basis.get("bridge")
            if bridge and bridge["from_basis"] == current_basis:
                nxt = basis
                break
        if nxt is None:
            raise ValueError(
                f"口径 {current_basis} 无法桥接到 {target_basis_id}：缺少可比桥接"
            )
        b = nxt["bridge"]
        current_value = current_value * b["factor"] + b["constant"]
        current_basis = nxt["basis_id"]
        chain.append(current_basis)
    raise ValueError("口径桥接链存在循环")


def latest_measurement(
    measurements: Iterable[dict], pledge_id: str, as_of: date
) -> dict | None:
    candidates = [
        m
        for m in measurements
        if m["pledge_id"] == pledge_id and _d(m["as_of_date"]) <= as_of
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda m: (_d(m["as_of_date"]), m["measure_id"]))


def derive_confidence(
    measurement: dict | None, as_of: date, reporting_lag_days: int
) -> str:
    """置信状态：已核实／初步；最新数据超出报送滞后期即为"迟到待报"。"""
    if measurement is None:
        return OVERDUE_PENDING
    lag_cutoff = _d(measurement["as_of_date"])
    lag_cutoff = lag_cutoff.fromordinal(
        lag_cutoff.toordinal() + reporting_lag_days
    )
    if lag_cutoff < as_of:
        return OVERDUE_PENDING
    return measurement["confidence"] if measurement["confidence"] in (
        VERIFIED,
        PROVISIONAL,
    ) else PROVISIONAL


def classify(gap_pct: float, warning_pct: float, breach_pct: float) -> str:
    if gap_pct >= breach_pct:
        return OFF_TRACK
    if gap_pct >= warning_pct:
        return WATCH
    return ON_TRACK


def milestone_position(pledge: dict, as_of: date) -> dict:
    due = None
    upcoming = None
    for m in pledge["milestones"]:
        if _d(m["due_date"]) <= as_of:
            due = m
        elif upcoming is None:
            upcoming = m
    return {"last_due": due, "next": upcoming}


def assess_pledge(
    pledge: dict,
    measurements: Iterable[dict],
    bases_by_id: dict[str, dict],
    as_of: date,
) -> dict:
    """对单个承诺在 as_of 时点做可重算判定。"""
    measurement = latest_measurement(measurements, pledge["pledge_id"], as_of)
    expected = interpolate_expected(pledge, as_of)

    actual = None
    bridged_from = None
    basis_chain: list[str] = []
    if measurement is not None:
        value, chain = bridge_to_current(
            measurement["value"],
            measurement["basis_id"],
            pledge["measurement_basis"],
            bases_by_id,
        )
        actual = round(value)
        basis_chain = chain
        bridged_from = measurement["basis_id"] if chain[0] != chain[-1] else None

    gap_pct = (expected - actual) / expected if expected > 0 and actual is not None else None
    status = classify(
        gap_pct, pledge["warning_pct"], pledge["breach_pct"]
    ) if gap_pct is not None else WATCH

    confidence = derive_confidence(
        measurement, as_of, pledge["reporting_lag_days"]
    )
    position = milestone_position(pledge, as_of)

    result = {
        "pledge_id": pledge["pledge_id"],
        "as_of": as_of.isoformat(),
        "expected": round(expected),
        "actual": actual,
        "unit": pledge["unit"],
        "gap_pct": None if gap_pct is None else round(gap_pct, 4),
        "status": status,
        "status_label": STATUS_LABELS[status],
        "confidence": confidence,
        "confidence_label": CONFIDENCE_LABELS[confidence],
        "data_as_of": measurement["as_of_date"] if measurement else None,
        "basis_chain": basis_chain,
        "bridged_from": bridged_from,
        "measurement_id": measurement["measure_id"] if measurement else None,
        "evidence_ids": list(measurement["evidence_ids"]) if measurement else [],
        "last_due_milestone": position["last_due"],
        "next_milestone": position["next"],
        "five_year_target": pledge["five_year_target"],
        "measurement_note": measurement.get("note") if measurement else None,
    }
    result["basis_hash"] = _basis_hash(pledge, result)
    return result


def _basis_hash(pledge: dict, result: dict) -> str:
    """对判定依据做确定性摘要：阈值、应完成量、实测量、口径链与数据截止日。"""
    payload = {
        "pledge_id": pledge["pledge_id"],
        "as_of": result["as_of"],
        "measurement_basis": pledge["measurement_basis"],
        "warning_pct": pledge["warning_pct"],
        "breach_pct": pledge["breach_pct"],
        "expected": result["expected"],
        "actual": result["actual"],
        "measurement_id": result["measurement_id"],
        "basis_chain": result["basis_chain"],
        "data_as_of": result["data_as_of"],
        "five_year_target": pledge["five_year_target"],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def status_timeline(
    pledge: dict,
    measurements: Iterable[dict],
    bases_by_id: dict[str, dict],
    checkpoints: Iterable[date],
) -> list[dict]:
    """在一组历史时点重算判定，供监督人员回放状态变迁。"""
    materialized = list(measurements)
    return [
        assess_pledge(pledge, materialized, bases_by_id, cp)
        for cp in sorted(checkpoints)
    ]

"""五年目标治理：年度方案可调整实现路径，但不得偷偷改写五年目标。

apply_revision 是唯一允许写入修订的入口，它强制：
1. 目标已锁定后，任何试图修改 target_value 的修订一律拒绝并留痕 rewrite_rejected；
2. metric_rebaseline 触及口径时必须提供有效桥接，且换算后的五年目标等效值不变
   （容差 0.5%，应对四舍五入）；
3. path_change / reschedule / budget_revise 不得携带 target_value 变更。
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from src import bridging

TARGET_VALUE_TOLERANCE = 0.005


class GovernanceError(ValueError):
    pass


class Governance:
    def __init__(self, domain: dict):
        self.domain = domain
        self.targets = {t["target_id"]: t for t in domain["targets"]}

    def apply_revision(self, revision: dict) -> dict:
        """校验并接收一个修订事件；返回写入结果。拒绝时抛 GovernanceError。"""
        for key in ("revision_id", "at", "plan_id", "target_id", "milestone_id",
                    "kind", "touches_five_year_target", "reason", "by_org"):
            if key not in revision:
                raise GovernanceError(f"修订缺少字段 {key}")
        target = self.targets.get(revision["target_id"])
        if target is None:
            raise GovernanceError(f"未知目标 {revision['target_id']}")
        if revision["revision_id"] in {r["revision_id"] for r in self.domain["revisions"]}:
            raise GovernanceError(f"修订编号重复 {revision['revision_id']}")

        new = revision.get("new", {})
        if "target_value" in new:
            self._guard_target_value(target, revision, new["target_value"])
        if revision["kind"] == "metric_rebaseline":
            self._guard_rebaseline(target, revision, new)
        if revision["kind"] in ("path_change", "reschedule", "budget_revise"):
            if revision["touches_five_year_target"]:
                raise GovernanceError(
                    f"{revision['revision_id']}: {revision['kind']} 不得标记为触及五年目标")

        self.domain["revisions"].append(deepcopy(revision))
        return {"accepted": True, "revision_id": revision["revision_id"]}

    def _guard_target_value(self, target: dict, revision: dict, new_value) -> None:
        if not target.get("locked"):
            return
        if new_value != target["target_value"]:
            target["history"].append({
                "at": revision["at"],
                "event": "rewrite_rejected",
                "by_org": revision["by_org"],
                "detail": (f"修订 {revision['revision_id']} 试图将五年目标值由 "
                           f"{target['target_value']} 改为 {new_value}，已被拒绝；"
                           f"理由：{revision['reason']}"),
            })
            raise GovernanceError(
                f"五年目标 {target['target_id']} 已锁定：年度方案不得改写目标值"
                f"（{target['target_value']} → {new_value}）。已留痕 rewrite_rejected。")

    def _guard_rebaseline(self, target: dict, revision: dict, new: dict) -> None:
        bridge_id = new.get("bridge_id")
        if not bridge_id:
            raise GovernanceError(
                f"{revision['revision_id']}: 口径变更必须附有效口径桥接（metric_bridge 编号）")
        bridge = next((b for b in self.domain["metric_bridges"]
                       if b["bridge_id"] == bridge_id), None)
        if bridge is None:
            raise GovernanceError(f"{revision['revision_id']}: 桥接 {bridge_id} 不存在")
        to_version = new.get("metric_version", bridge["to_version"])
        # 用桥接把锁定目标值换算到新口径，再要求新目标值显式等于该等效值
        equivalent, _ = bridging.convert(
            float(target["target_value"]), target["metric_code"],
            bridge["from_version"], to_version, self.domain["metric_bridges"])
        declared = new.get("target_value_equivalent", equivalent)
        if abs(declared - equivalent) / equivalent > TARGET_VALUE_TOLERANCE:
            raise GovernanceError(
                f"{revision['revision_id']}: 口径变更后五年目标等效值 {equivalent} "
                f"与申报 {declared} 不一致；缺桥接的换口径视为改写目标")

    def try_illegal_rewrite(self, revision: dict) -> dict:
        """供演练/测试：提交一个必然违规的改写，返回拒绝留痕而不中断。"""
        try:
            self.apply_revision(revision)
        except GovernanceError as exc:
            return {"accepted": False, "reason": str(exc)}
        return {"accepted": True, "revision_id": revision["revision_id"]}

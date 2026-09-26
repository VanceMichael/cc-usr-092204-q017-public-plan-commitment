"""统计口径桥接：口径变化时把观测值换算到可比版本，并保留换算轨迹。

支持 method：factor（乘法）、additive（加法）、factor_additive（先乘后加）、
parallel_series（仅提供重述序列，不可代数换算）。
"""
from __future__ import annotations

from dataclasses import dataclass


class BridgeError(ValueError):
    pass


@dataclass(frozen=True)
class ConversionStep:
    bridge_id: str
    metric_code: str
    from_version: str
    to_version: str
    method: str
    value_before: float
    value_after: float

    def as_dict(self) -> dict:
        return {
            "bridge_id": self.bridge_id,
            "metric_code": self.metric_code,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "method": self.method,
            "value_before": self.value_before,
            "value_after": self.value_after,
        }


def _apply(bridge: dict, value: float) -> float:
    method = bridge["method"]
    if method == "factor":
        return value * bridge["factor"]
    if method == "additive":
        return value + bridge["additive"]
    if method == "factor_additive":
        return value * bridge["factor"] + bridge["additive"]
    if method == "parallel_series":
        raise BridgeError(
            f"桥接 {bridge['bridge_id']} 为平行序列，不能代数换算；"
            "请改用 restated_from_values 中的重述值")
    raise BridgeError(f"未知换算方法: {method}")


def _find_bridge(bridges: list[dict], metric_code: str,
                 from_version: str, to_version: str) -> dict | None:
    for b in bridges:
        if (b["metric_code"] == metric_code and b["from_version"] == from_version
                and b["to_version"] == to_version):
            return b
    return None


def convert(value: float, metric_code: str, from_version: str, to_version: str,
            bridges: list[dict], *, _depth: int = 0) -> tuple[float, list[ConversionStep]]:
    """把 value 从 from_version 换算到 to_version，返回(换算值, 换算轨迹)。

    支持正向直接换算与单跳反向换算（v2→v1），以及最多 3 跳的链路。
    """
    if from_version == to_version:
        return value, []
    if _depth > 3:
        raise BridgeError(f"{metric_code}: {from_version}→{to_version} 桥接链路过长")

    direct = _find_bridge(bridges, metric_code, from_version, to_version)
    if direct:
        converted = _apply(direct, value)
        return converted, [ConversionStep(
            direct["bridge_id"], metric_code, from_version, to_version,
            direct["method"], value, converted)]

    reverse = _find_bridge(bridges, metric_code, to_version, from_version)
    if reverse:
        converted = _reverse_apply(reverse, value)
        return converted, [ConversionStep(
            reverse["bridge_id"], metric_code, from_version, to_version,
            reverse["method"] + "(反向)", value, converted)]

    # 尝试单跳中转
    for b in bridges:
        if b["metric_code"] != metric_code or b["from_version"] != from_version:
            continue
        mid = b["to_version"]
        try:
            mid_value, steps1 = convert(value, metric_code, from_version, mid,
                                        bridges, _depth=_depth + 1)
            rest_value, steps2 = convert(mid_value, metric_code, mid, to_version,
                                         bridges, _depth=_depth + 1)
            return rest_value, steps1 + steps2
        except BridgeError:
            continue
    raise BridgeError(f"找不到 {metric_code}: {from_version}→{to_version} 的口径桥接")


def _reverse_apply(bridge: dict, value: float) -> float:
    method = bridge["method"]
    if method == "factor":
        return value / bridge["factor"]
    if method == "additive":
        return value - bridge["additive"]
    if method == "factor_additive":
        return (value - bridge["additive"]) / bridge["factor"]
    raise BridgeError(f"桥接 {bridge['bridge_id']} 的 {method} 不可反向换算")


def restated_value(bridge: dict, as_of_date: str) -> float | None:
    """取某历史时点按新口径的重述值（平行序列或核对用）。"""
    return bridge.get("restated_from_values", {}).get(as_of_date)

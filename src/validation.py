"""零依赖的 JSON Schema 子集校验器。

仅实现本仓库契约实际使用的特性：type / format / enum / const / required /
properties / additionalProperties / items / minimum / maximum /
minItems / minLength / pattern 以及 #/$defs 下的 $ref。
生产环境可替换为 jsonschema，接口 validate(instance, schema) 保持不变。
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


class SchemaError(ValueError):
    pass


def _check_type(value: Any, expected: str | list[str]) -> bool:
    types = expected if isinstance(expected, list) else [expected]
    return any(_TYPE_CHECKS[t](value) for t in types)


def _check_format(value: Any, fmt: str) -> bool:
    if not isinstance(value, str):
        return True
    try:
        if fmt == "date":
            date.fromisoformat(value)
        elif fmt == "date-time":
            datetime.fromisoformat(value)
        else:
            return True
    except ValueError:
        return False
    return True


def validate(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """返回错误信息列表；空列表表示通过。"""
    errors: list[str] = []
    _validate(instance, schema, path, schema, errors)
    return errors


def _resolve(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    # 仅支持本地 "#/$defs/Name" 形式
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        raise SchemaError(f"暂不支持的 $ref: {ref}")
    name = ref[len(prefix):]
    try:
        return root["$defs"][name]
    except KeyError as exc:
        raise SchemaError(f"$ref 指向不存在的定义: {ref}") from exc


def _validate(value: Any, schema: dict[str, Any], path: str,
              root: dict[str, Any], errors: list[str]) -> None:
    if "$ref" in schema:
        _validate(value, _resolve(schema["$ref"], root), path, root, errors)
        return

    expected_type = schema.get("type")
    if expected_type and not _check_type(value, expected_type):
        errors.append(f"{path}: 类型应为 {expected_type}，实际为 {type(value).__name__}")
        return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: 值 {value!r} 不在允许范围内")
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: 值应为 {schema['const']!r}")
    if "format" in schema and not _check_format(value, schema["format"]):
        errors.append(f"{path}: {value!r} 不符合 {schema['format']} 格式")
    if "pattern" in schema and isinstance(value, str):
        if not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} 不符合模式 {schema['pattern']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} 小于最小值 {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} 大于最大值 {schema['maximum']}")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: 缺少必填字段 {key!r}")
        properties = schema.get("properties", {})
        for key, sub in value.items():
            sub_path = f"{path}.{key}"
            if key in properties:
                _validate(sub, properties[key], sub_path, root, errors)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: 不允许的额外字段 {key!r}")
            elif isinstance(schema.get("additionalProperties"), dict):
                _validate(sub, schema["additionalProperties"], sub_path, root, errors)

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: 数组长度 {len(value)} 小于最小值 {schema['minItems']}")
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(value):
                _validate(item, item_schema, f"{path}[{i}]", root, errors)

    if isinstance(value, str) and "minLength" in schema:
        if len(value) < schema["minLength"]:
            errors.append(f"{path}: 字符串短于最小长度 {schema['minLength']}")


def require_valid(instance: Any, schema: dict[str, Any]) -> None:
    errors = validate(instance, schema)
    if errors:
        raise SchemaError("；".join(errors))

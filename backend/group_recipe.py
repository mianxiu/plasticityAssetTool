"""Ordered solid operations captured from a Plasticity group."""
from .model_clipboard import parse_model

MODES = {"+": "union", "-": "difference", "&": "intersection", "^": "new-body"}


def validate_recipe(value, model=None):
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("不支持的组运算格式")
    name, parts = value.get("name"), value.get("parts")
    if not isinstance(name, str) or not 1 <= len(name) <= 120:
        raise ValueError("组名称无效或超过 120 字符")
    if not isinstance(parts, list) or not 1 <= len(parts) <= 128:
        raise ValueError("组必须包含 1 至 128 个直接子实体")
    result = []
    for index, part in enumerate(parts):
        if not isinstance(part, dict) or type(part.get("index")) is not int or part["index"] != index:
            raise ValueError("组子部件的索引或顺序无效")
        title = part.get("name")
        if not isinstance(title, str) or not 1 <= len(title) <= 120:
            raise ValueError("子部件名称无效或超过 120 字符")
        mode = MODES.get(title.lstrip()[:1], "new-body")
        if part.get("mode") != mode:
            raise ValueError("子部件名称与布尔模式不一致")
        result.append({"index": index, "name": title, "mode": mode})
    if model is not None and len(parse_model(model)) != len(parts):
        raise ValueError("组子部件与模型数量不一致")
    return {"version": 1, "name": name, "parts": result}

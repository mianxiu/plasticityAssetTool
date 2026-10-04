"""Persistent local preferences for the embedded component panel."""
import json
import logging
from pathlib import Path


class PanelSettings:
    def __init__(self, root):
        self.path = Path(root) / ".runtime" / "panel-settings.json"
        self.position = "fixed"
        self.sidebar_mode = "fixed"
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if value.get("position") in ("fixed", "cursor"):
                self.position = value["position"]
            if value.get("sidebar_mode") in ("fixed", "hover"):
                self.sidebar_mode = value["sidebar_mode"]
        except FileNotFoundError:
            pass
        except (OSError, ValueError, AttributeError):
            logging.warning("Panel settings could not be read; using fixed position")

    def snapshot(self):
        return {"position": self.position, "sidebar_mode": self.sidebar_mode}

    def update(self, position=None, sidebar_mode=None):
        if position is None and sidebar_mode is None:
            raise ValueError("请指定面板设置")
        if position is not None and position not in ("fixed", "cursor"):
            raise ValueError("请选择固定位置或鼠标位置")
        if sidebar_mode is not None and sidebar_mode not in ("fixed", "hover"):
            raise ValueError("请选择固定展开或悬停展开")
        settings = {"position": position or self.position, "sidebar_mode": sidebar_mode or self.sidebar_mode}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(settings), encoding="utf-8")
        temporary.replace(self.path)
        self.position, self.sidebar_mode = settings["position"], settings["sidebar_mode"]
        return self.snapshot()

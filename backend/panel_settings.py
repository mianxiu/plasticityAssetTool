"""Persistent local preferences for the embedded component panel."""
import json
import logging
from pathlib import Path


class PanelSettings:
    def __init__(self, root):
        self.path = Path(root) / ".runtime" / "panel-settings.json"
        self.position = "fixed"
        self.sidebar_mode = "fixed"
        self.card_size = 184
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if value.get("position") in ("fixed", "cursor"):
                self.position = value["position"]
            if value.get("sidebar_mode") in ("fixed", "hover"):
                self.sidebar_mode = value["sidebar_mode"]
            if self.valid_card_size(value.get("card_size")):
                self.card_size = value["card_size"]
        except FileNotFoundError:
            pass
        except (OSError, ValueError, AttributeError):
            logging.warning("Panel settings could not be read; using fixed position")

    def snapshot(self):
        return {"position": self.position, "sidebar_mode": self.sidebar_mode, "card_size": self.card_size}

    @staticmethod
    def valid_card_size(value):
        return type(value) is int and 112 <= value <= 400 and (value - 112) % 8 == 0

    def update(self, position=None, sidebar_mode=None, card_size=None):
        if position is None and sidebar_mode is None and card_size is None:
            raise ValueError("请指定面板设置")
        if position is not None and position not in ("fixed", "cursor"):
            raise ValueError("请选择固定位置或鼠标位置")
        if sidebar_mode is not None and sidebar_mode not in ("fixed", "hover"):
            raise ValueError("请选择固定展开或悬停展开")
        if card_size is not None and not self.valid_card_size(card_size):
            raise ValueError("组件大小必须为 112–400，步进 8")
        settings = {"position": position or self.position, "sidebar_mode": sidebar_mode or self.sidebar_mode, "card_size": self.card_size if card_size is None else card_size}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(settings), encoding="utf-8")
        temporary.replace(self.path)
        self.position, self.sidebar_mode = settings["position"], settings["sidebar_mode"]
        self.card_size = settings["card_size"]
        return self.snapshot()

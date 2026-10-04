"""Persistent local preferences for the embedded component panel."""
import json
import logging
from pathlib import Path


class PanelSettings:
    def __init__(self, root):
        self.path = Path(root) / ".runtime" / "panel-settings.json"
        self.position = "fixed"
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if value.get("position") in ("fixed", "cursor"):
                self.position = value["position"]
        except FileNotFoundError:
            pass
        except (OSError, ValueError, AttributeError):
            logging.warning("Panel settings could not be read; using fixed position")

    def snapshot(self):
        return {"position": self.position}

    def update(self, position):
        if position not in ("fixed", "cursor"):
            raise ValueError("请选择固定位置或鼠标位置")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"position": position}), encoding="utf-8")
        temporary.replace(self.path)
        self.position = position
        return self.snapshot()

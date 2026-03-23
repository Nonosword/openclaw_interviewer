from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Capability:
    name: str
    handler: Callable[..., Any]
    side_effect: bool = False
    description: str = ""


class CapabilityRegistry:
    def __init__(self):
        self._caps: dict[str, Capability] = {}

    def register(self, name: str, handler: Callable[..., Any], *, side_effect: bool = False, description: str = "") -> None:
        self._caps[name] = Capability(name=name, handler=handler, side_effect=side_effect, description=description)

    def execute(self, name: str, **kwargs: Any) -> Any:
        if name not in self._caps:
            raise ValueError(f"unsupported_capability:{name}")
        return self._caps[name].handler(**kwargs)

    def list(self) -> list[dict[str, Any]]:
        return [{"name": c.name, "side_effect": c.side_effect, "description": c.description} for c in self._caps.values()]

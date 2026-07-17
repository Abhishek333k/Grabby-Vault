"""
Plugin hooks (reserved).

No third-party plugins ship yet. This module exists so future extractors
can register without changing QueueManager / Downloader call sites.
"""
from __future__ import annotations

from typing import Any, Callable


class PluginManager:
    def __init__(self):
        self._hooks: dict[str, list[Callable[..., Any]]] = {}

    def register(self, event: str, callback: Callable[..., Any]) -> None:
        self._hooks.setdefault(event, []).append(callback)

    def emit(self, event: str, *args, **kwargs) -> list[Any]:
        results = []
        for cb in self._hooks.get(event, []):
            try:
                results.append(cb(*args, **kwargs))
            except Exception:
                continue
        return results

    def clear(self) -> None:
        self._hooks.clear()

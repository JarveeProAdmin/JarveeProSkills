"""Lightweight JSON cache used by jarvee.py to avoid repetitive API calls."""
from __future__ import annotations

import json
import time
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Optional


class JsonCache:
    """Simple timestamped cache persisted to disk.

    The cache structure is {"namespace": {"key": {"ts": float, "value": Any}}}.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()
        self._data: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            if self.path.exists():
                try:
                    self._data = json.loads(self.path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    self._data = {}
            else:
                self._data = {}
            self._loaded = True

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self.path)

    def get(self, namespace: str, key: str, ttl: float) -> Optional[Any]:
        self._ensure_loaded()
        with self._lock:
            ns = self._data.get(namespace, {})
            entry = ns.get(key)
            if not entry:
                return None
            if ttl <= 0:
                return entry.get("value")
            if time.time() - entry.get("ts", 0) > ttl:
                return None
            return entry.get("value")

    def set(self, namespace: str, key: str, value: Any) -> None:
        self._ensure_loaded()
        with self._lock:
            ns = self._data.setdefault(namespace, {})
            ns[key] = {"ts": time.time(), "value": value}
            self._write()

    def clear(self, namespace: Optional[str] = None) -> None:
        self._ensure_loaded()
        with self._lock:
            if namespace is None:
                self._data = {}
            else:
                self._data.pop(namespace, None)
            self._write()

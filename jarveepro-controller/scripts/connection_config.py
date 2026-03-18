"""Shared helpers for managing JarveePro default connection settings."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

CONFIG_FILE = Path(__file__).with_name(".jarvee_connection.json")


def load_connection() -> Optional[dict]:
    """Return the stored connection info, if available."""
    if not CONFIG_FILE.exists():
        return None
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None
    host = data.get("host")
    port = data.get("port")
    if not host or port is None:
        return None
    return {"host": host, "port": int(port)}


def save_connection(host: str, port: int) -> None:
    """Persist the connection info to disk."""
    host = (host or "").strip()
    if not host:
        raise ValueError("Host cannot be empty")
    if not isinstance(port, int):
        raise ValueError("Port must be an integer")
    if port <= 0 or port > 65535:
        raise ValueError("Port must be between 1 and 65535")
    CONFIG_FILE.write_text(json.dumps({"host": host, "port": port}, indent=2), encoding="utf-8")


def resolve_connection(cli_host: Optional[str], cli_port: Optional[int]) -> Tuple[str, int]:
    """Return the effective host/port, preferring CLI overrides then defaults."""
    host = cli_host
    port = cli_port
    if host and isinstance(host, str):
        host = host.strip() or None
    config = load_connection()
    if host is None and config:
        host = config.get("host")
    if port is None and config:
        port = config.get("port")
    if host is None or port is None:
        raise RuntimeError(
            "未配置 JarveePro 默认连接。请先运行 `./skills/jarveepro-controller/scripts/jarvee.py "
            "config --host <IP> --port <端口>` 来设置默认主机和端口，或在命令中显式提供 --host/--port。"
        )
    return host, int(port)

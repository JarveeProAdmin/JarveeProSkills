"""HTTP helper for JarveePro bridge (delegates to curl for reliability)."""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any, Dict


class HttpError(RuntimeError):
    def __init__(self, status_code: int, status_text: str, body: str) -> None:
        super().__init__(f"HTTP {status_code} {status_text}: {body[:200]}")
        self.status_code = status_code
        self.status_text = status_text
        self.body = body


def post_json(host: str, port: int, payload: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
    curl_path = shutil.which("curl")
    if curl_path is None:
        raise RuntimeError("curl not found in PATH; install curl to use the JarveePro helpers")
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    url = f"http://{host}:{port}/"
    cmd = [
        curl_path,
        "-sS",
        "-X",
        "POST",
        url,
        "-H",
        "Content-Type: application/json",
        "--data",
        body,
        "--max-time",
        str(timeout),
        "-w",
        "\n%{http_code}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"curl exited with code {proc.returncode}")
    if "\n" not in proc.stdout:
        raise RuntimeError("Unexpected curl output")
    body_text, status_code_str = proc.stdout.rsplit("\n", 1)
    try:
        status_code = int(status_code_str)
    except ValueError:
        raise RuntimeError(f"Invalid status code from curl: {status_code_str}")
    if status_code >= 400:
        raise HttpError(status_code, "", body_text)
    try:
        return json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response: {body_text[:200]}") from exc

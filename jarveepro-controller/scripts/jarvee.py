#!/usr/bin/env python3
"""Higher-level JarveePro controller (list/run/check/create templates)."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from cache_utils import JsonCache
from template_library import get_template, list_templates
from connection_config import load_connection, resolve_connection, save_connection
from http_bridge import HttpError, post_json
from mainkey_registry import resolve_mainkey


DEFAULT_PAGE_SIZE = 1000
CACHE_FILE = Path(__file__).with_name(".jarvee_cache.json")
CACHE = JsonCache(CACHE_FILE)


def request(host: str, port: int, cmd_type: str, platform: str, data: Optional[Any] = None, timeout: float = 30.0) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"Type": cmd_type, "Platform": platform}
    if data is not None:
        payload["Data"] = data
    try:
        return post_json(host, port, payload, timeout=timeout)
    except HttpError as exc:  # pragma: no cover - passthrough errors
        raise RuntimeError(str(exc)) from exc


def fetch_tasks(host: str, port: int, platform: str, timeout: float, use_cache: bool = True, cache_ttl: float = 30.0, force_refresh: bool = False) -> List[Dict[str, Any]]:
    cache_key = f"{host}:{port}:{platform}"
    if use_cache and not force_refresh:
        cached = CACHE.get("tasks", cache_key, cache_ttl)
        if cached is not None:
            return cached
    payload = {"PageIndex": 0, "PageSize": DEFAULT_PAGE_SIZE}
    resp = request(host, port, "GetTaskList", platform, payload, timeout)
    if not resp.get("Status"):
        raise RuntimeError(resp.get("Message", "GetTaskList failed"))
    tasks = resp.get("TaskList") or []
    if use_cache:
        CACHE.set("tasks", cache_key, tasks)
    return tasks


def get_tasks(args: argparse.Namespace) -> List[Dict[str, Any]]:
    return fetch_tasks(
        args.host,
        args.port,
        args.platform,
        args.timeout,
        use_cache=not args.no_cache,
        cache_ttl=args.cache_ttl,
        force_refresh=args.refresh_cache,
    )


def fetch_accounts(host: str, port: int, platform: str, timeout: float) -> List[Dict[str, Any]]:
    accounts: List[Dict[str, Any]] = []
    page_index = 0
    while True:
        payload = {"PageIndex": page_index, "PageSize": DEFAULT_PAGE_SIZE}
        resp = request(host, port, "GetAccountList", platform, payload, timeout)
        if not resp.get("Status"):
            raise RuntimeError(resp.get("Message", "GetAccountList failed"))
        chunk = resp.get("AccountList") or []
        accounts.extend(chunk)
        if len(chunk) < DEFAULT_PAGE_SIZE:
            break
        page_index += 1
        if page_index >= 1000:
            raise RuntimeError("Account list pagination exceeded 1000 pages")
    return accounts


def extract_account_ids_from_payload(payload: Dict[str, Any]) -> List[str]:
    account_ids = payload.get("AccountIds")
    normalized: List[str] = []
    if isinstance(account_ids, list):
        normalized = [str(item).strip() for item in account_ids if str(item).strip()]
        if normalized:
            return normalized
    account_json = payload.get("AccountJson")
    if isinstance(account_json, list):
        normalized = [str(item).strip() for item in account_json if str(item).strip()]
        if normalized:
            return normalized
    if isinstance(account_json, str) and account_json.strip():
        try:
            parsed = json.loads(account_json)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            normalized = [str(item).strip() for item in parsed if str(item).strip()]
            if normalized:
                return normalized
    return []


def ensure_accounts_on_payload(payload: Dict[str, Any], host: str, port: int, platform: str, timeout: float) -> List[str]:
    existing = extract_account_ids_from_payload(payload)
    if existing:
        payload["AccountIds"] = existing
        payload["AccountJson"] = json.dumps(existing, ensure_ascii=False)
        return existing

    accounts = fetch_accounts(host, port, platform, timeout)
    normal_ids: List[str] = []
    seen = set()
    for account in accounts:
        status_value = str(account.get("Status") or "").lower()
        if status_value != "normal":
            continue
        account_id = account.get("Id")
        if not account_id:
            continue
        account_id_str = str(account_id)
        if account_id_str in seen:
            continue
        seen.add(account_id_str)
        normal_ids.append(account_id_str)
    if not normal_ids:
        raise RuntimeError(f"No Normal accounts found for platform {platform}; please specify AccountIds explicitly")
    payload["AccountIds"] = normal_ids
    payload["AccountJson"] = json.dumps(normal_ids, ensure_ascii=False)
    return normal_ids


def load_task_payload(data_arg: Optional[str], data_file: Optional[str]) -> Dict[str, Any]:
    if data_arg and data_file:
        raise RuntimeError("Use either --data or --data-file, not both")
    if not data_arg and not data_file:
        raise RuntimeError("Provide task payload via --data or --data-file")
    if data_file:
        with open(data_file, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    else:
        try:
            payload = json.loads(data_arg or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse --data JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Task payload must be a JSON object")
    return payload


PATH_KEYS = {
    "PhotoPath",
    "VideoPath",
    "ImagePath",
    "FilePath",
    "CoverPath",
    "ThumbnailPath",
    "MusicPath",
    "AudioPath",
    "UploadPath",
}

WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:\\")


def is_windows_path(value: str) -> bool:
    return bool(WINDOWS_DRIVE_PATTERN.match(value) or value.startswith('\\'))


def convert_path_to_windows(value: str) -> str:
    if not value:
        return value
    if is_windows_path(value):
        return value
    path_obj = Path(value)
    if not path_obj.is_absolute():
        path_obj = (Path.cwd() / path_obj).resolve()
    abs_posix = str(path_obj)
    if os.name == 'nt':
        return abs_posix.replace('/', '\\')
    try:
        win_path = subprocess.check_output(['wslpath', '-w', abs_posix], text=True).strip()
        return win_path
    except Exception:
        return abs_posix


def normalize_parameter_paths(payload: Dict[str, Any]) -> None:
    parameter = payload.get('Parameter')
    if not isinstance(parameter, dict):
        return
    changed = False
    for key, block in parameter.items():
        if key not in PATH_KEYS or not isinstance(block, dict):
            continue
        values = block.get('Parameters')
        if not isinstance(values, list):
            continue
        new_values = []
        updated = False
        for item in values:
            if isinstance(item, str):
                converted = convert_path_to_windows(item)
                new_values.append(converted)
                if converted != item:
                    updated = True
            else:
                new_values.append(item)
        if updated:
            block['Parameters'] = new_values
            changed = True
    if changed or 'ParameterJson' in payload:
        payload['ParameterJson'] = json.dumps(parameter, ensure_ascii=False)


def auto_main_key(payload: Dict[str, Any]) -> None:
    if payload.get("MainKey"):
        return
    platform = payload.get("Platform")
    task_type = payload.get("TaskType")
    candidates = resolve_mainkey(platform, task_type)
    if not candidates:
        return
    parameter = payload.get("Parameter") or {}
    for candidate in candidates:
        block = parameter.get(candidate)
        if isinstance(block, dict):
            values = block.get("Parameters")
            if isinstance(values, list) and values:
                payload["MainKey"] = candidate
                return
    payload["MainKey"] = candidates[0]


def parse_template_kv(arg_values: Optional[List[str]]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not arg_values:
        return result
    for item in arg_values:
        if "=" not in item:
            raise RuntimeError(f"Template arg '{item}' must use key=value format")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise RuntimeError(f"Invalid template arg '{item}'")
        result[key] = value
    return result


def find_task(tasks: List[Dict[str, Any]], task_id: Optional[str], name: Optional[str]) -> Dict[str, Any]:
    if task_id:
        for task in tasks:
            if task.get("Id") == task_id:
                return task
        raise RuntimeError(f"Task with id {task_id} not found")
    if name:
        matches = [t for t in tasks if t.get("Name") == name]
        if not matches:
            raise RuntimeError(f"Task named {name} not found")
        if len(matches) > 1:
            raise RuntimeError(f"Multiple tasks named {name}, specify --task-id")
        return matches[0]
    raise RuntimeError("Provide either --task-id or --name")


def cmd_list(args: argparse.Namespace) -> None:
    tasks = get_tasks(args)
    if args.json:
        print(json.dumps(tasks, indent=2, ensure_ascii=False))
        return
    if not tasks:
        print("No tasks found")
        return
    print(f"Found {len(tasks)} tasks:")
    for task in tasks:
        print(f"- {task.get('Name')} | Id={task.get('Id')} | Type={task.get('TaskType')} | Status={task.get('Status')} | Accounts={len(task.get('AccountIds') or [])}")


def cmd_run(args: argparse.Namespace) -> None:
    tasks = get_tasks(args)
    task = find_task(tasks, args.task_id, args.name)
    resp = request(args.host, args.port, "RunTask", args.platform, task.get("Id"), args.timeout)
    print(json.dumps(resp, indent=2, ensure_ascii=False))


def cmd_check(args: argparse.Namespace) -> None:
    target = args.task_id or args.name
    data = target
    if args.name and not args.task_id:
        # resolve to Id so JarveePro gets exact task contents from cache
        tasks = get_tasks(args)
        task = find_task(tasks, None, args.name)
        data = task
    resp = request(args.host, args.port, "CheckTask", args.platform, data, args.timeout)
    print(json.dumps(resp, indent=2, ensure_ascii=False))


def cmd_add(args: argparse.Namespace) -> None:
    payload = load_task_payload(args.data, args.data_file)
    payload_platform = payload.get("Platform") or args.platform
    if not payload_platform:
        raise RuntimeError("Task payload missing Platform; supply --platform or include Platform in JSON")
    payload["Platform"] = payload_platform
    ensure_accounts_on_payload(payload, args.host, args.port, payload_platform, args.timeout)
    normalize_parameter_paths(payload)
    auto_main_key(payload)
    resp = request(args.host, args.port, "CreateTask", payload_platform, payload, args.timeout)
    print(json.dumps(resp, indent=2, ensure_ascii=False))


def cmd_create_like(args: argparse.Namespace) -> None:
    template = get_template("facebook_like_post")
    payload_args = {
        "name": args.name,
        "description": args.description,
        "accounts": args.accounts,
        "urls": args.url,
        "reaction": args.reaction,
        "random": "true" if args.random else "false",
    }
    payload = template.render({k: v for k, v in payload_args.items() if v is not None})
    normalize_parameter_paths(payload)
    auto_main_key(payload)
    resp = request(args.host, args.port, "CreateTask", args.platform, payload, args.timeout)
    print(json.dumps(resp, indent=2, ensure_ascii=False))
    if args.run_after and resp.get("Status") and resp.get("TaskList"):
        task_id = resp["TaskList"][0].get("Id")
        if task_id:
            print("Running newly created task...", file=sys.stderr)
            run_resp = request(args.host, args.port, "RunTask", args.platform, task_id, args.timeout)
            print(json.dumps(run_resp, indent=2, ensure_ascii=False))


def cmd_templates_list(args: argparse.Namespace) -> None:
    templates = list(list_templates())
    if not templates:
        print("No templates registered")
        return
    print("Registered task templates:")
    for tpl in templates:
        print(f"- {tpl.name} ({tpl.platform} / {tpl.task_type}) - {tpl.description}")


def cmd_templates_show(args: argparse.Namespace) -> None:
    template = get_template(args.template)
    info = {
        "name": template.name,
        "platform": template.platform,
        "task_type": template.task_type,
        "description": template.description,
        "required_args": template.required_args,
        "optional_args": template.optional_args,
    }
    print(json.dumps(info, indent=2, ensure_ascii=False))


def cmd_templates_render(args: argparse.Namespace) -> None:
    template = get_template(args.template)
    payload = template.render(parse_template_kv(args.arg))
    if args.pretty:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False))


def cmd_templates_create(args: argparse.Namespace) -> None:
    template = get_template(args.template)
    payload = template.render(parse_template_kv(args.arg))
    normalize_parameter_paths(payload)
    auto_main_key(payload)
    resp = request(args.host, args.port, "CreateTask", template.platform, payload, args.timeout)
    print(json.dumps(resp, indent=2, ensure_ascii=False))
    if args.run_after and resp.get("Status") and resp.get("TaskList"):
        task_id = resp["TaskList"][0].get("Id")
        if task_id:
            print("Running newly created task...", file=sys.stderr)
            run_resp = request(args.host, args.port, "RunTask", template.platform, task_id, args.timeout)
            print(json.dumps(run_resp, indent=2, ensure_ascii=False))


def cmd_config(args: argparse.Namespace) -> None:
    if args.show:
        config = load_connection()
        if not config:
            print("尚未设置默认 JarveePro 连接。")
        else:
            print(json.dumps({"host": config["host"], "port": config["port"]}, indent=2, ensure_ascii=False))
        if args.config_host is None and args.config_port is None:
            return
    if args.config_host is None or args.config_port is None:
        raise RuntimeError("设置默认连接时需同时提供 --set-host 与 --set-port")
    save_connection(args.config_host, args.config_port)
    print(f"已保存默认 JarveePro 连接：{args.config_host}:{args.config_port}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JarveePro higher-level helper")
    parser.add_argument("--host", help="JarveePro host (默认使用已保存的配置)")
    parser.add_argument("--port", type=int, help="JarveePro port (默认使用已保存的配置)")
    parser.add_argument("--platform", default="Facebook", help="PlatformType (default Facebook)")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds")
    parser.add_argument("--cache-ttl", type=float, default=30.0, help="Task list cache TTL seconds (default 30)")
    parser.add_argument("--no-cache", action="store_true", help="Disable local cache for task list lookups")
    parser.add_argument("--refresh-cache", action="store_true", help="Force refresh task cache for this invocation")

    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--json", action="store_true", help="Dump raw JSON")
    p_list.set_defaults(func=cmd_list)

    p_run = sub.add_parser("run", help="Run a task by id or name")
    p_run.add_argument("--task-id", help="Task Id")
    p_run.add_argument("--name", help="Task name")
    p_run.set_defaults(func=cmd_run)

    p_check = sub.add_parser("check", help="Check a task")
    p_check.add_argument("--task-id", help="Task Id")
    p_check.add_argument("--name", help="Task name")
    p_check.set_defaults(func=cmd_check)

    p_add = sub.add_parser("add", help="Create a task from a raw JSON payload")
    p_add.add_argument("--data", help="Inline JSON TaskBase payload")
    p_add.add_argument("--data-file", help="Path to a JSON file containing the TaskBase payload")
    p_add.set_defaults(func=cmd_add)

    p_like = sub.add_parser("create-like", help="Create a Facebook LikePost task")
    p_like.add_argument("--name", required=True, help="Task name")
    p_like.add_argument("--description", default="", help="Task description")
    p_like.add_argument("--accounts", required=True, help="Comma separated account ids")
    p_like.add_argument("--url", required=True, help="Post URL(s), comma separated")
    p_like.add_argument("--reaction", default="LIKE", help="Reaction type (LIKE/LOVE/etc)")
    p_like.add_argument("--random", action="store_true", help="Use random reaction")
    p_like.add_argument("--run-after", action="store_true", help="Run immediately after creation")
    p_like.set_defaults(func=cmd_create_like)

    p_templates = sub.add_parser("templates", help="Inspect and build task templates")
    templates_sub = p_templates.add_subparsers(dest="templates_command", required=True)

    t_list = templates_sub.add_parser("list", help="List registered templates")
    t_list.set_defaults(func=cmd_templates_list)

    t_show = templates_sub.add_parser("show", help="Show template metadata")
    t_show.add_argument("--template", required=True, help="Template name")
    t_show.set_defaults(func=cmd_templates_show)

    t_render = templates_sub.add_parser("render", help="Render a template without sending it")
    t_render.add_argument("--template", required=True, help="Template name")
    t_render.add_argument("--arg", action="append", help="Template argument key=value (repeatable)")
    t_render.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    t_render.set_defaults(func=cmd_templates_render)

    t_create = templates_sub.add_parser("create", help="Create a task from a template")
    t_create.add_argument("--template", required=True, help="Template name")
    t_create.add_argument("--arg", action="append", help="Template argument key=value (repeatable)")
    t_create.add_argument("--run-after", action="store_true", help="Run immediately after creation")
    t_create.set_defaults(func=cmd_templates_create)

    p_config = sub.add_parser("config", help="设置或查看默认 JarveePro 连接")
    p_config.add_argument("--set-host", dest="config_host", help="要保存的默认主机 IP")
    p_config.add_argument("--set-port", dest="config_port", type=int, help="要保存的默认端口")
    p_config.add_argument("--show", action="store_true", help="显示当前默认设置")
    p_config.set_defaults(func=cmd_config)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command != "config":
            args.host, args.port = resolve_connection(args.host, args.port)
        args.func(args)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

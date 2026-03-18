#!/usr/bin/env python3
"""CLI helper for sending JarveePro API commands."""
import argparse
import json
import sys

from connection_config import resolve_connection
from http_bridge import HttpError, post_json


def parse_data_arg(value: str):
    """Try to decode JSON; fall back to raw string."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def load_data(args):
    if args.data is not None and args.data_file is not None:
        raise SystemExit("Use either --data or --data-file, not both")
    if args.data is not None:
        return parse_data_arg(args.data)
    if args.data_file is not None:
        with open(args.data_file, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return None


def main():
    parser = argparse.ArgumentParser(description="Send commands to the JarveePro API bridge")
    parser.add_argument("--host", help="JarveePro API host (默认使用已保存的配置)")
    parser.add_argument("--port", type=int, help="JarveePro API port (默认使用已保存的配置)")
    parser.add_argument("--type", required=True, help="CommandType enum value, e.g. GetCategorys")
    parser.add_argument("--platform", required=True, help="PlatformType enum value, e.g. Facebook")
    parser.add_argument("--data", help="Inline JSON (or plain string) payload for the Data field")
    parser.add_argument("--data-file", help="Path to a JSON file containing the Data object")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON response")

    args = parser.parse_args()

    try:
        host, port = resolve_connection(args.host, args.port)
    except RuntimeError as exc:
        parser.error(str(exc))

    payload = {
        "Type": args.type,
        "Platform": args.platform
    }
    data = load_data(args)
    if data is not None:
        payload["Data"] = data

    try:
        response_obj = post_json(host, port, payload, timeout=args.timeout)
    except HttpError as exc:
        sys.stderr.write(str(exc) + "\n")
        sys.exit(exc.status_code)
    except OSError as exc:
        sys.stderr.write(f"Network error: {exc}\n")
        sys.exit(1)

    if args.pretty:
        print(json.dumps(response_obj, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(response_obj, ensure_ascii=False))


if __name__ == "__main__":
    main()

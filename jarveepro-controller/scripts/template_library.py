"""Task template registry for JarveePro helper scripts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List

from parameter_library import build_parameter_block


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _to_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class TaskTemplate:
    name: str
    description: str
    platform: str
    task_type: str
    required_args: Dict[str, str]
    optional_args: Dict[str, str] = field(default_factory=dict)
    builder: Callable[[Dict[str, Any]], Dict[str, Any]] = field(default=lambda _: {})

    def render(self, args: Dict[str, str]) -> Dict[str, Any]:
        missing = [key for key in self.required_args if key not in args]
        if missing:
            raise ValueError(f"Missing required template args: {', '.join(missing)}")
        payload = self.builder(args)
        payload.setdefault("Platform", self.platform)
        payload.setdefault("TaskType", self.task_type)
        return payload


# Builder implementations ----------------------------------------------------

def build_facebook_like_post(args: Dict[str, str]) -> Dict[str, Any]:
    accounts = _split_csv(args["accounts"])
    urls = _split_csv(args["urls"])
    description = args.get("description", "")
    reaction = args.get("reaction", "LIKE").upper()
    random_reaction = _to_bool(args.get("random", "false"))

    parameter = {
        "Url": build_parameter_block("Url", urls, {
            "SingleUseData": {"Min": 1, "Max": 1},
            "RandomUse": False,
        })
    }

    return {
        "Name": args["name"],
        "Description": description,
        "TaskType": "LikePost",
        "AccountIds": accounts,
        "AccountJson": json_dumps(accounts),
        "MainUseParam": False,
        "AccountUseNum": 1,
        "UnitIndex": 0,
        "Reallocation": True,
        "MainKey": "Url",
        "Parameter": parameter,
        "ParameterJson": json_dumps(parameter),
        "TaskSettingJson": json_dumps({"IsRandom": random_reaction, "Type": reaction}),
        "BrowserType": "DriverBrowser",
        "RunType": "None",
        "IsRun": False,
    }


def build_facebook_watch_video(args: Dict[str, str]) -> Dict[str, Any]:
    accounts = _split_csv(args["accounts"])
    keywords = _split_csv(args["keywords"])
    description = args.get("description", "")
    parameter = {
        "Search": build_parameter_block("Search", keywords, {
            "SingleUseData": {"Min": 1, "Max": 1},
            "RandomUse": True,
        })
    }

    setting = {
        "IsRandom": True,
        "WatchTime": {"Min": int(args.get("watch_min", "30")), "Max": int(args.get("watch_max", "90"))},
    }

    return {
        "Name": args["name"],
        "Description": description,
        "TaskType": "WatchVideo",
        "AccountIds": accounts,
        "AccountJson": json_dumps(accounts),
        "MainUseParam": False,
        "AccountUseNum": 1,
        "UnitIndex": 0,
        "Reallocation": True,
        "MainKey": "Search",
        "Parameter": parameter,
        "ParameterJson": json_dumps(parameter),
        "TaskSettingJson": json_dumps(setting),
        "BrowserType": "DriverBrowser",
        "RunType": "None",
        "IsRun": False,
    }


# Registry -------------------------------------------------------------------

TEMPLATES: Dict[str, TaskTemplate] = {
    "facebook_like_post": TaskTemplate(
        name="facebook_like_post",
        description="Facebook → Like specific post URLs with optional random reactions.",
        platform="Facebook",
        task_type="LikePost",
        required_args={
            "name": "Human friendly task name",
            "accounts": "Comma separated JarveePro AccountIds",
            "urls": "Comma separated Facebook post URLs",
        },
        optional_args={
            "description": "Optional task description",
            "reaction": "LIKE/LOVE/CARE/HAHA/WOW/SAD/ANGRY",
            "random": "true/false toggle for random reactions",
        },
        builder=build_facebook_like_post,
    ),
    "facebook_watch_video": TaskTemplate(
        name="facebook_watch_video",
        description="Facebook → Watch videos by search keyword with randomized watch times.",
        platform="Facebook",
        task_type="WatchVideo",
        required_args={
            "name": "Task name",
            "accounts": "Comma separated account ids",
            "keywords": "Comma separated search keywords",
        },
        optional_args={
            "description": "Task description",
            "watch_min": "Minimum watch seconds (default 30)",
            "watch_max": "Maximum watch seconds (default 90)",
        },
        builder=build_facebook_watch_video,
    ),
}


def list_templates() -> Iterable[TaskTemplate]:
    return TEMPLATES.values()


def get_template(name: str) -> TaskTemplate:
    if name not in TEMPLATES:
        raise KeyError(f"Unknown template '{name}'")
    return TEMPLATES[name]


# Helper to avoid importing json in jarvee.py twice --------------------------

def json_dumps(data: Any) -> str:
    import json

    return json.dumps(data, ensure_ascii=False)


__all__ = ["TaskTemplate", "list_templates", "get_template"]

---
name: jarveepro-controller
description: Control JarveePro via its local HTTP bridge (default 6473). Use when you need to list or manage categories, accounts, or automation tasks inside JarveePro by sending JSON commands defined in the JarveeProApi C# project.
---

# JarveePro Controller

## Overview
This skill wraps the `JarveeProApi` (.NET Framework 4.8) project so you can steer a running JarveePro instance entirely through HTTP POST calls. Everything funnels through the `SocketSendCommand` envelope defined in `JarveeProApi/model/SocketSendCommand.cs`, so once you know the command list and payload shapes you can automate anything that JarveePro exposes (categories, accounts, tasks, run/stop controls, etc.).

For detailed field descriptions and sample payloads, read [`references/api-guide.md`](references/api-guide.md) before constructing requests.

## Quick Start
1. **Set the default bridge host/port (one-time, but editable):** Run `./skills/jarveepro-controller/scripts/jarvee.py config --set-host <IP> --set-port <PORT>` to store the JarveePro listener details in `scripts/.jarvee_connection.json`. All helper scripts refuse to run without this default unless you explicitly pass `--host/--port`, and you can re-run the config command anytime to update the saved values. Use `--show` to inspect the current defaults.
2. **Verify connectivity:** JarveePro must be running with its API listener open (default `127.0.0.1:6473`). Test with `curl`, `jarveepro_request.py`, or the higher-level CLI:  
   `./skills/jarveepro-controller/scripts/jarvee.py --platform Facebook list`
3. **Shape your payload:** Use the C# models under `JarveeProApi/` to understand the JSON you need to send (e.g., `Account/Account.cs`, `TaskModel/TaskBase.cs`).
4. **Send the command:** Either run the helper script or issue your own `curl -X POST http://<host>:<port>/ -H 'Content-Type: application/json' -d '<json>'`.
5. **Check `Status` and `Message`:** Every response is a `SocketData` object; never trust `CategoryInfoList`/`AccountList`/`TaskList` unless `Status` is true.

## Core Operations

### 1. Category management
- `GetCategorys`: provide only `Platform`. Response populates `CategoryInfoList`.
- `AddCategory`: set `Data` to the new category name (string). JarveePro assigns the ID.
- `UpdateCategory` / `DeleteCategory`: send a full `Category` object (`CategoryType`, `CategoryName`, `Id`).
- Keep the returned IDs—they are required for linking accounts.

### 2. Account lifecycle
- `AccountAdd` / `AccountAddList`: payload is one or many `Account` objects (see `Account/Account.cs`). Include platform, category, credentials, optional proxy/email info, etc.
- `GetAccountList`: `Data` must be a `PageListLimit` (`PageIndex`, `PageSize`, optional `SearchData`). Inspect `AccountList` plus the echoed `Limit` for pagination.
- `UpdateAccount`: resend the full account object with edits applied.
- `AccountVery`: triggers JarveePro’s verification workflow for a specific account.
- `AccountDelete`: remove an account entirely.

### 3. Task orchestration
- `CreateTask`: payload is `TaskBase` (see `TaskModel/TaskBase.cs`). Set `TaskType` using the per-platform enums in `platform/*.cs` (e.g., `NewPost`, `WatchVideo`).
- Populate `AccountIds`, `Parameter` (dictionary of `ParameterKey` → `TaskParameter`), `MainKey`, and any platform-specific settings serialized into `TaskSettingJson`.
- `RunTask` / `StopTask`: send the task ID as `Data`, alongside the platform.
- `UpdateTask`, `DeleteTask`, `CheckTask`, `GetTaskList`: reuse the same structures (`TaskBase` or `PageListLimit`).
- Reference `TaskParameterKeyAttribute` annotations to know which `ParameterKey` entries are mandatory for a task.

## Helper Script
Use `scripts/jarveepro_request.py` whenever you need a reproducible CLI invocation (host/port fall back to the saved defaults from the config step):

```bash
./skills/jarveepro-controller/scripts/jarveepro_request.py \
  --type GetAccountList --platform Facebook \
  --data '{"PageIndex":0,"PageSize":20}' --pretty
```

- Override the destination bridge for one-off calls with `--host` / `--port`; otherwise the stored defaults are used.
- Transport layer now delegates to the system `curl` binary to match JarveePro’s picky HTTP parser (plain Python clients injected `Accept-Encoding` headers that the bridge misinterpreted). Make sure `curl` is in `PATH`.
- `--data` accepts inline JSON or plain strings (falls back to literal string if JSON decoding fails).
- `--data-file payload.json` loads larger objects from disk.
- `--pretty` pretty-prints valid JSON responses for easier inspection.

## References
- [`references/api-guide.md`](references/api-guide.md) — end-to-end explanation of the command envelope, command list, payload models, task parameters, and troubleshooting tips.
- Source of truth for structures lives under `JarveeProApi/` (e.g., `Account/Account.cs`, `TaskModel/TaskBase.cs`, `platform/*.cs`, `setting/*`). Skim them whenever you need an authoritative field list.


## Fast CLI (`jarvee.py`)
For repetitive actions use the higher-level helper (host/port pull from the saved defaults unless you override them):

```bash
./skills/jarveepro-controller/scripts/jarvee.py --platform Facebook list
```

Key subcommands:
- `list` — fetch tasks once and print a summary (`--json` dumps raw data). Results are cached for 30 s by default; add `--refresh-cache` or `--no-cache` if you need a live read.
- `run --task-id <id>` or `run --name <taskName>` — resolves IDs for you and triggers `RunTask`, reusing the warm cache so you avoid extra network calls.
- `check --task-id <id>` — runs `CheckTask`. When you pass only `--name`, the script resolves it through the cached task list, falling back to live queries when invalidated.
- `add --data <json>` (or `--data-file task.json`) — send a raw `CreateTask` payload. If `AccountIds`/`AccountJson` are missing or empty, the CLI auto-fetches every `Normal` status account for the specified platform and injects them so the task can run without manual selection.
- `templates list/show/render/create` — inspect the built-in task templates (currently Facebook LikePost + WatchVideo) or render/send them by supplying `--arg key=value` pairs. `templates create --template facebook_like_post --arg name=Foo --arg accounts=a1,a2 --arg urls=https://... --run-after` pushes a new task and optionally starts it immediately.
- `create-like --name <taskName> --accounts acc1,acc2 --url <postUrl> --random` — legacy shortcut backed by the `facebook_like_post` template.
- 所有 `add`/模板创建类命令在发送前会自动把 `PhotoPath`/`VideoPath`/`ImagePath` 等参数转换为当前系统的绝对路径：在 WSL 中会经由 `wslpath -w` 生成 Windows 风格路径，无需手动填 `C:\...`。
- 同时，CLI 会根据 `Platform + TaskType` 自动推断缺失的 `MainKey`（映射来自 `JarveeProApi/PlatForm/*TaskType.cs` 的 `TaskParameterKeyAttribute`）。例如 Instagram `Post` 会优先选用 `PhotoPath`（若无图片再回退到 `VideoPath`）。

## MainKey reference
- 不同任務的 `MainKey` 由 C# 中 `TaskParameterKeyAttribute` 決定，定義在 `JarveeProApi/PlatForm/<Platform>TaskType.cs`。在構建 payload 前務必查看對應 enum，確保 `MainKey` 與 JarveePro 期望一致。
- 例如 Instagram 的 `Post` 定義為 `mainKey: [PhotoPath, VideoPath]`（見 `JarveeProApi/PlatForm/InstagramTaskType.cs`），因此若僅發圖片，`MainKey` 應設為 `PhotoPath`，JarveePro 會依每張圖生成一個 TaskUnit；若包含影片則需切換/加入 `VideoPath`。
- 若 `MainKey` 填錯，會出現例如 “給定關鍵字不在字典中” 或僅執行第一個單元的問題。依需要把此知識寫入模板或任務生成腳本，避免日後重新踩坑。

`jarvee.py` now persists task caches to `scripts/.jarvee_cache.json` so repeated list/run operations stay snappy on slow bridges. Templates pull from the shared parameter library (`scripts/parameter_library.py`), guaranteeing consistent `TaskParameter` envelopes across automations. Manage the saved bridge target anytime with `jarvee.py config --show` or `jarvee.py config --set-host <IP> --set-port <PORT>`.

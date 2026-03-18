# JarveePro API Guide

This project exposes JarveePro's local automation API through a simple TCP/HTTP bridge (default `127.0.0.1:6473`). Sending the right JSON payload lets you manage platform categories, accounts, and tasks without touching the JarveePro UI.

## Connectivity & Health Checks

1. **Ensure JarveePro is running** with the API listener enabled on the workstation you want to control.
2. **Default endpoint:** `http://<host>:6473/` (no path segment). The bridge accepts plain HTTP `POST` requests with a JSON body.
3. **Connectivity test:**
   ```bash
   curl -s -X POST http://127.0.0.1:6473 \
     -H "Content-Type: application/json" \
     -d '{"Type":"GetCategorys","Platform":"Facebook"}'
   ```
   A healthy server returns a JSON `SocketData` object (see below). Connection errors usually mean JarveePro or its API service is not running, or the firewall blocks the port.

## Request Envelope

Every command follows the structure defined in [`model/SocketSendCommand.cs`](../../JarveeProApi/model/SocketSendCommand.cs):

```json
{
  "Type": "<CommandType>",
  "Platform": "<PlatformType>",
  "Data": <command specific payload>
}
```

- `Type` must be one of the `CommandType` enum values: `GetCategorys`, `AddCategory`, `UpdateCategory`, `DeleteCategory`, `AccountAdd`, `AccountAddList`, `UpdateAccount`, `AccountVery`, `AccountDelete`, `GetAccountList`, `CreateTask`, `UpdateTask`, `RunTask`, `StopTask`, `DeleteTask`, `CheckTask`, `GetTaskList`.
- `Platform` maps to [`PlatformType`](../../JarveeProApi/platform/PlatformType.cs): `Facebook`, `Instagram`, `Twitter`, `YouTube`, `TikTok`.
- `Data` is optional and varies per command. If omitted, send `null` or drop the property entirely.

> JSON serialization is case-insensitive on the .NET side. All examples here use the human-readable enum names.

## Response Shape

Responses are serialized `SocketData` objects (`model/SocketData.cs`):

```json
{
  "Status": true,
  "Message": "",
  "CategoryInfoList": [],
  "AccountList": [],
  "TaskList": [],
  "Limit": { "PageIndex": 0, ... }
}
```

Only the relevant collection is populated per command. Always check `Status` and `Message` before trusting the payload.

## Payload Types

### Categories (`Account/Category.cs`)
- `CategoryType`: platform (enum)
- `CategoryName`: display name
- `Id`: JarveePro's internal identifier

Used by `AddCategory`, `UpdateCategory`, `DeleteCategory`, `GetCategorys` (`Data` omitted).

### Accounts (`Account/Account.cs`)
Key fields:
- `Platform`, `Category`, `Username`, `Password`
- Optional: `MailInfo` (`Account/Email.cs`), `Proxy`, `Useragent`, `_2faKey`, etc.
- `Status`, `Description`, `Tag` help with filtering.

`AddAccount` / `AccountAddList` require the structure above. `GetAccountList` expects a [`PageListLimit`](#pagination) object in `Data`.

### Pagination (`model/PageListLimit.cs`)
- `PageIndex` (zero-based)
- `PageSize`
- `SearchData` for fuzzy filtering (string or object)

### Tasks (`TaskModel/TaskBase.cs`)
Essential fields:
- `Platform`
- `Name`, `Description`
- `TaskType`: string matching the per-platform enums in `platform/*.cs` (e.g. `FacebookTaskType.NewPost` → `"NewPost"`).
- `AccountIds`: list of account IDs that will run the task
- `Parameter`: dictionary of `ParameterKey` → `TaskParameter` (see below)
- `MainKey`: primary parameter key that each account must receive
- `BrowserType`, `RunType`, `IsRun`, `Reallocation`, `TaskSettingJson` (serialized advanced settings)

#### Task Parameters (`TaskModel/TaskParameter.cs`)
Each entry defines how JarveePro should distribute resources:
- `Parameters`: array of strings (text, URLs, local file paths, etc.)
- `SingleUseData`, `UnitUseNum`: `MaMi` min/max limits per task unit
- `AccountUseNum`: max consumptions per account
- `UseNum`: probability (0–100)
- `UseNoData`: allow task to run even if the list is empty
- `RandomUse`: shuffle vs. sequential allocation
- `AiSetting`: optional on-the-fly generation config

`ParameterKey` options live in `TaskBase.cs` (e.g. `Text`, `PhotoPath`, `Url`, `VideoPath`). Per-task requirements are annotated via [`TaskParameterKeyAttribute`](../../JarveeProApi/attributes/TaskParameterKeyAttribute.cs).

#### Task Types
- `platform/FacebookTaskType.cs`, `InstagramTaskType.cs`, `TwitterTaskType.cs`, `YoutubeTaskType.cs`, `TiktokTaskType.cs` enumerate all built-in automations and describe which parameter keys + settings they require.
- Many task types reference JSON settings classes under `setting/<Platform>Setting/`. Serialize these (with `JsonConvert.SerializeObject` or compatible tooling) into `TaskSettingJson`.

## Common Workflows

### 1. List and manage categories
1. `GetCategorys` with `Platform` only → returns `CategoryInfoList`.
2. `AddCategory`: set `Data` to the new category name (string) to create one.
3. `UpdateCategory` / `DeleteCategory`: provide a full `Category` object (platform, name, id).

### 2. Manage accounts
1. `AddAccount` or `AccountAddList`: supply one or many `Account` objects.
2. `GetAccountList`: send a `PageListLimit` with optional `SearchData` filter; inspect `AccountList`.
3. `UpdateAccount` / `AccountDelete`: send the modified `Account` object.
4. `AccountVery`: trigger JarveePro's verification workflow for a specific account.

### 3. Task lifecycle
1. Prepare `TaskBase` object (platform, task type, accounts, parameters, settings).
2. `CreateTask` adds it to JarveePro.
3. `RunTask` / `StopTask` control execution using the task ID.
4. `UpdateTask`, `DeleteTask`, `CheckTask`, `GetTaskList` follow the same envelope pattern.

## Helper Script (`scripts/jarveepro_request.py`)
Use the provided Python helper to send well-formed commands without rewriting curl invocations:

```bash
./jarveepro-controller/scripts/jarveepro_request.py \
  --host 192.168.0.123 --port 6473 \
  --type GetCategorys --platform Facebook
```

Add `--data '{"PageIndex":0,"PageSize":20}'` or `--data-file payload.json` for commands that need a body. The script pretty-prints the response or surfaces connection errors.

## `jarvee.py` cache + template library
`jarvee.py` is now opinionated enough that you rarely need to craft JSON manually:

- **Task cache:** every `list/run/check` call stores `GetTaskList` results in `scripts/.jarvee_cache.json` for 30 seconds. Pass `--refresh-cache` to invalidate, or `--no-cache` to bypass entirely when debugging real-time status.
- **Parameter library:** shared blueprints for `TaskParameter` blocks live in `scripts/parameter_library.py`. The helper guarantees consistent `SingleUseData`, `UseNum`, and other throttling knobs when you reuse keys such as `Url`, `CommentText`, etc.
- **Template registry:** `scripts/template_library.py` defines reusable task skeletons. Use `templates list/show` to browse, `templates render --template <name> --arg key=value` to print payloads, and `templates create ... --run-after` to push + launch them in one go. The legacy `create-like` subcommand is now just a focused wrapper around the `facebook_like_post` template.

These additions are designed to make JarveePro task authoring deterministic and auditable: all knobs live in version-controlled Python instead of ad-hoc shell snippets.

## Troubleshooting Checklist
- **`curl: (7)` / connection refused:** JarveePro API service not running or firewall blocked.
- **`Status:false` with `Message":"Port Api ERROR"`:** `ApiServer.IsPortInUse` failed—restart JarveePro.
- **Enum mismatch errors:** ensure `Type` and `Platform` strings exactly match the C# enum names.
- **Task validation failures:** confirm `TaskType` aligns with the platform-specific enum and that required `ParameterKey` entries are populated.

For anything not covered here, inspect the source files referenced above—they are lightweight and map 1:1 to the JSON payloads used over the wire.


## Task Types by Platform

JarveePro exposes dozens of per-platform automations. The tables below summarize every task enum from `JarveeProApi/platform/*.cs` along with the inputs each task expects (URL/Text/Media/Search) and any settings objects that must be provided. Use these when shaping `CreateTask` payloads so you no longer need to open the source files.

### Facebook Task Types
| Task Type | Required Inputs | Setting |
| --- | --- | --- |
| AcceptFriendRequest | — | FacebookAcceptFriendRequestSetting |
| AddBioInformation | Text (Bio Information) | — |
| AddFriends | User URL | — |
| ChangeLanguage | — | FacebookLanguageSetting |
| ChangeName | Text (Name) | — |
| ChangeProfileName | Text (Profile Name) | — |
| ChangeCoverPhoto | Photo Path | — |
| ChangeProfilePicture | Photo Path | — |
| FollowPage | Page URL | — |
| JoinGroup | Group URL | — |
| LikePage | Page URL | — |
| LikePost | Post URL | FacebookLikeSetting (set IsRandom/Type) |
| LikeCommentByLink | Comment URL | — |
| Comment | Post URL + Comment Text + Photo Path (optional) | — |
| ReplayComment | Comment URL + Comment Text + Photo Path | — |
| NewPost | Post Text + Photo Path + Video Path | FacebookPostSetting |
| PostToGroup | Group URL + Post Text + Photo Path + Video Path | FacebookPostGroupSetting |
| PostToPage | Page URL + Post Text + Photo Path + Video Path | — |
| ReportPages | Page URL | FacebookWatchVideoSetting |
| ReportPosts | Post URL | FacebookWatchVideoSetting |
| ReportUser | User URL | FacebookWatchVideoSetting |
| SearchCommentByPost | Post URL | FacebookSearchCommentSetting |
| SendMessage | User URL + Message Text | — |
| SharePost | Post URL + Share Text | — |
| WatchVideo | Search Text + Share Text | FacebookWatchVideoSetting |
| WatchVideoByLink | Post URL + Share Text | FacebookWatchVideoSetting |

### Instagram Task Types
| Task Type | Required Inputs | Setting |
| --- | --- | --- |
| ChangeName | Text (Name) | — |
| ChangeUsername | Text (Username) | — |
| ChangeProfilePicture | Photo Path | — |
| Follow | User URL | — |
| FollowFollowsers | User URL | InstagramFollowFollowersSetting |
| FollowFollowings | User URL | InstagramFollowFollowersSetting |
| LikePost | Post URL | — |
| LikeComment | Comment URL | — |
| Comment | Post URL + Comment Text | — |
| ReplyComment | Comment URL + Comment Text | — |
| Post | Post Text + Photo Path + Video Path | InstagramPostSetting |
| SendMessage | User URL + Message Text + Photo/Video Paths | — |
| Share | Post URL + Share User Text | — |
| UnFollow | User URL | — |
| ViewStoriesReels | Post URL | InstagramViewStoriesReelsSetting |

### TikTok Task Types
| Task Type | Required Inputs | Setting |
| --- | --- | --- |
| Comment | Post URL + Comment Text | — |
| Favorite | Post URL | — |
| Follow | User URL | — |
| Like | Post URL | — |
| Post | Title Text + Photo Path + Video Path + Tag Text + User List | — |
| Share | Post URL | — |
| SearchFollowerByUser | User URL | — |
| SearchFollowingByUser | User URL | — |
| SearchLive | Search Text | TikTokSearchSetting |
| SearchLiveUser | Search Text | TikTokSearchSetting |
| SearchPeople | Search Text | TikTokSearchSetting |
| SerarchVideo | Search Text | TikTokSearchSetting |
| SerarchVideoByUser | User URL | TikTokSearchSetting |
| SerarchVideoUser | Search Text | TikTokSearchSetting |
| SendMessage | User URL + Message Text | — |
| WatchVideo | Post URL | TikTokWatchVideoSetting |

### Twitter Task Types
| Task Type | Required Inputs | Setting |
| --- | --- | --- |
| AddWebsite | Text (URL/Name) | — |
| BlockUser | User URL | — |
| ChangeLanguage | — | TwitterLanguageSetting |
| ChangeProfileName | Text (Profile Name) | — |
| ChangeUsername | Text (Username) | — |
| ChangeBirthDate | Text (Birthdate) | TwitterChangeBirthdateSetting |
| FollowHisFollowers | User URL | TwitterFollowHisSetting |
| FollowHisFollowings | User URL | TwitterFollowHisSetting |
| FollowUser | User URL | — |
| LikeTweet | Post URL | — |
| ReplyTweet | Post URL + Comment Text + Photo/Video Path | — |
| ReportTweet | — | TwitterReportSetting |
| Retweet | Post URL + Comment Text + Photo Path | — |
| SendMessage | Post URL + Message Text + Photo/Video Path | — |
| SetupProfile | Bio Text + Location Text + Avatar Path + Banner Path | — |
| Tweet | Tweet Text + Photo Path + Video Path | TwitterTweetSetting |

### YouTube Task Types
| Task Type | Required Inputs | Setting |
| --- | --- | --- |
| ChangeLanguage | — | YoutubeChangeLanguageSetting |
| ChangeProfileName | Text (Profile Name) | — |
| Comment | Post URL + Comment Text | — |
| DislikeVideos | Post URL | — |
| LikeComment | Comment URL | — |
| LikeVideos | Post URL | — |
| ReplyComment | Comment URL + Comment Text | — |
| ReportVideo | Post URL | YoutubeReportSetting |
| Subsribe | Channel URL | — |
| UploadVideo | Title Text + Thumbnail Photo + Video Path + End Screen Photo + Tag Text + Playlist Text + Description + Location | YoutubeUploadVideoSetting |
| WatchVideo | Post URL | YoutubeWatchVideoSetting |

**Notes:**
- “Photo Path”/“Video Path” expect absolute local filesystem paths accessible to JarveePro.
- When both `elementName` and `searchElement` appear in earlier tables, either can be supplied; the values above describe what must ultimately reach JarveePro.
- For Like-type tasks, the `setting` JSON lets you choose specific reactions or leave `IsRandom=true` for random behavior.

JarveePro OpenClaw Skill
This skill acts as a wrapper for the JarveeProApi (.NET Framework 4.8) project, enabling full control of a running JarveePro instance via HTTP POST calls. It utilizes the SocketSendCommand envelope to automate categories, accounts, and tasks.

Quick Start
Configure Connection: Set your default bridge host and port using the config command:

./skills/jarveepro-controller/scripts/jarvee.py config --set-host <IP> --set-port <PORT>.

Verify Connectivity: Ensure JarveePro is running with its API listener open (default 127.0.0.1:6473) and test the connection.

Test Command: Run a high-level CLI command to list tasks:

./skills/jarveepro-controller/scripts/jarvee.py --platform Facebook list.

Core Operations
1. Category Management
List: Use GetCategorys with a specified Platform to populate the CategoryInfoList.

Add: Use AddCategory and provide a string for the category name; JarveePro assigns the ID.

Modify/Delete: Use UpdateCategory or DeleteCategory with a full Category object containing the ID.

2. Account Lifecycle
Add Accounts: Use AccountAdd or AccountAddList with Account objects including credentials and optional proxy info.

Verification: Trigger JarveePro’s internal verification workflow using the AccountVery command.

Fetch: Retrieve accounts using GetAccountList with PageListLimit for pagination.

3. Task Orchestration
Create: Use CreateTask with a TaskBase payload and set the TaskType based on platform-specific enums.

Control: Start or stop automation by sending the task ID to RunTask or StopTask.

Parameters: Define tasks using a dictionary of ParameterKey entries; mandatory keys are often annotated in the source code.

Path Handling: The CLI automatically converts paths (e.g., from WSL to Windows format) for PhotoPath, VideoPath, and ImagePath.

Helper Scripts
jarvee.py (High-Level CLI)
Smart Lists: Fetches and prints task summaries with a default 30-second cache to maintain performance.

Task Resolution: Resolves task names to IDs automatically when running or checking tasks.

Templates: Includes a template engine (e.g., facebook_like_post) to create and run tasks with simple arguments.

Auto-Injection: If AccountIds are missing during task creation, it auto-fetches all "Normal" status accounts for that platform.

jarveepro_request.py (Low-Level Tool)
Raw Requests: Sends reproducible HTTP POST requests to the bridge.

Curl Integration: Delegates to the system curl binary to avoid header misinterpretation by the JarveePro bridge.

Data Input: Supports inline JSON via --data or loading larger objects via --data-file.

Important Considerations
MainKey Accuracy: The MainKey (e.g., PhotoPath for Instagram posts) must match JarveePro's expectations defined in the TaskParameterKeyAttribute to avoid errors.

Response Validation: Always check the Status and Message fields in the SocketData response before trusting returned lists.

Persistence: Connection settings are stored in .jarvee_connection.json and task caches in .jarvee_cache.json.

# Smart Target Config Design

## Goal

Reduce manual setup for Web task configuration by detecting connected Android devices and the current foreground app, while keeping manual overrides for unusual emulator or package states.

## Background

The Web console currently asks the operator to type:

- `device_uri`
- `package_name`

This is reliable but slow and error-prone. In the current MuMu workflow, the operator usually already has the game open in the emulator, so the project can infer the two most important fields from ADB:

- `adb devices` for the device serial.
- `dumpsys activity activities` or `dumpsys window` for the foreground package/activity.

The implementation should stay conservative. Detection must be read-only and should not start apps, click UI, grant permissions, or change the emulator state.

## Scope

This phase includes:

- Backend read-only target discovery endpoints.
- Device list detection through the existing bundled ADB when available.
- Foreground app detection for a selected device.
- Package launchability validation for the configured package.
- Web UI buttons beside the existing task configuration fields:
  - `检测设备`
  - `使用当前前台应用`
  - `校验配置`
- Chinese status messages that explain what was detected and whether it is safe to start.
- Tests for backend parsing, endpoint responses, and static Web wiring.

This phase does not include:

- Starting or stopping apps from the discovery endpoints.
- Installing APKs.
- Granting permissions.
- Selecting apps from a full installed-app inventory.
- Persisting discovered values to project config files.
- Enabling click/swipe permissions automatically.
- Changing the existing `/api/runs` safety validation.

## Backend API

Add a small read-only module, for example `game_reverse.target_discovery`, with functions that can be tested without a real emulator:

- `list_android_devices(adb_runner) -> list[DeviceInfo]`
- `get_foreground_app(device_id, adb_runner) -> ForegroundApp`
- `validate_package(device_id, package_name, adb_runner) -> PackageValidation`

Use subprocess only behind an injected runner boundary so tests can provide command output.

Expose these HTTP endpoints in `game_reverse.web_server` and `game_reverse.web_service`:

```text
GET /api/devices
GET /api/devices/{device_id}/foreground
GET /api/devices/{device_id}/packages/{package_name}/validation
```

Example `/api/devices` response:

```json
{
  "devices": [
    {
      "id": "emulator-5554",
      "uri": "Android:///emulator-5554",
      "status": "device",
      "label": "emulator-5554"
    }
  ]
}
```

Example foreground response:

```json
{
  "device_id": "emulator-5554",
  "package_name": "com.redlinegames.matchsniper3d",
  "activity": "com.unity3d.player.UnityPlayerActivity",
  "source": "dumpsys activity activities"
}
```

Example validation response:

```json
{
  "device_id": "emulator-5554",
  "package_name": "com.redlinegames.matchsniper3d",
  "installed": true,
  "launchable": true,
  "activity": "com.unity3d.player.UnityPlayerActivity",
  "warnings": []
}
```

If ADB is missing or no device is online, return JSON with a clear `error` message and a non-2xx status. Do not crash the server.

## ADB Resolution

Prefer the bundled Windows ADB path already present in this repository:

```text
airtest/core/android/static/adb/windows/adb.exe
```

Fallback to `adb` from `PATH` if the bundled executable is missing. The resolved command path should be centralized so tests can verify the fallback order without launching a real process.

## Foreground Detection

Try foreground package parsing in this order:

1. `adb -s <device> shell dumpsys activity activities`
   - Prefer `topResumedActivity=... package/activity`.
   - Also support `mResumedActivity`.
2. `adb -s <device> shell dumpsys window`
   - Support `mCurrentFocus=Window{... package/activity}`.
   - Support `mFocusedApp=ActivityRecord{... package/activity}`.

Ignore Android system packages in the UI recommendation if a non-system foreground app is available. If only system UI is focused, show the package but do not auto-fill it without a warning.

## Web UI Behavior

Keep the existing text inputs. Add compact controls inside the Task Configuration panel:

- `检测设备`: calls `/api/devices`.
- If one device is found, fill `device_uri` with its `uri`.
- If multiple devices are found, show a select control with device labels and fill when selected.
- `使用当前前台应用`: reads the current device field, calls `/foreground`, then fills `package_name`.
- `校验配置`: calls package validation for the current device/package and shows the result.

The UI should not automatically enable `允许点击/滑动`. It should show a reminder when the detected foreground package differs from the package field:

```text
当前前台应用与包名不一致，请确认后再开始。
```

The start button remains controlled by the existing backend and runner availability logic. A failed validation should not erase manually typed values.

## Data Flow

On page load:

1. Load sample data and `/api/health` as today.
2. Do not automatically call ADB discovery.
3. Render task fields from sample data.

On `检测设备`:

1. GET `/api/devices`.
2. If exactly one online device exists, fill `device_uri`.
3. If multiple devices exist, render a select control.
4. Show a Chinese status line.

On `使用当前前台应用`:

1. Parse the current `device_uri` into a device id.
2. GET `/api/devices/{device_id}/foreground`.
3. Fill `package_name` with the detected package.
4. Show package/activity/source in the status line.

On `校验配置`:

1. Parse current `device_uri` and `package_name`.
2. GET package validation.
3. Render installed/launchable state and warnings.

## Error Handling

- No backend online: disable smart config buttons and keep manual inputs usable.
- No devices: show `未检测到在线设备`.
- Multiple devices: require explicit selection.
- Invalid `device_uri`: show `设备地址格式不正确`.
- Foreground app unavailable: show the raw command source if helpful, but do not fill package.
- Package missing: show `包名未安装`.
- Package installed but not launchable: show `包名存在，但未发现可启动 Activity`.

All errors should be visible in the Task Configuration panel. They should not replace the run event log.

## Safety

Discovery endpoints are read-only:

- No shell command text from the browser.
- Browser can only ask for fixed discovery operations.
- Device id and package name are path parameters and must be validated before command execution.
- Reject values containing whitespace, shell metacharacters, path separators, or empty segments.
- Never expose API keys, environment variables, or arbitrary command output.

The operator remains responsible for pressing `开始运行`. Smart config fills fields only.

## Testing

Add backend tests for:

- `adb devices` parsing, including no devices, one device, multiple devices, and offline devices.
- Foreground parsing from `topResumedActivity`, `mResumedActivity`, `mCurrentFocus`, and `mFocusedApp`.
- Package validation parsing for installed/launchable and missing package.
- Endpoint JSON shape and error status.
- Device id and package path validation reject unsafe strings.

Add Web static tests for:

- Buttons `检测设备`, `使用当前前台应用`, and `校验配置`.
- App script references `/api/devices`.
- App script still does not contain `child_process`, `codex exec`, or `claude -p`.
- Chinese status labels are readable.

Verification commands:

```text
python -m unittest tests.test_game_reverse_target_discovery tests.test_game_reverse_web_service tests.test_game_reverse_web_server tests.test_web_console_static
node --check web/app.js
git diff --check
```

Manual smoke:

1. Start MuMu with the target game in the foreground.
2. Open `http://127.0.0.1:8768/web/index.html`.
3. Click `检测设备`.
4. Confirm `Android:///emulator-5554` is filled when one device is online.
5. Click `使用当前前台应用`.
6. Confirm package becomes `com.redlinegames.matchsniper3d`.
7. Click `校验配置`.
8. Confirm the UI reports installed and launchable.
9. Start a low-step run with unsafe actions disabled first, then decide whether to enable click/swipe.

## Rollout Notes

Implement backend parsing and endpoint tests before touching the UI. The parsing logic is the riskiest part because Android and emulator dumpsys output varies by version. Keep the first UI version small: buttons, status text, and optional device select are enough.

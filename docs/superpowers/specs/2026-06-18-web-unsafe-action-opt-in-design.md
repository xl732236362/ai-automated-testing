# Web Unsafe Action Opt-In Design

## Goal

Allow the Web console to start real gameplay exploration with `tap` and `swipe`, while keeping those actions disabled by default and requiring explicit per-run operator approval.

## Background

The backend already supports the safety gate:

- `allowed_actions` may include `tap` and `swipe`.
- If either action is present, `/api/runs` requires `enable_unsafe_actions: true`.
- Without that flag, `GameReverseWebService` rejects the request with `enable_unsafe_actions is required for tap or swipe`.

The current Web UI always sends safe actions only and hard-codes `enable_unsafe_actions: false`. This is correct for diagnostic runs, but it prevents the agent from progressing through games that require tapping or swiping.

## Scope

This phase includes:

- A visible Web UI opt-in control for real click/swipe actions.
- Payload building that only includes `tap` and `swipe` when the operator opts in.
- Clear Chinese warning copy explaining that enabled actions will operate the connected emulator/app.
- Static tests proving the default remains safe and the opt-in path exists.
- Browser/API smoke verification that the opt-in payload can pass backend validation.

This phase does not include:

- New backend endpoints.
- Persisting the permission in local storage or configuration files.
- Automatically enabling unsafe actions based on mission text.
- Fine-grained coordinate allowlists or visual safe zones.
- Login/payment/permission screen detection beyond the existing model prompt and action validator.
- Direct manual tap/swipe buttons in the Web UI.

## UI Behavior

Add an "交互权限" area to the existing Safety panel, near the action chips.

The panel has one checkbox-style toggle:

- Label: `允许点击/滑动`
- Default: unchecked on every page load.
- Help text: `开启后，本次运行可能会真实点击或滑动当前连接的设备。请确认包名和画面正确。`

When unchecked:

- Action chips show `截图`, `等待`, `返回`.
- Start payload sends:

```json
{
  "allowed_actions": ["screenshot", "wait", "back"],
  "enable_unsafe_actions": false
}
```

When checked:

- Action chips show `截图`, `等待`, `返回`, `点击`, `滑动`.
- The Safety panel uses a warning visual state.
- Start payload sends:

```json
{
  "allowed_actions": ["screenshot", "wait", "back", "tap", "swipe"],
  "enable_unsafe_actions": true
}
```

The toggle affects only the current browser page state. Refreshing the page resets it to unchecked.

## Data Flow

On load:

1. Render the configured safe actions from sample/backend data.
2. Ensure the unsafe-action toggle is unchecked.
3. Render only safe action chips.

On toggle change:

1. Read `allow-unsafe-actions-input.checked`.
2. Re-render action chips using the effective actions for this page state.
3. Do not call the backend.

On start:

1. Build the normal run payload from selected runner and mission fields.
2. Call `getEffectiveAllowedActions(config)`:
   - unchecked: remove `tap` and `swipe`.
   - checked: add `tap` and `swipe` once.
3. Set `enable_unsafe_actions` to the same boolean.
4. POST `/api/runs`.

## Safety Rules

The default remains non-invasive:

- No `tap`.
- No `swipe`.
- `enable_unsafe_actions: false`.

Unsafe actions require an explicit UI control state. The app must not infer permission from mission text such as "通关", "点击", or "探索玩法".

The browser still never accepts command-line fragments and never edits environment variables or API keys.

The backend remains the final enforcement layer. If the UI sends `tap` or `swipe` without `enable_unsafe_actions: true`, backend validation must still reject the run.

## Error Handling

If the backend rejects the request, the existing start-run error path displays the validation message in the run state.

If the operator enables unsafe actions while no backend or runner is available, the start button remains disabled by the existing runner availability logic.

If sample data contains `tap` or `swipe` in the future, unchecked UI state still filters them out before rendering and before POST.

## Testing

Update `tests/test_web_console_static.py`:

- Assert `index.html` contains `id="allow-unsafe-actions-input"`.
- Assert touched Chinese labels include `交互权限` and `允许点击/滑动`.
- Assert sample data default `allowed_actions` remains `["screenshot", "wait", "back"]`.
- Assert `app.js` contains `getUnsafeActionsEnabled`.
- Assert `app.js` contains `getEffectiveAllowedActions`.
- Assert `app.js` sends `enable_unsafe_actions: getUnsafeActionsEnabled()`.
- Assert `app.js` still does not reference `child_process`, `codex exec`, or `claude -p`.

Verification commands:

```text
python -m unittest tests.test_web_console_static tests.test_game_reverse_web_service
node --check web/app.js
git diff --check
```

Manual smoke:

1. Start local backend with `GAME_REVERSE_ENABLE_CODEX_EXEC=1`.
2. Open `http://127.0.0.1:8768/web/index.html`.
3. Confirm the unsafe-action toggle is unchecked by default.
4. Confirm action chips show only safe actions.
5. Check `允许点击/滑动`.
6. Confirm action chips include `点击` and `滑动`.
7. Start a short run against the real package name, for example `com.redlinegames.matchsniper3d`.
8. Confirm `/api/runs` accepts the request and the generated session records `Allowed actions used` with `tap` and `swipe` when the runner uses them.

## Rollout Notes

This change intentionally makes real device control easy to enable but hard to enable accidentally. The first run after implementation should use a low `max_steps` value such as `5` or `10`, then inspect the generated `actions.jsonl` before increasing the budget.

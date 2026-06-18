# Web Unsafe Action Opt-In Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-run Web UI opt-in that allows `tap` and `swipe` only when the operator explicitly enables real device interaction.

**Architecture:** Keep the backend safety gate unchanged. Add a checkbox in the existing Safety panel, derive effective allowed actions in `web/app.js`, and send `enable_unsafe_actions` from that checkbox state. The default page load and sample data stay safe-only.

**Tech Stack:** Static HTML, vanilla JavaScript, CSS, Python `unittest`, `node --check`, existing `game_reverse.web_server`.

---

## File Structure

- Modify `tests/test_web_console_static.py`: static contract tests for the opt-in control, default-safe sample data, and JavaScript payload behavior.
- Modify `web/index.html`: add the visible `allow-unsafe-actions-input` checkbox and Chinese warning text to the existing Safety panel.
- Modify `web/app.js`: add unsafe-action state helpers, re-render action chips when the checkbox changes, and build POST payloads from effective actions.
- Modify `web/styles.css`: add compact styling for the permission toggle and warning state.
- Do not modify `game_reverse/web_service.py`: it already enforces `enable_unsafe_actions`.
- Do not modify `web/data/sample-run.json`: it must remain safe-only by default.
- Modify this plan file as tasks are executed, marking only completed steps as `[x]`.

## Task 1: Static Test Contract

**Files:**
- Modify: `tests/test_web_console_static.py`

- [ ] **Step 1: Add failing HTML assertions**

Update `test_index_wires_assets_and_sample_data` by adding these assertions after the existing mission input ID checks:

```python
        self.assertIn('id="allow-unsafe-actions-input"', html)
        self.assertIn("交互权限", html)
        self.assertIn("允许点击/滑动", html)
```

- [ ] **Step 2: Add failing sample safety assertions**

In `test_sample_run_json_has_required_shape`, keep the existing safe-only assertion and add explicit exclusions:

```python
        self.assertEqual(data["config"]["allowed_actions"], ["screenshot", "wait", "back"])
        self.assertNotIn("tap", data["config"]["allowed_actions"])
        self.assertNotIn("swipe", data["config"]["allowed_actions"])
```

If the exact safe-only assertion already exists, add only the two `assertNotIn` lines.

- [ ] **Step 3: Add failing JavaScript opt-in assertions**

Update `test_app_declares_static_only_boundary` so it requires the new helper names and dynamic payload:

```python
        self.assertIn("getUnsafeActionsEnabled", script)
        self.assertIn("getEffectiveAllowedActions", script)
        self.assertIn("wireUnsafeActionToggle", script)
        self.assertIn("enable_unsafe_actions: getUnsafeActionsEnabled()", script)
        self.assertIn('["tap", "swipe"]', script)
        self.assertNotIn("enable_unsafe_actions: true", script)
```

Keep these existing safety assertions:

```python
        self.assertNotIn("child_process", script)
        self.assertNotIn("codex exec", script)
        self.assertNotIn("claude -p", script)
```

- [ ] **Step 4: Update Chinese readability assertions**

Update `test_touched_web_files_use_readable_chinese` to include:

```python
        self.assertIn("交互权限", html)
        self.assertIn("允许点击/滑动", html)
        self.assertIn("真实点击或滑动", html)
```

- [ ] **Step 5: Run RED**

Run:

```powershell
python -m unittest tests.test_web_console_static
```

Expected: fail because `allow-unsafe-actions-input`, `getUnsafeActionsEnabled`, `getEffectiveAllowedActions`, and `wireUnsafeActionToggle` do not exist yet.

## Task 2: HTML Permission Toggle

**Files:**
- Modify: `web/index.html`

- [ ] **Step 1: Add the permission toggle markup**

Inside the existing `<section id="safety" class="panel">`, insert this block immediately after:

```html
<div class="actions-row" id="allowed-actions"></div>
```

Add:

```html
<div class="permission-toggle" id="unsafe-actions-panel">
  <label class="toggle-row" for="allow-unsafe-actions-input">
    <input id="allow-unsafe-actions-input" type="checkbox">
    <span>
      <strong>允许点击/滑动</strong>
      <small>开启后，本次运行可能会真实点击或滑动当前连接的设备。请确认包名和画面正确。</small>
    </span>
  </label>
</div>
```

Do not add manual tap or swipe buttons.

- [ ] **Step 2: Update Safety panel title if needed**

Ensure the Safety panel contains readable Chinese:

```html
<h2>动作与安全限制</h2>
```

Leave the existing action chips container ID unchanged:

```html
id="allowed-actions"
```

- [ ] **Step 3: Run HTML-focused tests**

Run:

```powershell
python -m unittest tests.test_web_console_static
```

Expected: HTML assertions pass; JavaScript opt-in assertions still fail.

## Task 3: JavaScript Opt-In State And Payload

**Files:**
- Modify: `web/app.js`

- [ ] **Step 1: Define unsafe action constants**

Near `ACTION_LABELS`, add:

```javascript
const UNSAFE_ACTIONS = ["tap", "swipe"];
```

- [ ] **Step 2: Wire the toggle on DOM ready**

In the `DOMContentLoaded` handler, after `wireStartButton();`, add:

```javascript
  wireUnsafeActionToggle();
```

The handler should look like:

```javascript
document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("app");
  const sampleUrl = root.dataset.sampleUrl;

  wireStartButton();
  wireUnsafeActionToggle();
  Promise.all([loadSample(sampleUrl), detectBackend()])
    .then(([sample, health]) => {
      currentData = mergeBackendHealth(sample, health);
      selectedRunnerId = chooseInitialRunner(currentData.runners);
      renderConsole(currentData);
      updateBackendStatus();
    })
    .catch(renderLoadError);
});
```

- [ ] **Step 3: Add toggle helper functions**

Add these functions before `wireStartButton()`:

```javascript
function wireUnsafeActionToggle() {
  const toggle = document.getElementById("allow-unsafe-actions-input");
  if (!toggle) {
    return;
  }
  toggle.checked = false;
  toggle.addEventListener("change", () => {
    if (currentData) {
      renderAllowedActions(currentData.config.allowed_actions);
    }
  });
}

function getUnsafeActionsEnabled() {
  const toggle = document.getElementById("allow-unsafe-actions-input");
  return Boolean(toggle && toggle.checked);
}

function getEffectiveAllowedActions(config) {
  const baseActions = (config.allowed_actions || []).filter(
    (action) => !UNSAFE_ACTIONS.includes(action)
  );
  if (!getUnsafeActionsEnabled()) {
    return baseActions;
  }
  return Array.from(new Set([...baseActions, ...UNSAFE_ACTIONS]));
}
```

- [ ] **Step 4: Render effective action chips**

Replace the body of `renderAllowedActions(actions)` with:

```javascript
function renderAllowedActions(actions) {
  const row = document.getElementById("allowed-actions");
  const effectiveActions = getEffectiveAllowedActions({allowed_actions: actions || []});
  row.replaceChildren(
    ...effectiveActions.map((action) => {
      const chip = document.createElement("span");
      chip.className = UNSAFE_ACTIONS.includes(action) ? "action-chip is-risky" : "action-chip";
      chip.textContent = ACTION_LABELS[action] || action;
      chip.title = UNSAFE_ACTIONS.includes(action) ? "已显式允许真实设备交互" : "默认安全动作";
      return chip;
    })
  );

  const panel = document.getElementById("unsafe-actions-panel");
  if (panel) {
    panel.classList.toggle("is-enabled", getUnsafeActionsEnabled());
  }
}
```

- [ ] **Step 5: Build payload from effective actions**

In `buildRunPayload(config)`, replace:

```javascript
    allowed_actions: config.allowed_actions,
```

with:

```javascript
    allowed_actions: getEffectiveAllowedActions(config),
```

Replace:

```javascript
    enable_unsafe_actions: false,
```

with:

```javascript
    enable_unsafe_actions: getUnsafeActionsEnabled(),
```

- [ ] **Step 6: Keep failed start state consistent**

In the `startRun()` `.catch()` block, replace:

```javascript
      button.disabled = false;
```

with:

```javascript
      markStaticControls();
```

This preserves the existing runner/backend gating after validation failures.

- [ ] **Step 7: Run JS/static GREEN**

Run:

```powershell
node --check web\app.js
python -m unittest tests.test_web_console_static
```

Expected: both pass.

## Task 4: CSS Permission Toggle Styling

**Files:**
- Modify: `web/styles.css`

- [ ] **Step 1: Add permission toggle styles**

Add these rules near `.actions-row` and `.safety-copy`:

```css
.permission-toggle {
  margin: 0 14px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-soft);
}

.permission-toggle.is-enabled {
  border-color: #f0c36d;
  background: #fff7e8;
}

.toggle-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin: 0;
  padding: 11px;
  color: var(--text);
}

.toggle-row input {
  width: 16px;
  height: 16px;
  min-height: 16px;
  margin-top: 2px;
  padding: 0;
  accent-color: var(--warning);
}

.toggle-row strong,
.toggle-row small {
  display: block;
}

.toggle-row strong {
  margin-bottom: 3px;
  font-size: 13px;
}

.toggle-row small {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.45;
}
```

- [ ] **Step 2: Run style/static checks**

Run:

```powershell
python -m unittest tests.test_web_console_static
node --check web\app.js
git diff --check
```

Expected: tests pass, JS syntax passes, no whitespace errors.

## Task 5: API Smoke For Backend Safety Contract

**Files:**
- Verify only unless failures reveal a real defect.

- [ ] **Step 1: Start or reuse local backend**

If no server is running on port `8768`, start one:

```powershell
$env:GAME_REVERSE_ENABLE_CODEX_EXEC = "1"
python -m game_reverse.web_server --host 127.0.0.1 --port 8768
```

If a server is already running, reuse it.

- [ ] **Step 2: Verify backend still rejects unsafe actions without opt-in**

Run:

```powershell
$body = @{
  runner = "game_reverse"
  device_uri = "Android:///emulator-5554"
  package_name = "com.redlinegames.matchsniper3d"
  max_steps = 1
  mission = @{
    type = "free_explore"
    goal = "Safety gate smoke"
  }
  allowed_actions = @("screenshot", "wait", "back", "tap", "swipe")
  enable_unsafe_actions = $false
} | ConvertTo-Json -Depth 5

try {
  Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8768/api/runs" -ContentType "application/json" -Body $body
} catch {
  $_.ErrorDetails.Message
}
```

Expected output includes:

```text
enable_unsafe_actions is required for tap or swipe
```

- [ ] **Step 3: Verify backend accepts unsafe actions with opt-in**

Run:

```powershell
$body = @{
  runner = "game_reverse"
  device_uri = "Android:///emulator-5554"
  package_name = "com.redlinegames.matchsniper3d"
  max_steps = 1
  mission = @{
    type = "free_explore"
    goal = "Unsafe opt-in smoke with one step"
  }
  allowed_actions = @("screenshot", "wait", "back", "tap", "swipe")
  enable_unsafe_actions = $true
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8768/api/runs" -ContentType "application/json" -Body $body
```

Expected: JSON object with fields including `id`, `runner`, and `status`. Because this can start a real one-step runner, only use `max_steps = 1`.

## Task 6: Final Verification And Commit

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Modify: `tests/test_web_console_static.py`
- Modify: `docs/superpowers/plans/2026-06-18-web-unsafe-action-opt-in.md`

- [ ] **Step 1: Run final relevant tests**

Run:

```powershell
python -m unittest tests.test_web_console_static tests.test_game_reverse_web_service
node --check web\app.js
git diff --check
git status --short
```

Expected:

- Python tests pass.
- `node --check` exits 0.
- `git diff --check` prints no whitespace errors.
- Only intended files are modified.

- [ ] **Step 2: Mark executed plan checkboxes**

Mark only completed steps as `[x]` in this plan file.

- [ ] **Step 3: Commit implementation**

Run:

```powershell
git add web/index.html web/app.js web/styles.css tests/test_web_console_static.py docs/superpowers/plans/2026-06-18-web-unsafe-action-opt-in.md
git commit -m "Add web unsafe action opt-in"
```

Expected: commit succeeds.

## Self-Review Checklist

- Spec coverage:
  - UI opt-in control: Task 2.
  - Dynamic payload allowed actions and `enable_unsafe_actions`: Task 3.
  - Default safe-only behavior: Tasks 1 and 3.
  - Styling warning state: Task 4.
  - Backend validation smoke: Task 5.
  - Final verification and commit: Task 6.
- No backend changes are planned because `game_reverse/web_service.py` already enforces the required gate.
- No persistence is planned; `wireUnsafeActionToggle()` resets the checkbox to unchecked on page load.
- No manual tap/swipe UI is planned.

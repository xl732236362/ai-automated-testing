# Web Runner Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Web console select available runners, start `codex_exec` through the backend API, and display events/reports from the browser.

**Architecture:** Keep the backend unchanged. Update static HTML/CSS/JS so `/api/health` runner metadata drives selectable cards, editable mission fields build the POST payload, polling renders run events, and final reports load through the existing session report endpoint.

**Tech Stack:** Static HTML, vanilla JavaScript, CSS, Python `unittest`, `node --check`, existing `game_reverse.web_server`.

---

## File Structure

- Modify `web/index.html`: fix Chinese labels, add editable form controls and runner selection affordances.
- Modify `web/app.js`: selected runner state, backend health runner merge, editable payload builder, event/report rendering improvements.
- Modify `web/styles.css`: selected/disabled runner card styles, compact editable form controls.
- Modify `web/data/sample-run.json`: ensure sample runner metadata has `available`/`description` shape compatible with backend.
- Modify `tests/test_web_console_static.py`: static assertions for editable IDs, selected runner state, Chinese labels, safety boundaries.

## Task 1: Static Tests For Runner UI Contract

**Files:**
- Modify: `tests/test_web_console_static.py`

- [x] **Step 1: Write failing tests**

Update `test_index_wires_assets_and_sample_data`:

```python
        self.assertIn('id="device-uri-input"', html)
        self.assertIn('id="package-name-input"', html)
        self.assertIn('id="model-input"', html)
        self.assertIn('id="max-steps-input"', html)
        self.assertIn('id="mission-goal"', html)
        self.assertIn("App/Game 探索控制台", html)
```

Update `test_app_declares_static_only_boundary`:

```python
        self.assertIn("selectedRunnerId", script)
        self.assertIn("runner: selectedRunnerId", script)
        self.assertIn("renderRunners", script)
        self.assertIn("enable_unsafe_actions: false", script)
        self.assertNotIn("child_process", script)
        self.assertNotIn("codex exec", script)
        self.assertNotIn("claude -p", script)
```

Add:

```python
    def test_touched_web_files_use_readable_chinese(self):
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        script = (WEB_DIR / "app.js").read_text(encoding="utf-8")

        self.assertIn("任务配置", html)
        self.assertIn("执行器选择", html)
        self.assertIn("开始运行", html)
        self.assertIn("后端在线", script)
        self.assertIn("运行完成", script)
```

- [x] **Step 2: Run RED**

Run:

```bash
python -m unittest tests.test_web_console_static
```

Expected: fail because the static files still use old IDs/text and `selectedRunnerId` does not exist.

- [ ] **Step 3: Commit tests if desired**

Do not commit a failing state. Proceed to Task 2.

## Task 2: HTML Structure And Chinese Text Cleanup

**Files:**
- Modify: `web/index.html`

- [x] **Step 1: Replace static shell text and add input IDs**

Rewrite the touched labels in `web/index.html` so they are readable Chinese. Keep the same three-column layout and existing IDs, but add these controls in the Mission panel:

```html
<label>
  设备地址
  <input id="device-uri-input" type="text" autocomplete="off">
</label>
<label>
  应用包名
  <input id="package-name-input" type="text" autocomplete="off">
</label>
<label>
  模型
  <input id="model-input" type="text" autocomplete="off">
</label>
<label>
  最大步数
  <input id="max-steps-input" type="number" min="1" max="999">
</label>
```

Keep:

```html
<textarea id="mission-goal"></textarea>
```

Do not add tap/swipe controls.

- [x] **Step 2: Run HTML/static RED-GREEN check**

Run:

```bash
python -m unittest tests.test_web_console_static
```

Expected: remaining failures should now be in `web/app.js`, not missing HTML IDs.

## Task 3: JavaScript Runner Selection And Payload

**Files:**
- Modify: `web/app.js`

- [x] **Step 1: Add selected runner state**

Add near the globals:

```javascript
let selectedRunnerId = "game_reverse";
```

- [x] **Step 2: Merge backend runner metadata**

Change startup so `detectBackend()` returns health and `renderConsole()` receives it:

```javascript
Promise.all([loadSample(sampleUrl), detectBackend()])
  .then(([sample, health]) => {
    currentData = mergeBackendHealth(sample, health);
    selectedRunnerId = chooseInitialRunner(currentData.runners);
    renderConsole(currentData);
    updateBackendStatus();
  })
```

Implement:

```javascript
function mergeBackendHealth(sample, health) {
  if (!health || !Array.isArray(health.runners)) {
    return sample;
  }
  return {...sample, runners: health.runners};
}

function chooseInitialRunner(runners) {
  const gameReverse = runners.find((runner) => runner.id === "game_reverse" && runner.available);
  if (gameReverse) {
    return gameReverse.id;
  }
  const firstAvailable = runners.find((runner) => runner.available);
  return firstAvailable ? firstAvailable.id : "";
}
```

- [x] **Step 3: Render selectable runner buttons**

Update `renderRunners(runners)` so each card is a `button`:

```javascript
button.type = "button";
button.className = "runner-card";
button.disabled = !runner.available;
button.classList.toggle("is-selected", runner.id === selectedRunnerId);
button.classList.toggle("is-disabled", !runner.available);
button.addEventListener("click", () => {
  selectedRunnerId = runner.id;
  renderRunners(currentData.runners);
  markStaticControls();
});
```

Use labels:

```javascript
status.textContent = runner.available ? "可用" : "不可用";
```

- [x] **Step 4: Render editable config fields**

Change `renderConfig(config)` to set:

```javascript
document.getElementById("device-uri-input").value = config.device_uri || "Android:///";
document.getElementById("package-name-input").value = config.package_name || "";
document.getElementById("model-input").value = config.model || "";
document.getElementById("max-steps-input").value = config.max_steps || 50;
```

Keep mission type as read-only display if useful.

- [x] **Step 5: Build payload from DOM**

Replace `buildRunPayload(config)` with:

```javascript
function buildRunPayload(config) {
  return {
    runner: selectedRunnerId,
    device_uri: readInputValue("device-uri-input", config.device_uri || "Android:///"),
    package_name: readInputValue("package-name-input", config.package_name || ""),
    max_steps: readPositiveInt("max-steps-input", config.max_steps || 50),
    mission: {
      ...config.mission,
      goal: readInputValue("mission-goal", config.mission.goal || ""),
    },
    model: readInputValue("model-input", config.model || ""),
    allowed_actions: config.allowed_actions,
    recent_steps: config.recent_steps,
    consecutive_failure_limit: config.consecutive_failure_limit,
    enable_unsafe_actions: false,
  };
}
```

Add helpers:

```javascript
function readInputValue(id, fallback) {
  const field = document.getElementById(id);
  const value = field ? field.value.trim() : "";
  return value || fallback;
}

function readPositiveInt(id, fallback) {
  const value = Number.parseInt(readInputValue(id, String(fallback)), 10);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}
```

- [x] **Step 6: Improve status and event rendering**

Update status strings to readable Chinese:

```javascript
queued: "排队中",
running: "运行中",
completed: "运行完成",
failed: "运行失败",
```

In `renderEvents`, show:

```javascript
detail.textContent = event.message || event.error || event.session_dir || event.created_at || "";
```

- [x] **Step 7: Run JS/static GREEN**

Run:

```bash
node --check web/app.js
python -m unittest tests.test_web_console_static
```

Expected: both pass.

## Task 4: CSS For Runner Selection And Inputs

**Files:**
- Modify: `web/styles.css`

- [x] **Step 1: Add input styling**

Add `input` beside existing `button, textarea` font reset:

```css
button,
input,
textarea {
  font: inherit;
}
```

Add compact input styles:

```css
.edit-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 14px;
}

.edit-grid label {
  display: grid;
  gap: 6px;
}

.edit-grid input {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 7px;
  padding: 9px 10px;
  background: var(--surface-soft);
  color: var(--text);
}
```

- [x] **Step 2: Add runner selected/disabled states**

```css
.runner-card {
  width: 100%;
  padding: 11px;
  color: inherit;
  text-align: left;
}

.runner-card.is-selected {
  border-color: var(--accent);
  background: #e8f1fb;
}

.runner-card.is-disabled {
  opacity: 0.62;
}
```

- [x] **Step 3: Run style/static check**

Run:

```bash
python -m unittest tests.test_web_console_static
node --check web/app.js
```

Expected: pass.

## Task 5: Browser Smoke

**Files:**
- Verify only unless failures require fixes.

- [x] **Step 1: Start backend with Codex enabled**

Run:

```powershell
$env:GAME_REVERSE_ENABLE_CODEX_EXEC = "1"
$env:GAME_REVERSE_CODEX_TIMEOUT_SECONDS = "300"
$env:GAME_REVERSE_CODEX_SANDBOX = "read-only"
python -m game_reverse.web_server --host 127.0.0.1 --port 8768
```

- [ ] **Step 2: Open browser**

Open:

```text
http://127.0.0.1:8768/web/index.html
```

Verify:

- Backend status shows online.
- `codex_exec` card shows available.
- Selecting `codex_exec` changes selection styling.
- Start button sends a run.
- Events appear.
- Final report appears.

- [ ] **Step 3: Stop backend**

Stop the local backend process.

## Task 6: Final Verification And Commit

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Modify: `web/data/sample-run.json`
- Modify: `tests/test_web_console_static.py`
- Modify: `docs/superpowers/plans/2026-06-18-web-runner-control.md`

- [x] **Step 1: Run final checks**

Run:

```bash
python -m unittest tests.test_web_console_static tests.test_game_reverse_web_server tests.test_game_reverse_web_service
node --check web/app.js
git diff --check
git status --short
```

Expected: tests pass, no whitespace errors, only intended files changed.

- [x] **Step 2: Mark executed plan checkboxes**

Mark only executed steps as `[x]`.

- [ ] **Step 3: Commit**

Run:

```bash
git add web/index.html web/app.js web/styles.css web/data/sample-run.json tests/test_web_console_static.py docs/superpowers/plans/2026-06-18-web-runner-control.md
git commit -m "Add web runner control"
```

Expected: commit succeeds.

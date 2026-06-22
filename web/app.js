const STATIC_ONLY = false;
const API_BASE = "";

let currentData = null;
let backendOnline = false;
let selectedRunnerId = "game_reverse";
let pollTimer = null;

const ACTION_LABELS = {
  screenshot: "截图",
  wait: "等待",
  back: "返回",
  tap: "点击",
  swipe: "滑动",
  hold_drag_release: "按住拖放",
  error: "错误",
};

const UNSAFE_ACTIONS = ["tap", "swipe", "hold_drag_release"];

document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("app");
  const sampleUrl = root.dataset.sampleUrl;

  wireStartButton();
  wireUnsafeActionToggle();
  wireTargetConfigControls();
  Promise.all([loadSample(sampleUrl), detectBackend(), detectBackendConfig()])
    .then(([sample, health, backendConfig]) => {
      currentData = mergeBackendConfig(mergeBackendHealth(sample, health), backendConfig);
      selectedRunnerId = chooseInitialRunner(currentData.runners);
      renderConsole(currentData);
      updateBackendStatus();
    })
    .catch(renderLoadError);
});

function mergeBackendHealth(sample, health) {
  if (!health || !Array.isArray(health.runners)) {
    return sample;
  }
  return {...sample, runners: health.runners};
}

function mergeBackendConfig(data, backendConfig) {
  if (!backendConfig) {
    return data;
  }
  return {
    ...data,
    config: {
      ...data.config,
      output_root: backendConfig.output_root || data.config.output_root,
      profile_root: backendConfig.profile_root || data.config.profile_root,
      allowed_actions: backendConfig.default_allowed_actions || data.config.allowed_actions,
    },
  };
}

function chooseInitialRunner(runners) {
  const gameReverse = runners.find((runner) => runner.id === "game_reverse" && isRunnerAvailable(runner));
  if (gameReverse) {
    return gameReverse.id;
  }
  const firstAvailable = runners.find(isRunnerAvailable);
  return firstAvailable ? firstAvailable.id : "";
}

function renderConsole(data) {
  renderRunState(data.run);
  renderConfig(data.config);
  renderMission(data.config.mission);
  renderRunners(data.runners);
  renderAllowedActions(data.config.allowed_actions);
  renderTimeline(data.run.steps);
  renderRisks(data.run.steps);
  renderReport(data.run);
  renderProfileSummary(data.profile || {exists: false});
  renderActionReasoning(data.run.steps || []);
  renderEvents([]);
  renderSessions([]);
  markStaticControls();
}

function renderRunState(run) {
  const state = document.getElementById("run-state");
  state.textContent = run.status_label || run.status || "静态预览";
  state.title = run.summary || "";
}

function renderConfig(config) {
  setInputValue("device-uri-input", config.device_uri || "Android:///");
  setInputValue("package-name-input", config.package_name || "");
  setInputValue("model-input", config.model || "");
  setInputValue("max-steps-input", config.max_steps || 50);
}

function renderMission(mission) {
  document.getElementById("mission-goal").value = mission.goal || "";
  renderList("mission-targets", mission.targets || [], "未设置目标对象");
  renderList("mission-success", mission.success_criteria || [], "未设置成功标准");
}

function renderRunners(runners) {
  const grid = document.getElementById("runner-grid");
  grid.replaceChildren(
    ...runners.map((runner) => {
      const available = isRunnerAvailable(runner);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "runner-card";
      button.disabled = !available;
      button.classList.toggle("is-selected", runner.id === selectedRunnerId);
      button.classList.toggle("is-disabled", !available);
      button.addEventListener("click", () => {
        selectedRunnerId = runner.id;
        renderRunners(currentData.runners);
        markStaticControls();
      });

      const header = document.createElement("header");
      const name = document.createElement("strong");
      name.textContent = runner.name || runner.id;
      const status = document.createElement("span");
      status.className = available ? "runner-status" : "runner-status is-planned";
      status.textContent = runnerStatusLabel(runner, available);
      header.append(name, status);

      const description = document.createElement("p");
      description.textContent = runner.description || "";

      button.append(header, description);
      return button;
    })
  );
}

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

function renderTimeline(steps) {
  const timeline = document.getElementById("timeline-list");
  timeline.replaceChildren(
    ...steps.map((step) => {
      const item = document.createElement("article");
      item.className = "timeline-item";

      const index = document.createElement("div");
      index.className = "step-index";
      index.textContent = String(step.step).padStart(2, "0");

      const body = document.createElement("div");
      const title = document.createElement("h3");
      title.textContent = step.state;
      const summary = document.createElement("p");
      summary.textContent = step.screen_summary;
      const reason = document.createElement("p");
      reason.textContent = step.reason;
      body.append(title, summary, reason);

      const action = document.createElement("span");
      action.className = "action-type";
      action.textContent = ACTION_LABELS[step.action.type] || step.action.type;

      item.append(index, body, action);
      return item;
    })
  );
}

function renderRisks(steps) {
  const riskList = document.getElementById("risk-list");
  const risks = steps.flatMap((step) => step.risks || []);

  if (risks.length === 0) {
    riskList.replaceChildren(createListItem("当前没有风险记录。"));
    return;
  }

  riskList.replaceChildren(...risks.map(createListItem));
}

function renderReport(run) {
  const report = document.getElementById("report-preview");
  report.replaceChildren(
    ...(run.report_preview || []).map((line) => {
      const paragraph = document.createElement("p");
      paragraph.textContent = line;
      return paragraph;
    })
  );

  const outputs = document.getElementById("output-list");
  const outputEntries = [
    ["会话目录", run.outputs.session_dir],
    ["任务草稿", run.outputs.mission_draft],
    ["最终报告", run.outputs.final_report],
  ];
  outputs.replaceChildren(...outputEntries.map(([label, value]) => createOutput(label, value)));
}

function markStaticControls() {
  const selectedRunner = currentData
    ? currentData.runners.find((runner) => runner.id === selectedRunnerId)
    : null;
  const startButton = document.getElementById("start-run-button");
  const canStart = Boolean(backendOnline && selectedRunner && isRunnerAvailable(selectedRunner));

  startButton.disabled = !canStart;
  startButton.setAttribute("aria-disabled", String(!canStart));
  startButton.title = canStart
    ? `通过本地后端启动 ${selectedRunnerId}`
    : "需要本地后端在线，并选择可用执行器。";
}

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

function wireTargetConfigControls() {
  const detectButton = document.getElementById("detect-devices-button");
  const foregroundButton = document.getElementById("use-foreground-app-button");
  const validateButton = document.getElementById("validate-target-button");
  const deviceSelect = document.getElementById("device-select");

  if (detectButton) {
    detectButton.addEventListener("click", detectDevices);
  }
  if (foregroundButton) {
    foregroundButton.addEventListener("click", useForegroundApp);
  }
  if (validateButton) {
    validateButton.addEventListener("click", validateTargetConfig);
  }
  if (deviceSelect) {
    deviceSelect.addEventListener("change", () => {
      const selected = selectedDeviceFromSelect();
      if (selected) {
        selectDevice(selected, {loadForeground: true});
      }
    });
  }
  updateTargetConfigControls();
}

function autoDetectTargetConfig() {
  if (!backendOnline) {
    return Promise.resolve([]);
  }
  return detectDevices({automatic: true});
}

function detectDevices(options = {}) {
  const automatic = Boolean(options.automatic);
  setTargetConfigStatus(automatic ? "正在自动检测设备..." : "正在检测设备...", "info");
  return fetch(`${API_BASE}/api/devices`)
    .then((response) => readJsonOrThrow(response, "检测设备失败"))
    .then((data) => {
      const sortedDevices = sortDevicesById(data.devices || []);
      renderDeviceSelect(sortedDevices);
      const devices = sortedDevices;
      if (devices.length === 0) {
        setTargetConfigStatus("未检测到在线设备，请手动填写设备地址", "warning");
        return devices;
      }

      if (devices.length > 1) {
        setTargetConfigStatus(`检测到 ${devices.length} 个设备，默认选择 ${devices[0].id}。`, "info");
      }
      return selectDevice(sortedDevices[0], {loadForeground: true}).then(() => devices);
    })
    .catch((error) => {
      setTargetConfigStatus(error.message, "error");
      renderDeviceSelect([]);
      return [];
    });
}

function sortDevicesById(devices) {
  return Array.from(devices || [])
    .map((device) => ({...device, id: device.id || ""}))
    .sort((device, otherDevice) => device.id.localeCompare(otherDevice.id));
}

function renderDeviceSelect(devices) {
  const deviceSelect = document.getElementById("device-select");
  if (!deviceSelect) {
    return;
  }

  deviceSelect.replaceChildren(
    ...devices.map((device) => {
      const option = document.createElement("option");
      option.value = device.id || "";
      option.textContent = device.label || device.id || device.uri || "unknown";
      option.dataset.uri = device.uri || "";
      option.dataset.label = device.label || "";
      return option;
    })
  );
  deviceSelect.disabled = devices.length <= 1;
  deviceSelect.hidden = devices.length === 0;
  if (devices.length > 0) {
    deviceSelect.value = devices[0].id || "";
  }
}

function selectedDeviceFromSelect() {
  const deviceSelect = document.getElementById("device-select");
  if (!deviceSelect || !deviceSelect.value) {
    return null;
  }
  const option = deviceSelect.selectedOptions[0];
  return {
    id: deviceSelect.value,
    uri: option ? option.dataset.uri : "",
    label: option ? option.dataset.label : "",
  };
}

function selectDevice(device, options = {}) {
  if (!device || !device.id) {
    return Promise.resolve(null);
  }
  const deviceSelect = document.getElementById("device-select");
  if (deviceSelect) {
    deviceSelect.value = device.id;
  }
  setInputValue("device-uri-input", device.uri || `Android:///${device.id}`);
  setTargetConfigStatus(`已选择设备 ${device.id}，正在读取前台应用...`, "info");
  if (options.loadForeground) {
    return useForegroundApp();
  }
  setTargetConfigStatus(`已选择设备 ${device.id}`, "ok");
  return Promise.resolve(device);
}

function useForegroundApp(options = {}) {
  const deviceId = readDeviceIdFromInput();
  if (!deviceId) {
    setTargetConfigStatus("设备地址格式不正确", "error");
    return Promise.resolve(null);
  }

  setTargetConfigStatus("正在读取前台应用...", "info");
  return fetch(`${API_BASE}/api/devices/${encodeURIComponent(deviceId)}/foreground`)
    .then((response) => readJsonOrThrow(response, "读取前台应用失败"))
    .then((data) => {
      handleForegroundAppDetection(data, options);
      return data;
    })
    .catch((error) => {
      setTargetConfigStatus(error.message, "error");
      return null;
    });
}

function handleForegroundAppDetection(data, options = {}) {
  const detectedPackage = data.package_name || "";
  const currentPackage = readInputValue("package-name-input", "");
  const shouldOverwrite = options.overwritePackage !== false;
  const foregroundContext = formatForegroundAppContext(data);

  if (!detectedPackage) {
    setTargetConfigStatus("未识别到前台应用包名", "warning");
    return;
  }

  if (isSystemPackageName(detectedPackage)) {
    setTargetConfigStatus(`检测到系统前台应用，请手动确认包名。${foregroundContext}`, "warning");
    return;
  }

  if (currentPackage && currentPackage !== detectedPackage && !shouldOverwrite) {
    setTargetConfigStatus(
      `当前前台应用与包名不一致，请确认后再开始。${foregroundContext}`,
      "warning"
    );
    return;
  }

  if (!currentPackage || currentPackage !== detectedPackage) {
    setInputValue("package-name-input", detectedPackage);
  }
  setTargetConfigStatus(`当前前台应用 ${foregroundContext}`, "ok");
}

function isSystemPackageName(packageName) {
  return (
    packageName === "android" ||
    packageName === "com.android.systemui" ||
    packageName.startsWith("com.google.android.") ||
    packageName.startsWith("com.miui.")
  );
}

function formatForegroundAppContext(data) {
  const packageName = data.package_name || "";
  const activity = data.activity || "";
  return activity ? `${packageName}/${activity}` : packageName;
}

function validateTargetConfig() {
  const deviceId = readDeviceIdFromInput();
  const packageName = readInputValue("package-name-input", "");
  if (!deviceId) {
    setTargetConfigStatus("设备地址格式不正确", "error");
    return Promise.resolve(null);
  }
  if (!packageName) {
    setTargetConfigStatus("应用包名不能为空", "error");
    return Promise.resolve(null);
  }

  setTargetConfigStatus("正在校验配置...", "info");
  return fetch(
    `${API_BASE}/api/devices/${encodeURIComponent(deviceId)}/packages/${encodeURIComponent(packageName)}/validation`
  )
    .then((response) => readJsonOrThrow(response, "校验配置失败"))
    .then((data) => {
      if (data.installed && data.launchable) {
        setTargetConfigStatus(
          `包名可启动：${data.package_name}/${data.activity || ""}`,
          "ok"
        );
      } else {
        setTargetConfigStatus((data.warnings || ["配置需要确认"]).join("；"), "warning");
      }
      return data;
    })
    .catch((error) => {
      setTargetConfigStatus(error.message, "error");
      return null;
    });
}

function readDeviceIdFromInput() {
  const deviceUri = readInputValue("device-uri-input", "");
  const match = deviceUri.match(/^Android:\/\/(?:[^/?#]+)?\/([^/?#]+)(?:[?#].*)?$/);
  if (!match) {
    return "";
  }

  try {
    return decodeURIComponent(match[1]);
  } catch (error) {
    return match[1];
  }
}

function setTargetConfigStatus(message, tone) {
  const status = document.getElementById("target-config-status");
  if (!status) {
    return;
  }
  status.textContent = message || "未检测设备";
  status.className = "target-status";
  if (tone) {
    status.classList.add(`is-${tone}`);
  }
}

function updateTargetConfigControls() {
  ["detect-devices-button", "use-foreground-app-button", "validate-target-button", "device-select"].forEach((id) => {
    const button = document.getElementById(id);
    if (button) {
      button.disabled = !backendOnline;
    }
  });
}

function wireStartButton() {
  const button = document.getElementById("start-run-button");
  button.addEventListener("click", () => {
    startRun();
  });
}

function startRun() {
  const button = document.getElementById("start-run-button");
  if (!backendOnline || !currentData || button.disabled) {
    return;
  }

  button.disabled = true;
  clearPollTimer();
  setRunState("排队中", `正在通过本地后端启动 ${selectedRunnerId}`);
  renderEvents([]);

  const payload = buildRunPayload(currentData.config);
  fetch(`${API_BASE}/api/runs`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  })
    .then((response) => readJsonOrThrow(response, "启动失败"))
    .then((run) => {
      updateOutputsFromRun(run);
      return pollRun(run.id);
    })
    .catch((error) => {
      setRunState("运行失败", error.message);
      markStaticControls();
    });
}

function loadSample(sampleUrl) {
  return fetch(sampleUrl).then((response) => {
    if (!response.ok) {
      throw new Error(`无法读取样例数据: ${response.status}`);
    }
    return response.json();
  });
}

function detectBackend() {
  return fetch(`${API_BASE}/api/health`)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`后端不可用: ${response.status}`);
      }
      return response.json();
    })
    .then((health) => {
      backendOnline = health.status === "ok";
      return health;
    })
    .catch(() => {
      backendOnline = false;
      return null;
    });
}

function detectBackendConfig() {
  return fetch(`${API_BASE}/api/config`)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`配置不可用: ${response.status}`);
      }
      return response.json();
    })
    .catch(() => null);
}

function pollRun(runId) {
  return fetch(`${API_BASE}/api/runs/${encodeURIComponent(runId)}`)
    .then((response) => readJsonOrThrow(response, "读取运行状态失败"))
    .then((run) => {
      updateOutputsFromRun(run);
      setRunState(runStatusLabel(run.status), run.error || run.session_dir || run.id);
      loadRunEvents(runId).then((events) => {
        setRunState(describeRunState(run, events), run.error || run.session_dir || run.id);
      });

      if (run.status === "queued" || run.status === "running") {
        pollTimer = window.setTimeout(() => pollRun(runId), 1000);
        return run;
      }

      const button = document.getElementById("start-run-button");
      button.disabled = !backendOnline;
      markStaticControls();

      if (run.status === "completed") {
        loadSessions();
        if (run.session_dir) {
          loadReport(run.id);
        }
      }

      return run;
    })
    .catch((error) => {
      setRunState("运行失败", error.message);
      markStaticControls();
    });
}

function loadRunEvents(runId) {
  return fetch(`${API_BASE}/api/runs/${encodeURIComponent(runId)}/events`)
    .then((response) => readJsonOrThrow(response, "读取事件失败"))
    .then((data) => {
      renderEvents(data.events || []);
      return data.events || [];
    })
    .catch((error) => {
      renderEvents([{type: "event_error", error: error.message}]);
      return [];
    });
}

function loadSessions() {
  return fetch(`${API_BASE}/api/sessions`)
    .then((response) => readJsonOrThrow(response, "读取会话失败"))
    .then((data) => {
      renderSessions(data.sessions || []);
      return data.sessions || [];
    })
    .catch((error) => {
      renderSessions([{id: "error", session_dir: error.message, has_final_report: false}]);
      return [];
    });
}

function loadReport(sessionId) {
  return fetch(`${API_BASE}/api/sessions/${encodeURIComponent(sessionId)}/report`)
    .then((response) => readJsonOrThrow(response, "读取报告失败"))
    .then((report) => {
      renderReportPreview(report.final_report || "暂无最终报告。");
      renderActionReasoning(parseJsonLines(report.actions || ""));
      loadProfileSummary();
      return report;
    })
    .catch((error) => {
      renderReportPreview(error.message);
      return null;
    });
}

function loadProfileSummary() {
  if (!backendOnline || !currentData) {
    renderProfileSummary(currentData && currentData.profile ? currentData.profile : {exists: false});
    return Promise.resolve(null);
  }

  const packageName = readInputValue("package-name-input", currentData.config.package_name || "");
  if (!packageName) {
    renderProfileSummary({exists: false});
    return Promise.resolve(null);
  }

  return fetch(`${API_BASE}/api/profiles/${encodeURIComponent(packageName)}`)
    .then((response) => readJsonOrThrow(response, "读取画像失败"))
    .then((profile) => {
      renderProfileSummary(profile);
      return profile;
    })
    .catch(() => {
      renderProfileSummary({exists: false});
      return null;
    });
}

function updateBackendStatus() {
  const status = document.getElementById("backend-status");
  status.classList.toggle("is-online", backendOnline);
  status.classList.toggle("is-offline", !backendOnline);
  status.textContent = backendOnline ? "后端在线" : "静态预览";
  status.title = backendOnline
    ? "已连接本地 Python 后端。"
    : "未检测到本地 Python 后端，当前使用静态样例数据。";
  updateTargetConfigControls();
  markStaticControls();
  if (backendOnline) {
    loadSessions();
    loadProfileSummary();
    autoDetectTargetConfig();
  }
}

function isRunnerAvailable(runner) {
  if (typeof runner.available === "boolean") {
    return runner.available;
  }
  return ["available", "ready", "可用", "可接入"].includes(runner.status);
}

function runnerStatusLabel(runner, available) {
  if (runner.status && !["available", "unavailable", "ready"].includes(runner.status)) {
    return runner.status;
  }
  return available ? "可用" : "不可用";
}

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
    allowed_actions: getEffectiveAllowedActions(config),
    recent_steps: config.recent_steps,
    consecutive_failure_limit: config.consecutive_failure_limit,
    enable_unsafe_actions: getUnsafeActionsEnabled(),
  };
}

function readInputValue(id, fallback) {
  const field = document.getElementById(id);
  const value = field ? field.value.trim() : "";
  return value || fallback;
}

function readPositiveInt(id, fallback) {
  const value = Number.parseInt(readInputValue(id, String(fallback)), 10);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function setInputValue(id, value) {
  const field = document.getElementById(id);
  if (field) {
    field.value = value;
  }
}

function readJsonOrThrow(response, prefix) {
  return response.json().then((data) => {
    if (!response.ok) {
      throw new Error(data.error || `${prefix}: ${response.status}`);
    }
    return data;
  });
}

function clearPollTimer() {
  if (pollTimer) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function setRunState(label, title) {
  const state = document.getElementById("run-state");
  state.textContent = label;
  state.title = title || "";
}

function updateOutputsFromRun(run) {
  const outputs = document.getElementById("output-list");
  const outputEntries = [
    ["运行 ID", run.id],
    ["执行器", run.runner || selectedRunnerId],
    ["运行状态", run.status],
    ["会话目录", run.session_dir || "-"],
  ];
  outputs.replaceChildren(...outputEntries.map(([label, value]) => createOutput(label, value)));
}

function renderEvents(events) {
  const log = document.getElementById("event-log");
  if (!log) {
    return;
  }

  if (events.length === 0) {
    log.replaceChildren(createEmptyBlock("暂无运行事件"));
    return;
  }

  log.replaceChildren(
    ...Array.from(events).reverse().map((event) => {
      const item = document.createElement("div");
      item.className = "event-item";

      const type = document.createElement("strong");
      type.textContent = eventTypeLabel(event.type);
      const detail = document.createElement("span");
      detail.textContent = formatEventDetail(event);

      item.append(type, detail);
      return item;
    })
  );
}

function formatEventDetail(event) {
  if (event.type === "runner_event") {
    return formatRunnerEventDetail(event);
  }
  if (event.message) {
    return event.message;
  }
  if (event.step && event.max_steps) {
    const action = event.action_type ? `：${event.action_type}` : "";
    const result = event.result ? `，${event.result}` : "";
    return `第 ${event.step} 步 / 共 ${event.max_steps} 步${action}${result}`;
  }
  return event.error || event.session_dir || event.created_at || "";
}

function formatRunnerEventDetail(event) {
  const rawItem = event.raw && event.raw.item ? event.raw.item : null;
  if (!rawItem) {
    return event.message || event.created_at || "";
  }
  if (rawItem.text) {
    return rawItem.text;
  }
  if (rawItem.type === "command_execution") {
    const status = rawItem.status || "";
    const output = rawItem.aggregated_output ? compactText(rawItem.aggregated_output, 140) : "";
    return [event.message, status, output].filter(Boolean).join(" · ");
  }
  return [event.message, rawItem.type, rawItem.status].filter(Boolean).join(" · ");
}

function describeRunState(run, events) {
  if (!run || run.status !== "running") {
    return runStatusLabel(run && run.status);
  }

  const latest = latestMeaningfulEvent(events);
  if (!latest) {
    return runStatusLabel(run.status);
  }
  if (latest.type === "run_started") {
    return "运行中";
  }
  if (latest.type === "runner_event") {
    const rawItem = latest.raw && latest.raw.item ? latest.raw.item : null;
    if (rawItem && rawItem.type === "agent_message") {
      return compactText(rawItem.text || "执行器正在分析", 28);
    }
    if (rawItem && rawItem.type === "command_execution") {
      return rawItem.status === "in_progress" ? "执行命令中" : "命令已返回";
    }
  }
  return eventTypeLabel(latest.type);
}

function latestMeaningfulEvent(events) {
  return Array.from(events || [])
    .reverse()
    .find((event) => event.type !== "run_queued" && event.type !== "session_prepared");
}

function compactText(value, maxLength) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1)}…`;
}

function renderSessions(sessions) {
  const list = document.getElementById("session-list");
  if (!list) {
    return;
  }

  if (sessions.length === 0) {
    list.replaceChildren(createEmptyBlock("暂无历史会话"));
    return;
  }

  list.replaceChildren(
    ...sessions.map((session) => {
      const button = document.createElement("button");
      button.className = "session-item";
      button.type = "button";
      button.disabled = !session.has_final_report;
      button.textContent = session.id;
      button.title = session.session_dir || "";
      button.addEventListener("click", () => loadReport(session.id));
      return button;
    })
  );
}

function renderReportPreview(markdown) {
  const report = document.getElementById("report-preview");
  const lines = String(markdown)
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 12);

  report.replaceChildren(
    ...(lines.length > 0 ? lines : ["暂无报告内容"]).map((line) => {
      const paragraph = document.createElement("p");
      paragraph.textContent = line;
      return paragraph;
    })
  );
}

function renderProfileSummary(profile) {
  const summary = profile || {};
  if (!summary.exists) {
    setPanelRows("profile-current-state", [createEmptyBlock("Profile not learned yet")]);
    setPanelRows("profile-goals", [createEmptyBlock("暂无目标进度")]);
    setPanelRows("profile-transitions", [createEmptyBlock("暂无状态迁移")]);
    setPanelRows("profile-affordances", [createEmptyBlock("暂无可交互区域")]);
    setPanelRows("profile-skills", [createEmptyBlock("暂无技能")]);
    setPanelRows("profile-safety", [createEmptyBlock("暂无安全干预")]);
    return;
  }

  renderCurrentState(summary.current_state || {});
  renderGoals(summary.goals || {});
  renderTransitions(summary.transitions || []);
  renderAffordances(summary.affordances || []);
  renderSkills(summary.skills || []);
  renderSafety(summary.safety || {});
}

function renderCurrentState(state) {
  const rows = state.state_id
    ? [
        createMetricRow("State", state.state_id),
        createMetricRow("Label", state.label || "-"),
        createMetricRow("Visits", state.visit_count || 0),
        createMetricRow("Last step", state.last_seen_step || "-"),
        createMetricRow("Summary", state.summary || "-"),
      ]
    : [createEmptyBlock("Profile not learned yet")];
  setPanelRows("profile-current-state", rows);
}

function renderGoals(goals) {
  const rows = [
    createMetricRow("Main", goals.main_goal || "-"),
    createMetricRow("Active", goals.active_subgoal || "-"),
  ];
  if ((goals.completed_subgoals || []).length > 0) {
    rows.push(createMetricRow("Completed", goals.completed_subgoals.join(", ")));
  }
  if ((goals.blocked_subgoals || []).length > 0) {
    rows.push(
      createMetricRow(
        "Blocked",
        goals.blocked_subgoals.map((item) => `${item.subgoal}: ${item.reason}`).join("; ")
      )
    );
  }
  setPanelRows("profile-goals", rows);
}

function renderTransitions(transitions) {
  setPanelRows(
    "profile-transitions",
    transitions.length
      ? transitions.slice(0, 5).map((item) =>
          createMetricRow(
            `#${item.step || "-"}`,
            `${item.from_state_id || "start"} -> ${item.to_state_id || "-"} (${item.classification || "-"})`
          )
        )
      : [createEmptyBlock("暂无状态迁移")]
  );
}

function renderAffordances(affordances) {
  setPanelRows(
    "profile-affordances",
    affordances.length
      ? affordances.slice(0, 6).map((item) =>
          createMetricRow(
            item.label || item.id || "region",
            `${formatConfidence(item.confidence)} · ${item.last_result || item.status || "candidate"}`
          )
        )
      : [createEmptyBlock("暂无可交互区域")]
  );
}

function renderSkills(skills) {
  setPanelRows(
    "profile-skills",
    skills.length
      ? skills.slice(0, 6).map((item) =>
          createMetricRow(
            item.name || "skill",
            `${formatConfidence(item.confidence)} · ${item.success_count || 0}/${item.run_count || 0}`
          )
        )
      : [createEmptyBlock("暂无技能")]
  );
}

function renderSafety(safety) {
  const interventions = safety.interventions || [];
  const sensitiveStates = safety.sensitive_states || [];
  const rows = [];
  if (sensitiveStates.length > 0) {
    rows.push(createMetricRow("Sensitive", sensitiveStates.join(", ")));
  }
  interventions.slice(-5).forEach((item) => {
    rows.push(createMetricRow(`#${item.step || "-"}`, item.reason || item.state_id || "-"));
  });
  setPanelRows("profile-safety", rows.length ? rows : [createEmptyBlock("暂无安全干预")]);
}

function renderActionReasoning(actions) {
  const rows = (actions || [])
    .slice(-5)
    .reverse()
    .map((item) => {
      const action = item.action && item.action.type ? item.action.type : "-";
      const source = item.action_source || "llm";
      const reason = item.reason || item.feedback_result || "-";
      const subgoal = item.active_subgoal ? ` · ${item.active_subgoal}` : "";
      return createMetricRow(`#${item.step || "-"} ${action}`, `${source}${subgoal} · ${reason}`);
    });
  setPanelRows("action-reasoning", rows.length ? rows : [createEmptyBlock("暂无动作依据")]);
}

function parseJsonLines(text) {
  return String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch (error) {
        return null;
      }
    })
    .filter(Boolean);
}

function setPanelRows(id, rows) {
  const panel = document.getElementById(id);
  if (panel) {
    panel.replaceChildren(...rows);
  }
}

function createMetricRow(label, value) {
  const row = document.createElement("div");
  row.className = "metric-row";
  const name = document.createElement("span");
  name.textContent = label;
  const content = document.createElement("strong");
  content.textContent = value;
  row.append(name, content);
  return row;
}

function formatConfidence(value) {
  const numeric = Number.parseFloat(value);
  if (!Number.isFinite(numeric)) {
    return "-";
  }
  return `${Math.round(numeric * 100)}%`;
}

function createEmptyBlock(text) {
  const item = document.createElement("p");
  item.className = "empty-block";
  item.textContent = text;
  return item;
}

function runStatusLabel(status) {
  const labels = {
    queued: "排队中",
    running: "运行中",
    completed: "运行完成",
    failed: "运行失败",
  };
  return labels[status] || status || "未知状态";
}

function eventTypeLabel(type) {
  const labels = {
    run_queued: "已排队",
    run_started: "已启动",
    session_prepared: "会话已准备",
    session_started: "会话已创建",
    step_screenshot: "第 N 步截图",
    step_action: "第 N 步动作",
    step_failed: "第 N 步失败",
    run_progress: "运行进度",
    run_report_written: "报告已写入",
    run_completed: "已完成",
    run_failed: "已失败",
    runner_process_started: "进程启动",
    runner_event: "执行器事件",
    runner_parse_error: "事件解析错误",
    runner_stderr: "执行器输出",
    runner_timeout: "执行超时",
    runner_process_failed: "进程失败",
    event_error: "事件错误",
  };
  return labels[type] || type;
}

function createOutput(label, value) {
  const item = document.createElement("div");
  item.className = "output-item";

  const name = document.createElement("span");
  name.textContent = label;
  const content = document.createElement("strong");
  content.textContent = value;

  item.append(name, content);
  return item;
}

function renderList(id, values, emptyText) {
  const list = document.getElementById(id);
  const items = values.length > 0 ? values : [emptyText];
  list.replaceChildren(...items.map(createListItem));
}

function createListItem(text) {
  const item = document.createElement("li");
  item.textContent = text;
  return item;
}

function renderLoadError(error) {
  const state = document.getElementById("run-state");
  state.textContent = "加载失败";
  state.title = error.message;

  const timeline = document.getElementById("timeline-list");
  const message = document.createElement("p");
  message.className = "safety-copy";
  message.textContent = error.message;
  timeline.replaceChildren(message);
}

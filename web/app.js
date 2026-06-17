const STATIC_ONLY = false;
const API_BASE = "";
let currentData = null;
let backendOnline = false;

const ACTION_LABELS = {
  screenshot: "截图",
  wait: "等待",
  back: "返回",
  tap: "点击",
  swipe: "滑动",
  error: "错误",
};

const FIELD_LABELS = [
  ["device_uri", "设备地址"],
  ["package_name", "应用包名"],
  ["model", "模型"],
  ["max_steps", "最大步数"],
  ["recent_steps", "上下文步数"],
  ["consecutive_failure_limit", "失败阈值"],
  ["output_root", "输出目录"],
];

document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("app");
  const sampleUrl = root.dataset.sampleUrl;

  wireStartButton();
  Promise.all([loadSample(sampleUrl), detectBackend()])
    .then(([sample]) => {
      currentData = sample;
      renderConsole(sample);
      updateBackendStatus();
    })
    .catch(renderLoadError);
});

function renderConsole(data) {
  renderRunState(data.run);
  renderConfig(data.config);
  renderMission(data.config.mission);
  renderRunners(data.runners);
  renderAllowedActions(data.config.allowed_actions);
  renderTimeline(data.run.steps);
  renderRisks(data.run.steps);
  renderReport(data.run);
  markStaticControls();
}

function renderRunState(run) {
  const state = document.getElementById("run-state");
  state.textContent = run.status_label || run.status || "静态预览";
  state.title = run.summary || "";
}

function renderConfig(config) {
  const grid = document.getElementById("config-grid");
  grid.replaceChildren(
    ...FIELD_LABELS.map(([key, label]) => createField(label, String(config[key] ?? "-"))),
    createField("任务类型", missionTypeLabel(config.mission.type))
  );
}

function renderMission(mission) {
  document.getElementById("mission-goal").value = mission.goal;
  renderList("mission-targets", mission.targets, "未设置目标对象");
  renderList("mission-success", mission.success_criteria, "未设置成功标准");
}

function renderRunners(runners) {
  const grid = document.getElementById("runner-grid");
  grid.replaceChildren(
    ...runners.map((runner) => {
      const card = document.createElement("article");
      card.className = "runner-card";

      const header = document.createElement("header");
      const name = document.createElement("strong");
      name.textContent = runner.name;
      const status = document.createElement("span");
      status.className = runner.status === "计划接入" ? "runner-status is-planned" : "runner-status";
      status.textContent = runner.status;
      header.append(name, status);

      const description = document.createElement("p");
      description.textContent = runner.description;

      card.append(header, description);
      return card;
    })
  );
}

function renderAllowedActions(actions) {
  const row = document.getElementById("allowed-actions");
  row.replaceChildren(
    ...actions.map((action) => {
      const chip = document.createElement("span");
      chip.className = ["tap", "swipe"].includes(action) ? "action-chip is-risky" : "action-chip";
      chip.textContent = ACTION_LABELS[action] || action;
      chip.title = ["tap", "swipe"].includes(action) ? "后端阶段需要显式启用" : "默认安全动作";
      return chip;
    })
  );
}

function renderTimeline(steps) {
  const timeline = document.getElementById("timeline");
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
    riskList.replaceChildren(createListItem("当前样例没有风险记录。"));
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
  document.querySelectorAll("button").forEach((button) => {
    if (button.id === "start-run-button") {
      button.disabled = !backendOnline;
      button.setAttribute("aria-disabled", String(!backendOnline));
      button.title = backendOnline
        ? "通过本地后端启动 game_reverse runner。"
        : "未检测到本地后端；运行 python -m game_reverse.web_server 后启用。";
      return;
    }

    button.disabled = true;
    button.setAttribute("aria-disabled", "true");
    button.title = "该控件将在后端功能扩展后启用。";
  });
}

function wireStartButton() {
  const button = document.getElementById("start-run-button");
  button.addEventListener("click", () => {
    if (!backendOnline || !currentData) {
      return;
    }

    button.disabled = true;
    setRunState("运行中", "正在通过本地后端启动 game_reverse runner。");
    const payload = buildRunPayload(currentData.config);
    fetch(`${API_BASE}/api/runs`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    })
      .then((response) => {
        if (!response.ok) {
          return response.json().then((error) => {
            throw new Error(error.error || `启动失败: ${response.status}`);
          });
        }
        return response.json();
      })
      .then((run) => {
        setRunState(run.status === "completed" ? "运行完成" : run.status, run.session_dir || "");
        updateOutputsFromRun(run);
      })
      .catch((error) => {
        setRunState("运行失败", error.message);
      })
      .finally(() => {
        button.disabled = false;
      });
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

function updateBackendStatus() {
  const status = document.getElementById("backend-status");
  status.classList.toggle("is-online", backendOnline);
  status.classList.toggle("is-offline", !backendOnline);
  status.textContent = backendOnline ? "后端在线" : "静态预览";
  status.title = backendOnline
    ? "已连接本地 Python 后端。"
    : "未检测到本地 Python 后端，当前使用静态样例数据。";
  markStaticControls();
}

function buildRunPayload(config) {
  return {
    runner: "game_reverse",
    device_uri: config.device_uri,
    package_name: config.package_name,
    max_steps: config.max_steps,
    mission: config.mission,
    model: config.model,
    allowed_actions: config.allowed_actions,
    recent_steps: config.recent_steps,
    consecutive_failure_limit: config.consecutive_failure_limit,
    enable_unsafe_actions: config.allowed_actions.some((action) => ["tap", "swipe"].includes(action)),
  };
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
    ["运行状态", run.status],
    ["会话目录", run.session_dir || "-"],
  ];
  outputs.replaceChildren(...outputEntries.map(([label, value]) => createOutput(label, value)));
}

function createField(label, value) {
  const field = document.createElement("div");
  field.className = "field";

  const name = document.createElement("span");
  name.textContent = label;
  const content = document.createElement("strong");
  content.textContent = value;

  field.append(name, content);
  return field;
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

function missionTypeLabel(type) {
  const labels = {
    free_explore: "自由探索",
    feature_test: "功能测试",
    level_design_reverse: "关卡逆向",
  };
  return labels[type] || type;
}

function renderLoadError(error) {
  const state = document.getElementById("run-state");
  state.textContent = "加载失败";
  state.title = error.message;

  const timeline = document.getElementById("timeline");
  const message = document.createElement("p");
  message.className = "safety-copy";
  message.textContent = error.message;
  timeline.replaceChildren(message);
}

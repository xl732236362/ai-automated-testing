# App/Game Explorer Automation Design

## 背景

目标是在当前 Airtest 项目基础上，设计一个用于 Android 模拟器的通用 App/Game 自动探索闭环。系统通过 Claude API 读取截图并决定下一步安全动作，由 Airtest 执行截图、等待、点击、滑动和返回键操作，并在探索过程中持续维护与本次任务相关的草稿和报告。

本设计面向授权测试、内部 QA、公开体验分析或合规的第三方 APK 黑盒分析。它不读取 APK 内部数据，不绕过反作弊，不执行购买、充值、账号输入、系统设置变更或任意 ADB shell 操作。

## 已确认约束

- 被测环境：Android 模拟器。
- 操作方式：Claude API 自动闭环。
- 执行动作：Airtest 安全动作集。
- 产品定位：通用 App/Game 探索器，而不是只服务游戏策划案逆推。
- 任务表达：通过 `mission` 配置定义本次探索目标。
- 输出目标：按 `mission.type` 生成不同类型草稿和阶段报告。
- 停止条件：固定步数。
- 第三方 APK：可通过 ADB 连接模拟器并黑盒操作；ADB 连接的是设备/模拟器，不是 APK 本身。

## 总体架构

```text
启动连接 Android 模拟器
  ↓
读取 mission：本次要测试/探索/逆推什么
  ↓
截图保存
  ↓
把截图 + mission + 历史摘要 + 当前草稿发给 Claude API
  ↓
Claude 输出结构化 JSON：
  - 当前界面判断
  - 下一步动作
  - 动作理由
  - 新发现
  - 截图证据价值
  - 当前不确定点
  ↓
本地校验动作是否属于安全动作集
  ↓
Airtest 执行：tap / swipe / wait / back / screenshot
  ↓
写入 action log、截图索引、mission 草稿
  ↓
达到固定步数后停止并按 mission 生成阶段报告
```

第一版不追求“玩得很好”或“覆盖所有功能”，而是追求稳定探索、保留证据、逐步形成与任务目标对应的报告。

## Mission 驱动设计

通用探索器的关键是把“探索目标”从代码里抽出来，放入配置文件：

```json
{
  "device_uri": "Android:///",
  "package_name": "com.example.game",
  "max_steps": 50,
  "mission": {
    "type": "level_design_reverse",
    "goal": "探索关卡设计并保存截图证据",
    "targets": ["关卡入口", "关卡列表", "关卡详情", "奖励", "解锁条件"]
  },
  "allowed_actions": ["screenshot", "wait", "back", "tap", "swipe"]
}
```

第一版支持 3 种 `mission.type`：

### `free_explore`

自由探索 App/Game，输出功能地图、界面状态、可疑入口和下一轮探索建议。

适合：刚拿到一个 APK，不知道里面有什么。

### `feature_test`

围绕指定功能入口做覆盖测试，保存关键截图，记录是否进入目标功能、是否卡住、是否出现异常页面。

适合：测试某个 App 的首页、任务、背包、商店、设置等功能是否可进入。

示例：

```json
{
  "type": "feature_test",
  "goal": "测试首页、任务、背包、商店四个入口是否可进入，并保存截图",
  "targets": ["首页", "任务", "背包", "商店"],
  "success_criteria": [
    "每个目标功能至少进入一次",
    "每个目标功能保存一张截图",
    "遇到登录、支付、实名页面停止并标记人工处理"
  ]
}
```

### `level_design_reverse`

围绕游戏关卡设计做逆向分析，保存关卡入口、关卡列表、关卡详情、结算、奖励、解锁条件等截图证据。

适合：逆推出某个游戏的关卡结构和设计规律。

示例：

```json
{
  "type": "level_design_reverse",
  "goal": "探索关卡入口、关卡列表、解锁条件、奖励、难度变化，并截图保存",
  "targets": ["关卡入口", "关卡列表", "关卡详情", "胜利结算", "失败结算"],
  "success_criteria": [
    "保存关卡列表截图",
    "保存至少 3 个关卡详情截图",
    "记录关卡名称、消耗、推荐战力、奖励、解锁条件",
    "输出关卡设计规律推测"
  ]
}
```

## 推荐实现路线

采用单进程 Python 编排器起步，但按模块边界组织代码。这样能快速跑通第一版，同时保留后续拆分为服务化架构的空间。

不采用第一版服务化架构，因为 Airtest 执行服务、Claude 策略服务和通信协议会显著增加调试成本。也不采用纯脚本随机探索，因为其噪声大，容易卡死，且不利于按任务目标输出高质量报告。

## 目录结构

```text
game_reverse/
  run_loop.py
  config.example.json
  mission.py
  prompts/
    decision_system.md
    report_templates/
      free_explore.md
      feature_test.md
      level_design_reverse.md
  outputs/
    sessions/
      <timestamp>/
        screens/
        actions.jsonl
        observations.jsonl
        mission_draft.md
        final_report.md
```

说明：第一版代码目录仍可叫 `game_reverse/`，避免在本轮设计中额外讨论命名迁移；但内部语义是 mission-driven App/Game explorer。

## 组件设计

### `run_loop.py`

主入口，负责读取配置、连接 Android 模拟器、初始化 session 目录、控制固定步数循环，并串联截图、LLM 决策、动作执行、日志写入和报告更新。

### `mission.py`

负责解析和校验 `mission`：

- `type`
- `goal`
- `targets`
- `success_criteria`

同时根据 `mission.type` 选择报告模板和提示词重点。

### `airtest_executor`

封装 Airtest 侧安全动作：

- `screenshot()` 保存当前画面。
- `tap(x, y)` 点击坐标。
- `swipe(x1, y1, x2, y2, duration)` 滑动。
- `back()` 返回键。
- `wait(seconds)` 等待。

所有动作必须经过白名单校验。第一版不暴露任意 shell、安装、卸载、清数据、输入文本或系统设置操作。

### `llm_decider`

调用 Claude API vision，输入当前截图、mission、最近若干步动作摘要和当前 `mission_draft.md`。输出结构化 JSON，包含界面总结、状态、下一步动作、动作理由、新发现、风险和截图价值。

示例输出：

```json
{
  "screen_summary": "主界面，能看到开始、角色、商店、任务入口",
  "state": "main_menu",
  "action": {
    "type": "tap",
    "x": 820,
    "y": 1610,
    "duration": 0
  },
  "reason": "点击任务入口以确认 feature_test 目标中的任务功能",
  "new_findings": [
    {
      "category": "任务系统",
      "claim": "主界面存在任务入口，可能有日常或成就系统",
      "evidence": "step_0012.png 中右侧出现任务图标",
      "confidence": "medium"
    }
  ],
  "screenshot_tags": ["主界面", "任务入口"],
  "risks": [
    "图标文字较小，任务入口判断可能需要下一步确认"
  ]
}
```

### `journal`

负责写入可复盘记录：

- `actions.jsonl`：每一步执行动作。
- `observations.jsonl`：Claude 的识别、推测和风险。
- `screens/step_0001.png`：截图证据。
- `mission_draft.md`：持续更新的任务草稿。

### `report_writer`

固定步数结束后按 `mission.type` 整理阶段报告：

- `free_explore`：功能地图、界面状态、入口列表、下一轮探索建议。
- `feature_test`：目标功能覆盖、每个功能截图、失败或卡住步骤、可疑 Bug。
- `level_design_reverse`：关卡入口、关卡列表、关卡详情字段、奖励结构、解锁条件、难度递进推测。

## 数据格式

### 动作日志

```json
{
  "step": 12,
  "screen": "screens/step_0012.png",
  "mission_type": "feature_test",
  "action": {"type": "tap", "x": 820, "y": 1610},
  "reason": "点击任务入口以确认目标功能",
  "result": "executed"
}
```

### 观察日志

```json
{
  "step": 12,
  "mission_type": "feature_test",
  "state": "main_menu",
  "screen_summary": "主界面，能看到开始、角色、商店、任务入口",
  "findings": [
    {
      "category": "任务系统",
      "claim": "主界面存在任务入口",
      "evidence": "screens/step_0012.png",
      "confidence": "medium"
    }
  ],
  "screenshot_tags": ["主界面", "任务入口"],
  "risks": ["需要点击后确认该入口真实功能"]
}
```

## 安全动作集

允许：

- `tap`
- `swipe`
- `wait`
- `back`
- `screenshot`

禁止：

- 购买、充值、支付确认。
- 安装、卸载、清数据。
- 改系统设置。
- 输入账号、密码、手机号、验证码。
- 任意非白名单 ADB shell 操作。

如 Claude 输出非安全动作，本地必须拒绝执行，并将 `blocked_unsafe_action` 写入日志。

## 错误处理

### Claude 输出非法 JSON

记录原始响应，自动重试 1 次。仍失败则执行 `screenshot` 或 `wait`，并标记 `llm_parse_failed`。

### Claude 给出非安全动作

拒绝执行，记录 `blocked_unsafe_action`，反馈给下一轮上下文，执行 `back` 或 `wait` 避免卡死。

### 坐标越界

读取截图宽高并校验坐标范围。越界动作拒绝执行，要求下一轮重新判断。

### Airtest 执行失败

记录异常类型和堆栈摘要。连续失败 3 次停止并生成 `final_report.md`，说明停止原因。

### 敏感界面

识别到登录页、实名认证、支付页、权限授权页、账号密码输入页时，不点击确认、支付或授权按钮。默认执行 `back` 或 `wait`，并在报告中标记需要人工确认。

## 停止条件

第一版使用固定步数：

```json
{
  "max_steps": 50
}
```

建议配置：

- 快速试跑：10 步。
- 正常探索：50 步。
- 深度探索：200 步。

后续版本可加入 mission 完成度停止，例如所有 `targets` 都有截图证据后提前停止。

## 测试策略

### 阶段一：安全冒烟测试

连接 Android 模拟器，只执行截图，让 Claude 识别当前画面，执行 1 个 `wait`，生成最小日志。

### 阶段二：无点击识别测试

手动打开 App/Game 主界面，运行 `max_steps=5`，仅允许 `screenshot / wait / back`，确认识别和日志正常。

### 阶段三：按 mission 测试

分别用 `free_explore`、`feature_test`、`level_design_reverse` 跑小步数任务，确认报告结构随 mission 改变。

### 阶段四：安全动作闭环测试

开启 `tap / swipe`，运行 `max_steps=10`，检查是否误点敏感页面、是否能沉淀 mission 草稿。

## 设计验收标准

第一版完成后应满足：

- 能连接 Android 模拟器并稳定截图。
- 能读取并校验 mission 配置。
- 能调用 Claude API 基于截图和 mission 输出结构化动作。
- 本地能拦截非法 JSON、越界坐标和非安全动作。
- 能执行安全动作并记录每步日志。
- 能持续更新 `mission_draft.md`。
- 固定步数结束后能按 mission 生成 `final_report.md`。

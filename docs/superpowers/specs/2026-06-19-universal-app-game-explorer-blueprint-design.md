# Universal App/Game Explorer Blueprint Design

## Goal

Build a general autonomous exploration framework for apps and games. The system should learn how a target app works by observing screens, trying safe actions, classifying feedback, building a state graph, mining reusable skills, and maintaining goal progress over repeated runs.

The target outcome is not a promise that every game can be fully cleared with one generic prompt. The target is a reusable exploration engine that can create and improve an app-specific knowledge package over time:

- what states/screens exist
- which regions are interactive
- which actions move progress forward
- which actions are unsafe, ineffective, or loop-forming
- which action sequences can be promoted into reusable skills
- which goals and subgoals are currently active

This keeps LLMs in the role where they are strongest: interpreting uncertain visual context, proposing hypotheses, and summarizing learned rules. Deterministic code remains responsible for safety, execution, validation, memory, loop control, and artifact integrity.

## Current Baseline

The current `game_reverse` subsystem already provides the first useful pieces:

- validated low-level actions: `screenshot`, `wait`, `back`, `tap`, `swipe`, `hold_drag_release`
- Airtest execution boundary
- mission config and run loop
- journal artifacts: screenshots, actions, observations, mission draft, final report
- LLM decision parsing and prompt construction
- Web service and local web console for starting and observing runs
- executor adapter layer, including local loop, Codex CLI adapter, and lightweight runner
- initial feedback classification for changed counters, trays, and no visible change
- unsafe action opt-in for real device interaction

This baseline is still primarily a step-by-step explorer. It can observe and act, but it does not yet maintain a durable state graph, automatically discover affordances, mine reusable skills, or manage long-horizon app/game goals.

## Non-Goals

This blueprint does not require:

- bypassing login, payment, permission, real-name verification, ads, anti-cheat, DRM, or account restrictions
- real-time millisecond control for reflex-heavy games
- guaranteed full completion of every game genre
- modifying target apps or injecting code
- cloud orchestration or multi-device farms
- replacing Airtest, ADB, or the existing local web service

The system should prefer safe exit, `back`, or `wait` when a screen is sensitive or ambiguous.

## Design Principles

1. **LLM proposes; code verifies.** LLMs may propose states, actions, skills, and goals, but every executable action passes through deterministic validation.
2. **Learn per app.** Generic logic should produce an app profile instead of pretending every target can be controlled with the same fixed policy.
3. **Prefer high-level skills after discovery.** Once a sequence is validated, the runner should reuse a skill rather than ask the LLM to rediscover coordinates.
4. **Keep memory inspectable.** Learned state graphs, skills, safety rules, and action traces should be JSON/JSONL/Markdown artifacts that humans can audit.
5. **Make failure useful.** Every failed or no-op action should improve future choices by updating feedback, state transitions, and avoid rules.
6. **Treat safety as a runtime invariant.** Unsafe actions require explicit operator opt-in, and sensitive screens remain wait/back-only.
7. **Optimize for staged delivery.** Each phase should provide an independently useful improvement and a concrete verification surface.

## Recommended Architecture

```text
Web Console / CLI
  -> Runner
    -> Observation Pipeline
    -> State Graph
    -> App Profile Memory
    -> Planner
    -> Skill Library
    -> Action Proposer
    -> Safety Validator
    -> Device Executor
    -> Feedback Classifier
    -> Artifact Writer
```

The LLM integration should be split into narrow roles:

```text
llm/state_analyzer.py   # summarize current screen/state
llm/action_proposer.py  # propose candidate actions, not final authority
llm/rule_miner.py       # summarize learned rules from traces
llm/skill_miner.py      # convert successful traces into skill candidates
llm/goal_planner.py     # propose or update subgoals
```

The deterministic core should own:

```text
core/observation.py     # screenshot, OCR, UI hierarchy, visual diff
core/state_graph.py     # states, transitions, loop detection
core/action_space.py    # action candidates and validation
core/feedback.py        # effect classification
core/planner.py         # goal/subgoal lifecycle
core/skill_library.py   # skill storage, replay, confidence
core/memory.py          # app profile loading and persistence
core/runner.py          # main control loop
```

The existing modules can be migrated incrementally rather than moved all at once. For example, `game_reverse.feedback` can grow first, then later become `game_reverse.core.feedback` when the boundary is useful.

## App Profile

Each target app/game should get a profile directory keyed by package name or a configured app id.

```text
game_reverse/profiles/<app_id>/
  profile.json
  state_map.json
  affordances.json
  skills.json
  goals.json
  safety_rules.json
  memory.jsonl
  traces/
    <run_id>.jsonl
```

### profile.json

Stores metadata:

- app id and package name
- first seen / last seen timestamps
- profile schema version
- preferred exploration policy
- operator safety settings

### state_map.json

Stores normalized states and transitions:

- state id
- representative screenshot path or hash
- visual/OCR/UI signatures
- state labels such as `home`, `popup`, `gameplay`, `result`, `failure`, `sensitive`
- outgoing transitions
- known loops and dead ends

### affordances.json

Stores interactable hypotheses and evidence:

- region bounds
- source: OCR, UI hierarchy, visual saliency, LLM proposal, prior action
- supported action types: tap, swipe, hold-drag-release, back, wait
- confidence
- last tested result

### skills.json

Stores reusable skills:

- skill name
- trigger state predicates
- ordered action steps
- success signal
- failure signal
- confidence score
- run count
- last successful trace

### goals.json

Stores app-specific goals and subgoals:

- current main goal
- known goal templates
- phase order
- success/failure criteria
- recovery policy

### safety_rules.json

Stores learned and configured guardrails:

- sensitive text patterns
- forbidden states
- forbidden regions
- action throttles
- max retry counts
- operator opt-in requirements

### memory.jsonl

Append-only event memory for mining:

- observations
- actions
- feedback
- state transitions
- skill attempts
- goal updates
- safety interventions

## Runtime Loop

Each step should follow this control flow:

```text
1. Capture observation
2. Build observation features
3. Match or create state node
4. Load app profile context for this state
5. Update or select current subgoal
6. Choose candidate action source:
   - known skill
   - known affordance
   - systematic exploration
   - LLM proposal
7. Validate action against safety and bounds
8. Execute action
9. Capture post-action observation
10. Classify feedback
11. Update state graph, affordances, skills, goals, and memory
12. Emit web/run events and write artifacts
13. Stop, continue, recover, or ask for operator intervention
```

The runner should prefer deterministic choices when confidence is high, and ask the LLM when the state is new, ambiguous, or stuck.

## Observation Model

An observation should be a structured record, not only a screenshot summary.

```json
{
  "step": 12,
  "screen": "screens/step_0012.png",
  "screenshot_hash": "sha256:...",
  "ocr": [{"text": "Start", "bounds": [100, 500, 260, 570]}],
  "ui_nodes": [{"text": "Start", "class": "Button", "bounds": [96, 490, 270, 580]}],
  "visual_regions": [{"bounds": [90, 480, 280, 590], "reason": "salient button"}],
  "llm_summary": "Main menu with start button and settings icon.",
  "state_labels": ["home"],
  "safety_labels": []
}
```

OCR and UI hierarchy should be optional. Pure games may not expose useful UI nodes, so visual diff and screenshot analysis must still work.

## State Identity

State matching should combine multiple signals:

- screenshot perceptual hash
- OCR text set
- UI hierarchy summary
- LLM state label
- layout regions
- previous/next transition context

The first version can use a conservative heuristic:

- identical or near-identical screenshot hash means same state
- same OCR/UI labels and low visual diff means same state
- otherwise create a new state and allow later merge

State merging should be explicit and traceable. A mistaken merge can poison skills and goals.

## Action Space

Actions should exist at three levels.

### Level 1: Primitive Actions

Current validated actions:

- `screenshot`
- `wait`
- `back`
- `tap`
- `swipe`
- `hold_drag_release`

Primitive actions are still useful, but the LLM should not be forced to choose raw coordinates for every step after the system has learned better abstractions.

### Level 2: Targeted Actions

Actions against a discovered target:

- tap OCR text
- tap UI node
- tap visual region
- swipe region
- hold-drag from source region toward target region

Example:

```json
{
  "type": "tap_target",
  "target": {"kind": "ocr", "text": "Start", "bounds": [100, 500, 260, 570]}
}
```

The validator resolves targeted actions into primitive actions after checking bounds and safety.

### Level 3: Skills

Multi-step reusable actions:

- close popup
- start level
- navigate to next stage
- collect reward
- retry level
- aim and release
- open menu
- return to safe screen

Skill execution should be interruptible. After each internal step, feedback can stop the skill early if the success signal appears or a safety signal is detected.

## Feedback Taxonomy

The feedback classifier should grow from simple no-change detection to a richer taxonomy:

- `no_visible_change`
- `visual_changed`
- `state_changed`
- `entered_new_state`
- `returned_to_previous_state`
- `popup_opened`
- `popup_closed`
- `counter_changed`
- `resource_changed`
- `level_started`
- `level_completed`
- `level_failed`
- `reward_available`
- `reward_collected`
- `sensitive_screen`
- `ad_or_external_screen`
- `permission_prompt`
- `login_or_account_screen`
- `payment_or_purchase_screen`
- `loop_detected`
- `executor_error`

Each feedback result should include evidence:

- visual diff score
- OCR/UI changes
- state id before/after
- short human-readable reason
- confidence

## Planner and Goal Management

The planner should maintain a goal stack:

```json
{
  "main_goal": "Explore the app and progress as far as safely possible.",
  "active_subgoal": "Start the next playable level.",
  "completed_subgoals": ["dismiss startup popup", "reach main menu"],
  "blocked_subgoals": [],
  "next_candidates": ["tap start", "open level list"],
  "stop_conditions": ["sensitive screen", "max steps", "operator stop"]
}
```

A generic app/game goal ladder can start with:

1. stabilize launch state
2. dismiss safe popups
3. identify main navigation or gameplay entry
4. enter a non-sensitive primary flow
5. interact with core task or level
6. detect success/failure/result
7. collect safe reward or continue
8. repeat until stop condition

LLM goal planning should be periodic, not necessarily every step. The deterministic planner can handle routine progress while LLM re-plans when state labels change, repeated failures happen, or no known skill applies.

## Skill Mining

Skill candidates should be mined from successful traces:

```text
state A + action sequence S -> state B with desired feedback
```

Promotion criteria:

- the sequence completed a recognizable subgoal
- the before/after states are stable
- the action count is bounded
- the sequence avoids sensitive states
- success is observed at least once

Confidence should increase with repeated success and decrease with failures.

Example skill:

```json
{
  "name": "start_level_from_main_menu",
  "trigger": {
    "state_labels": ["home"],
    "required_affordance": "start_button"
  },
  "steps": [
    {"type": "tap_target", "target_ref": "start_button"},
    {"type": "wait", "seconds": 1}
  ],
  "success_signal": "level_started",
  "failure_signal": "no_visible_change",
  "confidence": 0.75
}
```

## Safety Model

Safety must be layered:

1. **Config safety**: unsafe primitive actions require explicit opt-in.
2. **State safety**: sensitive screens restrict actions to `wait` or `back`.
3. **Region safety**: known risky regions cannot be tapped.
4. **Action safety**: coordinates must be in bounds and durations capped.
5. **Loop safety**: repeated ineffective actions are blocked.
6. **Run safety**: max steps, max time, max failures, and operator stop.
7. **Profile safety**: known unsafe transitions are remembered.

Sensitive categories include:

- login
- account creation
- real-name verification
- payment or purchase
- permission grants
- password or credential input
- ads or external app handoff
- irreversible destructive actions

The LLM may label a screen as safe or unsafe, but code should apply conservative keyword, UI, and transition rules as backup.

## Web Console Evolution

The web console should eventually expose the learned model, not only run logs:

- current state id and labels
- state graph viewer
- discovered interactable regions
- active subgoal
- selected action source: skill, affordance, exploration, or LLM
- feedback evidence
- learned skills and confidence
- known unsafe paths
- profile memory summary
- replay trace for a session

The first UI implementation can remain textual/table-driven. Visual graph rendering can come later.

## Artifact Contract

Each run should keep the current artifacts and add profile-aware artifacts:

```text
session_dir/
  screens/
  actions.jsonl
  observations.jsonl
  state_transitions.jsonl
  skill_attempts.jsonl
  goal_events.jsonl
  feedback.jsonl
  mission_draft.md
  final_report.md
  run_summary.json
```

Profile updates should be written separately under `profiles/<app_id>/` so run artifacts remain immutable.

## Phase Plan

### Phase 1: State Graph Foundation

Goal: turn exploration history into a reusable graph.

Implementation scope:

- create state identity records
- write `state_transitions.jsonl`
- maintain `state_map.json` for a run
- classify same/new/no-change state transitions
- expose state id and transition info in observations

Acceptance:

- a 20-step run produces a readable state graph
- repeated screens reuse the same state id
- no-change actions are visible in transition records
- tests cover state id generation and transition writing

### Phase 2: Affordance Discovery

Goal: identify likely interactive regions before action selection.

Implementation scope:

- collect OCR regions when OCR is available
- collect Android UI hierarchy nodes when available
- add visual/LLM proposed regions
- track tested regions and feedback
- avoid repeating failed regions in the same state

Acceptance:

- ordinary apps prefer real UI buttons over random coordinates
- games record candidate regions for main buttons, popups, and controls
- repeated no-change actions on the same region are deprioritized
- tests cover region normalization, de-duplication, and feedback updates

### Phase 3: Feedback and Recovery Expansion

Goal: make action effects precise enough to guide future decisions.

Implementation scope:

- add screenshot diff scoring
- compare OCR/UI before and after actions
- classify sensitive, popup, failure, result, and loop states
- add recovery policies for repeated no-change and failure screens
- include feedback evidence in LLM prompts and profile memory

Acceptance:

- repeated ineffective actions switch action family or target
- sensitive screens trigger back/wait-only policy
- failure/result screens are labeled in observations
- tests cover feedback taxonomy and recovery decisions

### Phase 4: Profile Memory

Goal: reuse learned app knowledge across sessions.

Implementation scope:

- create `profiles/<app_id>/`
- persist state map, affordances, safety rules, and memory
- load profile at run start
- update profile atomically at safe points
- version profile schema

Acceptance:

- second run of the same app loads prior states and affordances
- known unsafe or ineffective paths are remembered
- profile files remain human-readable JSON/JSONL
- tests cover profile create/load/update/migration basics

### Phase 5: Skill Library

Goal: promote successful traces into reusable multi-step skills.

Implementation scope:

- define skill schema
- record skill attempts
- replay skills with step-by-step validation
- mine initial skill candidates from successful traces
- update skill confidence from success/failure

Acceptance:

- validated skills are tried before raw LLM coordinate proposals
- skill failure falls back to exploration mode
- common flows such as close popup and start level can be represented
- tests cover skill matching, replay, success, failure, and confidence updates

### Phase 6: Goal Planner

Goal: make exploration purposeful instead of purely step-local.

Implementation scope:

- define main goal and subgoal schema
- maintain active/completed/blocked subgoals
- emit goal events
- periodically ask LLM to re-plan from state graph and memory
- stop when success, safety, or budget conditions are met

Acceptance:

- reports include current goal progress and blocked reasons
- the runner avoids repeating completed subgoals
- failed subgoals can trigger recovery or alternate plan
- tests cover goal lifecycle transitions

### Phase 7: Web Console Profile Viewer

Goal: make learned knowledge inspectable by the operator.

Implementation scope:

- show current state id and labels
- show transition list or simple graph table
- show affordances with confidence and last result
- show skills with confidence
- show safety rules and recent interventions

Acceptance:

- operator can understand why the runner chose an action
- operator can inspect what the system has learned about an app
- tests cover API shapes and static UI wiring

### Phase 8: Cross-App Evaluation

Goal: measure generality across target categories.

Implementation scope:

- define benchmark scenarios for ordinary apps, menu-heavy games, and pure-render games
- collect metrics: states discovered, useful transitions, unsafe screens avoided, skill reuse, progress depth
- generate comparison reports across runs

Acceptance:

- ordinary apps produce usable navigation maps
- menu-heavy games can learn launch/menu/level/result flows
- pure-render games produce state graphs and local skills, even when full completion is not possible
- regressions are visible in metrics

## Testing Strategy

Unit tests should cover:

- state identity and transition recording
- affordance normalization and de-duplication
- feedback classification
- safety filtering
- profile persistence
- skill matching and replay
- goal lifecycle updates
- LLM prompt compaction and schema parsing

Integration tests should use fake executors and fake observations:

- app with button-like UI hierarchy
- game-like screenshots with no UI hierarchy
- repeated no-change loop
- sensitive screen entry
- successful level flow

Manual smoke tests should run against a real emulator with low step limits and unsafe actions disabled first.

## Success Metrics

Track these metrics per run:

- number of unique states discovered
- number of transitions discovered
- percentage of actions with visible effect
- repeated no-change count
- unsafe screen avoidance count
- skills attempted/succeeded/failed
- profile reuse rate
- subgoals completed
- average LLM calls per useful transition
- run cost and duration

The framework is improving if subsequent runs for the same app need fewer LLM calls and fewer ineffective actions to reach equivalent progress.

## Risks

- State identity can merge unrelated screens or split the same screen too often.
- LLM-generated affordances can be plausible but wrong.
- Pure-render games may require stronger vision models or domain-specific skills.
- Skill replay can become stale after app updates.
- Profile memory can accumulate bad assumptions if feedback is weak.
- Web UI can become noisy if every internal event is shown without grouping.

Mitigations:

- keep state merging conservative
- store evidence with every learned rule
- age or decay low-confidence memories
- require success signals before promoting skills
- allow profile reset or per-run memory disablement
- summarize web views by state, skill, and goal rather than raw event spam

## Recommended First Implementation Slice

Start with Phase 1 only:

- state id generation
- transition records
- run-local `state_map.json`
- same/new/no-change classification
- tests and report summary

This is the foundation for affordance discovery, skill mining, and goal management. It is also low-risk because it mostly adds observation artifacts without changing action selection yet.

After Phase 1 is stable, Phase 2 and Phase 3 can make action selection smarter. Phase 4 then makes the learning durable across sessions.

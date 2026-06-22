# Continuous Control Exploration Design

## Goal

Upgrade the game exploration system from single-step discrete action exploration to a general continuous-control exploration framework.

The system should be able to discover, execute, verify, and remember interactions such as:

- Hold a control while the screen changes.
- Move a cursor, crosshair, object, slider, or joystick while still holding.
- Observe intermediate state before releasing.
- Fine-tune toward a target.
- Release only after the action is aligned with a likely success condition.

This design targets the current hidden-object aiming game case, but the framework must stay general enough for other apps and games that require dragging, aiming, long-pressing, sliders, virtual joysticks, charging, drawing paths, or press-and-hold workflows.

## Background

The current loop is built around one complete action per step:

```text
screenshot -> LLM decision -> validate action -> execute full action -> post-action screenshot -> feedback
```

That works for many UI and game interactions:

- Tap a button.
- Swipe a list.
- Press back.
- Wait for a state change.
- Execute a one-shot hold-drag-release gesture.

It does not fully support interactions where the important state exists while the pointer is still down:

```text
screenshot -> touch down -> screenshot while held -> move -> screenshot while held -> fine adjust -> release -> verify
```

The latest observed run shows this limitation clearly. The explorer eventually tried `hold_drag_release`, and some attempts produced `counter_changed`, but it could not keep the press active while observing and correcting aim. The system therefore found parts of the mechanic by chance, but could not turn it into a reliable generalized skill.

## Scope

This upgrade includes:

- A low-level pointer action layer with interruptible touch primitives.
- A continuous action session model that can stay active across observations.
- A controller layer for generic hold/move/release exploration.
- A first reusable `aim_fire` style composite interaction.
- LLM prompt and schema changes so the model can describe controls, targets, cursors, and movement intent.
- Feedback categories for intermediate continuous-control progress.
- Skill mining that stores parameterized control strategies instead of only fixed coordinates.
- Web run controls that can explicitly enable continuous unsafe actions.
- Tests covering action validation, executor behavior, loop orchestration, feedback, and skill persistence.

This upgrade does not include:

- Hard-coding rules for one specific package name or level.
- Solving object detection with a separate trained vision model.
- Fully autonomous completion of all possible games.
- Account login, purchases, payment, real-name flows, permission approval, or shell/ADB automation beyond the existing safety policy.
- Multi-touch gestures beyond a single active pointer in the first implementation phase.

## Design Principles

The framework should treat continuous control as a general exploration capability, not a one-off game script.

The system should separate:

- Low-level touch primitives: what the device can do.
- Interaction sessions: what is currently being held or moved.
- Visual interpretation: what the screen appears to contain.
- Control hypotheses: what the system thinks a gesture might accomplish.
- Feedback: whether an attempt moved closer to the goal.
- Skills: reusable parameterized strategies learned from successful attempts.

The LLM should describe intent and visual anchors. Deterministic controller code should handle careful repeated movement, bounds checks, and release behavior.

## Architecture

Add a continuous-control layer between the run loop and the executor.

```text
RunLoop
  -> Decider
  -> ActionPlanner
  -> ContinuousControlController
  -> Executor
  -> Feedback
  -> SkillLibrary
```

### Low-Level Pointer Actions

Extend the action schema with primitive pointer actions:

```json
{"type": "touch_down", "x": 450, "y": 1175}
{"type": "touch_move", "x": 420, "y": 980, "duration": 0.2}
{"type": "touch_hold", "seconds": 0.3}
{"type": "touch_up", "x": 420, "y": 980}
```

These actions are internal by default. The LLM should not freely emit them in normal mode until the controller has opened a continuous-control session. This keeps the safety surface smaller and prevents dangling touches.

The existing `tap`, `swipe`, and `hold_drag_release` actions remain supported and can be implemented using the same primitives.

### Continuous Action Session

Introduce a session object that tracks an active pointer:

```json
{
  "active": true,
  "pointer_id": 0,
  "start": {"x": 450, "y": 1175},
  "current": {"x": 420, "y": 980},
  "started_at_step": 12,
  "mode": "aiming",
  "must_release_before_exit": true
}
```

The run loop must guarantee cleanup. If a controller error, validator rejection, user stop, or consecutive failure occurs while a pointer is down, the executor must release the pointer before the run exits.

### Composite Continuous Actions

Add high-level actions that are safe to expose to the LLM:

```json
{
  "type": "aim_fire",
  "control": {"x": 450, "y": 1175, "role": "fire_button"},
  "target": {"x": 205, "y": 842, "role": "collectible"},
  "cursor": {"x": 448, "y": 800, "role": "crosshair"},
  "hold_seconds": 0.3,
  "max_adjustments": 4,
  "release": true
}
```

```json
{
  "type": "hold_adjust_release",
  "start": {"x": 450, "y": 1175},
  "path": [
    {"x": 420, "y": 980, "duration": 0.2},
    {"x": 390, "y": 900, "duration": 0.2}
  ],
  "observe_between_moves": true
}
```

The first phase should implement `aim_fire` and map it internally to touch primitives.

## Visual State Model

The LLM decision schema should include optional visual anchors:

```json
{
  "detected_controls": [
    {
      "role": "fire_button",
      "bounds": [410, 1130, 500, 1230],
      "confidence": 0.7
    }
  ],
  "detected_cursors": [
    {
      "role": "crosshair",
      "bounds": [430, 780, 470, 820],
      "confidence": 0.8
    }
  ],
  "detected_targets": [
    {
      "role": "collectible",
      "label": "milk carton",
      "bounds": [180, 810, 230, 870],
      "confidence": 0.75
    }
  ],
  "control_hypothesis": {
    "type": "hold_to_aim_then_release",
    "confidence": 0.65,
    "evidence": "crosshair and fire control are visible; taps often failed"
  }
}
```

The fields are optional for ordinary app exploration. They become important when feedback repeatedly recommends switching away from direct taps.

## Control Hypothesis Flow

When direct actions fail repeatedly, the planner should create a control hypothesis:

```text
tap failed several times
  -> try swipe or hold-drag
  -> if hold-drag produces visual/counter change
  -> promote hypothesis: screen has continuous aiming mechanic
  -> ask LLM for controls, cursor, and target anchors
  -> invoke AimController
```

The hypothesis should include:

- Candidate control point.
- Candidate manipulated cursor/object.
- Candidate target.
- Expected intermediate feedback.
- Expected release feedback.
- Confidence.

The system should avoid committing to one hypothesis forever. If repeated continuous attempts fail, it should downgrade or replace the hypothesis.

## AimController

`AimController` is the first concrete continuous controller.

Inputs:

- Current screenshot path.
- Screen size.
- Allowed action policy.
- Visual anchors from the LLM.
- Recent feedback and memory summary.

Loop:

```text
1. Validate control, cursor, and target coordinates.
2. touch_down on control.
3. hold briefly to enter the interaction state.
4. Capture an intermediate screenshot.
5. Ask the decider or a lightweight visual evaluator whether cursor/target alignment improved.
6. Move toward the target in bounded increments.
7. Repeat for max_adjustments.
8. Release.
9. Capture post-action screenshot.
10. Classify feedback.
```

The first implementation can use simple geometry:

```text
dx = target_center.x - cursor_center.x
dy = target_center.y - cursor_center.y
next_move = current + clamp(dx, dy, max_step)
```

Later implementations can replace this with visual tracking or model-assisted correction.

## Feedback Model

Add continuous-control feedback labels:

- `control_mode_entered`: a hold changed the screen or exposed a cursor/magnifier.
- `cursor_detected`: a likely movable cursor/crosshair was detected.
- `cursor_moved`: cursor position changed after a move.
- `cursor_closer_to_target`: cursor moved closer to the selected target.
- `target_centered`: cursor is likely over the target.
- `target_collected`: release changed a target count or removed the object.
- `wrong_target_collected`: release changed an undesired target or added a wrong item.
- `control_attempt_failed`: no useful movement or result happened.
- `control_released_safely`: pointer was released after an interrupted session.

These labels give the system partial rewards. It can learn that a sequence is improving even before final success.

## Skill Learning

Successful continuous attempts should be mined into parameterized skills:

```json
{
  "name": "aim_and_release_visible_target",
  "type": "continuous_control",
  "trigger": {
    "state_labels": ["hidden_object", "crosshair_visible"],
    "required_roles": ["fire_button", "crosshair", "collectible"]
  },
  "strategy": {
    "controller": "AimController",
    "control_role": "fire_button",
    "cursor_role": "crosshair",
    "target_role": "collectible",
    "release_condition": "target_centered_or_max_adjustments"
  },
  "success_signal": "target_collected",
  "confidence": 0.55
}
```

This avoids storing only fixed coordinates from one run. The next session can reuse the strategy with newly detected controls and targets.

## Safety

Continuous actions are more powerful than taps. They need explicit gates:

- Disabled unless the run allows unsafe actions.
- A separate `enable_continuous_actions` flag in the Web/API layer.
- Maximum hold duration.
- Maximum number of move events.
- Bounds validation for every point.
- Guaranteed release on failure or stop.
- Sensitive screens still force `back` or `wait`.
- Continuous sessions cannot execute shell, install, payment, login, or account-entry flows.

The default Web console should keep continuous actions disabled unless the operator opts in.

## Web Console Impact

The Web console should eventually show a separate option:

```text
Allow continuous gestures
```

When enabled, the run payload may include:

```json
{
  "allowed_actions": [
    "screenshot",
    "wait",
    "back",
    "tap",
    "swipe",
    "hold_drag_release",
    "aim_fire"
  ],
  "enable_unsafe_actions": true,
  "enable_continuous_actions": true
}
```

The live run view should display continuous attempts as grouped events:

```text
Step 12: aim_fire
  touch_down -> observe -> move -> observe -> move -> release -> verify
```

## Data Artifacts

Continuous runs should write new or extended artifacts:

- `actions.jsonl`: high-level action plus summarized internal pointer events.
- `feedback.jsonl`: intermediate and final feedback labels.
- `observations.jsonl`: detected controls, cursors, targets, and hypotheses.
- `control_sessions.jsonl`: low-level continuous session timeline.
- `skills.json`: parameterized continuous skills.
- `memory.jsonl`: successful and failed hypotheses.

The existing artifacts remain readable by older tooling. New fields should be additive.

## Phase Plan

### Phase 1: Pointer Primitives

Add validation and executor support for `touch_down`, `touch_move`, `touch_hold`, and `touch_up`.

Acceptance:

- Primitive actions validate coordinates and durations.
- Executor maps primitives to Airtest touch APIs where available.
- Any failed sequence releases the pointer.
- Existing `tap`, `swipe`, and `hold_drag_release` behavior remains compatible.

### Phase 2: `aim_fire` Composite Action

Add a high-level `aim_fire` action that performs a bounded hold-move-release sequence.

Acceptance:

- The LLM can emit `aim_fire` only when continuous actions are enabled.
- Validation requires control and target points.
- The executor records internal events.
- Post-action feedback works the same way as existing actions.

### Phase 3: Visual Anchor Schema

Extend the LLM prompt and schema with controls, cursors, targets, and control hypotheses.

Acceptance:

- Prompt asks for visual anchors when direct actions fail.
- Parsed decisions include normalized anchors.
- Recent actions include continuous feedback in compact form.
- Tests prove old decisions still parse.

### Phase 4: AimController Closed Loop

Add a controller that can observe while holding and fine-adjust before release.

Acceptance:

- Controller captures intermediate screenshots.
- Controller adjusts toward the target for a bounded number of moves.
- Controller emits intermediate feedback.
- Controller always releases on error.

### Phase 5: Continuous Skill Mining

Store successful continuous-control attempts as parameterized skills.

Acceptance:

- Successful `aim_fire` attempts create `continuous_control` skills.
- Skill replay uses newly detected anchors instead of old absolute coordinates when possible.
- Failed attempts reduce confidence.
- Memory summaries mention useful continuous skills.

### Phase 6: Broader Generalization

Expand controllers and templates beyond aiming:

- Slider adjustment.
- Virtual joystick movement.
- Drag-to-sort.
- Long-press charge and release.
- Draw path gestures.

Acceptance:

- Each controller is a separate module with shared session safety.
- The planner can choose a controller based on hypotheses and feedback.
- Skills remain parameterized by roles and anchors.

## Testing Strategy

Unit tests:

- Action validation for primitive and composite actions.
- Executor primitive call order.
- Cleanup behavior on errors.
- Prompt/schema parsing for visual anchors.
- Feedback labels for continuous control.
- Skill mining for parameterized continuous skills.

Integration tests:

- A fake executor simulates a cursor moving while held.
- A fake decider emits anchors and `aim_fire`.
- The run loop records intermediate control session events.
- A successful simulated target collection creates a reusable skill.

Regression tests:

- Existing safe action runs still work.
- Existing unsafe tap/swipe opt-in remains unchanged.
- Existing profile memory and progress verification still pass.

Manual smoke tests:

- Start the Web console.
- Enable unsafe and continuous gestures.
- Run the hidden-object aiming game.
- Confirm logs show grouped continuous attempts.
- Confirm pointer release after stop, failure, and normal completion.

## Open Decisions

The first implementation should choose conservative defaults:

- `max_adjustments`: 3.
- `max_hold_seconds`: 5.
- `max_move_duration`: 1 second per move.
- Continuous actions disabled by default.
- Single pointer only.

Future work can add calibrated values per device, game, or learned profile.

## Success Criteria

The upgrade is successful when the system can:

- Recognize that direct taps are failing and a continuous-control hypothesis is useful.
- Ask for or infer control, cursor, and target anchors.
- Hold a control, observe while held, move toward a target, and release safely.
- Record whether each intermediate movement improved alignment.
- Convert successful attempts into a reusable parameterized skill.
- Preserve all existing safe exploration behavior.

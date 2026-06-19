# -*- coding: utf-8 -*-
"""Lightweight step runner for bounded App/Game exploration."""

import os
import time

from game_reverse.actions import validate_action
from game_reverse.airtest_executor import AirtestExecutor
from game_reverse.journal import Journal
from game_reverse.llm_decider import parse_decision
from game_reverse.report_writer import update_mission_draft, write_final_report


def run_lightweight_loop(
    config,
    executor=None,
    decider=None,
    session_name=None,
    context=None,
    executor_factory=None,
):
    executor = executor or (executor_factory() if executor_factory is not None else AirtestExecutor())
    if decider is None:
        raise ValueError("decider is required")

    session_name = session_name or time.strftime("%Y%m%d-%H%M%S")
    journal = Journal.create(config.output_root, session_name)
    _emit_context_event(
        context,
        "session_started",
        session_dir=journal.session_dir,
        max_steps=config.max_steps,
    )

    executor.connect(config.device_uri)
    executor.start_app(config.package_name)

    recent_actions = []
    mission_draft = journal.read_mission_draft()
    stop_reason = "max_steps_reached"

    for step in range(1, config.max_steps + 1):
        screen_path = journal.screen_path(step)
        executor.execute({"type": "screenshot"}, screen_path)
        relative_screen = os.path.relpath(screen_path, journal.session_dir)
        _emit_context_event(
            context,
            "step_screenshot",
            step=step,
            max_steps=config.max_steps,
            screen=relative_screen,
        )

        decision = _normalize_decision(
            decider.decide_action(
            {
                "step": step,
                "max_steps": config.max_steps,
                "screen": relative_screen,
                "mission": {
                    "type": config.mission.type,
                    "goal": config.mission.goal,
                    "targets": list(config.mission.targets),
                    "success_criteria": list(config.mission.success_criteria),
                },
                "allowed_actions": list(config.allowed_actions),
                "recent_actions": recent_actions[-config.recent_steps :],
            }
            )
        )
        action = validate_action(decision["action"], config.allowed_actions, _read_screen_size(screen_path))
        if action["type"] == "screenshot":
            action = {"type": "wait", "seconds": 0}
        result = executor.execute(action, screen_path)

        action_record = {
            "step": step,
            "screen": relative_screen,
            "mission_type": config.mission.type,
            "action": action,
            "reason": decision.get("reason", ""),
            "result": result,
        }
        observation_record = {
            "step": step,
            "mission_type": config.mission.type,
            "state": decision.get("state", "unknown"),
            "screen_summary": decision.get("screen_summary", ""),
            "findings": decision.get("new_findings", []),
            "screenshot_tags": decision.get("screenshot_tags", []),
            "risks": decision.get("risks", []),
        }
        journal.write_action(action_record)
        journal.write_observation(observation_record)
        mission_draft = update_mission_draft(mission_draft, step, decision)
        journal.update_mission_draft(mission_draft)
        _emit_context_event(
            context,
            "run_progress",
            step=step,
            max_steps=config.max_steps,
            action_type=action["type"],
            result=result,
            message="第 %s 步 / 共 %s 步：%s" % (step, config.max_steps, action["type"]),
        )
        recent_actions.append(action_record)

    write_final_report(
        journal.session_dir,
        journal.read_mission_draft(),
        config.mission,
        stop_reason,
    )
    _emit_context_event(
        context,
        "run_report_written",
        session_dir=journal.session_dir,
        stop_reason=stop_reason,
    )
    return journal.session_dir


def _emit_context_event(context, event_type, **extra):
    if context is None:
        return
    emit_event = getattr(context, "emit_event", None)
    if emit_event is not None:
        emit_event(event_type, **extra)


def _read_screen_size(screen_path):
    try:
        from PIL import Image

        with Image.open(screen_path) as image:
            return image.size
    except Exception:
        return (1080, 1920)


def _normalize_decision(decision):
    import json

    if isinstance(decision, str):
        return parse_decision(decision)
    return parse_decision(json.dumps(decision, ensure_ascii=False))

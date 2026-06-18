# -*- coding: utf-8 -*-
"""Mission-driven App/Game exploration loop."""

import argparse
import os
import time

from game_reverse.actions import validate_action
from game_reverse.airtest_executor import AirtestExecutor
from game_reverse.config import load_config
from game_reverse.journal import Journal
from game_reverse.llm_decider import ClaudeDecider
from game_reverse.report_writer import update_mission_draft, write_final_report


def run_loop(config, executor=None, decider=None, session_name=None, context=None):
    executor = executor or AirtestExecutor()
    decider = decider or ClaudeDecider(config.model)
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
    failure_count = 0
    stop_reason = "max_steps_reached"

    for step in range(1, config.max_steps + 1):
        screen_path = journal.screen_path(step)
        try:
            executor.execute({"type": "screenshot"}, screen_path)
            relative_screen = os.path.relpath(screen_path, journal.session_dir)
            _emit_context_event(
                context,
                "step_screenshot",
                step=step,
                max_steps=config.max_steps,
                screen=relative_screen,
            )
            screen_size = _read_screen_size(screen_path)
            mission_draft = journal.read_mission_draft()
            decision = decider.decide(
                screen_path,
                config.mission,
                recent_actions[-config.recent_steps :],
                mission_draft,
            )
            action = validate_action(decision["action"], config.allowed_actions, screen_size)
            if action["type"] == "screenshot":
                action = {"type": "wait", "seconds": 1}
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
            journal.update_mission_draft(update_mission_draft(mission_draft, step, decision))
            _emit_context_event(
                context,
                "step_action",
                step=step,
                max_steps=config.max_steps,
                screen=relative_screen,
                action_type=action["type"],
                result=result,
                reason=decision.get("reason", ""),
            )
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
            failure_count = 0
        except Exception as exc:
            failure_count += 1
            relative_screen = os.path.relpath(screen_path, journal.session_dir)
            journal.write_action(
                {
                    "step": step,
                    "screen": relative_screen,
                    "mission_type": config.mission.type,
                    "action": {"type": "error"},
                    "error_type": exc.__class__.__name__,
                    "reason": str(exc),
                    "result": "failed",
                }
            )
            _emit_context_event(
                context,
                "step_failed",
                step=step,
                max_steps=config.max_steps,
                screen=relative_screen,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )
            if failure_count >= config.consecutive_failure_limit:
                stop_reason = "consecutive_failures"
                break

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


def main():
    parser = argparse.ArgumentParser(description="Run Claude-guided Airtest App/Game exploration.")
    parser.add_argument("--config", required=True, help="Path to game_reverse config JSON")
    args = parser.parse_args()
    config = load_config(args.config)
    session_dir = run_loop(config)
    print("Session written to: %s" % session_dir)


if __name__ == "__main__":
    main()

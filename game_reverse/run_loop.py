# -*- coding: utf-8 -*-
"""Mission-driven App/Game exploration loop."""

import argparse
import hashlib
import os
import time

from game_reverse.actions import validate_action
from game_reverse.airtest_executor import AirtestExecutor
from game_reverse.affordances import AffordanceMemory
from game_reverse.config import load_config
from game_reverse.feedback import classify_feedback, recommend_next_strategy
from game_reverse.journal import Journal
from game_reverse.llm_decider import ClaudeDecider
from game_reverse.memory import ProfileStore
from game_reverse.report_writer import update_mission_draft, write_final_report
from game_reverse.state_graph import StateGraph


def run_loop(config, executor=None, decider=None, session_name=None, context=None):
    executor = executor or AirtestExecutor()
    decider = decider or ClaudeDecider(config.model)
    session_name = session_name or time.strftime("%Y%m%d-%H%M%S")
    journal = Journal.create(config.output_root, session_name)
    profile_store = _create_profile_store(config)
    _emit_context_event(
        context,
        "session_started",
        session_dir=journal.session_dir,
        max_steps=config.max_steps,
    )

    executor.connect(config.device_uri)
    executor.start_app(config.package_name)

    recent_actions = []
    feedback_history = []
    previous_observation = None
    previous_screen_path = None
    state_graph = StateGraph()
    affordance_memory = AffordanceMemory()
    failure_count = 0
    stop_reason = "max_steps_reached"

    for step in range(1, config.max_steps + 1):
        screen_path = journal.screen_path(step)
        try:
            executor.execute({"type": "screenshot"}, screen_path)
            relative_screen = os.path.relpath(screen_path, journal.session_dir)
            screenshot_hash = _file_sha256(screen_path)
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
                "screenshot_hash": screenshot_hash,
                "ocr": decision.get("ocr", []),
                "ui_nodes": decision.get("ui_nodes", []),
                "visual_regions": decision.get("visual_regions", []),
                "proposed_regions": decision.get("proposed_regions", []),
            }
            state_update = state_graph.update(
                step=step,
                screen_path=relative_screen,
                observation=observation_record,
                screenshot_hash=screenshot_hash,
            )
            transition = state_update["transition"]
            observation_record["state_id"] = state_update["state_id"]
            observation_record["state_visit_count"] = state_update["state_visit_count"]
            observation_record["state_transition"] = transition["classification"]
            affordance_memory.collect_from_observation(
                state_update["state_id"],
                observation_record,
                screen_size=screen_size,
            )
            feedback = classify_feedback(
                previous_observation,
                observation_record,
                before_screen_path=previous_screen_path,
                after_screen_path=screen_path,
            )
            feedback["action_type"] = action["type"]
            feedback["state_id"] = state_update["state_id"]
            feedback_history.append(feedback)
            strategy = recommend_next_strategy(feedback_history)
            affordance_memory.record_action_feedback(
                state_update["state_id"],
                action,
                feedback["result"],
            )
            action_record["state_id"] = state_update["state_id"]
            action_record["state_transition"] = transition["classification"]
            action_record["feedback_result"] = feedback["result"]
            action_record["feedback_evidence"] = feedback["evidence"]
            action_record["feedback_confidence"] = feedback["confidence"]
            action_record["visual_diff_score"] = feedback["visual_diff_score"]
            action_record["ocr_changed"] = feedback["ocr_changed"]
            action_record["ui_changed"] = feedback["ui_changed"]
            action_record["safety_label"] = feedback["safety_label"]
            action_record["next_strategy"] = strategy["next_strategy"]
            action_record["recommended_actions"] = strategy["recommended_actions"]
            action_record["recovery_reason"] = strategy["reason"]
            observation_record["feedback_result"] = feedback["result"]
            observation_record["feedback_confidence"] = feedback["confidence"]
            observation_record["visual_diff_score"] = feedback["visual_diff_score"]
            observation_record["safety_label"] = feedback["safety_label"]
            observation_record["next_strategy"] = strategy["next_strategy"]
            observation_record["recovery_reason"] = strategy["reason"]
            journal.write_action(action_record)
            journal.write_observation(observation_record)
            journal.write_state_transition(transition)
            journal.write_state_map(state_graph.to_state_map())
            journal.write_affordances(affordance_memory.to_affordances())
            _update_profile(
                profile_store,
                session_name,
                state_graph,
                affordance_memory,
                observation_record,
                action_record,
                transition,
                feedback,
            )
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
            previous_observation = observation_record
            previous_screen_path = screen_path
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
    journal.write_state_map(state_graph.to_state_map())
    journal.write_affordances(affordance_memory.to_affordances())
    if profile_store is not None:
        profile_store.update_json("state_map.json", state_graph.to_state_map())
        profile_store.update_json("affordances.json", affordance_memory.to_affordances())
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


def _create_profile_store(config):
    if not getattr(config, "profile_enabled", True):
        return None
    store = ProfileStore(config.profile_root, config.package_name)
    return store.initialize(package_name=config.package_name)


def _update_profile(
    profile_store,
    session_name,
    state_graph,
    affordance_memory,
    observation_record,
    action_record,
    transition,
    feedback,
):
    if profile_store is None:
        return
    profile_store.update_json("state_map.json", state_graph.to_state_map())
    profile_store.update_json("affordances.json", affordance_memory.to_affordances())
    profile_store.update_json(
        "safety_rules.json",
        _profile_safety_rules(profile_store, observation_record, feedback),
    )
    profile_store.append_memory(
        {
            "event": "step",
            "session_name": session_name,
            "step": observation_record["step"],
            "state_id": observation_record.get("state_id"),
            "action": action_record.get("action"),
            "feedback_result": feedback.get("result"),
            "transition": transition,
            "screen": observation_record.get("screen"),
        }
    )


def _profile_safety_rules(profile_store, observation_record, feedback):
    safety_rules = profile_store.load_json(
        "safety_rules.json",
        {"version": 1, "sensitive_states": [], "interventions": []},
    )
    safety_rules.setdefault("version", 1)
    safety_rules.setdefault("sensitive_states", [])
    safety_rules.setdefault("interventions", [])
    if feedback.get("result") == "sensitive_screen":
        state_id = observation_record.get("state_id")
        if state_id and state_id not in safety_rules["sensitive_states"]:
            safety_rules["sensitive_states"].append(state_id)
        safety_rules["interventions"].append(
            {
                "step": observation_record.get("step"),
                "state_id": state_id,
                "reason": feedback.get("evidence", ""),
            }
        )
    return safety_rules


def _read_screen_size(screen_path):
    try:
        from PIL import Image

        with Image.open(screen_path) as image:
            return image.size
    except Exception:
        return (1080, 1920)


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:%s" % digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Run Claude-guided Airtest App/Game exploration.")
    parser.add_argument("--config", required=True, help="Path to game_reverse config JSON")
    args = parser.parse_args()
    config = load_config(args.config)
    session_dir = run_loop(config)
    print("Session written to: %s" % session_dir)


if __name__ == "__main__":
    main()

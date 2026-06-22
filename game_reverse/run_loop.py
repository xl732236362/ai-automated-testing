# -*- coding: utf-8 -*-
"""Mission-driven App/Game exploration loop."""

import argparse
import hashlib
import inspect
import os
import time

from game_reverse.actions import validate_action
from game_reverse.airtest_executor import AirtestExecutor
from game_reverse.affordances import AffordanceMemory
from game_reverse.config import load_config
from game_reverse.feedback import classify_feedback, recommend_next_strategy
from game_reverse.goal_planner import GoalPlanner
from game_reverse.journal import Journal
from game_reverse.llm_decider import ClaudeDecider
from game_reverse.memory import ProfileStore
from game_reverse.profile_learning import merge_profile_payloads, summarize_profile_memory
from game_reverse.profile_view import load_profile_summary
from game_reverse.progress import compare_progress, normalize_progress
from game_reverse.report_writer import update_mission_draft, write_final_report
from game_reverse.skill_library import SkillLibrary
from game_reverse.state_graph import StateGraph


def run_loop(config, executor=None, decider=None, session_name=None, context=None):
    executor = executor or AirtestExecutor()
    decider = decider or ClaudeDecider(config.model)
    session_name = session_name or time.strftime("%Y%m%d-%H%M%S")
    journal = Journal.create(config.output_root, session_name)
    profile_store = _create_profile_store(config)
    skill_library = _create_skill_library(profile_store)
    goal_planner = _create_goal_planner(config, profile_store)
    memory_summary = _create_memory_summary(config, profile_store)
    _write_goal_artifacts(journal, profile_store, goal_planner, None)
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
    completed_steps = []
    previous_observation = None
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
            base_observation_record = {
                "step": step,
                "mission_type": config.mission.type,
                "state": "unknown",
                "screen_summary": "",
                "findings": [],
                "screenshot_tags": [],
                "risks": [],
                "screenshot_hash": screenshot_hash,
                "ocr": [],
                "ui_nodes": [],
                "visual_regions": [],
                "proposed_regions": [],
                "progress": {},
            }
            skill_result = _try_skill(
                skill_library,
                base_observation_record,
                affordance_memory,
                executor,
                screen_path,
                screen_size,
                config.allowed_actions,
            )
            if skill_result is not None:
                journal.write_skill_attempt(dict(skill_result, step=step))
                profile_store and profile_store.update_json("skills.json", skill_library.to_skills())
                if not skill_result["success"]:
                    skill_result = None
                else:
                    observation_record = base_observation_record
                    post_screen_path, relative_post_screen, post_screenshot_hash = _capture_post_action_screen(
                        executor,
                        journal,
                        step,
                    )
                    observation_record["post_action_screen"] = relative_post_screen
                    observation_record["post_action_screenshot_hash"] = post_screenshot_hash
                    state_update = _update_state_and_affordances(
                        state_graph,
                        affordance_memory,
                        step,
                        relative_screen,
                        screenshot_hash,
                        observation_record,
                        screen_size,
                    )
                    transition = state_update["transition"]
                    action_record = {
                        "step": step,
                        "screen": relative_screen,
                        "post_action_screen": relative_post_screen,
                        "mission_type": config.mission.type,
                        "action": {"type": "skill", "name": skill_result["skill_name"]},
                        "reason": "replayed skill %s" % skill_result["skill_name"],
                        "result": "executed",
                        "action_source": "skill",
                    }
                    feedback = _record_feedback_and_artifacts(
                        previous_observation,
                        observation_record,
                        screen_path,
                        post_screen_path,
                        action_record,
                        transition,
                        state_update,
                        feedback_history,
                        affordance_memory,
                        journal,
                        state_graph,
                        profile_store,
                        session_name,
                        goal_planner,
                    )
                    _emit_context_event(
                        context,
                        "step_action",
                        step=step,
                        max_steps=config.max_steps,
                        screen=relative_screen,
                        action_type="skill",
                        result=action_record["result"],
                        reason=action_record["reason"],
                    )
                    _emit_context_event(
                        context,
                        "run_progress",
                        step=step,
                        max_steps=config.max_steps,
                        action_type="skill",
                        result=action_record["result"],
                        message="第 %s 步 / 共 %s 步：skill" % (step, config.max_steps),
                    )
                    recent_actions.append(action_record)
                    completed_steps.append(action_record)
                    previous_observation = observation_record
                    failure_count = 0
                    continue
            decision = _decide(
                decider,
                screen_path,
                config.mission,
                recent_actions[-config.recent_steps :],
                mission_draft,
                memory_summary=memory_summary,
            )
            action = validate_action(decision["action"], config.allowed_actions, screen_size)
            if action["type"] == "screenshot":
                action = {"type": "wait", "seconds": 1}
            result = executor.execute(action, screen_path)
            post_screen_path, relative_post_screen, post_screenshot_hash = _capture_post_action_screen(
                executor,
                journal,
                step,
            )

            action_record = {
                "step": step,
                "screen": relative_screen,
                "post_action_screen": relative_post_screen,
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
                "pre_action_screenshot_hash": screenshot_hash,
                "post_action_screenshot_hash": post_screenshot_hash,
                "post_action_screen": relative_post_screen,
                "ocr": decision.get("ocr", []),
                "ui_nodes": decision.get("ui_nodes", []),
                "visual_regions": decision.get("visual_regions", []),
                "proposed_regions": decision.get("proposed_regions", []),
                "progress": normalize_progress(decision.get("progress")),
            }
            observation_record["verified_progress"] = compare_progress(
                (previous_observation or {}).get("progress"),
                observation_record.get("progress"),
            )
            state_update = _update_state_and_affordances(
                state_graph,
                affordance_memory,
                step,
                relative_screen,
                screenshot_hash,
                observation_record,
                screen_size,
            )
            transition = state_update["transition"]
            action_record["action_source"] = "llm"
            feedback = _record_feedback_and_artifacts(
                previous_observation,
                observation_record,
                screen_path,
                post_screen_path,
                action_record,
                transition,
                state_update,
                feedback_history,
                affordance_memory,
                journal,
                state_graph,
                profile_store,
                session_name,
                goal_planner,
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
            completed_steps.append(action_record)
            previous_observation = observation_record
            failure_count = 0
        except Exception as exc:
            failure_count += 1
            relative_screen = os.path.relpath(screen_path, journal.session_dir)
            action_record = {
                "step": step,
                "screen": relative_screen,
                "mission_type": config.mission.type,
                "action": {"type": "error"},
                "error_type": exc.__class__.__name__,
                "reason": str(exc),
                "result": "failed",
            }
            goal_event = goal_planner.update(
                {},
                action_record,
                {"result": "executor_error", "evidence": str(exc)},
            )
            _attach_goal_context(action_record, {}, goal_planner, goal_event)
            journal.write_action(action_record)
            _write_goal_artifacts(journal, profile_store, goal_planner, dict(goal_event, step=step))
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

    _write_goal_artifacts(journal, profile_store, goal_planner, None)
    journal.write_state_map(state_graph.to_state_map())
    journal.write_affordances(affordance_memory.to_affordances())
    if profile_store is not None:
        _merge_profile_artifacts(
            profile_store,
            session_name,
            state_graph,
            affordance_memory,
            skill_library,
            completed_steps,
        )
    journal.write_run_summary(
        _run_summary(
            session_name,
            stop_reason,
            completed_steps,
            state_graph,
            affordance_memory,
            goal_planner,
        )
    )
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


def _capture_post_action_screen(executor, journal, step):
    post_screen_path = journal.post_action_screen_path(step)
    executor.execute({"type": "screenshot"}, post_screen_path)
    relative_post_screen = os.path.relpath(post_screen_path, journal.session_dir)
    return post_screen_path, relative_post_screen, _file_sha256(post_screen_path)


def _create_profile_store(config):
    if not getattr(config, "profile_enabled", True):
        return None
    store = ProfileStore(config.profile_root, config.package_name)
    return store.initialize(package_name=config.package_name)


def _create_skill_library(profile_store):
    if profile_store is None:
        return SkillLibrary()
    skills_payload = profile_store.load_json("skills.json", {"version": 1, "skills": []})
    return SkillLibrary(skills_payload.get("skills", []))


def _create_goal_planner(config, profile_store):
    existing_goals = None
    if profile_store is not None:
        existing_goals = profile_store.load_json("goals.json", {})
    return GoalPlanner(config.mission, existing=existing_goals)


def _create_memory_summary(config, profile_store):
    if profile_store is None:
        return ""
    profile = load_profile_summary(config.profile_root, config.package_name)
    return summarize_profile_memory(profile)


def _decide(decider, screen_path, mission, recent_actions, mission_draft, memory_summary):
    try:
        parameters = inspect.signature(decider.decide).parameters
    except (TypeError, ValueError):
        parameters = {}
    if "memory_summary" in parameters:
        return decider.decide(
            screen_path,
            mission,
            recent_actions,
            mission_draft,
            memory_summary=memory_summary,
        )
    return decider.decide(screen_path, mission, recent_actions, mission_draft)


def _update_state_and_affordances(
    state_graph,
    affordance_memory,
    step,
    relative_screen,
    screenshot_hash,
    observation_record,
    screen_size,
):
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
    return state_update


def _try_skill(
    skill_library,
    observation_record,
    affordance_memory,
    executor,
    screen_path,
    screen_size,
    allowed_actions,
):
    skill = skill_library.best_match(observation_record, affordances=[])
    if skill is None:
        return None
    result = skill_library.replay(
        skill,
        executor=executor,
        screen_path=screen_path,
        screen_size=screen_size,
        allowed_actions=allowed_actions,
    )
    return result


def _record_feedback_and_artifacts(
    previous_observation,
    observation_record,
    pre_action_screen_path,
    post_action_screen_path,
    action_record,
    transition,
    state_update,
    feedback_history,
    affordance_memory,
    journal,
    state_graph,
    profile_store,
    session_name,
    goal_planner,
):
    feedback = classify_feedback(
        previous_observation,
        observation_record,
        before_screen_path=pre_action_screen_path,
        after_screen_path=post_action_screen_path,
    )
    feedback["action_type"] = action_record["action"]["type"]
    feedback["state_id"] = state_update["state_id"]
    feedback_history.append(feedback)
    strategy = recommend_next_strategy(feedback_history)
    affordance_memory.record_action_feedback(
        state_update["state_id"],
        action_record["action"],
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
    action_record["before_counts"] = feedback.get("before_counts", [])
    action_record["after_counts"] = feedback.get("after_counts", [])
    action_record["progress_delta"] = feedback.get("progress_delta", 0)
    action_record["progress_changed"] = feedback.get("progress_changed", False)
    action_record["next_strategy"] = strategy["next_strategy"]
    action_record["recommended_actions"] = strategy["recommended_actions"]
    action_record["recovery_reason"] = strategy["reason"]
    observation_record["feedback_result"] = feedback["result"]
    observation_record["feedback_confidence"] = feedback["confidence"]
    observation_record["visual_diff_score"] = feedback["visual_diff_score"]
    observation_record["safety_label"] = feedback["safety_label"]
    observation_record["progress_delta"] = feedback.get("progress_delta", 0)
    observation_record["progress_changed"] = feedback.get("progress_changed", False)
    observation_record["next_strategy"] = strategy["next_strategy"]
    observation_record["recovery_reason"] = strategy["reason"]
    goal_event = goal_planner.update(observation_record, action_record, feedback)
    replan_event = _maybe_replan_goals(goal_planner, strategy)
    _attach_goal_context(action_record, observation_record, goal_planner, goal_event)
    if replan_event is not None:
        action_record["replan_event"] = replan_event["event"]
        observation_record["replan_event"] = replan_event["event"]
    journal.write_feedback(
        _feedback_record(
            observation_record,
            action_record,
            transition,
            feedback,
            strategy,
        )
    )
    journal.write_action(action_record)
    journal.write_observation(observation_record)
    journal.write_state_transition(transition)
    journal.write_state_map(state_graph.to_state_map())
    journal.write_affordances(affordance_memory.to_affordances())
    _write_goal_artifacts(
        journal,
        profile_store,
        goal_planner,
        dict(goal_event, step=observation_record["step"]),
    )
    if replan_event is not None:
        _write_goal_artifacts(
            journal,
            profile_store,
            goal_planner,
            dict(replan_event, step=observation_record["step"]),
        )
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
    return feedback


def _maybe_replan_goals(goal_planner, strategy):
    if strategy.get("next_strategy") not in ("switch_gesture", "switch_target"):
        return None
    return goal_planner.replan(
        {
            "next_candidates": strategy.get("recommended_actions", []),
            "reason": strategy.get("reason", ""),
        }
    )


def _attach_goal_context(action_record, observation_record, goal_planner, goal_event):
    goals = goal_planner.to_goals()
    action_record["active_subgoal"] = goals["active_subgoal"]
    action_record["goal_event"] = goal_event["event"]
    action_record["goal_candidates"] = goals["next_candidates"]
    if observation_record is not None:
        observation_record["active_subgoal"] = goals["active_subgoal"]
        observation_record["goal_event"] = goal_event["event"]


def _write_goal_artifacts(journal, profile_store, goal_planner, goal_event):
    if goal_event is not None:
        journal.write_goal_event(goal_event)
    goals = goal_planner.to_goals()
    journal.write_goals(goals)
    if profile_store is not None:
        profile_store.update_json("goals.json", goals)


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
    profile_store.update_json(
        "safety_rules.json",
        _profile_safety_rules(profile_store, observation_record, feedback),
    )
    profile_store.append_memory(
        _profile_step_event(session_name, observation_record, action_record, transition, feedback)
    )
    profile_store.append_trace(
        session_name,
        _profile_step_event(session_name, observation_record, action_record, transition, feedback),
    )


def _merge_profile_artifacts(
    profile_store,
    session_name,
    state_graph,
    affordance_memory,
    skill_library,
    completed_steps,
):
    existing_state_map = profile_store.load_json("state_map.json", {"version": 1, "states": {}, "transitions": []})
    existing_affordances = profile_store.load_json("affordances.json", {"version": 1, "states": {}})
    existing_skills = profile_store.load_json("skills.json", {"version": 1, "skills": []})
    mined_skills = skill_library.mine_candidates(completed_steps)
    merged = merge_profile_payloads(
        existing_state_map=existing_state_map,
        current_state_map=state_graph.to_state_map(),
        existing_affordances=existing_affordances,
        current_affordances=affordance_memory.to_affordances(),
        existing_skills=existing_skills,
        mined_skills=mined_skills,
        session_name=session_name,
    )
    profile_store.update_json("state_map.json", merged["state_map"])
    profile_store.update_json("affordances.json", merged["affordances"])
    profile_store.update_json("skills.json", merged["skills"])


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


def _feedback_record(observation_record, action_record, transition, feedback, strategy):
    return {
        "step": observation_record.get("step"),
        "state_id": observation_record.get("state_id"),
        "state_transition": transition.get("classification"),
        "action": action_record.get("action"),
        "action_source": action_record.get("action_source"),
        "result": feedback.get("result"),
        "evidence": feedback.get("evidence"),
        "confidence": feedback.get("confidence"),
        "visual_diff_score": feedback.get("visual_diff_score"),
        "ocr_changed": feedback.get("ocr_changed"),
        "ui_changed": feedback.get("ui_changed"),
        "safety_label": feedback.get("safety_label"),
        "before_counts": feedback.get("before_counts", []),
        "after_counts": feedback.get("after_counts", []),
        "progress_delta": feedback.get("progress_delta", 0),
        "progress_changed": feedback.get("progress_changed", False),
        "next_strategy": strategy.get("next_strategy"),
        "recommended_actions": strategy.get("recommended_actions"),
        "recovery_reason": strategy.get("reason"),
    }


def _profile_step_event(session_name, observation_record, action_record, transition, feedback):
    return {
        "event": "step",
        "session_name": session_name,
        "step": observation_record["step"],
        "state_id": observation_record.get("state_id"),
        "action": action_record.get("action"),
        "feedback_result": feedback.get("result"),
        "transition": transition,
        "screen": observation_record.get("screen"),
        "post_action_screen": observation_record.get("post_action_screen"),
    }


def _run_summary(session_name, stop_reason, completed_steps, state_graph, affordance_memory, goal_planner):
    action_counts = {}
    feedback_counts = {}
    for action_record in completed_steps:
        action_type = (action_record.get("action") or {}).get("type", "unknown")
        action_counts[action_type] = action_counts.get(action_type, 0) + 1
        feedback_result = action_record.get("feedback_result", "unknown")
        feedback_counts[feedback_result] = feedback_counts.get(feedback_result, 0) + 1
    state_map = state_graph.to_state_map()
    affordances = affordance_memory.to_affordances()
    return {
        "version": 1,
        "session_id": session_name,
        "stop_reason": stop_reason,
        "steps_completed": len(completed_steps),
        "action_counts": action_counts,
        "feedback_counts": feedback_counts,
        "states_discovered": len(state_map.get("states", {})),
        "transitions_discovered": len(state_map.get("transitions", [])),
        "affordances_discovered": sum(len(items) for items in affordances.get("states", {}).values()),
        "final_goals": goal_planner.to_goals(),
    }


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

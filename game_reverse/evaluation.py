# -*- coding: utf-8 -*-
"""Offline cross-app evaluation metrics for game_reverse sessions."""

import argparse
import json
import os


VISIBLE_EFFECT_RESULTS = {
    "visual_changed",
    "ocr_changed",
    "ui_changed",
    "counter_changed",
    "tray_changed",
    "state_changed",
    "entered_new_state",
    "level_started",
    "level_completed",
    "popup_closed",
}
NO_CHANGE_RESULTS = {"no_visible_change"}
REGRESSION_METRICS = [
    "states_discovered",
    "useful_transitions",
    "visible_effect_rate",
    "skill_reuse_rate",
    "progress_depth",
]


def default_benchmark_scenarios():
    return [
        {
            "id": "ordinary_app",
            "label": "Ordinary App",
            "goal": "Produce usable navigation maps for button and list oriented apps.",
        },
        {
            "id": "menu_heavy_game",
            "label": "Menu-Heavy Game",
            "goal": "Learn launch, menu, level, and result flows.",
        },
        {
            "id": "pure_render_game",
            "label": "Pure-Render Game",
            "goal": "Produce state graphs and local skills without UI hierarchy.",
        },
    ]


def collect_session_metrics(session_dir, scenario_id="unclassified"):
    state_map = _read_json(session_dir, "state_map.json", {"states": {}, "transitions": []})
    actions = _read_jsonl(session_dir, "actions.jsonl")
    skill_attempts = _read_jsonl(session_dir, "skill_attempts.jsonl")
    goals = _read_json(session_dir, "goals.json", {"completed_subgoals": []})
    observations = _read_jsonl(session_dir, "observations.jsonl")
    transitions = state_map.get("transitions") or []
    useful_transitions = [
        transition for transition in transitions if transition.get("classification") != "no_change"
    ]
    visible_actions = [
        action for action in actions if action.get("feedback_result") in VISIBLE_EFFECT_RESULTS
    ]
    no_change_actions = [
        action for action in actions if action.get("feedback_result") in NO_CHANGE_RESULTS
    ]
    unsafe_avoidance_actions = [
        action
        for action in actions
        if action.get("feedback_result") == "sensitive_screen"
        or action.get("safety_label") == "sensitive"
    ]
    skill_actions = [action for action in actions if action.get("action_source") == "skill"]
    llm_actions = [action for action in actions if action.get("action_source", "llm") == "llm"]
    skills_succeeded = [attempt for attempt in skill_attempts if attempt.get("success")]
    skills_failed = [attempt for attempt in skill_attempts if not attempt.get("success")]

    return {
        "session_id": os.path.basename(os.path.normpath(session_dir)),
        "session_dir": session_dir,
        "scenario_id": scenario_id,
        "states_discovered": len(state_map.get("states") or {}),
        "transitions_discovered": len(transitions),
        "useful_transitions": len(useful_transitions),
        "visible_effect_rate": _ratio(len(visible_actions), len(actions)),
        "repeated_no_change_count": len(no_change_actions),
        "unsafe_screen_avoidance_count": len(unsafe_avoidance_actions),
        "skills_attempted": len(skill_attempts),
        "skills_succeeded": len(skills_succeeded),
        "skills_failed": len(skills_failed),
        "skill_reuse_rate": _ratio(len(skill_actions), len(actions)),
        "subgoals_completed": len(goals.get("completed_subgoals") or []),
        "progress_depth": max([int(item.get("step") or 0) for item in observations] or [len(actions)]),
        "llm_calls_per_useful_transition": _ratio(len(llm_actions), len(useful_transitions)),
        "run_cost": 0,
        "duration_seconds": 0,
    }


def compare_sessions(session_dirs, scenario_id="unclassified"):
    runs = [collect_session_metrics(session_dir, scenario_id=scenario_id) for session_dir in session_dirs]
    runs.sort(key=lambda item: item["session_id"])
    return {
        "version": 1,
        "scenario_id": scenario_id,
        "scenario": _scenario_by_id(scenario_id),
        "runs": runs,
        "regressions": _detect_regressions(runs),
        "summary": _comparison_summary(runs),
    }


def write_comparison_report(comparison, markdown_path):
    lines = [
        "# Cross-App Evaluation",
        "",
        "- Scenario: %s" % comparison.get("scenario_id", "unclassified"),
        "- Runs: %s" % len(comparison.get("runs", [])),
        "",
        "## Metrics",
        "",
        "| session | states discovered | useful transitions | visible effect rate | unsafe screens avoided | skill reuse rate | progress depth |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for run in comparison.get("runs", []):
        lines.append(
            "| {session_id} | {states_discovered} | {useful_transitions} | {visible_effect_rate:.2f} | {unsafe_screen_avoidance_count} | {skill_reuse_rate:.2f} | {progress_depth} |".format(
                **run
            )
        )
    lines.extend(["", "## Regression Notes", ""])
    regressions = comparison.get("regressions", [])
    if regressions:
        for item in regressions:
            lines.append(
                "- %s dropped from %s to %s between %s and %s"
                % (
                    item["metric"],
                    item["previous"],
                    item["current"],
                    item["previous_session"],
                    item["current_session"],
                )
            )
    else:
        lines.append("- No regressions detected.")
    _write_text(markdown_path, "\n".join(lines) + "\n")


def write_comparison_json(comparison, json_path):
    os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(comparison, json_file, ensure_ascii=False, indent=2, sort_keys=True)
        json_file.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare game_reverse session metrics.")
    parser.add_argument("--scenario", default="unclassified")
    parser.add_argument("--session", action="append", required=True)
    parser.add_argument("--json-output")
    parser.add_argument("--markdown-output")
    args = parser.parse_args(argv)

    comparison = compare_sessions(args.session, scenario_id=args.scenario)
    if args.json_output:
        write_comparison_json(comparison, args.json_output)
    if args.markdown_output:
        write_comparison_report(comparison, args.markdown_output)
    if not args.json_output and not args.markdown_output:
        print(json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _read_json(session_dir, filename, default):
    path = os.path.join(session_dir, filename)
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as json_file:
        return json.load(json_file)


def _read_jsonl(session_dir, filename):
    path = os.path.join(session_dir, filename)
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as jsonl_file:
        for line in jsonl_file:
            if line.strip():
                records.append(json.loads(line))
    return records


def _ratio(numerator, denominator):
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def _scenario_by_id(scenario_id):
    for scenario in default_benchmark_scenarios():
        if scenario["id"] == scenario_id:
            return scenario
    return {"id": scenario_id, "label": scenario_id, "goal": ""}


def _detect_regressions(runs):
    regressions = []
    for previous, current in zip(runs, runs[1:]):
        for metric in REGRESSION_METRICS:
            if current.get(metric, 0) < previous.get(metric, 0):
                regressions.append(
                    {
                        "metric": metric,
                        "previous_session": previous["session_id"],
                        "current_session": current["session_id"],
                        "previous": previous.get(metric, 0),
                        "current": current.get(metric, 0),
                    }
                )
    return regressions


def _comparison_summary(runs):
    if not runs:
        return {"run_count": 0}
    return {
        "run_count": len(runs),
        "best_states_discovered": max(run["states_discovered"] for run in runs),
        "best_useful_transitions": max(run["useful_transitions"] for run in runs),
        "best_progress_depth": max(run["progress_depth"] for run in runs),
    }


def _write_text(path, content):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as text_file:
        text_file.write(content)


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Session journal writer for game_reverse exploration runs."""

import json
import os
from dataclasses import dataclass


@dataclass
class Journal:
    session_dir: str
    screens_dir: str

    @classmethod
    def create(cls, output_root, session_name):
        session_dir = os.path.join(output_root, session_name)
        screens_dir = os.path.join(session_dir, "screens")
        os.makedirs(screens_dir, exist_ok=True)

        for filename in ("actions.jsonl", "observations.jsonl", "state_transitions.jsonl", "skill_attempts.jsonl"):
            path = os.path.join(session_dir, filename)
            if not os.path.exists(path):
                open(path, "a", encoding="utf-8").close()

        draft_path = os.path.join(session_dir, "mission_draft.md")
        if not os.path.exists(draft_path):
            with open(draft_path, "w", encoding="utf-8") as draft_file:
                draft_file.write("# App/Game 鎺㈢储鑽夌\n")

        return cls(session_dir=session_dir, screens_dir=screens_dir)

    def screen_path(self, step):
        return os.path.join(self.screens_dir, "step_%04d.png" % step)

    def write_action(self, record):
        self._append_jsonl("actions.jsonl", record)

    def write_observation(self, record):
        self._append_jsonl("observations.jsonl", record)

    def write_state_transition(self, record):
        self._append_jsonl("state_transitions.jsonl", record)

    def write_skill_attempt(self, record):
        self._append_jsonl("skill_attempts.jsonl", record)

    def write_state_map(self, state_map):
        path = os.path.join(self.session_dir, "state_map.json")
        with open(path, "w", encoding="utf-8") as state_map_file:
            json.dump(state_map, state_map_file, ensure_ascii=False, indent=2, sort_keys=True)
            state_map_file.write("\n")

    def write_affordances(self, affordances):
        path = os.path.join(self.session_dir, "affordances.json")
        with open(path, "w", encoding="utf-8") as affordances_file:
            json.dump(affordances, affordances_file, ensure_ascii=False, indent=2, sort_keys=True)
            affordances_file.write("\n")

    def update_mission_draft(self, content):
        with open(os.path.join(self.session_dir, "mission_draft.md"), "w", encoding="utf-8") as draft_file:
            draft_file.write(content)

    def read_mission_draft(self):
        with open(os.path.join(self.session_dir, "mission_draft.md"), "r", encoding="utf-8") as draft_file:
            return draft_file.read()

    def _append_jsonl(self, filename, record):
        with open(os.path.join(self.session_dir, filename), "a", encoding="utf-8") as jsonl_file:
            jsonl_file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

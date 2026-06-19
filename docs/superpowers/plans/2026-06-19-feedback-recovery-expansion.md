# Feedback and Recovery Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Phase 3 feedback and recovery expansion so action effects include screenshot diff evidence, OCR/UI comparison, sensitive/result/failure/popup/loop labels, and recovery recommendations.

**Architecture:** Extend `game_reverse.feedback` in place because it already owns feedback classification and next-strategy recommendations. Keep the first version deterministic and artifact-friendly: compare observation fields already available from the runner, use screenshot hashes or bytes for visual diff scoring, and expose simple recovery policy outputs through existing action records and LLM prompt context.

**Tech Stack:** Python standard library, JSON artifacts, existing `unittest`/`pytest` tests, existing `game_reverse` runner and LLM prompt compaction.

---

## File Structure

- Modify `game_reverse/feedback.py`: add screenshot diff scoring, OCR/UI text comparison, taxonomy labels, and expanded recovery policies.
- Modify `tests/test_game_reverse_feedback.py`: cover screenshot diff, OCR/UI changes, sensitive/popup/result/failure classifications, and loop recovery.
- Modify `game_reverse/run_loop.py`: pass previous/current screenshot paths into feedback classification and include richer feedback fields in action/observation records.
- Modify `tests/test_game_reverse_run_loop.py`: verify richer feedback evidence and recovery policy are recorded.
- Modify `tests/test_game_reverse_llm_decider.py`: verify prompt compaction includes recovery policy/action family guidance already stored in recent actions.

---

### Task 1: Feedback Taxonomy Core

**Files:**
- Modify: `game_reverse/feedback.py`
- Modify: `tests/test_game_reverse_feedback.py`

- [ ] **Step 1: Write failing tests**

Add tests for:

- `visual_changed` when screenshot hashes differ
- `ocr_changed` when OCR text changes
- `sensitive_screen` for login/payment/permission terms
- `popup_opened` for modal/dialog/popup terms
- `level_completed` and `level_failed` for result/failure text
- `loop_detected` recovery recommendation after repeated no-change in one state/action family

- [ ] **Step 2: Verify tests fail**

Run:

```bash
python -m pytest tests/test_game_reverse_feedback.py -q
```

Expected: FAIL because the current classifier lacks the expanded taxonomy.

- [ ] **Step 3: Implement taxonomy**

Extend `classify_feedback(before=None, after=None, before_screen_path=None, after_screen_path=None)` to return:

```python
{
  "result": "...",
  "evidence": "...",
  "confidence": "low|medium|high",
  "visual_diff_score": 0.0,
  "ocr_changed": False,
  "ui_changed": False,
  "safety_label": "",
}
```

Keep existing result names compatible for old tests.

- [ ] **Step 4: Verify feedback tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_feedback.py -q
```

Expected: PASS.

---

### Task 2: Recovery Policy Integration

**Files:**
- Modify: `game_reverse/feedback.py`
- Modify: `tests/test_game_reverse_feedback.py`

- [ ] **Step 1: Write failing recovery tests**

Add tests that repeated `no_visible_change` in the same state/action family returns `switch_target`, sensitive feedback returns `back_or_wait_only`, and failure screens return `recover_from_failure`.

- [ ] **Step 2: Implement policy**

Extend `recommend_next_strategy(feedback_history)` to inspect recent results, states, and action types, returning:

```python
{
  "next_strategy": "...",
  "recommended_actions": [...],
  "reason": "..."
}
```

- [ ] **Step 3: Verify feedback tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_feedback.py -q
```

Expected: PASS.

---

### Task 3: Run Loop and Prompt Evidence

**Files:**
- Modify: `game_reverse/run_loop.py`
- Modify: `tests/test_game_reverse_run_loop.py`
- Modify: `tests/test_game_reverse_llm_decider.py`

- [ ] **Step 1: Write failing run-loop test**

Use fake screenshots with changed bytes and a decider that returns sensitive/result/failure text. Assert `actions.jsonl` contains `feedback_confidence`, `visual_diff_score`, and `recovery_reason`.

- [ ] **Step 2: Update run-loop integration**

Track `previous_screen_path` alongside `previous_observation`. Pass screenshot paths to `classify_feedback()`. Copy richer feedback fields and strategy reason into action and observation records.

- [ ] **Step 3: Verify prompt compacting includes recovery reason**

Update prompt tests so `compact_recent_actions()` includes `recovery_reason` and selected recommended actions.

- [ ] **Step 4: Verify focused tests pass**

Run:

```bash
python -m pytest tests/test_game_reverse_feedback.py tests/test_game_reverse_run_loop.py tests/test_game_reverse_llm_decider.py -q
```

Expected: PASS.

---

### Task 4: Phase 3 Acceptance Verification and Commit

- [ ] **Step 1: Run full game_reverse regression suite**

Run:

```bash
python -m pytest tests/test_game_reverse_actions.py tests/test_game_reverse_affordances.py tests/test_game_reverse_airtest_executor.py tests/test_game_reverse_config.py tests/test_game_reverse_executors.py tests/test_game_reverse_feedback.py tests/test_game_reverse_journal.py tests/test_game_reverse_lightweight_runner.py tests/test_game_reverse_llm_decider.py tests/test_game_reverse_mission.py tests/test_game_reverse_report_writer.py tests/test_game_reverse_run_loop.py tests/test_game_reverse_state_graph.py tests/test_game_reverse_target_discovery.py tests/test_game_reverse_web_server.py tests/test_game_reverse_web_service.py tests/test_web_console_static.py -q
```

Expected: PASS.

- [ ] **Step 2: Commit Phase 3**

Run:

```bash
git add docs/superpowers/plans/2026-06-19-feedback-recovery-expansion.md game_reverse/feedback.py game_reverse/run_loop.py game_reverse/llm_decider.py tests/test_game_reverse_feedback.py tests/test_game_reverse_run_loop.py tests/test_game_reverse_llm_decider.py
git commit -m "feat: expand feedback and recovery classification"
```

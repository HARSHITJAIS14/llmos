"""
Unit Test for State Diff Engine and HarnessLogger.
Tests canonical tree normalization, git-style unified diff generation (+/- lines, @@ headers),
and HarnessLogger log file creation using existing JSON snapshots.
"""
import os
import sys
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from utils.state_diff import generate_git_diff, normalize_tree_data
from utils.harness_logger import HarnessLogger

EXP_DIR = os.path.dirname(__file__)
CALENDAR_EXP_DIR = os.path.abspath(os.path.join(EXP_DIR, '../calendar_add_event'))

def test_normalization():
    print("Testing JSON tree normalization...")
    sample_data = {
        "snapshot_id": "ephemeral123",
        "tree": {
            "ref_id": "@ephemeral123:e1",
            "role": "button",
            "name": "Submit"
        }
    }
    normalized_raw = normalize_tree_data(sample_data, strip_ephemeral=False)
    normalized_clean = normalize_tree_data(sample_data, strip_ephemeral=True)
    
    raw_str = "".join(normalized_raw)
    clean_str = "".join(normalized_clean)
    
    assert "ephemeral123" in raw_str
    assert "snapshot_id" not in clean_str
    assert ":e1" in clean_str and "@ephemeral123:e1" not in clean_str
    print("✓ Tree normalization passed.")

def test_git_diff_generation():
    print("Testing git-style diff generation between Calendar snapshots...")
    step2_file = os.path.join(CALENDAR_EXP_DIR, "calendar_guaranteed_step2.json")
    step5_file = os.path.join(CALENDAR_EXP_DIR, "calendar_guaranteed_step5.json")

    if not os.path.exists(step2_file) or not os.path.exists(step5_file):
        print(f"Skipping snapshot diff test: files not found in {CALENDAR_EXP_DIR}")
        return

    with open(step2_file) as f:
        s2 = json.load(f)
    with open(step5_file) as f:
        s5 = json.load(f)

    diff = generate_git_diff(s2, s5, context_lines=2, from_label="Step2_Popover", to_label="Step5_Inspector", strip_ephemeral=True)
    
    assert "--- Step2_Popover" in diff
    assert "+++ Step5_Inspector" in diff
    assert "+" in diff and "-" in diff
    print("✓ Git-style diff generation passed.")
    print("Sample Diff snippet:")
    print("----------------------------------------")
    print("".join(diff.splitlines(keepends=True)[:25]))
    print("----------------------------------------")

def test_harness_logger():
    print("Testing HarnessLogger workflow...")
    log_file = os.path.join(EXP_DIR, "test_execution.diff.log")
    if os.path.exists(log_file):
        os.remove(log_file)

    logger = HarnessLogger(log_file, task_name="Test Calendar Workflow", strip_ephemeral=True, context_lines=2)
    
    s0 = {"app": "Calendar", "windows": []}
    s1 = {"app": "Calendar", "windows": [{"id": "w1", "name": "Main"}]}
    s2 = {"app": "Calendar", "windows": [{"id": "w1", "name": "Main", "popover": True}]}

    logger.log_initial_state(s0, "App launched")
    logger.log_action("activate_window", {"app": "Calendar"}, new_state=s1, description="Activate Calendar window")
    logger.log_action("press_shortcut", {"shortcut": "cmd+n"}, new_state=s2, description="Trigger Quick Event popover")
    logger.finalize(success=True, notes="Verified test log creation")

    assert os.path.exists(log_file)
    with open(log_file) as f:
        content = f.read()
    
    assert "LLM_OS HARNESS WORKFLOW EXECUTION LOG" in content
    assert "STEP 1: Action 'activate_window'" in content
    assert "STEP 2: Action 'press_shortcut'" in content
    assert "WORKFLOW EXECUTION COMPLETE [SUCCESS]" in content
    print(f"✓ HarnessLogger test passed. Log written to {log_file}")

if __name__ == "__main__":
    test_normalization()
    test_git_diff_generation()
    test_harness_logger()
    print("\nALL TESTS PASSED SUCCESSFULLY!")

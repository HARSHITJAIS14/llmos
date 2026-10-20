"""
Harness Logger for LLM_OS tasks.
Logs a sequence of (tree_state, action) pairs as git-style state diffs.
"""
import os
import json
import time
from utils.state_diff import generate_git_diff

class HarnessLogger:
    def __init__(self, log_path, task_name="LLM_OS Task", strip_ephemeral=False, context_lines=3):
        self.log_path = os.path.abspath(log_path)
        self.task_name = task_name
        self.strip_ephemeral = strip_ephemeral
        self.context_lines = context_lines
        self.step_count = 0
        self.last_state = None
        self.start_time = time.time()
        self.last_step_time = self.start_time

        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        
        # Initialize log file
        with open(self.log_path, "w") as f:
            f.write("========================================================================\n")
            f.write(f"LLM_OS HARNESS WORKFLOW EXECUTION LOG: {self.task_name}\n")
            f.write(f"Start Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("========================================================================\n\n")

    def log_initial_state(self, initial_state, description="Initial State Capture"):
        """Records baseline state S0."""
        self.step_count = 0
        self.last_state = initial_state
        self.start_time = time.time()
        self.last_step_time = self.start_time
        
        with open(self.log_path, "a") as f:
            f.write(f"=== STEP 0: Baseline State ({description}) ===\n")
            f.write(f"Timestamp: {time.strftime('%H:%M:%S')}\n")
            f.write("Captured initial accessibility tree state.\n")
            f.write("------------------------------------------------------------------------\n\n")

    def log_action(self, action_name, action_details=None, new_state=None, description=""):
        """
        Records an action performed and the resulting state change diff (S_{t-1} -> S_t).
        """
        now = time.time()
        step_duration = now - self.last_step_time
        total_elapsed = now - self.start_time
        self.last_step_time = now

        self.step_count += 1
        step_str = f"STEP {self.step_count}"
        prev_idx = self.step_count - 1
        curr_idx = self.step_count
        
        with open(self.log_path, "a") as f:
            f.write(f"=== {step_str}: Action '{action_name}' ===\n")
            if description:
                f.write(f"Description: {description}\n")
            if action_details is not None:
                if isinstance(action_details, (dict, list)):
                    f.write(f"Action Details: {json.dumps(action_details)}\n")
                else:
                    f.write(f"Action Details: {action_details}\n")
            
            f.write(f"Timestamp: {time.strftime('%H:%M:%S')} (Duration: {step_duration:.2f}s | Elapsed: {total_elapsed:.2f}s)\n")
            f.write("------------------------------------------------------------------------\n")
            f.write(f"State Diff (State_T{prev_idx} -> State_T{curr_idx}):\n\n")
            
            if new_state is not None:
                if self.last_state is not None:
                    diff_text = generate_git_diff(
                        self.last_state,
                        new_state,
                        context_lines=self.context_lines,
                        from_label=f"State_T{prev_idx}",
                        to_label=f"State_T{curr_idx}",
                        strip_ephemeral=self.strip_ephemeral
                    )
                    f.write(diff_text)
                else:
                    f.write("(First state logged, baseline created)\n")
                self.last_state = new_state
            else:
                f.write("(No state snapshot captured for this step)\n")
                
            f.write("========================================================================\n\n")

    def finalize(self, success=True, notes=""):
        """Finalizes the workflow log."""
        total_duration = time.time() - self.start_time
        with open(self.log_path, "a") as f:
            status = "SUCCESS" if success else "FAILED"
            f.write(f"=== WORKFLOW EXECUTION COMPLETE [{status}] ===\n")
            if notes:
                f.write(f"Notes: {notes}\n")
            f.write(f"Total Duration: {total_duration:.2f}s ({total_duration / 60:.2f} min)\n")
            f.write(f"Total Steps: {self.step_count}\n")
            f.write("========================================================================\n")
        print(f"Harness log finalized ({total_duration:.2f}s): {self.log_path}")

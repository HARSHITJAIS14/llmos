import json
import subprocess
import time
import os
import sys

AGENT = '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js'
EXP_DIR = os.path.abspath(os.path.dirname(__file__))

def run_cmd(args):
    res = subprocess.run([AGENT] + args, capture_output=True, text=True)
    try:
        return json.loads(res.stdout)
    except Exception as e:
        return {"ok": False, "raw": res.stdout, "error": str(e)}

print("=== STEP 1: Activating Calendar app ===")
subprocess.run(["osascript", "-e", 'tell application "Calendar" to activate'], check=True)
time.sleep(1.5)

print("\n=== STEP 2: Triggering Quick Event Macro (Cmd+N) ===")
# Ensure focus right before keystroke
subprocess.run(["osascript", "-e", 'tell application "Calendar" to activate'], check=True)
time.sleep(0.5)
res_cmd_n = run_cmd(["press", "cmd+n"])
print("Cmd+N result:", res_cmd_n)
time.sleep(1.5)

print("\n=== STEP 3: Setting Clipboard & Pasting Event Text ===")
event_text = "visit Hc at 3 pm"
res_clip = run_cmd(["clipboard-set", event_text])
print("Clipboard result:", res_clip)

subprocess.run(["osascript", "-e", 'tell application "Calendar" to activate'], check=True)
time.sleep(0.5)

res_paste = run_cmd(["press", "cmd+v"])
print("Cmd+V paste result:", res_paste)
time.sleep(1.0)

print("\n=== STEP 4: Committing Event with Return Key ===")
subprocess.run(["osascript", "-e", 'tell application "Calendar" to activate'], check=True)
time.sleep(0.5)

res_return = run_cmd(["press", "return"])
print("Return result:", res_return)
time.sleep(1.5)

# Record log output to experiment folder
log_file = os.path.join(EXP_DIR, "execution_log.json")
with open(log_file, "w") as f:
    json.dump({
        "cmd_n": res_cmd_n,
        "clipboard": res_clip,
        "paste": res_paste,
        "return": res_return
    }, f, indent=2)

print(f"\nSaved execution log to: {log_file}")
print("=== Execution Complete ===")

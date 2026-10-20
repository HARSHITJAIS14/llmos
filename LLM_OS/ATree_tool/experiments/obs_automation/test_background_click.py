import json
import subprocess

print("Querying window list (OBS in background)...")
res = subprocess.run(["/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js", "list-windows"], capture_output=True, text=True)
try:
    windows = json.loads(res.stdout).get("data", [])
    obs_win = next((w for w in windows if w.get("app_name") == "OBS Studio" and w.get("title", "").startswith("OBS ") and w.get("title") != "OBS Studio"), None)
    if not obs_win:
        print("OBS main window not found in list-windows.")
        exit(1)
        
    win_id = obs_win["id"]
    print(f"Found OBS window: {win_id} ({obs_win['title']})")
except Exception as e:
    print(f"Failed to parse windows: {e}")
    exit(1)

print("Taking snapshot of OBS window...")
snap_res = subprocess.run(["/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js", "snapshot", "-i", "--window-id", win_id], capture_output=True, text=True)
try:
    tree = json.loads(snap_res.stdout).get("data", {}).get("tree", {})
    
    target_ref = None
    def find_btn(n):
        global target_ref
        if target_ref: return
        name = str(n.get("name", "")).lower()
        if "start recording" in name or "stop recording" in name:
            target_ref = n.get("ref_id")
            return
        for c in n.get("children", []):
            find_btn(c)
            
    find_btn(tree)
    if not target_ref:
        print("Could not find recording button in the tree.")
        exit(1)
        
    print(f"Found recording button with ref: {target_ref}")
except Exception as e:
    print(f"Failed to parse snapshot: {e}")
    exit(1)

print("Dispatching synthetic click to recording button in background...")
click_res = subprocess.run(["/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js", "click", target_ref], capture_output=True, text=True)
print(click_res.stdout)

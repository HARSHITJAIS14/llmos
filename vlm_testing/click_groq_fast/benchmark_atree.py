import os
import sys
import json
import time
import subprocess
import requests
from dotenv import load_dotenv

# Load env variables (including CEREBRAS_API_KEY)
load_dotenv()

sys.path.append("/Users/harshit/Desktop/YC/atree")
from core import snapshot, axdiff

INTERACTIVE = {"button", "textfield", "textarea", "searchfield", "combobox", "checkbox",
               "menuitem", "tab", "link", "slider", "popupbutton", "cell", "radiobutton"}

def get_condensed_atree(app_name):
    print(f"Snapshotting {app_name} via YC/atree...")
    env = snapshot.capture(app=app_name)
    tree = env.get("data", {}).get("tree", env)
    
    # Condense 24k tokens into <2k using the sidecar pattern
    content, sidecar = axdiff.flatten(tree)
    
    # Only keep interactive elements with names
    interactive_rows = []
    for path, attrs in sorted(content.items()):
        if attrs.get("role") in INTERACTIVE and attrs.get("name"):
            interactive_rows.append({
                "path": path,
                "role": attrs.get("role"),
                "name": attrs.get("name")
            })
            
    return interactive_rows, sidecar

def ask_cerebras(target_desc, atree_json):
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        print("ERROR: CEREBRAS_API_KEY not found in .env")
        sys.exit(1)
        
    url = "https://api.cerebras.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        f"You are a strict UI element matcher. Given the following JSON array of interactive UI elements on a screen, "
        f"find the ONE element that best matches this user request: '{target_desc}'.\n\n"
        f"Respond ONLY with the raw string of the 'id' (e.g. @sXYZ:e42). Do not include quotes, markdown, or any other text.\n\n"
        f"UI Elements JSON:\n{json.dumps(atree_json)}"
    )
    
    payload = {
        "model": "gemma-4-31b",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0
    }
    
    print(f"Firing request to Cerebras (gemma-4-31b) with {len(json.dumps(atree_json))} bytes of JSON...")
    t0 = time.time()
    resp = requests.post(url, headers=headers, json=payload)
    t1 = time.time()
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"Cerebras Latency: {t1 - t0:.3f}s")
        print(f"Cerebras Output: {data['choices'][0]['message']['content'].strip()}")
    else:
        print(f"Cerebras Error: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 benchmark_atree.py <app_name> <target_description>")
        sys.exit(1)
        
    app_name_or_file = sys.argv[1]
    target_desc = sys.argv[2]
    
    overall_t0 = time.time()
    
    if app_name_or_file.endswith(".json"):
        print(f"Loading ATree from file {app_name_or_file}...")
        t_snapshot_0 = time.time()
        with open(app_name_or_file, 'r') as f:
            atree = json.load(f)
        
        tree = atree.get("data", {}).get("tree", atree)
        content, sidecar = axdiff.flatten(tree)
        interactive_rows = []
        for path, attrs in sorted(content.items()):
            if attrs.get("role") in INTERACTIVE and attrs.get("name"):
                interactive_rows.append({
                    "path": path,
                    "role": attrs.get("role"),
                    "name": attrs.get("name")
                })
        t_snapshot_1 = time.time()
        print(f"ATree Load/Condense Latency: {t_snapshot_1 - t_snapshot_0:.3f}s")
    else:
        print(f"Activating {app_name_or_file}...")
        subprocess.run(["open", "-a", app_name_or_file])
        time.sleep(1.0) # wait for app to become active
            
        t_snapshot_0 = time.time()
        interactive_rows, sidecar = get_condensed_atree(app_name_or_file)
        t_snapshot_1 = time.time()
        print(f"ATree Extraction+Condense Latency: {t_snapshot_1 - t_snapshot_0:.3f}s")
    
    print(f"Found {len(interactive_rows)} interactive elements.")
    
    ask_cerebras(target_desc, interactive_rows)
    
    print(f"Total Pipeline Latency: {time.time() - overall_t0:.3f}s")

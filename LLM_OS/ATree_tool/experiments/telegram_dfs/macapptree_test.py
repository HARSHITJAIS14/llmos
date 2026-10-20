import json
import sys
import subprocess
import time

sys.path.append("/Users/harshit/Desktop/YC/LLM_OS/experiments/macapptree")

try:
    print("Launching Telegram via osascript...")
    subprocess.run(["osascript", "-e", 'tell application "Telegram" to activate'], check=True)
    
    print("Waiting for Telegram to open and render its window...")
    time.sleep(3)
    
    from macapptree import get_tree, get_app_bundle
    
    print("Getting bundle for Telegram...")
    bundle = get_app_bundle("Telegram")
    print(f"Bundle: {bundle}")
    
    print("Getting tree via macapptree...")
    tree = get_tree(bundle)
    
    out_path = "/Users/harshit/Desktop/YC/LLM_OS/experiments/telegram_dfs/macapptree_telegram.json"
    with open(out_path, "w") as f:
        json.dump(tree, f, indent=2)
    print(f"Saved tree to {out_path}")
    
    def count_nodes(nodes):
        if not nodes:
            return 0
        c = len(nodes)
        for n in nodes:
            c += count_nodes(n.get("children", []))
        return c
        
    print(f"Total nodes extracted by macapptree: {count_nodes(tree)}")
    
except Exception as e:
    print(f"Error: {e}")

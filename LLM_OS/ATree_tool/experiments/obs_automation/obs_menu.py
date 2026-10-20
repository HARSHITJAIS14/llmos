import json

tree = json.load(open('/Users/harshit/Desktop/YC/LLM_OS/experiments/obs_snapshot.json')).get('data', {}).get('tree', {})

def walk(n):
    name = str(n.get('name', '')).lower()
    role = str(n.get('role', '')).lower()
    if 'record' in name or 'controls' in name:
        print(f"Found: '{n.get('name')}' | Role: {n.get('role')}")
    for c in n.get('children', []): walk(c)

walk(tree)

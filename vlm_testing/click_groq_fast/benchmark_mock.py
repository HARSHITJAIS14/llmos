import os
import time
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def benchmark_mock():
    api_key = os.environ.get("GROQ_API_KEY")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Mocking a ~100 token accessibility tree snippet
    mock_atree = [
        {"id": "@e1", "role": "button", "name": "Play Video"},
        {"id": "@e2", "role": "link", "name": "Aarzu Song - Official Music Video"},
        {"id": "@e3", "role": "image", "name": "Sweater Weather Cover"},
        {"id": "@e4", "role": "button", "name": "Wi-Fi Settings"},
        {"id": "@e5", "role": "checkbox", "name": "Enable Notifications"}
    ]
    
    target_desc = "Aarzu"
    prompt = (
        f"You are a strict UI element matcher. Given the following JSON array of interactive UI elements on a screen, "
        f"find the ONE element that best matches this user request: '{target_desc}'.\n\n"
        f"Respond ONLY with the raw string of the 'id' (e.g. @sXYZ:e42). Do not include quotes, markdown, or any other text.\n\n"
        f"UI Elements JSON:\n{json.dumps(mock_atree, indent=2)}"
    )
    
    payload = {
        "model": "openai/gpt-oss-120b", 
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0
    }
    
    print(f"Firing request to Groq (gpt-oss-120b) with mock JSON payload ({len(json.dumps(mock_atree))} bytes)...")
    t0 = time.time()
    resp = requests.post(url, headers=headers, json=payload)
    t1 = time.time()
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"Groq Inference Latency: {t1 - t0:.3f}s")
        print(f"Groq Output: {data['choices'][0]['message']['content'].strip()}")
    else:
        print(f"Groq Error: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    benchmark_mock()

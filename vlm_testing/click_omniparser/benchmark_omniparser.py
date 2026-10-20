import os
import sys
import time
import json
import base64
from io import BytesIO
from PIL import Image
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), 'OmniParser'))
os.chdir(os.path.join(os.path.dirname(__file__), 'OmniParser'))

import transformers.dynamic_module_utils
_original_check_imports = transformers.dynamic_module_utils.check_imports
def _patched_check_imports(filename):
    try:
        return _original_check_imports(filename)
    except ImportError as e:
        if "flash_attn" in str(e):
            return []
        raise e
transformers.dynamic_module_utils.check_imports = _patched_check_imports

from util.utils import get_yolo_model, get_caption_model_processor, get_som_labeled_img, check_ocr_box

def get_groq_response(target_text, parsed_content_list, api_key):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        f"You are a UI automation agent. I will give you a list of UI elements detected on a screen.\n"
        f"Each element has an ID and a description.\n"
        f"Find the ONE element that best matches this user request: '{target_text}'.\n\n"
        f"Respond ONLY with the raw integer ID (e.g. 5). Do not include quotes, markdown, or any other text.\n\n"
        f"UI Elements:\n{parsed_content_list}"
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 10
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content'].strip()
    else:
        print(f"Groq API Error: {response.text}")
        return None

def benchmark_omniparser(image_path, target_text, groq_api_key):
    print("Initializing OmniParser models (this will be fast on subsequent runs if kept in memory)...")
    t_init_start = time.time()
    yolo_model = get_yolo_model()
    caption_model_processor = get_caption_model_processor(model_name="florence2", model_name_or_path="weights/icon_caption_florence")
    t_init_end = time.time()
    print(f"OmniParser Init Latency: {t_init_end - t_init_start:.3f}s")
    
    print(f"Loading image from {image_path}...")
    image_input = Image.open(image_path).convert("RGB")
    
    print("Running OmniParser (OCR + YOLO detection + Captioning)...")
    t_parse_start = time.time()
    
    box_overlay_ratio = image_input.size[0] / 3200
    draw_bbox_config = {
        'text_scale': 0.8 * box_overlay_ratio,
        'text_thickness': max(int(2 * box_overlay_ratio), 1),
        'text_padding': max(int(3 * box_overlay_ratio), 1),
        'thickness': max(int(3 * box_overlay_ratio), 1),
    }

    ocr_bbox_rslt, _ = check_ocr_box(image_input, display_img=False, output_bb_format='xyxy', goal_filtering=None, easyocr_args={'paragraph': False, 'text_threshold':0.9}, use_paddleocr=False)
    text, ocr_bbox = ocr_bbox_rslt
    
    dino_labled_img, label_coordinates, parsed_content_list = get_som_labeled_img(
        image_input, yolo_model, BOX_TRESHOLD=0.05, output_coord_in_ratio=True, 
        ocr_bbox=ocr_bbox, draw_bbox_config=draw_bbox_config, 
        caption_model_processor=caption_model_processor, ocr_text=text, iou_threshold=0.1, imgsz=640
    )
    
    t_parse_end = time.time()
    print(f"OmniParser Parsing Latency: {t_parse_end - t_parse_start:.3f}s")
    
    parsed_content_str = '\n'.join([f'ID {i}: ' + str(v) for i, v in enumerate(parsed_content_list)])
    
    print("Querying Groq (Qwen 32B) for the target element...")
    t_groq_start = time.time()
    target_id_str = get_groq_response(target_text, parsed_content_str, groq_api_key)
    t_groq_end = time.time()
    
    print(f"Groq Latency: {t_groq_end - t_groq_start:.3f}s")
    print(f"Groq Selected ID: {target_id_str}")
    
    if target_id_str and target_id_str.isdigit():
        target_id = int(target_id_str)
        if target_id in label_coordinates:
            coord = label_coordinates[target_id]
            print(f"Success! Element '{target_text}' found at coordinates (ratio): {coord}")
        else:
            print(f"Error: Groq returned ID {target_id} which is out of bounds.")
            
    print("\n--- RESULTS ---")
    print(f"Total Action Latency (Parsing + LLM): {(t_parse_end - t_parse_start) + (t_groq_end - t_groq_start):.3f}s")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 benchmark_omniparser.py <screenshot_path> <target_text>")
        sys.exit(1)
        
    with open("../../click_groq_fast/.env", "r") as f:
        env_content = f.read()
    groq_api_key = None
    for line in env_content.splitlines():
        if line.startswith("GROQ_API_KEY="):
            groq_api_key = line.split("=")[1].strip().strip('"').strip("'")
            break
            
    if not groq_api_key:
        print("Error: GROQ_API_KEY not found in .env")
        sys.exit(1)
        
    image_path = os.path.abspath(sys.argv[1])
    target_text = sys.argv[2]
    
    benchmark_omniparser(image_path, target_text, groq_api_key)

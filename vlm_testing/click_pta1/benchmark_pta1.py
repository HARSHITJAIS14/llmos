import os
import sys
import time
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForCausalLM
import transformers
from transformers.modeling_utils import PreTrainedModel

# Patch transformers PretrainedConfig to support older custom models (like Florence2/PTA-1)
if not hasattr(transformers.configuration_utils.PretrainedConfig, 'forced_bos_token_id'):
    transformers.configuration_utils.PretrainedConfig.forced_bos_token_id = None

# Patch PreTrainedModel __init__ to avoid _supports_sdpa AttributeError in newer transformers
old_init = PreTrainedModel.__init__
def new_init(self, config, *args, **kwargs):
    # Dynamically add the attribute to the instance before __init__ runs
    self.__class__._supports_sdpa = False 
    old_init(self, config, *args, **kwargs)

PreTrainedModel.__init__ = new_init

def benchmark_pta1(image_path, target_text):
    print("Loading AskUI/PTA-1 model...")
    t0 = time.time()
    
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    torch_dtype = torch.float16 if torch.backends.mps.is_available() else torch.float32
    
    # We load the Florence-2 based PTA-1 model
    model = AutoModelForCausalLM.from_pretrained("AskUI/PTA-1", torch_dtype=torch_dtype, trust_remote_code=True).to(device)
    processor = AutoProcessor.from_pretrained("AskUI/PTA-1", trust_remote_code=True)
    
    t1 = time.time()
    print(f"Model Load Latency: {t1 - t0:.3f}s")
    
    print(f"Loading image from {image_path}...")
    image = Image.open(image_path).convert("RGB")
    
    # Setup prompt for object detection
    task_prompt = "<OPEN_VOCABULARY_DETECTION>"
    prompt = task_prompt + target_text
    
    print(f"Tokenizing inputs...")
    t2 = time.time()
    inputs = processor(text=prompt, images=image, return_tensors="pt").to(device, torch_dtype)
    t3 = time.time()
    print(f"Preprocessing Latency: {t3 - t2:.3f}s")
    
    print(f"Generating bounding box for '{target_text}'...")
    t4 = time.time()
    generated_ids = model.generate(
        input_ids=inputs["input_ids"],
        pixel_values=inputs["pixel_values"],
        max_new_tokens=1024,
        do_sample=False,
        num_beams=3,
    )
    t5 = time.time()
    print(f"Inference Latency: {t5 - t4:.3f}s")
    
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    parsed_answer = processor.post_process_generation(generated_text, task=task_prompt, image_size=(image.width, image.height))
    
    print("\n--- RESULTS ---")
    print(f"AskUI/PTA-1 Total Prediction Latency: {t5 - t2:.3f}s")
    print(f"Output:\n{parsed_answer}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 benchmark_pta1.py <screenshot_path> <target_text>")
        sys.exit(1)
        
    image_path = sys.argv[1]
    target_text = sys.argv[2]
    benchmark_pta1(image_path, target_text)

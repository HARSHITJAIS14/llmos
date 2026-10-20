# Training & Model Checkpoints

All fine-tuned model checkpoints (SafeTensors weights, tokenizers, and configs) are hosted publicly on Hugging Face to keep the repository lightweight:

- **Hugging Face Model**: [chhola14bhatoora/screen-understanding-micro-v2](https://huggingface.co/chhola14bhatoora/screen-understanding-micro-v2)
- **Base Architecture**: `Idefics3ForConditionalGeneration` (SmolVLM)
- **Specialization**: Desktop UI localization, accessibility node grounding, and coordinate action prediction.

## Loading the Model
```python
from transformers import AutoProcessor, AutoModelForVision2Seq
import torch

model_id = "chhola14bhatoora/screen-understanding-micro-v2"

processor = AutoProcessor.from_pretrained(model_id)
model = AutoModelForVision2Seq.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
    device_map="auto"
)
```

## Downloading Model Weights Locally
If you need the raw `.safetensors` files locally for training or offline evaluation:
```bash
hf download chhola14bhatoora/screen-understanding-micro-v2 --local-dir screen_understanding/training/runs/micro-train-v2/best
```

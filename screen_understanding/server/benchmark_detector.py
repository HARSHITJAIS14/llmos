"""Measure detector inference on an existing GPU; no desktop actions."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--weights', required=True)
    p.add_argument('--image', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    import torch
    from ultralytics import YOLO
    from PIL import Image
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=False)
    assert torch.cuda.is_available(), 'CUDA required for GPU benchmark'
    image = Image.open(a.image).convert('RGB')
    started = time.perf_counter()
    model = YOLO(a.weights)
    load_seconds = time.perf_counter() - started
    timings = []
    for i in range(4):
        torch.cuda.synchronize()
        started = time.perf_counter()
        result = model.predict(image, imgsz=1280, conf=0.10, iou=0.10, device=0, verbose=False)[0]
        torch.cuda.synchronize()
        timings.append(time.perf_counter() - started)
    elements = [{'label': model.names[int(c)], 'bbox': b, 'confidence': float(s)}
                for b, c, s in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.cls.cpu().tolist(), result.boxes.conf.cpu().tolist())]
    result.save(filename=str(out / 'overlay.jpg'))
    summary = {'gpu': torch.cuda.get_device_name(0), 'torch': torch.__version__, 'image_size': image.size,
               'weights_sha256': hashlib.sha256(Path(a.weights).read_bytes()).hexdigest(),
               'load_seconds': load_seconds, 'first_prediction_seconds': timings[0],
               'warm_prediction_seconds': timings[1:], 'warm_median_seconds': statistics.median(timings[1:]),
               'scope': 'In-memory image preprocessing + detector inference + postprocessing; excludes transfer, disk loading, model load, OCR and semantics',
               'count': len(elements), 'elements': elements}
    (out / 'result.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k != 'elements'}, indent=2))


if __name__ == '__main__':
    main()

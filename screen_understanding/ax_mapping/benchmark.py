"""Mapping-only microbenchmark on saved AX data; NOT a real paired accuracy test."""
import json
import platform
import statistics
import time
from pathlib import Path

from matcher import Frame, associate, normalize_ax


def main():
    root = Path(__file__).resolve().parents[2]
    source = root / 'Ax_analysis/finder/full.json'
    snapshot = json.loads(source.read_text())
    meta = {'capture_bounds': snapshot['data']['tree']['bounds'], 'image_size': [1840, 872]}
    nodes, _ = normalize_ax(snapshot, Frame(meta))
    candidates = [n for n in nodes if n['bbox']]
    report = {'scope': 'In-memory association including AX normalization; excludes file/image IO, capture, AX IPC, detector, OCR and network',
              'fixture': str(source), 'platform': platform.platform(),
              'processor': platform.machine(),
              'accuracy_warning': 'Synthetic regions copied from AX geometry. No real screenshot pairing or accuracy claim.',
              'capture_warning': 'Root bounds assumed ONLY to construct this diagnostic frame; not a calibrated real capture.',
              'runs': []}
    for count in (1, 8, 32, 50):
        regions = [{'id': f'v{i}', 'bbox': n['bbox']} for i, n in enumerate(candidates[:count])]
        if len(regions) != count:
            raise RuntimeError('Not enough fixture candidates')
        for _ in range(3):
            associate(snapshot, regions, meta)
        times = []
        for _ in range(30):
            start = time.perf_counter()
            result = associate(snapshot, regions, meta)
            times.append((time.perf_counter() - start) * 1000)
        report['runs'].append({'regions': count, 'samples': len(times),
                               'ax_nodes': result['ax_observation']['total_nodes'],
                               'projected_nodes': result['ax_observation']['projected_nodes'],
                               'p50_ms': statistics.median(times),
                               'p95_ms': sorted(times)[int(.95 * (len(times)-1))],
                               'max_ms': max(times),
                               'statuses': {s: sum(r['status'] == s for r in result['regions'])
                                            for s in sorted({r['status'] for r in result['regions']})}})
    dest = Path(__file__).with_name('benchmark.json')
    dest.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

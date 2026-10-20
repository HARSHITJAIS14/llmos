"""Capture an existing window and bracket it with native AX reads; no UI actions."""
import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from PIL import Image


def native(*args):
    response = subprocess.run(['agent-desktop', *args], capture_output=True, text=True, timeout=30)
    data = json.loads(response.stdout)
    if not data.get('ok'):
        raise RuntimeError(json.dumps(data.get('error', data)))
    return data


def signature(snapshot):
    def semantic(node):
        return {k: ([semantic(c) for c in v] if k == 'children' else v)
                for k, v in node.items() if k not in {'ref_id'}}
    return hashlib.sha256(json.dumps(semantic(snapshot['data']['tree']), sort_keys=True).encode()).hexdigest()


def capture(app, window_id, out, mode='window', max_depth=14):
    out.mkdir(parents=True, exist_ok=False)
    def window():
        return next(w for w in native('list-windows', '--app', app)['data'] if w['id'] == window_id)
    before_window = window()
    (out / 'window-before.json').write_text(json.dumps(before_window, indent=2))
    t0 = time.time()
    ax_before = native('snapshot', '--app', app, '--window-id', window_id,
                       '--include-bounds', '--max-depth', str(max_depth))
    t1 = time.time()
    (out / 'ax.json').write_text(json.dumps(ax_before, indent=2))
    image_path = out / 'capture.png'
    bounds = before_window['bounds']
    front_checks = []
    def check_frontmost():
        helper = Path(__file__).resolve().parents[2] / 'lsfg/.venv/bin/python'
        r = subprocess.run([str(helper), '-c',
            'from AppKit import NSWorkspace; print(NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier())'],
            check=True, capture_output=True, text=True, timeout=5)
        pid = int(r.stdout.strip())
        front_checks.append(pid)
        if pid != before_window['pid']:
            raise RuntimeError('Region capture refused: target app is not frontmost')
    if mode == 'region':
        check_frontmost()
        if ax_before['data']['tree'].get('bounds') != bounds:
            raise RuntimeError('Region capture refused: AX root and CG bounds differ')
    s0 = time.time()
    # -o excludes the shadow. Capture the exact CGWindow ID; do not crop a display guess.
    target = ['-l', window_id.removeprefix('w-')] if mode == 'window' else [
        '-R' + ','.join(str(int(bounds[k])) for k in ('x','y','width','height'))]
    shot = subprocess.run(['/usr/sbin/screencapture', '-x', '-o', *target, str(image_path)],
                          capture_output=True, timeout=30)
    if shot.returncode:
        (out / 'capture-error.txt').write_text(shot.stderr.decode(errors='replace'))
        raise RuntimeError('Screenshot failed: ' + shot.stderr.decode(errors='replace').strip())
    s1 = time.time()
    if mode == 'region':
        check_frontmost()
    t2 = time.time()
    ax_after = native('snapshot', '--app', app, '--window-id', window_id,
                      '--include-bounds', '--max-depth', str(max_depth))
    t3 = time.time()
    (out / 'ax-after.json').write_text(json.dumps(ax_after, indent=2))
    after_window = window()
    (out / 'window-after.json').write_text(json.dumps(after_window, indent=2))
    image = Image.open(image_path)
    root = ax_before['data']['tree'].get('bounds')
    validation = {'window_geometry_unchanged': bounds == after_window['bounds'],
                  'process_instance_unchanged': before_window.get('process_instance') == after_window.get('process_instance'),
                  'ax_signature_unchanged': signature(ax_before) == signature(ax_after),
                  'ax_root_matches_capture_bounds': root == bounds,
                  'screenshot_sha256': hashlib.sha256(image_path.read_bytes()).hexdigest(),
                  'ax_before_ms': (t1-t0)*1000, 'screenshot_ms': (s1-s0)*1000,
                  'ax_after_ms': (t3-t2)*1000,
                  'capture_mode': mode, 'frontmost_pid_checks': front_checks,
                  'occlusion_note': 'Region capture includes any occluders; frontmost PID alone cannot exclude floating windows.' if mode=='region' else 'Exact native window image',
                  'note': 'Sequential bracketed observations, not an atomic OS snapshot. No action correctness claim.'}
    meta = {'capture_bounds': bounds, 'image_size': list(image.size), 'ax_origin': 'top_left',
            'ax_depth_limit': max_depth,
            'screenshot_time': (s0+s1)/2, 'ax_time': (t0+t1)/2, 'max_skew_ms': 250,
            'screenshot_window_id': window_id, 'ax_window_id': window_id,
            'ax_snapshot_id': ax_before['data'].get('snapshot_id'),
            'validation': validation}
    (out / 'frame.json').write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    return meta


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--app', required=True)
    p.add_argument('--window-id', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--mode', choices=['window','region'], default='window')
    p.add_argument('--max-depth', type=int, default=14)
    a = p.parse_args()
    capture(a.app, a.window_id, a.out, a.mode, a.max_depth)

"""Export existing teacher labels for the one-day micro-caption experiment."""
import argparse
import collections
import hashlib
import json
import shutil
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--inventory', type=Path)
    p.add_argument('--val-app', action='append', default=[])
    p.add_argument('--test-app', action='append', default=[])
    p.add_argument('--previous-export', type=Path, help='Preserve old pixel-group splits across changed representatives')
    args = p.parse_args()
    base = Path(__file__).resolve().parents[1] / 'dataset'
    inventory = args.inventory or base / 'training_inventory/daily_01'
    masks = {(r['screen'], r['node']): r['candidate_for_teacher_supervision']
             for line in (inventory / 'candidate_masks.jsonl').read_text().splitlines()
             for r in [json.loads(line)]}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'images').mkdir()
    from PIL import Image
    seen = set()
    rows = []
    screens = []
    counts = collections.Counter()
    old_splits = {}
    if args.previous_export:
        old_splits = {r['pixel_hash']:r['split'] for r in json.loads((args.previous_export/'screens.json').read_text())}
    for line in (inventory / 'screens.jsonl').read_text().splitlines():
        s = json.loads(line)
        image = Path(s['image'])
        with Image.open(image) as im:
            rgb = im.convert('RGB')
            digest = hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
        if digest in seen:
            counts['duplicate_screens_removed'] += 1
            continue
        seen.add(digest)
        # App-disjoint splits also keep related captures of the same app together.
        split = 'val' if s['app'] in {'Preview',*args.val_app} else 'test' if s['app'] in {'System Settings',*args.test_app} else 'train'
        split = old_splits.get(digest,split)
        rel = f"images/{s['screen']}.png"
        shutil.copyfile(image, args.output / rel)
        a = json.loads(Path(s['annotation']).read_text())
        for n in a['nodes']:
            if not masks.get((s['screen'], n['id']), False):
                continue
            name = n.get('semantic_name')
            if not name or not name.strip():
                counts['missing_name'] += 1
                continue
            rows.append(dict(screen=s['screen'], node=n['id'], image=rel, split=split,
                             app=s['app'], bbox=n['bbox'], role=n['role'],
                             semantic_name=name, description=n['description'],
                             context_description=n['context_description'], teacher_reviewed=False))
            counts[f'{split}_candidate_nodes'] += 1
        screens.append(dict(screen=s['screen'], app=s['app'], split=split, pixel_hash=digest))
        counts[f'{split}_screens'] += 1
    (args.output / 'records.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    (args.output / 'screens.json').write_text(json.dumps(screens, indent=2))
    (args.output / 'summary.json').write_text(json.dumps(dict(counts), indent=2))
    print(json.dumps(dict(counts), indent=2))


if __name__ == '__main__':
    main()

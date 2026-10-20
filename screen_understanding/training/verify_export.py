"""Verify a portable screenshot export before spending GPU time."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
from PIL import Image


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',type=Path,required=True)
    args=parser.parse_args()
    screens=json.loads((args.data/'screens.json').read_text())
    by_screen={r['screen']:r for r in screens}
    assert len(by_screen)==len(screens)
    assert len({r['pixel_hash'] for r in screens})==len(screens)
    for r in screens:
        with Image.open(args.data/'images'/f"{r['screen']}.png") as im:
            rgb=im.convert('RGB')
            digest=hashlib.sha256(str(rgb.size).encode()+rgb.tobytes()).hexdigest()
        assert digest==r['pixel_hash'],f"Pixel mismatch: {r['screen']}"
    counts=collections.Counter()
    for line in (args.data/'records.jsonl').read_text().splitlines():
        r=json.loads(line)
        assert r['split']==by_screen[r['screen']]['split']
        assert (args.data/r['image']).exists()
        counts[r['split']]+=1
    result=dict(verified_screens=len(screens),candidate_nodes=dict(counts),status='passed')
    (args.data/'integrity_verified.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()

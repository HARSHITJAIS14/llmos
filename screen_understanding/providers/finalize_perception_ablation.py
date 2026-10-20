"""Offline coordinate-unit normalization and report rendering; no API calls."""
import argparse
import json
from benchmark_perception_help import ground_metrics, render


def main():
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    cases=json.loads((a.run/'cases.json').read_text());by={c['screen']:c for c in cases}
    for f in (a.run/'responses').glob('*.json'):
        r=json.loads(f.read_text())
        if 'scores' not in r:continue
        if 'strict_scores' not in r:r['strict_scores']=dict(r['scores'])
        r['coordinate_units']={}
        for key,q in by[r['screen']]['truth'].items():
            if q['type']!='box':continue
            value=r['answers'].get(key); normalized=value;units='0–1 as requested'
            if r['provider'].startswith('gemini') and isinstance(value,list) and len(value)==4:
                if all(isinstance(v,(int,float)) and 0<=v<=1000 for v in value) and max(value)>1:
                    normalized=[v/1000 for v in value];units='0–1000; divided by 1000; axis order unchanged'
            r['scores'][key]=dict(type='box',**ground_metrics(normalized,q['bbox']))
            r['coordinate_units'][key]=dict(rule=units,normalized_answer=normalized)
        f.write_text(json.dumps(r,indent=2))
    render(a.run,cases)
    print(json.dumps(json.loads((a.run/'summary.json').read_text()),indent=2))


if __name__=='__main__':main()

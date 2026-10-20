"""Download pinned public model snapshots; never disables TLS verification."""
import json
from pathlib import Path
import requests
import time

root=Path('/data/harshitj23/screen-understanding/models')
specs=[('docling-project/ScreenVLM','ScreenVLM',None),
       ('microsoft/OmniParser-v2.0','OmniParser',['icon_caption/']),
       ('microsoft/Florence-2-base','Florence2processor',['processor'])]
for repo, folder, prefixes in specs:
    r=requests.get(f'https://huggingface.co/api/models/{repo}',timeout=30); r.raise_for_status(); meta=r.json(); rev=meta['sha']
    out=root/folder;out.mkdir(parents=True,exist_ok=True)
    (out/'snapshot.json').write_text(json.dumps({'repo':repo,'revision':rev},indent=2))
    for f in meta['siblings']:
        name=f['rfilename']
        if prefixes==['processor']:
            keep=name.endswith(('.json','.py','.txt','.model')) and not name.endswith('.safetensors')
        else:
            keep=name.endswith(('.json','.py','.txt','.model','.safetensors','.jinja')) and (prefixes is None or any(name.startswith(p) for p in prefixes))
        if not keep: continue
        path=out/name;path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists(): continue
        print(repo,rev,name,flush=True)
        for attempt in range(3):
            try:
                with requests.get(f'https://huggingface.co/{repo}/resolve/{rev}/{name}',stream=True,timeout=(30,120)) as resp:
                    resp.raise_for_status()
                    temp=path.with_suffix(path.suffix+'.partial')
                    with temp.open('wb') as handle:
                        for chunk in resp.iter_content(1024*1024):handle.write(chunk)
                    temp.replace(path)
                break
            except requests.RequestException:
                if attempt==2: raise
                time.sleep(2)
print('Snapshots downloaded.',flush=True)

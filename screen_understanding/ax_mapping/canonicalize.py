"""Conservative, app-independent AX nesting reduction with lossless membership."""
from __future__ import annotations

import hashlib
import json
import time

from matcher import Frame, area, intersection, normalize_ax, rect, evidence

VERSION = 'ax-entities-v1'
CONTROLS = {'button', 'menubutton', 'popupbutton', 'combobox', 'textfield',
            'searchfield', 'textarea', 'checkbox', 'radiobutton', 'tab',
            'slider', 'link', 'switch', 'treeitem', 'cell', 'disclosure'}
WRAPPERS = {'group', 'cell', 'treeitem', 'row', 'container', 'statictext', 'image'}
STRUCTURAL = {'application', 'window', 'dialog', 'group', 'scrollarea', 'splitgroup',
              'toolbar', 'table', 'list', 'outline', 'column', 'row', 'layoutarea'}


def text(n):
    return ' '.join(str(n.get('name') or n.get('description') or '').split())


def family(n):
    return n['role'] if n['role'] in CONTROLS - {'cell', 'treeitem'} else None


def is_control(n):
    return n['role'] in CONTROLS and (n['role'] not in {'cell','treeitem'} or bool(n['actions']))


def ancestor(a, b):
    return b['id'].startswith(a['id'] + '.')


def conflicts(nodes):
    labels = {text(n).casefold() for n in nodes if text(n)}
    if len(labels) > 1:
        return True
    families = {family(n) for n in nodes if family(n)}
    if len(families) > 1:
        return True
    states = {str(s).lower() for n in nodes for s in n['states']}
    if any(a in states and b in states for a,b in [('enabled','disabled'),
           ('checked','unchecked'), ('selected','unselected'), ('expanded','collapsed')]):
        return True
    # Conflicting nonempty values are never discarded through wrapper reduction.
    values = {str(n['value']) for n in nodes if n.get('value') not in (None, '')}
    return len(values) > 1


def canonicalize(snapshot, metadata):
    start = time.perf_counter()
    frame = Frame(metadata)
    nodes, info = normalize_ax(snapshot, frame)
    visible = [n for n in nodes if n['bbox']]
    lookup = {n['id']: n for n in nodes}
    parent = {n['id']: n['id'] for n in visible}
    members = {n['id']: [n] for n in visible}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    merges = []
    # Only ancestor/descendant pairs can coalesce. Equal-geometry siblings stay distinct.
    for child in visible:
        aid = child['parent']
        while aid:
            a = lookup[aid]
            if a['bbox']:
                overlap = area(intersection(a['bbox'], child['bbox']))
                union = area(a['bbox']) + area(child['bbox']) - overlap
                if overlap / union >= .85 and (a['role'] in WRAPPERS or child['role'] in WRAPPERS):
                    x, y = find(aid), find(child['id'])
                    if x != y and not conflicts(members[x] + members[y]):
                        parent[y] = x
                        members[x].extend(members.pop(y))
                        merges.append({'ancestor': aid, 'descendant': child['id'],
                                       'reason': 'nested_iou>=0.85_and_no_semantic_conflict'})
            aid = a['parent']

    entities = []
    for group in members.values():
        # Prefer an explicit control; do not give a text child its parent's actions.
        primary = min(group, key=lambda n: (family(n) is None, not bool(n['actions']),
                                            n['role'] in STRUCTURAL, area(n['bbox']), n['id']))
        label_node = next((n for n in [primary] + group if text(n)), None)
        contexts = []
        aid = primary['parent']
        while aid:
            n = lookup[aid]
            if text(n) and n['id'] not in {g['id'] for g in group}:
                contexts.append({'id': n['id'], 'role': n['role'], 'label': text(n)[:160]})
            aid = n['parent']
        eid = 'E' + primary['id'].replace('.', '_')
        entities.append({'id': eid, 'primary': primary, 'label': text(label_node) if label_node else '',
                         'label_source': label_node['id'] if label_node else None,
                         'member_ids': sorted(n['id'] for n in group),
                         'member_refs': [n['ref'] for n in group if n['ref']],
                         'context': list(reversed(contexts))[-5:], 'kind': 'control' if
                         is_control(primary) else 'context' if primary['role'] in STRUCTURAL else 'content',
                         'overlap_ambiguities': []})
    for entity in entities:
        n = entity['primary']
        # A multi-column/list wrapper remains queryable context, not a duplicated target.
        if n['role'] in {'cell', 'treeitem'} and any(
                ancestor(n, e['primary']) and e['kind'] == 'control'
                and e['id'] != entity['id'] and text(e['primary']) != text(n) for e in entities):
            entity['kind'] = 'context'
            entity['display_reason'] = 'wrapper_contains_distinct_controls; original actions retained'
    controls = [e for e in entities if e['kind'] == 'control']
    for i, a in enumerate(controls):
        for b in controls[i+1:]:
            x,y = a['primary']['bbox'],b['primary']['bbox']
            overlap = area(intersection(x,y))
            if overlap / (area(x)+area(y)-overlap) >= .8:
                a['overlap_ambiguities'].append(b['id'])
                b['overlap_ambiguities'].append(a['id'])
    projected = sorted(({k:n.get(k) for k in ('id','role','name','value','states','actions','bbox')}
                        for n in visible), key=lambda n:n['id'])
    fingerprint = hashlib.sha256(json.dumps(projected,sort_keys=True).encode()).hexdigest()
    validation = metadata.get('validation', {})
    reasons = list(frame.check['reasons'])
    if metadata.get('ax_snapshot_id') is not None and metadata['ax_snapshot_id'] != info['snapshot_id']:
        reasons.append('snapshot_payload_mismatch')
    for key in ('window_geometry_unchanged','process_instance_unchanged','ax_root_matches_capture_bounds'):
        if validation.get(key) is False:
            reasons.append(key)
    if validation.get('visible_ax_signature_unchanged') is False:
        reasons.append('visible_AX_changed_during_capture')
    if (validation.get('ax_signature_unchanged') is False
            and validation.get('visible_ax_signature_unchanged') is not True):
        reasons.append('AX_changed_without_visible_stability_check')
    return {'algorithm': VERSION, 'ax_observation': info, 'entities': entities,
            'all_nodes': nodes, 'merges': merges,
            'capture_status': 'blocked' if reasons else 'unverified',
            'capture_reasons': reasons, 'action_authorized': False,
            'visible_fingerprint': fingerprint,
            'counts': {'projected': len(visible), 'entities': len(entities),
                       'controls': len(controls), 'merged_nodes': len(visible)-len(entities),
                       'ambiguous_controls': sum(bool(e['overlap_ambiguities']) for e in controls)},
            'processing_ms': (time.perf_counter()-start)*1000}


def map_regions(snapshot, metadata, regions):
    """Optional detector/OCR association against the conservative entity graph."""
    graph = canonicalize(snapshot, metadata)
    frame = Frame(metadata)
    links, seen = [], set()
    for region in regions:
        rid = str(region['id'])
        if rid in seen:
            raise ValueError('Duplicate visual region ID: ' + rid)
        seen.add(rid)
        box = rect(region['bbox'])
        item = {'region_id': rid, 'status': 'unmatched', 'entity_id': None, 'candidates': []}
        if graph['capture_status'] == 'blocked':
            item['status'] = 'blocked'
        elif intersection(box, frame.content) != box:
            item['status'] = 'invalid_region'
        else:
            ranked = []
            for e in graph['entities']:
                n = dict(e['primary'], name=e['label'])
                ev = evidence(box, region, n)
                if ev:
                    ranked.append({'entity_id': e['id'], 'evidence': ev})
            ranked.sort(key=lambda c:(-c['evidence']['score'],c['entity_id']))
            item['candidates'] = ranked[:5]
            if ranked:
                score = ranked[0]['evidence']['score']
                margin = score - (ranked[1]['evidence']['score'] if len(ranked)>1 else 0)
                best = next(e for e in graph['entities'] if e['id']==ranked[0]['entity_id'])
                item.update(score=score, margin=margin)
                if score >= .67:
                    if margin < .08 or best['overlap_ambiguities']:
                        item['status'] = 'ambiguous'
                    else:
                        item.update(status='matched', entity_id=best['id'])
        links.append(item)
    return dict(graph, links=links)


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('ax','frame','out'):
        p.add_argument('--'+k, type=Path, required=True)
    p.add_argument('--regions',type=Path)
    a=p.parse_args()
    snapshot=json.loads(a.ax.read_text()); meta=json.loads(a.frame.read_text())
    if a.regions:
        regions=json.loads(a.regions.read_text())
        if isinstance(regions,dict): regions=regions['proposals']
        result=map_regions(snapshot,meta,regions)
    else:
        result=canonicalize(snapshot,meta)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'output':str(a.out),'counts':result['counts'],'status':result['capture_status']}))

"""Offline spatial association, not an action resolver. Pure Python; no model/API."""
from __future__ import annotations

import argparse
import json
import math
import re
import time
from pathlib import Path


def rect(value):
    """Accept xyxy pixel arrays or native AX {x,y,width,height} objects."""
    if isinstance(value, dict):
        x, y = float(value['x']), float(value['y'])
        out = (x, y, x + float(value['width']), y + float(value['height']))
    else:
        out = tuple(map(float, value))
    if len(out) != 4 or not all(math.isfinite(v) for v in out):
        raise ValueError('Expected four finite coordinates')
    if out[2] <= out[0] or out[3] <= out[1]:
        raise ValueError('Rectangle must have positive area')
    return out


def area(b):
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def intersection(a, b):
    return (max(a[0], b[0]), max(a[1], b[1]),
            min(a[2], b[2]), min(a[3], b[3]))


def role(value):
    value = re.sub('[^a-z]', '', str(value).lower())
    return value[2:] if value.startswith('ax') else value


def words(value):
    return set(re.findall(r'\w+', str(value).casefold()))


class Frame:
    """One calibrated affine capture; split mixed-scale monitor captures first."""
    def __init__(self, meta):
        if meta.get('ax_origin', 'top_left') != 'top_left':
            raise ValueError('Convert AX coordinates to top-left global points first')
        if meta.get('mixed_scale_displays', False):
            raise ValueError('Mixed-scale captures need a separate frame per display')
        self.capture = rect(meta['capture_bounds'])
        w, h = map(float, meta['image_size'])
        self.image = rect((0, 0, w, h))
        self.content = rect(meta.get('content_rect', self.image))
        if intersection(self.content, self.image) != self.content:
            raise ValueError('content_rect must lie inside image_size')
        self.sx = (self.content[2] - self.content[0]) / (self.capture[2] - self.capture[0])
        self.sy = (self.content[3] - self.content[1]) / (self.capture[3] - self.capture[1])
        reasons = []
        for key in ('window_id', 'snapshot_id'):
            a, b = meta.get('screenshot_' + key), meta.get('ax_' + key)
            if a is not None and b is not None and a != b:
                reasons.append(key + '_mismatch')
        a, b = meta.get('screenshot_time'), meta.get('ax_time')
        if a is not None and b is not None:
            a, b = float(a), float(b)
            limit = float(meta.get('max_skew_ms', 250))
            if not all(math.isfinite(v) for v in (a, b, limit)) or limit < 0:
                raise ValueError('Invalid timestamps or skew limit')
            skew = abs(a - b) * 1000
            if skew > limit:
                reasons.append('capture_time_skew')
        else:
            skew = None
        self.check = {'status': 'blocked' if reasons else 'unverified',
                      'reasons': reasons, 'skew_ms': skew,
                      'note': 'Time proximity does not establish identical UI or occlusion.'}
        # No setting here authorizes a click. Even matching timestamps need live validation.

    def project(self, box):
        return (self.content[0] + (box[0] - self.capture[0]) * self.sx,
                self.content[1] + (box[1] - self.capture[1]) * self.sy,
                self.content[0] + (box[2] - self.capture[0]) * self.sx,
                self.content[1] + (box[3] - self.capture[1]) * self.sy)


def normalize_ax(snapshot, frame):
    """Adapter for saved agent-desktop snapshot envelopes or a nested raw tree."""
    if snapshot.get('ok') is False:
        raise ValueError('Cannot map a failed AX snapshot')
    data = snapshot.get('data', snapshot)
    tree = data.get('tree', data)
    if not isinstance(tree, dict) or 'role' not in tree:
        raise ValueError('Expected nested AX tree with role fields')
    nodes, frontiers = [], []
    counts = {'invalid_bounds': 0, 'outside_capture': 0, 'hidden': 0}

    def walk(raw, parent=None, path='0', hidden_parent=False):
        states = raw.get('states', [])
        if not isinstance(states, list):
            states = []
        hidden = hidden_parent or raw.get('visible') is False or bool(
            {'hidden', 'invisible', 'offscreen'} & {str(s).lower() for s in states})
        children = raw.get('children', [])
        if raw.get('children_count', len(children)) > len(children):
            frontiers.append(path)
        node = {'id': path, 'ref': raw.get('ref_id'), 'parent': parent,
                'role': role(raw.get('role', 'unknown')),
                'name': str(raw.get('name', '')), 'value': raw.get('value'),
                'description': raw.get('description'), 'states': states,
                'actions': raw.get('available_actions', []), 'bbox': None}
        if hidden:
            counts['hidden'] += 1
        elif raw.get('bounds') is not None:
            try:
                projected = frame.project(rect(raw['bounds']))
                clipped = intersection(projected, frame.content)
                if area(clipped) > 0:
                    node.update(bbox=clipped, full_bbox=projected,
                                visible_fraction=area(clipped) / area(projected))
                else:
                    counts['outside_capture'] += 1
            except (KeyError, TypeError, ValueError):
                counts['invalid_bounds'] += 1
        nodes.append(node)
        for i, child in enumerate(children):
            walk(child, path, f'{path}.{i}', hidden)

    walk(tree)
    info = {'snapshot_id': data.get('snapshot_id'), 'app': data.get('app'),
            'reported_complete': data.get('complete'), 'frontier_count': len(frontiers),
            'frontiers': frontiers[:50], 'filtered': counts,
            'total_nodes': len(nodes), 'projected_nodes': sum(n['bbox'] is not None for n in nodes)}
    return nodes, info


def evidence(box, region, node):
    target = node['bbox']
    overlap = area(intersection(box, target))
    if overlap <= 0:
        return None
    av, aa = area(box), area(target)
    coverage, ax_coverage = overlap / av, overlap / aa
    ratio = min(av, aa) / max(av, aa)
    iou = overlap / (av + aa - overlap)
    # Reject huge ancestors, one-pixel slivers and mere touching edges.
    if (node['role'] in {'window', 'application', 'group', 'scrollarea', 'splitgroup', 'toolbar'}
            and iou < .5):
        return None
    if coverage < .55 or ratio < .08 or min(
            (box[2] - box[0]) / (target[2] - target[0]),
            (target[2] - target[0]) / (box[2] - box[0]),
            (box[3] - box[1]) / (target[3] - target[1]),
            (target[3] - target[1]) / (box[3] - box[1])) < .08:
        return None
    geometry = .65 * coverage + .20 * iou + .15 * math.sqrt(ratio)
    score = geometry
    text_score = None
    # Only observed OCR participates. Generated captions never become matching truth.
    a = words(region.get('ocr_text', ''))
    b = words(' '.join(str(node.get(k) or '') for k in ('name', 'value', 'description')))
    if a and b:
        text_score = len(a & b) / len(a | b)
        score = .85 * score + .15 * text_score
    role_match = None
    if region.get('role'):
        role_match = role(region['role']) == node['role']
        score = .95 * score + .05 * float(role_match)
    return {'score': score, 'geometry': geometry, 'iou': iou,
            'region_coverage': coverage, 'ax_coverage': ax_coverage,
            'area_ratio': ratio, 'ocr_similarity': text_score,
            'role_match': role_match}


def associate(snapshot, regions, metadata, min_score=.67, min_margin=.08):
    start = time.perf_counter()
    frame = Frame(metadata)
    nodes, info = normalize_ax(snapshot, frame)
    declared_id = metadata.get('ax_snapshot_id')
    if declared_id is not None and info['snapshot_id'] != declared_id:
        frame.check['status'] = 'blocked'
        frame.check['reasons'].append('snapshot_payload_mismatch')
    index = {n['id']: n for n in nodes}
    visible = [n for n in nodes if n['bbox'] is not None]

    def public(n):
        return {k: n[k] for k in ('id', 'ref', 'parent', 'role', 'name', 'value',
                                  'description', 'states', 'actions', 'bbox')}

    results = []
    ids = set()
    for region in regions:
        rid = str(region['id'])
        if rid in ids:
            raise ValueError('Duplicate region ID: ' + rid)
        ids.add(rid)
        box = rect(region['bbox'])
        result = {'region_id': rid, 'bbox': box, 'status': 'unmatched',
                  'matched_ax': None, 'action_ancestor': None,
                  'candidates': [], 'contains': [], 'contains_count': 0}
        if intersection(box, frame.content) != box:
            result.update(status='invalid_region', reason='Region extends outside captured content')
            results.append(result)
            continue
        if frame.check['status'] == 'blocked':
            result.update(status='blocked', reason='Capture metadata mismatch')
            results.append(result)
            continue
        candidates, contains = [], []
        for node in visible:
            ev = evidence(box, region, node)
            if ev:
                candidates.append({'ax': public(node), 'evidence': ev})
            overlap = area(intersection(box, node['bbox']))
            if overlap / area(node['bbox']) >= .8 and area(node['bbox']) / area(box) <= .4:
                contains.append(node)
        # Contains is a spatial relation only; keep parent pointers, never merge semantics.
        result['contains_count'] = len(contains)
        result['contains'] = [public(n) for n in contains[:20]]
        candidates.sort(key=lambda c: (-c['evidence']['score'], c['ax']['id']))
        result['candidates'] = candidates[:5]
        if candidates:
            best = candidates[0]
            gap = best['evidence']['score'] - (candidates[1]['evidence']['score'] if len(candidates) > 1 else 0)
            result.update(score=best['evidence']['score'], margin=gap)
            if best['evidence']['score'] < min_score:
                result.update(status='unmatched', reason='Insufficient evidence')
            elif gap < min_margin:
                result.update(status='ambiguous', reason='Several AX nodes fit this region')
            else:
                result.update(status='matched', matched_ax=best['ax'])
                node = index[best['ax']['id']]
                while node:
                    if node['actions']:
                        result['action_ancestor'] = public(node)
                        break
                    node = index.get(node['parent'])
        else:
            result['reason'] = 'No sufficiently overlapping AX node'
        results.append(result)
    linked = {r['matched_ax']['id'] for r in results if r['matched_ax']}
    unassociated = [n for n in visible if n['id'] not in linked]
    return {'version': 1, 'frame_check': frame.check, 'ax_observation': info,
            'unassociated_ax_count': len(unassociated),
            'unassociated_ax': [public(n) for n in unassociated[:50]],
            'action_authorized': False,
            'score_kind': 'heuristic ranking, not calibrated probability',
            'mapping_ms': (time.perf_counter() - start) * 1000,
            'regions': results}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ax', type=Path, required=True)
    p.add_argument('--regions', type=Path, required=True)
    p.add_argument('--frame', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    regions = json.loads(args.regions.read_text())
    if isinstance(regions, dict):
        regions = regions['proposals']
    result = associate(json.loads(args.ax.read_text()), regions, json.loads(args.frame.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'output': str(args.out), 'mapping_ms': result['mapping_ms'],
                      'counts': {s: sum(r['status'] == s for r in result['regions'])
                                 for s in sorted({r['status'] for r in result['regions']})}}))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Framework classifier from tree evidence alone. Ordered if/then rules."""
import json, os, re, collections

BASE = '/Users/harshit/Desktop/YC/Ax_analysis'
APPS = ['antigravity_ide','brave_browser','calendar','claude','discord','finder',
        'firefox','gemini','google_chrome','keynote','microsoft_word','music',
        'notes','notion','obs','reminders','safari','telegram','textedit','utm',
        'vlc','whatsapp','yt_music','zoom_us']

GROUND_TRUTH = {
    'antigravity_ide':'electron','claude':'electron','discord':'electron','notion':'electron',
    'brave_browser':'chromium_browser','google_chrome':'chromium_browser',
    'firefox':'gecko',
    'yt_music':'webkit_webapp',
    'obs':'qt',
    'microsoft_word':'custom_cpp','zoom_us':'custom_cpp',
    'telegram':'opaque_native',
    'calendar':'apple_native','finder':'apple_native','gemini':'apple_native',
    'keynote':'apple_native','music':'apple_native','notes':'apple_native',
    'reminders':'apple_native','safari':'apple_native','textedit':'apple_native',
    'utm':'apple_native','vlc':'apple_native','whatsapp':'apple_native',
}

UUID_RE = re.compile(r'[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$')
VIEW_RE = re.compile(r'view_\d+$')

def load(app, f):
    p = os.path.join(BASE, app, f)
    if not os.path.exists(p): return None
    try: d = json.load(open(p))
    except Exception: return None
    return d['data'] if d.get('ok') and 'tree' in d.get('data', {}) else None

def captures(app):
    # union evidence over all trees of the SAME app (music/forced is a known
    # cross-app contamination: data.app says 'YT Music', filtered generically
    # by checking data['app'] consistency against the majority)
    out = []
    for f in ['skeleton.json','full.json','forced.json','forced_warm.json']:
        d = load(app, f)
        if d: out.append((f, d))
    names = collections.Counter(d.get('app') for _, d in out)
    keep = names.most_common(1)[0][0]
    return [(f, d) for f, d in out if d.get('app') == keep]

def walk(n, inweb=False):
    yield n, inweb
    w = inweb or n.get('role') == 'webarea'
    for c in n.get('children', []):
        yield from walk(c, w)

def extract(app):
    F = dict(n_max=0, webarea=0, dom_id=0, dom_outside_nonview=0, ax_id=0,
             uuid_ax=0, shell_browser_roles=0, root_truncated_childless=False,
             ax_cov=0.0, dotted_share=0.0, shell_nameless_buttons=0)
    best_n = 0
    for fname, d in captures(app):
        t = d['tree']
        n = 0; ax_vals = []; dom_out_nonview = 0; dom = 0; web = 0
        shell_roles = collections.Counter(); nameless_btn = 0
        uuid_ax = 0
        for node, inweb in walk(t):
            n += 1
            r = node.get('role')
            if r == 'webarea': web += 1
            nid = node.get('native_id')
            if isinstance(nid, dict):
                v = str(nid.get('value', ''))
                if nid.get('kind') == 'ax_dom_identifier':
                    dom += 1
                    if not inweb and r != 'webarea' and not VIEW_RE.fullmatch(v):
                        dom_out_nonview += 1
                elif nid.get('kind') == 'ax_identifier':
                    ax_vals.append(v)
                    if UUID_RE.fullmatch(v): uuid_ax += 1
            if not inweb and r != 'webarea':
                shell_roles[r] += 1
                if r == 'button' and not node.get('name'):
                    nameless_btn += 1
        F['n_max'] = max(F['n_max'], n)
        F['webarea'] = max(F['webarea'], web)
        F['dom_id'] = max(F['dom_id'], dom)
        F['dom_outside_nonview'] = max(F['dom_outside_nonview'], dom_out_nonview)
        F['ax_id'] = max(F['ax_id'], len(ax_vals))
        F['uuid_ax'] = max(F['uuid_ax'], uuid_ax)
        F['shell_nameless_buttons'] = max(F['shell_nameless_buttons'], nameless_btn)
        F['shell_browser_roles'] = max(F['shell_browser_roles'],
            sum(shell_roles[r] for r in ('toolbar','tablist','combobox')))
        if n > best_n:
            best_n = n
            cov = len(ax_vals)/n if n else 0
            dotted = [v for v in ax_vals if '.' in v]
            share = 0.0
            if ax_vals and dotted:
                pref = collections.Counter(v.split('.')[0] for v in dotted)
                share = pref.most_common(1)[0][1]/len(ax_vals)
            F['ax_cov'] = cov; F['dotted_share'] = share
        root = t
        if root.get('subtree_truncated') and not root.get('children'):
            F['root_truncated_childless'] = True
    # shell ax_id: ax identifiers only make sense in webarea apps for R4
    return F

def classify(F):
    # R1 OPAQUE: even forced+warm capture yields a childless truncated root
    if F['n_max'] <= 2 and F['root_truncated_childless']:
        return 'opaque_native', 'R1'
    # R1b CUSTOM C++ (zoom-like): uuid-valued ax identifiers — checked before
    # the web branch because Zoom also embeds a small webview (webarea present)
    if F['uuid_ax'] >= 3:
        return 'custom_cpp', 'R1b'
    web = F['webarea'] > 0 or F['dom_id'] > 0
    if web:
        # R2 GECKO: dom identifiers on shell nodes (outside any webarea) whose
        # values are NOT Chromium Views auto-ids (view_<n>)
        if F['dom_outside_nonview'] >= 3:
            return 'gecko', 'R2'
        # R3 WEBKIT WEBAPP: web content + native ax_identifier shell
        if F['ax_id'] >= 2:
            return 'webkit_webapp', 'R3'
        # R4 CHROMIUM BROWSER: browser chrome roles in shell (toolbar/tablist/combobox)
        if F['shell_browser_roles'] >= 2:
            return 'chromium_browser', 'R4'
        # R5 ELECTRON: Chromium host, no browser chrome, no native shell ids
        return 'electron', 'R5'
    # R6 QT: near-total ax_identifier coverage, single dotted objectName root
    if F['ax_cov'] >= 0.5 and F['dotted_share'] >= 0.5:
        return 'qt', 'R6'
    # R8 default: apple native (AppKit/Catalyst/SwiftUI/iWork/custom-with-NS-shell)
    return 'apple_native', 'R8'

if __name__ == '__main__':
    right = 0; rows = []
    for a in APPS:
        F = extract(a)
        pred, rule = classify(F)
        gt = GROUND_TRUTH[a]
        ok = pred == gt
        right += ok
        rows.append((a, gt, pred, rule, ok, F))
        mark = '' if ok else '  <-- MISS'
        print(f"{a:17s} gt={gt:16s} pred={pred:16s} {rule} "
              f"[n={F['n_max']:4d} web={F['webarea']} dom={F['dom_id']:3d} "
              f"domOutNV={F['dom_outside_nonview']:2d} axid={F['ax_id']:3d} "
              f"uuid={F['uuid_ax']} brRoles={F['shell_browser_roles']} "
              f"cov={F['ax_cov']:.2f} dot={F['dotted_share']:.2f} "
              f"noNameBtn={F['shell_nameless_buttons']}]{mark}")
    print(f"\nACCURACY: {right}/{len(APPS)} = {right/len(APPS)*100:.1f}%")

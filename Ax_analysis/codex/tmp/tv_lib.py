import json, os, collections

BASE = '/Users/harshit/Desktop/YC/Ax_analysis'
APPS = ['antigravity_ide','brave_browser','calendar','claude','discord','finder','firefox','gemini','google_chrome','keynote','microsoft_word','music','notes','notion','obs','reminders','safari','telegram','textedit','utm','vlc','whatsapp','yt_music','zoom_us']

def load(app, which='forced.json'):
    p = os.path.join(BASE, app, which)
    if not os.path.exists(p): return None
    try: return json.load(open(p))
    except Exception: return None

def tree_of(d):
    if not isinstance(d, dict): return None
    dd = d.get('data')
    if isinstance(dd, dict): return dd.get('tree')
    return d.get('tree')

def walk(node, depth=0, parent=None):
    if not isinstance(node, dict): return
    yield node, depth, parent
    for k in (node.get('children') or []):
        yield from walk(k, depth+1, node)

def nodes(app, which='forced.json'):
    t = tree_of(load(app, which))
    if t is None: return []
    return list(walk(t))

def best(app):
    """forced if present & non-degenerate else full"""
    ns = nodes(app, 'forced.json')
    nf = nodes(app, 'full.json')
    if len(ns) >= len(nf): return ns, 'forced'
    return nf, 'full'

def meta(app):
    p = os.path.join(BASE, app, 'meta.json')
    if not os.path.exists(p): return {}
    try: return json.load(open(p))
    except Exception: return {}

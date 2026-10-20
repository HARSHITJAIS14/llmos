import json, os, collections

BASE = '/Users/harshit/Desktop/YC/Ax_analysis'

CLASS = {
 'finder':'appkit','calendar':'appkit','notes':'appkit','reminders':'appkit','textedit':'appkit',
 'music':'appkit','safari':'appkit_webkit','yt_music':'wkwebview_webapp','telegram':'appkit_swift',
 'whatsapp':'appkit_swift','gemini':'appkit_swift','vlc':'appkit','utm':'appkit_swift',
 'antigravity_ide':'electron','claude':'electron','discord':'electron','notion':'electron',
 'visual_studio_code':'electron','cursor':'electron','postman':'electron','canva':'electron',
 'brave_browser':'chromium','google_chrome':'chromium','firefox':'gecko',
 'obs':'qt_cef','microsoft_word':'customkit','keynote':'customkit','zoom_us':'customkit',
}

INTERACTIVE_ROLES = {
 'button','link','checkbox','radiobutton','textfield','textarea','popupbutton','menubutton',
 'combobox','slider','incrementor','menuitem','tab','cell','row','treeitem','disclosuretriangle',
 'segmentedcontrol','colorwell','searchfield','stepper','switch','togglebutton','listitem',
 'menubaritem','outline','table','list','radiogroup','tabgroup','checkbox','textbox','browser',
}

CONTAINER_ROLES = {'group','genericcontainer','scrollarea','splitgroup','layoutarea','unknown','region','none','generic'}


def apps():
    out = []
    for d in sorted(os.listdir(BASE)):
        p = os.path.join(BASE, d, 'meta.json')
        if os.path.exists(p):
            out.append(d)
    return out


def load(app, which):
    p = os.path.join(BASE, app, which + '.json')
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p))
    except Exception:
        return None


def tree_of(doc):
    if not doc or not doc.get('ok'):
        return None
    d = doc.get('data') or {}
    return d.get('tree')


def walk(node, depth=0, parent=None, path=()):
    """yield (depth, node, parent, path_of_roles)"""
    yield depth, node, parent, path
    for c in node.get('children') or []:
        yield from walk(c, depth+1, node, path + (node.get('role'),))


def nodes(doc):
    t = tree_of(doc)
    if t is None:
        return []
    return list(walk(t))


def is_interactive(n):
    r = (n.get('role') or '').lower()
    acts = n.get('available_actions') or []
    real = [a for a in acts if a not in ('SetFocus',)]
    return bool(real) or r in ('textfield','textarea','searchfield','combobox','slider','checkbox','radiobutton','popupbutton','menubutton')


def has_action(n):
    acts = n.get('available_actions') or []
    return bool([a for a in acts if a != 'SetFocus'])

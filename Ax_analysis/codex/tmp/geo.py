import sys; sys.path.insert(0,'/Users/harshit/Desktop/YC/Ax_analysis/codex/tmp')
from flat import *
import collections, json
INTER={'button','link','textfield','checkbox','radiobutton','combobox','menubutton','switch','slider','cell','treeitem','row','tab','menuitem','incrementor','disclosure','popupbutton'}
BAD={'music':['forced.json']}  # mislabeled capture
def trees():
    for a in APPS:
        for f in ['full.json','forced.json']:
            if f in BAD.get(a,[]): continue
            n=get(a,f)
            if n: yield a,f,n
def B(r):
    b=r.get('bounds')
    if not b: return None
    return (b['x'],b['y'],b['width'],b['height'])

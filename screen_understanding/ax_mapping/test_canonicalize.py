import unittest
from canonicalize import canonicalize, map_regions
from test_matcher import node, snapshot, frame


class EntityTests(unittest.TestCase):
    def test_nested_equivalent_label_coalesces(self):
        child=node('Save');child['role']='statictext'
        parent=node('Save',children=[child],available_actions=['Click'])
        g=canonicalize(snapshot(parent),frame())
        self.assertEqual(g['counts']['merged_nodes'],1)
        e=next(e for e in g['entities'] if e['label']=='Save')
        self.assertEqual(len(e['member_ids']),2)
        self.assertEqual(e['primary']['role'],'button')
        self.assertEqual(sum(len(e['member_ids']) for e in g['entities']),g['counts']['projected'])

    def test_equal_siblings_never_coalesce(self):
        g=canonicalize(snapshot(node('Save'),node('Save')),frame())
        self.assertEqual(g['counts']['merged_nodes'],0)
        self.assertGreater(g['counts']['ambiguous_controls'],0)
        r=map_regions(snapshot(node('Save'),node('Save')),frame(),[{'id':'v','bbox':[10,10,30,30]}])
        self.assertEqual(r['links'][0]['status'],'ambiguous')

    def test_conflicting_labels_roles_states_and_values_survive(self):
        for overrides in ({'name':'Cancel'},{'role':'checkbox'},
                          {'states':['unchecked']},{'value':'other'}):
            child=node('Save',states=['checked'],value='first');child['role']='statictext';child.update(overrides)
            parent=node('Save',states=['checked'],value='first',children=[child])
            g=canonicalize(snapshot(parent),frame())
            self.assertEqual(g['counts']['merged_nodes'],0)

    def test_repeated_label_retains_group_context(self):
        a=node('Editor',(1,1,45,45),children=[node('Save',(10,10,30,30))]);a['role']='group'
        b=node('Billing',(50,50,95,95),children=[node('Save',(60,60,80,80))]);b['role']='group'
        g=canonicalize(snapshot(a,b),frame())
        saves=[e for e in g['entities'] if e['label']=='Save']
        self.assertEqual(len(saves),2)
        self.assertEqual({e['context'][-1]['label'] for e in saves},{'Editor','Billing'})

    def test_unknown_nesting_remains_explicit(self):
        child=node('Cancel')
        parent=node('Save',children=[child])
        g=canonicalize(snapshot(parent),frame())
        self.assertEqual(g['counts']['merged_nodes'],0)
        self.assertEqual(g['counts']['ambiguous_controls'],2)

    def test_viewport_change_validation(self):
        m=frame(validation={'ax_signature_unchanged':False,'visible_ax_signature_unchanged':True})
        self.assertEqual(canonicalize(snapshot(node()),m)['capture_status'],'unverified')
        m['validation']['visible_ax_signature_unchanged']=False
        self.assertEqual(canonicalize(snapshot(node()),m)['capture_status'],'blocked')

    def test_stale_snapshot_blocks_visual_links(self):
        m=frame(ax_snapshot_id='wrong')
        r=map_regions(snapshot(node()),m,[{'id':'v','bbox':[10,10,30,30]}])
        self.assertEqual(r['links'][0]['status'],'blocked')

    def test_label_child_does_not_get_parent_action(self):
        child=node('Save');child['role']='statictext'
        parent=node('Save',children=[child],available_actions=['Click'])
        g=canonicalize(snapshot(parent),frame())
        rawchild=next(n for n in g['all_nodes'] if n['id']=='0.0.0')
        self.assertEqual(rawchild['actions'],[])
        self.assertFalse(g['action_authorized'])

    def test_data_cell_without_native_actions_is_content(self):
        child=node('Folder');child['role']='cell'
        g=canonicalize(snapshot(child),frame())
        self.assertEqual(next(e for e in g['entities'] if e['label']=='Folder')['kind'],'content')


if __name__=='__main__':unittest.main()

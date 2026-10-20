import hashlib
import unittest

from screen_map import build_map
from test_matcher import node, snapshot, frame


IMAGE=b'test-image-fixture'


def visual(items=None):
    return {'image_sha256':hashlib.sha256(IMAGE).hexdigest(),'image_size':[100,100],
            'source':'synthetic test evidence', 'items':items or [
            {'id':'T1','kind':'text','bbox':[12,12,28,28],'text':'Save','confidence':.95}]}


def execute(tree,meta=None,v=None):
    return build_map(tree,meta or frame(),IMAGE,[100,100],v or visual())


class ScreenMapTests(unittest.TestCase):
    def test_independent_label_and_geometry_support(self):
        r=execute(snapshot(node(available_actions=['Click'])))
        target=next(x for x in r['records'] if x['label']=='Save')
        self.assertEqual(target['status'],'visually_supported')
        self.assertEqual(target['visual_links'][0]['visual_id'],'T1')
        self.assertFalse(target['action_authorized'])
        self.assertEqual(r['coverage']['ax_records'],r['coverage']['accounted_ax_records'])

    def test_hidden_invalid_and_tiny_are_excluded(self):
        hidden=node('Hidden',states=['hidden'],available_actions=['Click'])
        invalid=node('Invalid');invalid['bounds']['height']=0
        tiny=node('Tiny',(10,10,30,11),available_actions=['Click'])
        r=execute(snapshot(hidden,invalid,tiny))
        for label in ('Hidden','Invalid','Tiny'):
            self.assertEqual(next(x for x in r['records'] if x['label']==label)['status'],'excluded')

    def test_disabled_label_never_becomes_supported_target(self):
        r=execute(snapshot(node(states=['disabled'],available_actions=['Click'])))
        self.assertEqual(next(x for x in r['records'] if x['label']=='Save')['status'],'excluded')

    def test_wrong_location_or_text_does_not_match(self):
        for item in ({'id':'T','kind':'text','bbox':[60,60,80,80],'text':'Save','confidence':1},
                     {'id':'T','kind':'text','bbox':[12,12,28,28],'text':'Cancel','confidence':1}):
            r=execute(snapshot(node(available_actions=['Click'])),v=visual([item]))
            self.assertEqual(next(x for x in r['records'] if x['label']=='Save')['status'],'unresolved')

    def test_rightclick_and_scrollto_are_context_not_primary_click(self):
        r=execute(snapshot(node(available_actions=['RightClick','ScrollTo'])))
        n=next(x for x in r['records'] if x['label']=='Save')
        self.assertEqual(n['status'],'context_only')
        self.assertEqual(n['capabilities'],['secondary','reveal'])

    def test_unknown_icon_not_invented_from_pixels(self):
        r=execute(snapshot(node('',available_actions=['Click'])))
        n=next(x for x in r['records'] if x['ax_node_id']=='0.0')
        self.assertEqual(n['status'],'unresolved')
        self.assertIn('unnamed_target',n['review_reasons'])

    def test_overlap_preserves_uncertainty(self):
        r=execute(snapshot(node(available_actions=['Click']),node(available_actions=['Click'])))
        self.assertTrue(all(n['status']=='unresolved' for n in r['records'] if n['label']=='Save'))

    def test_other_image_or_duplicate_evidence_rejected(self):
        v=visual();v['image_sha256']='wrong'
        with self.assertRaises(ValueError):execute(snapshot(node()),v=v)
        v=visual();v['items']*=2
        with self.assertRaises(ValueError):execute(snapshot(node()),v=v)

    def test_global_stale_guard_does_not_erase_diagnostic_links(self):
        r=execute(snapshot(node(available_actions=['Click'])),frame(screenshot_time=1,ax_time=3))
        self.assertEqual(r['capture_status'],'blocked')
        self.assertEqual(next(n for n in r['records'] if n['label']=='Save')['status'],'visually_supported')
        self.assertFalse(r['action_authorized'])

    def test_capture_hash_mismatch_blocks(self):
        r=execute(snapshot(node()),frame(validation={'screenshot_sha256':'bad'}))
        self.assertIn('capture_image_hash_mismatch',r['capture_reasons'])

    def test_shape_supports_geometry_without_inventing_icon_semantics(self):
        v=visual([{'id':'S','kind':'shape_proposal','bbox':[10,10,30,30]}])
        r=execute(snapshot(node('Multiply',available_actions=['Click'])),v=v)
        n=next(n for n in r['records'] if n['label']=='Multiply')
        self.assertEqual(n['status'],'visually_supported')
        self.assertEqual(n['visual_links'][0]['kind'],'shape_geometry')
        self.assertIsNone(n['visual_links'][0]['text_similarity'])

    def test_structural_clickable_wrapper_stays_unresolved(self):
        n=node(available_actions=['Click']);n['role']='group'
        r=execute(snapshot(n))
        self.assertEqual(next(n for n in r['records'] if n['label']=='Save')['status'],'unresolved')


if __name__=='__main__':unittest.main()

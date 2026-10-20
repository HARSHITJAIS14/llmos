import json
import unittest
from pathlib import Path

from matcher import Frame, associate, normalize_ax


def node(name='Save', bounds=(10, 10, 30, 30), **kwargs):
    x, y, x2, y2 = bounds
    return dict(role='button', name=name, ref_id='@snapshot:e1',
                bounds=dict(x=x, y=y, width=x2-x, height=y2-y), **kwargs)


def snapshot(*children):
    return {'data': {'snapshot_id': 'snapshot', 'complete': True,
                     'tree': node('Window', (0, 0, 100, 100), children=list(children))}}


def frame(**kwargs):
    return dict(capture_bounds=[0, 0, 100, 100], image_size=[100, 100], **kwargs)


def run(tree, boxes=None, meta=None):
    return associate(tree, boxes or [{'id': 'v1', 'bbox': [10, 10, 30, 30]}], meta or frame())


class MatchingTests(unittest.TestCase):
    def test_exact_and_parent_action(self):
        child = node('Save label', (10, 10, 30, 30))
        child['role'] = 'statictext'
        parent = node('Save', (8, 8, 32, 32), available_actions=['Click'], children=[child])
        result = run(snapshot(parent))['regions'][0]
        self.assertEqual(result['status'], 'matched')
        self.assertEqual(result['matched_ax']['role'], 'statictext')
        self.assertEqual(result['action_ancestor']['actions'], ['Click'])

    def test_no_overlap_never_snaps(self):
        result = run(snapshot(node(bounds=(60, 60, 80, 80))))['regions'][0]
        self.assertEqual(result['status'], 'unmatched')

    def test_duplicate_geometry_abstains(self):
        result = run(snapshot(node('A'), node('B')))['regions'][0]
        self.assertEqual(result['status'], 'ambiguous')
        self.assertIsNone(result['matched_ax'])

    def test_ocr_can_resolve_duplicate_geometry(self):
        result = run(snapshot(node('Save'), node('Cancel')),
                     [{'id': 'v', 'bbox': [10, 10, 30, 30], 'ocr_text': 'Save'}])['regions'][0]
        self.assertEqual(result['status'], 'matched')
        self.assertEqual(result['matched_ax']['name'], 'Save')

    def test_generated_caption_is_not_matching_evidence(self):
        result = run(snapshot(node('Save'), node('Cancel')),
                     [{'id': 'v', 'bbox': [10, 10, 30, 30], 'caption': 'Save'}])['regions'][0]
        self.assertEqual(result['status'], 'ambiguous')

    def test_two_regions_can_map_to_one_node(self):
        result = run(snapshot(node()), [{'id': 'a', 'bbox': [10, 10, 20, 30]},
                                        {'id': 'b', 'bbox': [20, 10, 30, 30]}])
        self.assertEqual([r['status'] for r in result['regions']], ['matched', 'matched'])
        self.assertEqual(result['regions'][0]['matched_ax']['id'], result['regions'][1]['matched_ax']['id'])

    def test_sliver_is_not_a_target(self):
        result = run(snapshot(node(bounds=(0, 20, 100, 21))))['regions'][0]
        self.assertEqual(result['status'], 'unmatched')

    def test_container_relationship_does_not_imply_identity(self):
        tree = snapshot(node('Save'), node('Cancel', (60, 60, 80, 80)))
        result = run(tree, [{'id': 'group', 'bbox': [5, 5, 85, 85]}])['regions'][0]
        self.assertEqual(result['contains_count'], 2)

    def test_frame_scaling_offset_negative_origin_and_padding(self):
        for scale in (1, 2):
            meta = dict(capture_bounds=[-100, 40, 0, 140], image_size=[100*scale+20, 100*scale+40],
                        content_rect=[10, 20, 100*scale+10, 100*scale+20])
            projected = Frame(meta).project((-90, 50, -70, 70))
            self.assertEqual(projected, (10+10*scale, 20+10*scale, 10+30*scale, 20+30*scale))
        self.assertEqual(Frame(dict(capture_bounds=[0, 0, 100, 100], image_size=[200, 300])).project((10,10,30,30)),
                         (20,30,60,90))

    def test_timestamp_and_window_mismatch_block(self):
        metas = [frame(screenshot_time=10, ax_time=11),
                 frame(screenshot_window_id=1, ax_window_id=2),
                 frame(ax_snapshot_id='wrong')]
        for meta in metas:
            result = run(snapshot(node()), meta=meta)
            self.assertEqual(result['frame_check']['status'], 'blocked')
            self.assertEqual(result['regions'][0]['status'], 'blocked')

    def test_close_timestamp_does_not_authorize_action(self):
        result = run(snapshot(node()), meta=frame(screenshot_time=10, ax_time=10.01))
        self.assertFalse(result['action_authorized'])
        self.assertEqual(result['frame_check']['status'], 'unverified')

    def test_hidden_parent_hides_descendants(self):
        tree = snapshot(node('Hidden', states=['hidden'], children=[node()]))
        result = run(tree)
        self.assertEqual(result['regions'][0]['status'], 'unmatched')
        self.assertEqual(result['ax_observation']['filtered']['hidden'], 2)

    def test_frontier_overrides_complete_claim(self):
        tree = snapshot(node(children_count=10))
        result = run(tree)
        self.assertTrue(result['ax_observation']['reported_complete'])
        self.assertEqual(result['ax_observation']['frontier_count'], 1)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            Frame(frame(mixed_scale_displays=True))
        with self.assertRaises(ValueError):
            Frame(frame(ax_origin='bottom_left'))
        with self.assertRaises(ValueError):
            run(snapshot(node()), [{'id': 'v', 'bbox': [0, 0, float('nan'), 30]}])
        with self.assertRaises(ValueError):
            run(snapshot(node()), [{'id':'v','bbox':[0,0,20,20]}, {'id':'v','bbox':[0,0,20,20]}])
        with self.assertRaises(ValueError):
            run({'ok': False})

    def test_bad_ax_geometry_and_outside_regions(self):
        broken = node()
        broken['bounds']['width'] = 0
        result = run(snapshot(broken))
        self.assertEqual(result['ax_observation']['filtered']['invalid_bounds'], 1)
        self.assertEqual(result['regions'][0]['status'], 'unmatched')
        result = run(snapshot(node()), [{'id': 'v', 'bbox': [-1, 0, 20, 20]}])
        self.assertEqual(result['regions'][0]['status'], 'invalid_region')

    def test_real_saved_finder_snapshot_adapter(self):
        path = Path(__file__).resolve().parents[2] / 'Ax_analysis/finder/full.json'
        if not path.exists():
            self.skipTest('Historical workspace fixture not present')
        tree = json.loads(path.read_text())
        meta = dict(capture_bounds=tree['data']['tree']['bounds'], image_size=[1840, 872])
        nodes, info = normalize_ax(tree, Frame(meta))
        self.assertGreater(info['total_nodes'], 100)
        self.assertGreater(info['projected_nodes'], 0)
        self.assertTrue(any(n['name'] == 'Recents' for n in nodes))


if __name__ == '__main__':
    unittest.main()

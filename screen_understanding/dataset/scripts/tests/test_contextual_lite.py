import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_contextual_lite import valid_box,validate_regions,validate_items,check_chunk

class ValidationTests(unittest.TestCase):
    def test_bad_geometry(self):
        for box in ([0,0,3840,2160],[1,1,1,2],[0,0,float('nan'),2],[0,0,True,2]):
            self.assertFalse(valid_box(box,2940,1912))
        self.assertTrue(valid_box([0,0,2940,1912],2940,1912))
    def test_missing_candidate_is_not_completed(self):
        with self.assertRaises(ValueError):validate_items({'items':[]},['d_0001'],{'r1'})
    def test_unknown_parent_cannot_fall_back_to_root(self):
        item=dict(id='d_0001',status='retained',role='button',surface='native_app_ui',parent='root',description='Search button',context='In toolbar',evidence='Magnifying glass',name='Search',function='Search',selected='unknown',uncertainties=[])
        with self.assertRaises(ValueError):validate_items({'items':[item]},['d_0001'],{'r1'})
        item['parent']='r1';validate_items({'items':[item]},['d_0001'],{'r1'})
    def test_region_cycle(self):
        region=dict(id='r1',parent='r1',bbox_1000=[0,0,1000,1000],role='sidebar',surface='native_app_ui',name='Sidebar',description='Navigation list',context='Left of content')
        with self.assertRaises(ValueError):validate_regions(dict(description='Settings',visible_app_names=['Settings'],regions=[region]))
    def test_bad_parent_quarantined_without_inventing_region(self):
        item=dict(id='d_0001',status='retained',parent='nonexistent',description='Search',context='Toolbar',evidence='Glyph')
        data={'items':[item]}
        check_chunk(data,['d_0001'],{'r1'})
        self.assertEqual(item['status'],'unresolved')
        self.assertEqual(item['parent'],'nonexistent')
        self.assertEqual(item['original_status'],'retained')

if __name__=='__main__':unittest.main()

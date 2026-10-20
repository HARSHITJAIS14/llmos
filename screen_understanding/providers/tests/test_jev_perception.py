import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jev_perception import box_pixels,spatial_relation,validate_answers

class GeometryTests(unittest.TestCase):
    def test_projection(self):
        self.assertEqual(box_pixels({'box':dict(left=.1,top=.2,right=.5,bottom=.6)},(1000,500)),[100,100,500,300])
    def test_reject_invalid_regions(self):
        for left,right in [(float('nan'),.5),(-.1,.5),(.6,.5),(True,.5)]:
            with self.subTest(left=left,right=right),self.assertRaises(ValueError):
                box_pixels({'box':dict(left=left,top=.1,right=right,bottom=.9)},(1000,500))
    def test_parent_overlap_uses_child_area(self):
        self.assertEqual(spatial_relation([0,0,10,10],[0,0,100,100]),1)
        self.assertEqual(spatial_relation([0,0,10,10],[5,0,100,100]),.5)
        self.assertEqual(spatial_relation([0,0,10,10],[20,20,100,100]),0)
    def test_reject_unrecognized_answers(self):
        questions={'role':{'type':'choice','criteria':{'button':'Button'}},'present':{'type':'noul'}}
        self.assertEqual(len(validate_answers({'answers':{'role':{'type':'choice','choice':'invented'},'present':{'type':'noul','noul':2}}},questions)),2)

if __name__=='__main__':unittest.main()

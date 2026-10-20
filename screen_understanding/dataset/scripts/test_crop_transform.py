"""Unit tests for crop coordinate transforms and validation."""
import unittest
from PIL import Image
from crop_transform import (
    CropTransform,
    validate_box,
    clip_box,
    compute_iou,
    compute_containment,
    extract_padded_crop,
)


class TestCropTransform(unittest.TestCase):
    def test_forward_and_inverse_point(self):
        # Origin at (100, 200), padding (10, 20), scale (2.0, 2.0)
        t = CropTransform(source_origin=(100, 200), padding=(10, 20), scale=(2.0, 2.0))
        # source point (150, 250)
        # crop_x = (150 - 100)*2 + 10 = 110
        # crop_y = (250 - 200)*2 + 20 = 120
        cx, cy = t.to_crop_point(150, 250)
        self.assertAlmostEqual(cx, 110.0)
        self.assertAlmostEqual(cy, 120.0)

        # Invert back to source
        sx, sy = t.to_source_point(cx, cy)
        self.assertAlmostEqual(sx, 150.0)
        self.assertAlmostEqual(sy, 250.0)

    def test_box_transform(self):
        t = CropTransform(source_origin=(500, 300), padding=(0, 0), scale=(1.0, 1.0))
        src_box = [520, 310, 600, 450]
        crop_box = t.to_crop_box(src_box)
        self.assertEqual(crop_box, [20, 10, 100, 150])

        inverted_box = t.to_source_box(crop_box)
        self.assertEqual(inverted_box, src_box)

    def test_serialization(self):
        t1 = CropTransform(source_origin=(100, 200), padding=(5, 5), scale=(0.5, 0.5), crop_box_in_source=(100, 200, 300, 400), crop_image_size=(105, 105))
        d = t1.to_dict()
        t2 = CropTransform.from_dict(d)
        self.assertEqual(t1.x0, t2.x0)
        self.assertEqual(t1.y0, t2.y0)
        self.assertEqual(t1.sx, t2.sx)
        self.assertEqual(t1.sy, t2.sy)
        self.assertEqual(t1.px, t2.px)
        self.assertEqual(t1.py, t2.py)

    def test_validation_and_containment(self):
        self.assertTrue(validate_box([10, 10, 100, 100], 1920, 1080))
        self.assertFalse(validate_box([100, 100, 10, 10], 1920, 1080))  # inverted
        self.assertFalse(validate_box([-50, 10, 100, 100], 1920, 1080)) # far out of bounds

        child = [20, 20, 60, 60]
        parent = [0, 0, 100, 100]
        self.assertAlmostEqual(compute_containment(child, parent), 1.0)
        self.assertAlmostEqual(compute_iou([0, 0, 10, 10], [0, 0, 10, 10]), 1.0)

    def test_padded_crop_extraction(self):
        im = Image.new("RGB", (1000, 800), color="white")
        box = [100, 100, 300, 250]
        crop_im, transform = extract_padded_crop(im, box, pad_fraction=0.1, min_pad=10)
        self.assertTrue(crop_im.size[0] > 200)
        self.assertTrue(crop_im.size[1] > 150)
        # Test mapping
        src_box_back = transform.to_source_box(transform.to_crop_box(box))
        for a, b in zip(box, src_box_back):
            self.assertAlmostEqual(a, b)


if __name__ == "__main__":
    unittest.main()

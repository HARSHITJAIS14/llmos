import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from pipeline import project_box, run


class FakeClient:
    def __init__(self):
        self.calls = 0

    def ask(self, prompt, images):
        self.calls += 1
        if self.calls == 1:
            return {"label":"Synthetic test screen", "observations":["test fixture"],
                    "children":[{"label":"Panel <script>", "bbox":[100,100,500,800],
                                 "inspect":True,"reason":"test crop"}]}
        return {"description":"Synthetic reconciliation", "regions":[{"id":"r1","context":"test panel"}],
                "conflicts":[],"unknowns":["region not inspected"]}


class PipelineTests(unittest.TestCase):
    def test_recursive_crop_keeps_global_and_parent_context(self):
        class RecursiveClient:
            def __init__(self):
                self.calls = 0

            def ask(self, prompt, images):
                self.calls += 1
                if self.calls == 1:
                    return {"label":"Screen", "children":[{"label":"Panel", "bbox":[100,100,500,800], "inspect":True}]}
                if self.calls == 2:
                    self_detail = images[-1]
                    assert len(images) == 3
                    assert self_detail.size == (104,92)
                    return {"label":"Panel", "children":[{"label":"Child", "bbox":[200,200,600,600], "inspect":True}]}
                return {"description":"Done", "regions":[], "unknowns":[], "conflicts":[]}

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "crops").mkdir()
            result = run(Image.new("RGB", (200,100)), out, RecursiveClient(), max_depth=1)
            self.assertEqual(result["analysis_count"], 2)
            self.assertEqual(result["regions"][2]["box"], [29,18,70,55])
            self.assertEqual(result["regions"][2]["status"], "uninspected")

    def test_inspect_all_overrides_model_skip_with_budget(self):
        class SkipClient:
            def __init__(self):
                self.calls = 0
            def ask(self, prompt, images):
                self.calls += 1
                if self.calls == 1:
                    return {"label":"Screen", "children":[{"label":"Panel", "bbox":[100,100,500,800], "inspect":False}]}
                if self.calls == 2:
                    return {"label":"Panel", "children":[]}
                return {"description":"Done", "regions":[]}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "crops").mkdir()
            result = run(Image.new("RGB", (200,100)), out, SkipClient(), max_depth=1, max_regions=2, inspect_all=True)
            self.assertEqual(result["analysis_count"], 2)
            self.assertEqual(result["regions"][1]["status"], "analyzed")

    def test_crop_coordinates_include_offset_and_parent_clip(self):
        self.assertEqual(project_box([0,0,500,500], [80,80,320,320], [100,100,300,300]),
                         [100,100,200,200])

    def test_reject_bad_geometry(self):
        for box in ([0,0,1000,1000], [900,0,100,100], [0,0,float("nan"),10], [-1,0,4,8]):
            with self.assertRaises(ValueError):
                project_box(box, [0,0,100,100], [0,0,100,100])

    def test_bounded_run_preserves_uninspected_and_escapes_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "crops").mkdir()
            client = FakeClient()
            result = run(Image.new("RGB", (200,100), "white"), out, client, max_regions=1)
            self.assertEqual(client.calls, 2)
            self.assertEqual(result["uninspected_ids"], ["r1"])
            self.assertEqual(result["regions"][1]["box"], [20,10,100,80])
            self.assertNotIn("<script>", (out / "report.html").read_text())
            self.assertEqual(json.loads((out / "tree.json").read_text())["analysis_count"], 1)


if __name__ == "__main__":
    unittest.main()

"""Run with: python -m unittest discover -s skills/8signal-linkedin-growth-analyst/scripts"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("analyze_posts", Path(__file__).with_name("analyze_posts.py"))
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class AnalyzerTests(unittest.TestCase):
    def test_true_median_missing_metrics_and_deduplication(self):
        rows = [
            {"url": "https://www.linkedin.com/posts/a?trk=x", "reactions": "1", "comments": "0", "reposts": "0", "text": "A"},
            {"url": "https://www.linkedin.com/posts/b", "reactions": "2", "comments": "0", "reposts": "0", "text": "B"},
            {"url": "https://www.linkedin.com/posts/c", "reactions": "99", "comments": "0", "reposts": "0", "text": "C"},
            {"url": "https://www.linkedin.com/posts/a", "reactions": "1000", "comments": "0", "reposts": "0"},
            {"url": "https://www.linkedin.com/posts/d", "reactions": "0", "comments": "", "reposts": "0"},
        ]
        result = module.analyze(rows)
        self.assertEqual(result["posts_observed"], 4)
        self.assertEqual(result["duplicates_removed"], 1)
        self.assertEqual(result["median_visible_interactions"], 2)
        self.assertEqual(result["coverage"]["visible_interactions"], 3)
        self.assertIsNone(result["posts"][-1]["visible_interactions"])

    def test_nested_json_bom_and_even_median(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.json"
            path.write_text("\ufeff" + json.dumps({"posts": [
                {"linkedinUrl": "https://linkedin.com/posts/a", "engagement": {"likes": 2, "comments": 0, "shares": 0}},
                {"linkedinUrl": "https://linkedin.com/posts/b", "engagement": {"likes": 4, "comments": 0, "shares": 0}},
            ]}), encoding="utf-8")
            result = module.analyze(module.read_rows(path))
            self.assertEqual(result["median_visible_interactions"], 3)

    def test_csv_bom_date_and_windows_style_paths(self):
        with tempfile.TemporaryDirectory(prefix="LinkedIn audit ") as directory:
            path = Path(directory) / "Posts Export.csv"
            path.write_text("\ufeffurl,published_at,text,reactions,comments,reposts\nhttps://linkedin.com/posts/a,2026-09-20,Hi,0,0,0\n", encoding="utf-8")
            result = module.analyze(module.read_rows(path))
            self.assertEqual(result["observed_date_range"]["first"], "2026-09-20T00:00:00")
            self.assertEqual(result["median_visible_interactions"], 0)


if __name__ == "__main__":
    unittest.main()

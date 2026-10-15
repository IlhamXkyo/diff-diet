import json
import unittest
from diff_diet.compressor import DiffCompressor
from diff_diet.formatter import format_diff, format_json, format_prompt
from diff_diet.parser import parse_unified_diff

DIFF_SAMPLE = """diff --git a/src/main.py b/src/main.py
index 1234567..89abcdef 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,4 @@
 def main():
-    pass
+    print("hello world")
+    return 0
"""


class TestFormatter(unittest.TestCase):
    def setUp(self):
        report = parse_unified_diff(DIFF_SAMPLE)
        compressor = DiffCompressor()
        self.compressed = compressor.compress(report)

    def test_format_diff(self):
        diff_out = format_diff(self.compressed)
        self.assertIn("diff --git a/src/main.py b/src/main.py", diff_out)
        self.assertIn('+    print("hello world")', diff_out)

    def test_format_prompt(self):
        prompt_out = format_prompt(self.compressed, review_goal="Verify return code")
        self.assertIn("# Code Change Summary & Review Context", prompt_out)
        self.assertIn("`src/main.py`", prompt_out)
        self.assertIn("Verify return code", prompt_out)
        self.assertIn("```diff", prompt_out)

    def test_format_json(self):
        json_out = format_json(self.compressed)
        data = json.loads(json_out)
        self.assertIn("stats", data)
        self.assertIn("files", data)
        self.assertEqual(len(data["files"]), 1)
        self.assertEqual(data["files"][0]["path"], "src/main.py")
        self.assertEqual(data["files"][0]["additions"], 2)


if __name__ == "__main__":
    unittest.main()

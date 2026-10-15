import unittest
from diff_diet.compressor import DiffCompressor, estimate_tokens
from diff_diet.parser import parse_unified_diff

COMPLEX_DIFF = """diff --git a/package-lock.json b/package-lock.json
index 1111111..2222222 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -10,6 +10,10 @@
+    "foo": "1.0.0",
+    "bar": "2.0.0",
+    "baz": "3.0.0",
+    "qux": "4.0.0"
diff --git a/src/core.py b/src/core.py
index 3333333..4444444 100644
--- a/src/core.py
+++ b/src/core.py
@@ -1,10 +1,10 @@
 context 1
 context 2
 context 3
-old line
+new line
 context 4
 context 5
 context 6
diff --git a/README.md b/README.md
index 5555555..6666666 100644
--- a/README.md
+++ b/README.md
@@ -1,3 +1,4 @@
 # Title
-old doc
+new doc
"""


class TestCompressor(unittest.TestCase):
    def test_noise_suppression(self):
        report = parse_unified_diff(COMPLEX_DIFF)
        compressor = DiffCompressor(suppress_noise=True)
        compressed = compressor.compress(report)

        files_map = {f.display_path: f for f in compressed.files}
        self.assertTrue(files_map["package-lock.json"].is_suppressed)
        self.assertIn("lockfile", files_map["package-lock.json"].suppress_reason)
        self.assertFalse(files_map["src/core.py"].is_suppressed)
        self.assertFalse(files_map["README.md"].is_suppressed)

    def test_context_lines_shrink(self):
        report = parse_unified_diff(COMPLEX_DIFF)
        compressor = DiffCompressor(max_context_lines=1)
        compressed = compressor.compress(report)

        core_file = [f for f in compressed.files if f.display_path == "src/core.py"][0]
        hunk = core_file.hunks[0]
        context_lines = [l for l in hunk.lines if l.origin == " "]
        # Max context lines is 1, so leading has 1 and trailing has 1
        self.assertEqual(len(context_lines), 2)

    def test_token_budget_enforcement(self):
        report = parse_unified_diff(COMPLEX_DIFF)
        # Set a very tight token budget
        compressor = DiffCompressor(token_budget=50, suppress_noise=True)
        compressed = compressor.compress(report)

        self.assertIsNotNone(compressed.stats)
        st = compressed.stats
        self.assertGreater(st.saved_tokens, 0)
        self.assertGreater(st.compression_ratio_percent, 0.0)

    def test_estimate_tokens(self):
        self.assertEqual(estimate_tokens(""), 0)
        tokens = estimate_tokens("def hello_world(): return True")
        self.assertGreater(tokens, 0)


if __name__ == "__main__":
    unittest.main()

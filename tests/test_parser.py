import unittest
from diff_diet.parser import parse_unified_diff

SAMPLE_DIFF = """diff --git a/src/math.py b/src/math.py
index e69de29..49b389b 100644
--- a/src/math.py
+++ b/src/math.py
@@ -1,4 +1,6 @@ def add(a, b):
 context before
-return a - b
+return a + b
+return abs(a + b)
 context after
diff --git a/src/new_file.py b/src/new_file.py
new file mode 100644
index 0000000..f9821a3
--- /dev/null
+++ b/src/new_file.py
@@ -0,0 +1,2 @@
+def brand_new():
+    pass
"""


class TestParser(unittest.TestCase):
    def test_parse_multi_file_diff(self):
        report = parse_unified_diff(SAMPLE_DIFF)
        self.assertEqual(len(report.files), 2)

        file1 = report.files[0]
        self.assertEqual(file1.old_path, "src/math.py")
        self.assertEqual(file1.new_path, "src/math.py")
        self.assertEqual(len(file1.hunks), 1)
        self.assertEqual(file1.additions, 2)
        self.assertEqual(file1.deletions, 1)

        hunk1 = file1.hunks[0]
        self.assertEqual(hunk1.func_context, "def add(a, b):")
        self.assertFalse(hunk1.is_whitespace_only())

        file2 = report.files[1]
        self.assertEqual(file2.old_path, "/dev/null")
        self.assertEqual(file2.new_path, "src/new_file.py")
        self.assertTrue(file2.is_new)
        self.assertEqual(file2.additions, 2)
        self.assertEqual(file2.deletions, 0)

    def test_whitespace_only_hunk(self):
        diff_whitespace = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
-def foo(): 
+def foo():
"""
        report = parse_unified_diff(diff_whitespace)
        self.assertEqual(len(report.files), 1)
        hunk = report.files[0].hunks[0]
        self.assertTrue(hunk.is_whitespace_only())


if __name__ == "__main__":
    unittest.main()

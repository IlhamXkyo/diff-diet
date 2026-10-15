import io
import sys
import unittest
from unittest.mock import patch

from diff_diet import __version__
from diff_diet.cli import build_parser, main

DIFF_INPUT = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
 def run():
+    print("starting")
     return True
"""


class TestCLI(unittest.TestCase):
    def test_parser_defaults(self):
        parser = build_parser()
        args = parser.parse_args([])
        self.assertEqual(args.format, "prompt")
        self.assertEqual(args.context, 2)
        self.assertFalse(args.staged)
        self.assertIsNone(args.budget)

    def test_cli_execution_with_stdin(self):
        with patch("diff_diet.cli.read_stdin", return_value=DIFF_INPUT):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                code = main(["--format", "diff"])
                self.assertEqual(code, 0)
                out = mock_stdout.getvalue()
                self.assertIn("diff --git a/app.py b/app.py", out)
                self.assertIn('+    print("starting")', out)

    def test_cli_json_format(self):
        with patch("diff_diet.cli.read_stdin", return_value=DIFF_INPUT):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                code = main(["--format", "json"])
                self.assertEqual(code, 0)
                out = mock_stdout.getvalue()
                self.assertIn('"path": "app.py"', out)

    def test_cli_empty_diff(self):
        with patch("diff_diet.cli.read_stdin", return_value=""):
            code = main([])
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()

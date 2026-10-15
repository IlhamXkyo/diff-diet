"""Command-line interface for diff-diet."""

import argparse
import os
import platform
import subprocess
import sys
from typing import List, Optional

from diff_diet import __version__
from diff_diet.compressor import DiffCompressor
from diff_diet.formatter import format_diff, format_json, format_prompt
from diff_diet.git_util import (
    is_git_installed,
    is_inside_git_repo,
    read_stdin,
    run_git_diff,
)
from diff_diet.parser import parse_unified_diff


def copy_to_clipboard(text: str) -> bool:
    """Copies text to the system clipboard using native OS utilities."""
    system = platform.system()
    try:
        if system == "Windows":
            # Use clip.exe or PowerShell
            proc = subprocess.Popen(
                ["clip.exe"],
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            proc.communicate(input=text)
            return proc.returncode == 0
        elif system == "Darwin":
            proc = subprocess.Popen(
                ["pbcopy"],
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            proc.communicate(input=text)
            return proc.returncode == 0
        elif system == "Linux":
            # Try xclip or wl-copy
            for tool, args in [("wl-copy", []), ("xclip", ["-selection", "clipboard"])]:
                try:
                    proc = subprocess.Popen(
                        [tool] + args,
                        stdin=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    proc.communicate(input=text)
                    if proc.returncode == 0:
                        return True
                except FileNotFoundError:
                    continue
        return False
    except Exception:
        return False


def build_parser() -> argparse.ArgumentParser:
    """Constructs the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="diff-diet",
        description="Compress, filter, and budget Git diffs for LLMs, code reviews, and AI agents.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  git diff | diff-diet                    # Pipe git diff to generate LLM markdown review prompt
  diff-diet                               # Run diff-diet directly on unstaged working tree
  diff-diet --staged                      # Review staged changes
  diff-diet --budget 3000                 # Cap diff to 3000 tokens, prioritizing high-signal files
  diff-diet HEAD~1 --format diff          # Output cleaned unified diff for previous commit
  diff-diet --copy                        # Copy LLM review prompt directly to clipboard
  diff-diet origin/main...HEAD -f json    # Generate structured JSON for CI/CD pipelines
""",
    )

    parser.add_argument(
        "git_args",
        nargs="*",
        help="Optional revisions, branches, or file paths passed to git diff (e.g. HEAD~1, main..feature, src/)",
    )
    parser.add_argument(
        "-s",
        "--staged",
        "--cached",
        action="store_true",
        help="Diff staged/cached changes instead of working tree",
    )
    parser.add_argument(
        "-b",
        "--budget",
        type=int,
        default=None,
        metavar="TOKENS",
        help="Target LLM token budget limit (e.g. 2000, 4000, 8000)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["prompt", "diff", "json"],
        default="prompt",
        help="Output format: 'prompt' (LLM Markdown, default), 'diff' (unified diff), 'json' (structured data)",
    )
    parser.add_argument(
        "-c",
        "--context",
        type=int,
        default=2,
        metavar="LINES",
        help="Maximum surrounding context lines per change hunk (default: 2)",
    )
    parser.add_argument(
        "-w",
        "--ignore-whitespace",
        action="store_true",
        help="Strip and ignore whitespace-only changes",
    )
    parser.add_argument(
        "--include-noise",
        action="store_true",
        help="Do not suppress high-noise files (lockfiles, sourcemaps, minified assets)",
    )
    parser.add_argument(
        "-g",
        "--goal",
        type=str,
        default="",
        metavar="TEXT",
        help="Custom goal or instructions to include in the review prompt",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        metavar="FILE",
        help="Write output to a file instead of stdout",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy output directly to clipboard",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print compression and token statistics to stderr",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Step 1: Obtain diff input (piped stdin or git execution)
    diff_input = read_stdin()

    if diff_input is None:
        if not is_git_installed():
            sys.stderr.write("Error: 'git' is not installed or not found in system PATH.\n")
            return 1

        if not is_inside_git_repo():
            sys.stderr.write("Error: Not inside a Git repository. Pass piped diff via stdin or run inside a git repo.\n")
            return 1

        stdout, stderr, code = run_git_diff(
            args=args.git_args,
            staged=args.staged,
            context_lines=args.context,
            ignore_whitespace=args.ignore_whitespace,
        )
        if code != 0:
            if stderr:
                sys.stderr.write(f"git diff error: {stderr}\n")
            return code
        diff_input = stdout

    if not diff_input.strip():
        sys.stderr.write("No changes detected in diff.\n")
        return 0

    # Step 2: Parse unified diff into AST
    report = parse_unified_diff(diff_input)
    if not report.files:
        sys.stderr.write("No file changes found in provided diff.\n")
        return 0

    # Step 3: Compress according to options
    compressor = DiffCompressor(
        token_budget=args.budget,
        suppress_noise=not args.include_noise,
        ignore_whitespace=args.ignore_whitespace,
        max_context_lines=args.context,
    )
    compressed = compressor.compress(report)

    # Step 4: Format output
    if args.format == "diff":
        output_text = format_diff(compressed)
    elif args.format == "json":
        output_text = format_json(compressed)
    else:
        output_text = format_prompt(compressed, review_goal=args.goal)

    # Step 5: Optional stats display
    if args.stats and compressed.stats:
        st = compressed.stats
        sys.stderr.write(
            f"[diff-diet stats] Files: {st.total_files} | Reviewed: {st.included_files} | "
            f"Suppressed: {st.suppressed_files} | Omitted: {st.omitted_files}\n"
            f"[diff-diet stats] Tokens: ~{st.compressed_tokens:,} (from ~{st.original_tokens:,}, "
            f"saved ~{st.saved_tokens:,} / {st.compression_ratio_percent}%)\n"
        )

    # Step 6: Output destination (clipboard, file, or stdout)
    if args.copy:
        copied = copy_to_clipboard(output_text)
        if copied:
            sys.stderr.write("Copied diff-diet output to clipboard.\n")
        else:
            sys.stderr.write("Warning: Failed to copy to clipboard.\n")

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_text)
            sys.stderr.write(f"Wrote output to {args.output}\n")
        except Exception as e:
            sys.stderr.write(f"Error writing to output file: {e}\n")
            return 1
    else:
        sys.stdout.write(output_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())

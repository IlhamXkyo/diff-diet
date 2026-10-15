"""Git interaction utilities and subprocess runner."""

import os
import subprocess
import sys
from typing import List, Optional, Tuple


def is_git_installed() -> bool:
    """Checks whether the git executable is available in PATH."""
    try:
        res = subprocess.run(
            ["git", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return res.returncode == 0
    except (FileNotFoundError, OSError):
        return False


def is_inside_git_repo(cwd: Optional[str] = None) -> bool:
    """Checks whether the specified directory is inside a Git repository."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return res.returncode == 0 and res.stdout.strip() == "true"
    except (FileNotFoundError, OSError):
        return False


def run_git_diff(
    args: Optional[List[str]] = None,
    staged: bool = False,
    context_lines: Optional[int] = None,
    ignore_whitespace: bool = False,
    cwd: Optional[str] = None,
) -> Tuple[str, str, int]:
    """Executes git diff with specified arguments and returns (stdout, stderr, returncode)."""
    cmd = ["git", "diff"]

    if staged:
        cmd.append("--staged")

    if context_lines is not None:
        cmd.append(f"-U{context_lines}")

    if ignore_whitespace:
        cmd.append("-w")

    if args:
        cmd.extend(args)

    try:
        res = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return res.stdout, res.stderr, res.returncode
    except Exception as e:
        return "", str(e), 1


def read_stdin() -> Optional[str]:
    """Reads all input from sys.stdin if data is being piped in."""
    if not sys.stdin.isatty():
        try:
            return sys.stdin.read()
        except Exception:
            return None
    return None

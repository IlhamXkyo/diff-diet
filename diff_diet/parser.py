"""Streaming unified diff parser producing structured AST for compression."""

from dataclasses import dataclass, field
import re
from typing import List, Optional


@dataclass
class DiffLine:
    origin: str  # '+', '-', ' ', '\\'
    content: str

    def to_unified(self) -> str:
        return f"{self.origin}{self.content}"


@dataclass
class Hunk:
    header: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    func_context: str
    lines: List[DiffLine] = field(default_factory=list)

    @property
    def additions_count(self) -> int:
        return sum(1 for line in self.lines if line.origin == "+")

    @property
    def deletions_count(self) -> int:
        return sum(1 for line in self.lines if line.origin == "-")

    def is_whitespace_only(self) -> bool:
        """Determines if the additions and deletions in this hunk differ only by whitespace."""
        added = [line.content.strip() for line in self.lines if line.origin == "+"]
        deleted = [line.content.strip() for line in self.lines if line.origin == "-"]
        return added == deleted


@dataclass
class DiffFile:
    old_path: str
    new_path: str
    is_new: bool = False
    is_deleted: bool = False
    is_binary: bool = False
    is_rename: bool = False
    file_mode: Optional[str] = None
    hunks: List[Hunk] = field(default_factory=list)
    raw_headers: List[str] = field(default_factory=list)

    @property
    def display_path(self) -> str:
        if self.new_path and self.new_path != "/dev/null":
            return self.new_path
        return self.old_path

    @property
    def additions(self) -> int:
        return sum(hunk.additions_count for hunk in self.hunks)

    @property
    def deletions(self) -> int:
        return sum(hunk.deletions_count for hunk in self.hunks)


@dataclass
class DiffReport:
    files: List[DiffFile] = field(default_factory=list)

    @property
    def total_additions(self) -> int:
        return sum(f.additions for f in self.files)

    @property
    def total_deletions(self) -> int:
        return sum(f.deletions for f in self.files)

    @property
    def total_files(self) -> int:
        return len(self.files)


# Regex pattern to match hunk headers: @@ -10,6 +10,8 @@ optional context
HUNK_HEADER_RE = re.compile(
    r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@\s*(.*)$"
)

# Regex pattern for git diff file headers
DIFF_GIT_RE = re.compile(r"^diff --git\s+(?:a/)?(.*?)\s+(?:b/)?(.*)$")


def parse_unified_diff(diff_text: str) -> DiffReport:
    """Parses unified diff text into a structured DiffReport object."""
    report = DiffReport()
    lines = diff_text.splitlines()
    i = 0
    total = len(lines)

    current_file: Optional[DiffFile] = None
    current_hunk: Optional[Hunk] = None

    while i < total:
        line = lines[i]

        # Match start of a new file diff
        if line.startswith("diff --git"):
            match = DIFF_GIT_RE.match(line)
            if match:
                old_p = match.group(1).strip()
                new_p = match.group(2).strip()
            else:
                old_p = "unknown"
                new_p = "unknown"

            current_file = DiffFile(old_path=old_p, new_path=new_p)
            current_file.raw_headers.append(line)
            report.files.append(current_file)
            current_hunk = None
            i += 1
            continue

        # If inside file header
        if current_file is not None and current_hunk is None:
            if line.startswith("new file mode"):
                current_file.is_new = True
                current_file.raw_headers.append(line)
                i += 1
                continue
            elif line.startswith("deleted file mode"):
                current_file.is_deleted = True
                current_file.raw_headers.append(line)
                i += 1
                continue
            elif line.startswith("similarity index") or line.startswith("rename from") or line.startswith("rename to"):
                current_file.is_rename = True
                current_file.raw_headers.append(line)
                i += 1
                continue
            elif line.startswith("Binary files ") or "GIT binary patch" in line:
                current_file.is_binary = True
                current_file.raw_headers.append(line)
                i += 1
                continue
            elif line.startswith("--- "):
                path_part = line[4:].strip()
                if path_part.startswith("a/"):
                    current_file.old_path = path_part[2:]
                elif path_part == "/dev/null":
                    current_file.old_path = "/dev/null"
                    current_file.is_new = True
                else:
                    current_file.old_path = path_part
                current_file.raw_headers.append(line)
                i += 1
                continue
            elif line.startswith("+++ "):
                path_part = line[4:].strip()
                if path_part.startswith("b/"):
                    current_file.new_path = path_part[2:]
                elif path_part == "/dev/null":
                    current_file.new_path = "/dev/null"
                    current_file.is_deleted = True
                else:
                    current_file.new_path = path_part
                current_file.raw_headers.append(line)
                i += 1
                continue
            elif line.startswith("index "):
                current_file.raw_headers.append(line)
                i += 1
                continue

        # Check for Hunk header
        hunk_match = HUNK_HEADER_RE.match(line)
        if hunk_match and current_file is not None:
            old_start = int(hunk_match.group(1))
            old_count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
            new_start = int(hunk_match.group(3))
            new_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1
            func_ctx = hunk_match.group(5).strip()

            current_hunk = Hunk(
                header=line,
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                func_context=func_ctx,
            )
            current_file.hunks.append(current_hunk)
            i += 1
            continue

        # If inside a hunk
        if current_hunk is not None:
            if line and line[0] in ("+", "-", " ", "\\"):
                origin = line[0]
                content = line[1:]
                current_hunk.lines.append(DiffLine(origin=origin, content=content))
                i += 1
                continue
            elif line == "":
                # Empty line in hunk is treated as context line
                current_hunk.lines.append(DiffLine(origin=" ", content=""))
                i += 1
                continue

        # Unrecognized line or transition without diff --git
        i += 1

    return report

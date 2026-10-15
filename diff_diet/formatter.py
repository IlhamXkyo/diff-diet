"""Formatters for prompt markdown, unified diff, and JSON outputs."""

import json
from typing import Dict, Any

from diff_diet.compressor import CompressedReport


def format_diff(report: CompressedReport) -> str:
    """Formats the compressed report back into a clean Unified Diff string."""
    output_lines = []

    for file in report.files:
        if file.is_suppressed:
            output_lines.append(f"# [diff-diet: {file.display_path} - {file.suppress_reason}]")
            output_lines.append("")
            continue

        if file.is_omitted:
            output_lines.append(f"# [diff-diet: {file.display_path} - {file.omitted_reason}]")
            output_lines.append("")
            continue

        orig = file.original_file
        output_lines.append(f"diff --git a/{orig.old_path} b/{orig.new_path}")
        if orig.is_new:
            output_lines.append("new file mode 100644")
            output_lines.append("--- /dev/null")
            output_lines.append(f"+++ b/{orig.new_path}")
        elif orig.is_deleted:
            output_lines.append("deleted file mode 100644")
            output_lines.append(f"--- a/{orig.old_path}")
            output_lines.append("+++ /dev/null")
        else:
            output_lines.append(f"--- a/{orig.old_path}")
            output_lines.append(f"+++ b/{orig.new_path}")

        for hunk in file.hunks:
            output_lines.append(hunk.header)
            for line in hunk.lines:
                output_lines.append(line.to_unified())

        output_lines.append("")

    return "\n".join(output_lines).rstrip() + "\n"


def format_prompt(report: CompressedReport, review_goal: str = "") -> str:
    """Formats the compressed diff into a structured Markdown prompt for LLM consumption."""
    stats = report.stats
    parts = []

    # Title & Metadata
    parts.append("# Code Change Summary & Review Context")
    if stats:
        parts.append(
            f"**Token Efficiency**: ~{stats.compressed_tokens:,} tokens "
            f"(reduced from ~{stats.original_tokens:,} tokens, "
            f"**{stats.compression_ratio_percent}% compression**)"
        )
        parts.append(
            f"**File Scope**: {stats.included_files} reviewed, "
            f"{stats.suppressed_files} noise suppressed, "
            f"{stats.omitted_files} budget omitted."
        )
    parts.append("")

    # Change Manifest Table
    parts.append("## Changed Files Manifest")
    parts.append("| File | Category | Churn | Review Status |")
    parts.append("| :--- | :--- | :--- | :--- |")

    for file in report.files:
        churn = f"+{file.additions}/-{file.deletions}"
        if file.is_suppressed:
            status = f"Suppressed ({file.category.value})"
        elif file.is_omitted:
            status = "Omitted (Budget Limit)"
        else:
            status = "Included"
        parts.append(f"| `{file.display_path}` | `{file.category.value}` | `{churn}` | {status} |")

    parts.append("")

    # Core Diffs
    parts.append("## Unified Changes")
    active_files = [f for f in report.files if not f.is_suppressed and not f.is_omitted]

    if not active_files:
        parts.append("_No active source changes remaining after filtering._")
    else:
        for file in active_files:
            orig = file.original_file
            status_desc = "Modified"
            if orig.is_new:
                status_desc = "Created"
            elif orig.is_deleted:
                status_desc = "Deleted"

            parts.append(f"### `{file.display_path}` ({status_desc}, +{file.additions}/-{file.deletions})")
            parts.append("```diff")
            for hunk in file.hunks:
                parts.append(hunk.header)
                for line in hunk.lines:
                    parts.append(line.to_unified())
            parts.append("```")
            parts.append("")

    # Guidance for the Reviewer / LLM
    parts.append("## Review Guidelines")
    if review_goal:
        parts.append(f"**Goal**: {review_goal}")
    else:
        parts.append(
            "1. Focus strictly on the logic, edge cases, and safety of the included source changes.\n"
            "2. Verify there are no unhandled errors, unintended breaking changes, or regressions.\n"
            "3. High-noise files (lockfiles, generated code) were excluded by `diff-diet` to preserve token attention."
        )

    return "\n".join(parts) + "\n"


def format_json(report: CompressedReport) -> str:
    """Serializes the compressed report into JSON for automation pipelines."""
    stats = report.stats
    data: Dict[str, Any] = {
        "stats": {
            "total_files": stats.total_files if stats else 0,
            "included_files": stats.included_files if stats else 0,
            "suppressed_files": stats.suppressed_files if stats else 0,
            "omitted_files": stats.omitted_files if stats else 0,
            "original_tokens": stats.original_tokens if stats else 0,
            "compressed_tokens": stats.compressed_tokens if stats else 0,
            "compression_ratio_percent": stats.compression_ratio_percent if stats else 0.0,
        },
        "files": [],
    }

    for file in report.files:
        file_dict = {
            "path": file.display_path,
            "category": file.category.value,
            "priority": file.priority_score,
            "is_suppressed": file.is_suppressed,
            "suppress_reason": file.suppress_reason,
            "is_omitted": file.is_omitted,
            "omitted_reason": file.omitted_reason,
            "additions": file.additions,
            "deletions": file.deletions,
            "original_tokens": file.original_tokens,
            "compressed_tokens": file.compressed_tokens,
            "hunks_count": len(file.hunks),
        }
        data["files"].append(file_dict)

    return json.dumps(data, indent=2) + "\n"

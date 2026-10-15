"""Compression and token budgeting engine for unified diffs."""

from dataclasses import dataclass, field
import math
from typing import List, Optional

from diff_diet.classifier import (
    FileCategory,
    classify_path,
    get_priority_weight,
    is_noise_category,
)
from diff_diet.parser import DiffFile, DiffLine, DiffReport, Hunk


def estimate_tokens(text: str) -> int:
    """Estimates LLM token count using a calibrated heuristic for code diffs."""
    if not text:
        return 0
    # Average ~3.6 characters per token in unified diffs with indentation & syntax symbols
    tokens = math.ceil(len(text) / 3.6)
    return max(1, tokens)


@dataclass
class CompressedFile:
    original_file: DiffFile
    category: FileCategory
    priority_score: int
    is_suppressed: bool = False
    suppress_reason: str = ""
    is_omitted: bool = False
    omitted_reason: str = ""
    hunks: List[Hunk] = field(default_factory=list)
    original_tokens: int = 0
    compressed_tokens: int = 0

    @property
    def display_path(self) -> str:
        return self.original_file.display_path

    @property
    def additions(self) -> int:
        return self.original_file.additions

    @property
    def deletions(self) -> int:
        return self.original_file.deletions


@dataclass
class CompressionStats:
    total_files: int
    included_files: int
    suppressed_files: int
    omitted_files: int
    original_tokens: int
    compressed_tokens: int

    @property
    def saved_tokens(self) -> int:
        return max(0, self.original_tokens - self.compressed_tokens)

    @property
    def compression_ratio_percent(self) -> float:
        if self.original_tokens <= 0:
            return 0.0
        return round((1.0 - (self.compressed_tokens / self.original_tokens)) * 100, 1)


@dataclass
class CompressedReport:
    files: List[CompressedFile] = field(default_factory=list)
    stats: Optional[CompressionStats] = None


class DiffCompressor:
    def __init__(
        self,
        token_budget: Optional[int] = None,
        suppress_noise: bool = True,
        ignore_whitespace: bool = False,
        max_context_lines: int = 2,
    ):
        self.token_budget = token_budget
        self.suppress_noise = suppress_noise
        self.ignore_whitespace = ignore_whitespace
        self.max_context_lines = max(0, max_context_lines)

    def _shrink_hunk_context(self, hunk: Hunk) -> Hunk:
        """Trims excessive leading, trailing, and internal context lines in a hunk."""
        if not hunk.lines or self.max_context_lines <= 0:
            return hunk

        new_lines: List[DiffLine] = []
        i = 0
        total = len(hunk.lines)

        # Leading context trim
        leading_context: List[DiffLine] = []
        while i < total and hunk.lines[i].origin == " ":
            leading_context.append(hunk.lines[i])
            i += 1

        if len(leading_context) > self.max_context_lines:
            new_lines.extend(leading_context[-self.max_context_lines:])
        else:
            new_lines.extend(leading_context)

        # Middle lines processing
        while i < total:
            line = hunk.lines[i]
            if line.origin != " ":
                new_lines.append(line)
                i += 1
            else:
                # Group of context lines
                ctx_group: List[DiffLine] = []
                while i < total and hunk.lines[i].origin == " ":
                    ctx_group.append(hunk.lines[i])
                    i += 1

                # Check if this context group is at the very end
                if i >= total:
                    # Trailing context
                    if len(ctx_group) > self.max_context_lines:
                        new_lines.extend(ctx_group[:self.max_context_lines])
                    else:
                        new_lines.extend(ctx_group)
                else:
                    # Internal context between changes
                    max_internal = self.max_context_lines * 2
                    if len(ctx_group) > max_internal:
                        new_lines.extend(ctx_group[:self.max_context_lines])
                        omitted_count = len(ctx_group) - (self.max_context_lines * 2)
                        new_lines.append(
                            DiffLine(
                                origin=" ",
                                content=f"... ({omitted_count} unchanged lines collapsed) ...",
                            )
                        )
                        new_lines.extend(ctx_group[-self.max_context_lines:])
                    else:
                        new_lines.extend(ctx_group)

        return Hunk(
            header=hunk.header,
            old_start=hunk.old_start,
            old_count=hunk.old_count,
            new_start=hunk.new_start,
            new_count=hunk.new_count,
            func_context=hunk.func_context,
            lines=new_lines,
        )

    def compress(self, report: DiffReport) -> CompressedReport:
        """Processes and compresses the parsed DiffReport according to configuration."""
        raw_files = report.files
        compressed_files: List[CompressedFile] = []

        total_original_tokens = 0

        # Step 1: Initial classification and noise suppression
        for file in raw_files:
            category = classify_path(file.display_path, is_binary=file.is_binary)
            priority = get_priority_weight(category)

            # Calculate raw tokens for original file
            raw_text = "\n".join(file.raw_headers) + "\n"
            for hunk in file.hunks:
                raw_text += hunk.header + "\n"
                for line in hunk.lines:
                    raw_text += line.to_unified() + "\n"
            orig_tokens = estimate_tokens(raw_text)
            total_original_tokens += orig_tokens

            comp_file = CompressedFile(
                original_file=file,
                category=category,
                priority_score=priority,
                original_tokens=orig_tokens,
            )

            # Check noise suppression
            if self.suppress_noise and is_noise_category(category):
                comp_file.is_suppressed = True
                comp_file.suppress_reason = (
                    f"Suppressed noisy {category.value} file (+{file.additions}, -{file.deletions} lines)"
                )
                comp_file.compressed_tokens = estimate_tokens(
                    f"[{comp_file.suppress_reason}]"
                )
                compressed_files.append(comp_file)
                continue

            # Process hunks
            processed_hunks: List[Hunk] = []
            for hunk in file.hunks:
                if self.ignore_whitespace and hunk.is_whitespace_only():
                    continue

                shrunk_hunk = self._shrink_hunk_context(hunk)
                processed_hunks.append(shrunk_hunk)

            if not processed_hunks and file.hunks:
                # All hunks were whitespace or empty
                comp_file.is_suppressed = True
                comp_file.suppress_reason = "All changes were whitespace-only formatting"
                comp_file.compressed_tokens = estimate_tokens(
                    f"[{comp_file.suppress_reason}]"
                )
                compressed_files.append(comp_file)
                continue

            comp_file.hunks = processed_hunks

            # Calculate compressed tokens for this file
            comp_text = f"diff --git a/{file.old_path} b/{file.new_path}\n"
            for h in processed_hunks:
                comp_text += h.header + "\n"
                for line in h.lines:
                    comp_text += line.to_unified() + "\n"
            comp_file.compressed_tokens = estimate_tokens(comp_text)
            compressed_files.append(comp_file)

        # Step 2: Apply token budget if specified
        if self.token_budget is not None and self.token_budget > 0:
            current_tokens = sum(
                f.compressed_tokens for f in compressed_files if f.is_suppressed
            )

            # Sort unsuppressed files by priority score descending, then by churn descending
            unsuppressed = [f for f in compressed_files if not f.is_suppressed]
            unsuppressed.sort(
                key=lambda f: (
                    -f.priority_score,
                    -(f.additions + f.deletions),
                )
            )

            for comp_file in unsuppressed:
                if current_tokens + comp_file.compressed_tokens <= self.token_budget:
                    current_tokens += comp_file.compressed_tokens
                else:
                    # Try fitting individual hunks
                    budget_left = self.token_budget - current_tokens
                    if budget_left > 150:
                        fitted_hunks: List[Hunk] = []
                        file_tokens = estimate_tokens(
                            f"diff --git a/{comp_file.original_file.old_path} b/{comp_file.original_file.new_path}\n"
                        )
                        for hunk in comp_file.hunks:
                            hunk_text = hunk.header + "\n" + "\n".join(
                                l.to_unified() for l in hunk.lines
                            )
                            hunk_tokens = estimate_tokens(hunk_text)
                            if file_tokens + hunk_tokens <= budget_left:
                                fitted_hunks.append(hunk)
                                file_tokens += hunk_tokens
                            else:
                                break

                        if fitted_hunks:
                            omitted_hunks_count = len(comp_file.hunks) - len(fitted_hunks)
                            if omitted_hunks_count > 0:
                                fitted_hunks.append(
                                    Hunk(
                                        header="@@ ... @@",
                                        old_start=0,
                                        old_count=0,
                                        new_start=0,
                                        new_count=0,
                                        func_context="",
                                        lines=[
                                            DiffLine(
                                                origin=" ",
                                                content=f"... ({omitted_hunks_count} hunks truncated to fit token budget) ...",
                                            )
                                        ],
                                    )
                                )
                            comp_file.hunks = fitted_hunks
                            comp_file.compressed_tokens = file_tokens
                            current_tokens += file_tokens
                            continue

                    # Could not fit whole file or meaningful hunks
                    comp_file.is_omitted = True
                    comp_file.hunks = []
                    comp_file.omitted_reason = (
                        f"Omitted due to token budget constraint (+{comp_file.additions}, -{comp_file.deletions} lines)"
                    )
                    comp_file.compressed_tokens = estimate_tokens(
                        f"[{comp_file.omitted_reason}]"
                    )
                    current_tokens += comp_file.compressed_tokens

        # Step 3: Compute final statistics
        total_compressed_tokens = sum(f.compressed_tokens for f in compressed_files)
        included_count = sum(
            1 for f in compressed_files if not f.is_suppressed and not f.is_omitted
        )
        suppressed_count = sum(1 for f in compressed_files if f.is_suppressed)
        omitted_count = sum(1 for f in compressed_files if f.is_omitted)

        stats = CompressionStats(
            total_files=len(compressed_files),
            included_files=included_count,
            suppressed_files=suppressed_count,
            omitted_files=omitted_count,
            original_tokens=total_original_tokens,
            compressed_tokens=total_compressed_tokens,
        )

        return CompressedReport(files=compressed_files, stats=stats)

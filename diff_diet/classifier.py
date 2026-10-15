"""File category classification and priority scoring for diff compression."""

from enum import Enum
import os
import re
from typing import Dict, List, Pattern, Tuple


class FileCategory(str, Enum):
    SOURCE = "source"
    CONFIG = "config"
    TEST = "test"
    DOCS = "docs"
    SNAPSHOT = "snapshot"
    GENERATED = "generated"
    MINIFIED = "minified"
    LOCKFILE = "lockfile"
    ASSET = "asset"
    SOURCEMAP = "sourcemap"
    BINARY = "binary"
    OTHER = "other"


# Category weight determines retention priority when budget is constrained (higher = more important)
CATEGORY_WEIGHTS: Dict[FileCategory, int] = {
    FileCategory.SOURCE: 100,
    FileCategory.CONFIG: 70,
    FileCategory.TEST: 60,
    FileCategory.DOCS: 40,
    FileCategory.SNAPSHOT: 20,
    FileCategory.GENERATED: 10,
    FileCategory.MINIFIED: 5,
    FileCategory.LOCKFILE: 1,
    FileCategory.ASSET: 1,
    FileCategory.SOURCEMAP: 1,
    FileCategory.BINARY: 0,
    FileCategory.OTHER: 50,
}

# Categories classified as high-noise by default
NOISE_CATEGORIES = {
    FileCategory.LOCKFILE,
    FileCategory.MINIFIED,
    FileCategory.SOURCEMAP,
    FileCategory.ASSET,
    FileCategory.GENERATED,
    FileCategory.BINARY,
}

# Exact filename matches (case-insensitive)
EXACT_LOCKFILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "cargo.lock",
    "poetry.lock",
    "pipfile.lock",
    "composer.lock",
    "go.sum",
    "gemfile.lock",
    "flake.lock",
    "bun.lockb",
    "mix.lock",
    "packages.lock.json",
}

# Regex patterns for fast category detection
CLASSIFICATION_RULES: List[Tuple[FileCategory, Pattern[str]]] = [
    # Lockfiles
    (
        FileCategory.LOCKFILE,
        re.compile(
            r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|cargo\.lock|poetry\.lock|pipfile\.lock|composer\.lock|go\.sum|gemfile\.lock|flake\.lock|bun\.lockb|mix\.lock)$",
            re.IGNORECASE,
        ),
    ),
    # Sourcemaps
    (
        FileCategory.SOURCEMAP,
        re.compile(r"\.map$", re.IGNORECASE),
    ),
    # Minified files
    (
        FileCategory.MINIFIED,
        re.compile(
            r"(\.min\.(js|css|mjs)|(\.bundle|\.chunk|\.vendor)\.(js|css))$",
            re.IGNORECASE,
        ),
    ),
    # Generated stubs and schemas
    (
        FileCategory.GENERATED,
        re.compile(
            r"(\.generated\.(ts|js|py|go|rs)|_pb2\.py|_pb2_grpc\.py|\.pb\.go|\.g\.dart|\.freezed\.dart|schema\.d\.ts|\.auto\.(ts|js))$",
            re.IGNORECASE,
        ),
    ),
    # Snapshot test fixtures
    (
        FileCategory.SNAPSHOT,
        re.compile(r"(__snapshots__/|\.snap$)", re.IGNORECASE),
    ),
    # Image and font assets
    (
        FileCategory.ASSET,
        re.compile(
            r"\.(svg|png|jpe?g|gif|webp|avif|ico|woff2?|ttf|eot|otf)$",
            re.IGNORECASE,
        ),
    ),
    # Tests
    (
        FileCategory.TEST,
        re.compile(
            r"((^|/)(test|tests|__tests__|spec|specs)/|\.(test|spec)\.[a-zA-Z0-9]+$|_test\.[a-zA-Z0-9]+$)",
            re.IGNORECASE,
        ),
    ),
    # Documentation
    (
        FileCategory.DOCS,
        re.compile(
            r"((^|/)docs?/|\.(md|rst|txt|adoc)$|(^|/)(license|changelog|contributing)(\.|$))",
            re.IGNORECASE,
        ),
    ),
    # Configuration
    (
        FileCategory.CONFIG,
        re.compile(
            r"(\.(json|ya?ml|toml|ini|env(\.[a-zA-Z0-9_-]+)?|cfg)$|(^|/)(dockerfile|makefile|cmakelists\.txt|\.gitignore|\.editorconfig))",
            re.IGNORECASE,
        ),
    ),
    # Source code
    (
        FileCategory.SOURCE,
        re.compile(
            r"\.(py|tsx?|jsx?|rs|go|c|cpp|h|hpp|cs|java|kt|kts|rb|php|swift|dart|scala|zig|lua|sh|bash|zsh|sql|html|css|scss|less)$",
            re.IGNORECASE,
        ),
    ),
]


def classify_path(path: str, is_binary: bool = False) -> FileCategory:
    """Classifies a file path into its appropriate FileCategory."""
    if is_binary:
        return FileCategory.BINARY

    normalized = path.replace("\\", "/").strip()
    basename = os.path.basename(normalized).lower()

    if basename in EXACT_LOCKFILES:
        return FileCategory.LOCKFILE

    for category, pattern in CLASSIFICATION_RULES:
        if pattern.search(normalized):
            return category

    return FileCategory.OTHER


def get_priority_weight(category: FileCategory) -> int:
    """Returns the priority score for a category."""
    return CATEGORY_WEIGHTS.get(category, 50)


def is_noise_category(category: FileCategory) -> bool:
    """Returns True if the category represents high-noise files by default."""
    return category in NOISE_CATEGORIES

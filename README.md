# diff-diet

> Token-budgeted Git diff optimizer and noise compressor for LLMs, AI agents, and code review.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests: Passing](https://img.shields.io/badge/tests-21%20passing-brightgreen.svg)](tests/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-success.svg)](pyproject.toml)

---

## The Problem

When developers feed raw `git diff` into Large Language Models (ChatGPT, Claude, Gemini, Cursor, or autonomous coding agents), up to 85% of the payload is pure noise:
- Thousands of auto-generated lockfile lines (`package-lock.json`, `pnpm-lock.yaml`, `Cargo.lock`, `go.sum`).
- Minified bundles, sourcemaps, and compiled build artifacts.
- Generated RPC/GraphQL/Protobuf stubs and test snapshot fixtures.
- Cosmetic formatting and whitespace churn.

This noise burns context tokens, degrades model attention away from critical business logic, triggers rate limits, and multiplies API costs. Existing tools either dump the entire raw diff or force users to manually exclude files using complex git ignore flags.

## The Solution

`diff-diet` parses unified diffs into a structured AST, classifies files by cognitive importance, strips noise, shrinks context padding, and applies strict token budgeting so you only send high-signal logic changes to your models.

```
+-------------------------------------------------------------+
| Raw Git Diff (e.g. 14,200 tokens with lockfiles & assets)   |
+-------------------------------------------------------------+
                              |
                              v
                  [ diff-diet AST Engine ]
   1. Noise Suppression   -> Suppresses lockfiles, maps, stubs
   2. Whitespace Filter   -> Strips cosmetic-only formatting
   3. Context Shrinker    -> Collapses unchanged filler lines
   4. Priority Budgeter   -> Allocates tokens to core logic first
                              |
                              v
+-------------------------------------------------------------+
| LLM-Ready Markdown Prompt / Clean Diff (~1,850 tokens, -87%)|
+-------------------------------------------------------------+
```

---

## 30-Second Quickstart

### Installation

Requires Python 3.8+ (Zero third-party dependencies):

```bash
# Clone and install locally
git clone https://github.com/IlhamXkyo/diff-diet.git
cd diff-diet
pip install .
```

Or run standalone without installing:

```bash
python -m diff_diet.cli --help
```

### Basic Usage

Generate an LLM code review prompt directly from unstaged changes:

```bash
diff-diet
```

Pipe directly from any git command:

```bash
git diff | diff-diet
git diff HEAD~1 | diff-diet --budget 3000
```

Review staged changes and copy the output directly to your system clipboard:

```bash
diff-diet --staged --copy
```

Output a clean, noise-free unified diff instead of markdown:

```bash
diff-diet --format diff
```

Generate structured JSON for CI/CD pipelines:

```bash
diff-diet main...feature -f json -o review-payload.json
```

---

## Key Features

- **Intelligent Noise Filter**: Automatically detects and compresses lockfiles, sourcemaps, minified assets, and generated stubs with compact one-line change summaries.
- **Priority-Based Token Budgeting**: Set `--budget 4000` to guarantee your diff fits within your model's context limit. Retains high-priority source code files first, truncating lower-priority hunks gracefully.
- **Cognitive File Scoring**: Files are prioritized based on architectural impact (Source code > Config > Tests > Documentation > Generated > Lockfiles).
- **Whitespace and Context Pruning**: Collapse bloated surrounding context lines (`--context 1`) and eliminate whitespace-only formatting changes (`--ignore-whitespace`).
- **Prompt-Ready Markdown**: Produces a structured Markdown review document with change summary tables, token efficiency stats, and fenced syntax blocks.
- **Direct Clipboard Integration**: Use `--copy` on Windows, macOS, or Linux to immediately paste the review prompt into your chat or web UI.
- **Zero Dependencies**: Pure Python standard library. Fast startup (< 15ms), zero network calls, completely offline.

---

## Benchmark Comparison

On a typical pull request containing 1 dependency upgrade, 2 feature files, and 1 test update:

| Metric | Raw `git diff` | With `diff-diet` | Savings |
| :--- | :--- | :--- | :--- |
| **Total Lines** | 1,842 lines | 148 lines | **91.9% reduction** |
| **Estimated Tokens** | ~12,400 tokens | ~1,620 tokens | **86.9% reduction** |
| **Lockfile Noise** | Included (1,680 lines) | Suppressed (1 summary line) | 100% noise pruned |
| **Model Attention** | Diluted across lockfile hashes | Concentrated on business logic | Maximum focus |

---

## CLI Reference

```
usage: diff-diet [-h] [-s] [-b TOKENS] [-f {prompt,diff,json}] [-c LINES]
                 [-w] [--include-noise] [-g TEXT] [-o FILE] [--copy] [--stats]
                 [-v] [git_args ...]

Compress, filter, and budget Git diffs for LLMs, code reviews, and AI agents.

positional arguments:
  git_args              Optional revisions, branches, or file paths (e.g. HEAD~1, main..feature, src/)

options:
  -h, --help            Show this help message and exit
  -s, --staged          Diff staged/cached changes instead of working tree
  -b, --budget TOKENS   Target LLM token budget limit (e.g. 2000, 4000, 8000)
  -f, --format {prompt,diff,json}
                        Output format: 'prompt' (default), 'diff', 'json'
  -c, --context LINES   Maximum surrounding context lines per change hunk (default: 2)
  -w, --ignore-whitespace
                        Strip and ignore whitespace-only changes
  --include-noise       Do not suppress high-noise files (lockfiles, sourcemaps)
  -g, --goal TEXT       Custom goal or instructions to include in the review prompt
  -o, --output FILE     Write output to a file instead of stdout
  --copy                Copy output directly to clipboard
  --stats               Print compression and token statistics to stderr
  -v, --version         Show program's version number and exit
```

---

## Git Alias Setup

Add `diff-diet` as a native git command by creating a git alias:

```bash
git config --global alias.diet "!diff-diet"
```

Now you can run:

```bash
git diet
git diet --staged --budget 4000
```

---

## Architecture

The project consists of 5 modular components:
1. `classifier.py`: File classification rules and cognitive priority weights.
2. `parser.py`: Unified diff streaming parser producing structured AST representations.
3. `compressor.py`: Context trimmer, whitespace filter, and priority token budgeting engine.
4. `formatter.py`: Serializers for Markdown review prompts, unified diffs, and structured JSON.
5. `git_util.py`: Subprocess execution, piped stdin handling, and platform-native clipboard support.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

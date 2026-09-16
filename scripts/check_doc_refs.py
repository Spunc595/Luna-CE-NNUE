"""
Guard against dangling references: every citation to a filename in a
committed .md file (backtick-quoted) or in a .py/.sh source comment
(bare, since comments don't use backticks) should point at something a
reader can actually open. Same remedy as the [cite grep guard in the
engine repository, applied to a failure mode found twice in this
repository's own docs and once more, at much larger scale, in the
pipeline sources themselves: comments citing private working notes that
were never committed.

Only .md is checked as a citation TARGET (a script legitimately mentions
sibling .py/.sh files that aren't necessarily meant to resolve here) --
what matters is that no comment or doc line points at a note nobody but
the author can open.

ALLOWLIST covers documents that genuinely exist in this repository and
genuinely external files (not ours to commit, so naturally absent).
PLACEHOLDER_RE covers naming-pattern text (gen3_shard_NNNNN_...) that
isn't a citation at all.

Usage: python scripts/check_doc_refs.py   (run from repo root or anywhere)
Exit code 1 if any reference is unresolved.
"""
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SOURCE_EXTENSIONS = {".md", ".py", ".sh"}

ALLOWLIST = {
    "lichess_db_puzzle.csv",  # external dataset (database.lichess.org), 6.1M rows, not committed -- see COMPLIANCE.md
    "8moves_v3.pgn",  # external public opening book, committed as data under results/girone/, not a doc
    "README.md", "LINEAGE.md", "COMPLIANCE.md", "RESULTS.md",  # exist at repo root
}

BACKTICK_RE = re.compile(r"`([^`\n]+\.md)`")
BARE_MD_RE = re.compile(r"\b([A-Za-z0-9_-]+\.md)\b")
PLACEHOLDER_RE = re.compile(r"NNNNN|genN\b")


def find_source_files():
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for fn in filenames:
            if os.path.splitext(fn)[1] in SOURCE_EXTENSIONS:
                yield os.path.join(dirpath, fn)


def repo_has_file(basename_or_path):
    if "/" in basename_or_path:
        return os.path.isfile(os.path.join(REPO_ROOT, basename_or_path))
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        if ".git" in dirnames:
            dirnames.remove(".git")
        if basename_or_path in filenames:
            return True
    return False


def main():
    problems = []
    for src_path in find_source_files():
        rel_src = os.path.relpath(src_path, REPO_ROOT)
        is_md = src_path.endswith(".md")
        pattern = BACKTICK_RE if is_md else BARE_MD_RE
        with open(src_path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                for span in pattern.findall(line):
                    if span in ALLOWLIST or PLACEHOLDER_RE.search(span):
                        continue
                    if not repo_has_file(span):
                        problems.append((rel_src, lineno, span))

    if problems:
        print(f"{len(problems)} dangling reference(s):\n")
        for rel_src, lineno, span in problems:
            print(f"  {rel_src}:{lineno}: `{span}` not found in repository")
        print(
            "\nEither the file is missing and should be added/committed, "
            "or the reference is to a private note and should be rewritten "
            "inline, or -- if genuinely external and not ours to commit -- "
            "add it to ALLOWLIST in this script with a one-line reason."
        )
        return 1

    print("No dangling references found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

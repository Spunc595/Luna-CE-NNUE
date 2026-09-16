"""
Guard against dangling references: every backtick-quoted filename in a
committed .md file should point at something a reader can actually open.
This is the same remedy as the [cite grep guard in the engine repository,
applied to the failure mode found twice in RESULTS.md -- backtick
references to private working notes (gen3.md, girone-tre-reti.md, ...)
that never got committed.

Not every backtick span is a path (commit hashes, version tags, UCI
option names, code identifiers) -- EXTENSIONS below limits the check to
extensions this repository's own docs/pipeline actually use, and
ALLOWLIST covers legitimate exceptions: genuinely external files (not
ours to commit) and template placeholders (gen3_shard_NNNNN_...,
nets/luna_genN.nnue) that describe a naming pattern, not one file.

Usage: python scripts/check_doc_refs.py   (run from repo root or anywhere)
Exit code 1 if any reference is unresolved.
"""
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXTENSIONS = {".md", ".py", ".sh"}

# Genuinely not ours to commit, or a naming pattern rather than one file --
# each entry documented so the exception doesn't need rediscovering.
ALLOWLIST = {
    "lichess_db_puzzle.csv",  # external dataset (database.lichess.org), 6.1M rows, not committed -- see COMPLIANCE.md
}

BACKTICK_RE = re.compile(r"`([^`\n]+)`")
PLACEHOLDER_RE = re.compile(r"NNNNN|genN\b")


def find_md_files():
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for fn in filenames:
            if fn.endswith(".md"):
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
    for md_path in find_md_files():
        rel_md = os.path.relpath(md_path, REPO_ROOT)
        with open(md_path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                for span in BACKTICK_RE.findall(line):
                    if " " in span or span in ALLOWLIST:
                        continue
                    _, ext = os.path.splitext(span)
                    if ext not in EXTENSIONS:
                        continue
                    if PLACEHOLDER_RE.search(span):
                        continue
                    if not repo_has_file(span):
                        problems.append((rel_md, lineno, span))

    if problems:
        print(f"{len(problems)} dangling doc reference(s):\n")
        for rel_md, lineno, span in problems:
            print(f"  {rel_md}:{lineno}: `{span}` not found in repository")
        print(
            "\nEither the file is missing and should be added/committed, "
            "or the reference is to a private note and should be rewritten "
            "inline, or -- if genuinely external and not ours to commit -- "
            "add it to ALLOWLIST in this script with a one-line reason."
        )
        return 1

    print("No dangling doc references found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

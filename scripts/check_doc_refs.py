"""
Guard against dangling references: every citation to a filename in a
committed .md file (backtick-quoted) or elsewhere in the repository
(bare, since most file types don't use backticks) should point at
something a reader can actually open. Same remedy as the [cite grep
guard in the engine repository, applied to a failure mode found in three
different file types so far -- .md docs, .py/.sh comments, and JSON
manifest prose fields -- each time in a file type the previous pass
hadn't looked at: comments/prose citing private working notes that were
never committed.

Scans every TEXT file in the repository, whatever its extension --
binary files (detected by content, not by an extension list: a NUL byte
or a decode failure means binary) are skipped automatically. Extending a
fixed list of extensions just means the next occurrence shows up in
whatever extension isn't on it yet; scanning by content instead of by
extension closes that off structurally.

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

ALLOWLIST = {
    "lichess_db_puzzle.csv",  # external dataset (database.lichess.org), 6.1M rows, not committed -- see COMPLIANCE.md
    "8moves_v3.pgn",  # external public opening book, committed as data under results/girone/, not a doc
    "README.md", "LINEAGE.md", "COMPLIANCE.md", "RESULTS.md",  # exist at repo root
}

BACKTICK_RE = re.compile(r"`([^`\n]+\.md)`")
BARE_MD_RE = re.compile(r"\b([A-Za-z0-9_-]+\.md)\b")
PLACEHOLDER_RE = re.compile(r"NNNNN|genN\b")


def is_binary(path, sniff_bytes=8192):
    try:
        with open(path, "rb") as f:
            chunk = f.read(sniff_bytes)
    except OSError:
        return True
    if b"\x00" in chunk:
        return True
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def find_text_files():
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for fn in filenames:
            path = os.path.join(dirpath, fn)
            if not is_binary(path):
                yield path


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
    for src_path in find_text_files():
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

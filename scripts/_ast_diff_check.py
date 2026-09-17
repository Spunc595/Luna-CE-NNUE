"""
Verifies that translating comments/docstrings in a .py file changed
nothing else: strips docstrings from both versions' AST and compares.
Used as a one-off review tool during the C1/C2 comment-translation pass
-- not part of the guard suite, not wired into CI.

Usage: python scripts/_ast_diff_check.py <old_path_or_git_ref:path> <new_path>
   or: python scripts/_ast_diff_check.py --git <path>   (compares HEAD vs working tree)
"""
import ast
import subprocess
import sys


def strip_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
               and isinstance(b[0].value.value, str):
                node.body = b[1:] or [ast.Pass()]
    return tree


def dump(source):
    return ast.dump(strip_docstrings(ast.parse(source)))


def main():
    if sys.argv[1] == "--git":
        path = sys.argv[2]
        old = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True, text=True,
                              encoding="utf-8").stdout
        with open(path, encoding="utf-8") as f:
            new = f.read()
    else:
        with open(sys.argv[1], encoding="utf-8") as f:
            old = f.read()
        with open(sys.argv[2], encoding="utf-8") as f:
            new = f.read()

    d_old, d_new = dump(old), dump(new)
    if d_old == d_new:
        print("IDENTICAL (docstrings excluded)")
        return 0
    else:
        print("DIFFERENT: something beyond docstrings changed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

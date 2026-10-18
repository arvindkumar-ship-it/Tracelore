import ast
import logging
from pathlib import Path

ROOTS = ("backend", "sdk/python", "sdk/typescript/src", "dashboard/src", "bench", "scripts")
MAX_FILE_LINES, MAX_STATEMENTS = 300, 30


def statement_count(node: ast.AST) -> int:
    count = 0
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        count += int(isinstance(child, ast.stmt)) + statement_count(child)
    return count


def check(root: Path) -> list[str]:
    failures = []
    for directory in ROOTS:
        for path in (root / directory).rglob("*"):
            if path.suffix not in (".py", ".ts", ".tsx", ".css") or path.name == "generated.ts":
                continue
            text = path.read_text(encoding="utf-8")
            if len(text.splitlines()) > MAX_FILE_LINES:
                failures.append(f"{path}: exceeds {MAX_FILE_LINES} lines")
            if path.suffix != ".py":
                continue
            for node in ast.walk(ast.parse(text)):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if statement_count(node) > MAX_STATEMENTS:
                    failures.append(
                        f"{path}:{node.lineno}: {node.name} exceeds {MAX_STATEMENTS} statements"
                    )
                arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                if node.returns is None or any(
                    arg.annotation is None for arg in arguments if arg.arg not in ("self", "cls")
                ):
                    failures.append(f"{path}:{node.lineno}: {node.name} needs type annotations")
    return failures


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    failures = check(Path(__file__).resolve().parents[1])
    for failure in failures:
        logging.getLogger(__name__).error(failure)
    if failures:
        raise SystemExit(1)
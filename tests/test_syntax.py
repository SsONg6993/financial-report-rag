import ast
from pathlib import Path


def test_all_application_python_files_parse():
    files = [Path("app.py"), *Path("src").glob("*.py")]
    for path in files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

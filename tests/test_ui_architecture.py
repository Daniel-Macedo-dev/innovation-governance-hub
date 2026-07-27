import ast
from pathlib import Path


def test_views_do_not_import_persistence_or_sqlalchemy():
    forbidden = {
        "sqlalchemy",
        "innovation_governance_hub.database",
        "innovation_governance_hub.persistence.models",
    }
    for path in Path("src/innovation_governance_hub/ui/views").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not [
            name
            for name in imports
            if any(name == item or name.startswith(f"{item}.") for item in forbidden)
        ], path

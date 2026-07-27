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


def test_legacy_views_are_gone_and_pages_use_specific_views():
    assert not Path("src/innovation_governance_hub/ui/legacy_views.py").exists()
    for path in [Path("app.py"), *Path("pages").glob("*.py")]:
        source = path.read_text(encoding="utf-8")
        assert "legacy_views" not in source
        assert "from innovation_governance_hub.ui.views import" not in source

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("path", [Path("app.py"), *sorted(Path("pages").glob("*.py"))])
def test_streamlit_pages_load(path: Path):
    app = AppTest.from_file(str(path), default_timeout=15).run()
    assert not app.exception, f"{path}: {app.exception}"
    assert app.title, f"{path} não exibiu título"

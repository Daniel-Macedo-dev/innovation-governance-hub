from pathlib import Path

import pytest

from scripts.capture_screenshots import (
    EXPECTED_SCREENSHOTS,
    PNG_SIGNATURE,
    browser_candidates,
    cleanup_temporary,
    isolated_environment,
    png_dimensions,
    project_root,
    validate_manifest,
)


def fake_png(path: Path, marker: bytes = b"x") -> None:
    path.write_bytes(
        PNG_SIGNATURE
        + b"\x00\x00\x00\rIHDR"
        + (1440).to_bytes(4, "big")
        + (1000).to_bytes(4, "big")
        + marker
    )


def test_project_root_contains_application() -> None:
    assert (project_root() / "app.py").is_file()


def test_isolated_environment_uses_dedicated_database(tmp_path: Path) -> None:
    environment = isolated_environment(tmp_path)
    assert environment["APP_ENV"] == "screenshot"
    assert environment["DATABASE_URL"] == "sqlite:///data/screenshots_demo.db"
    assert environment["AI_PROVIDER"] == "demo"
    assert environment["N8N_ENABLED"] == "false"


def test_manifest_requires_all_valid_distinct_pngs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ausentes"):
        validate_manifest(tmp_path)
    for index, name in enumerate(EXPECTED_SCREENSHOTS):
        fake_png(tmp_path / name, marker=bytes([index]))
    manifest = validate_manifest(tmp_path)
    assert set(manifest) == set(EXPECTED_SCREENSHOTS)
    assert manifest[EXPECTED_SCREENSHOTS[0]][:2] == (1440, 1000)


def test_png_validation_rejects_invalid_signature(tmp_path: Path) -> None:
    path = tmp_path / "broken.png"
    path.write_bytes(b"not a png")
    with pytest.raises(ValueError, match="PNG inválido"):
        png_dimensions(path)


def test_cleanup_removes_only_capture_artifacts(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    for suffix in ("", "-shm", "-wal"):
        (data / f"screenshots_demo.db{suffix}").write_text("temporary")
    keep = data / "innovation_governance_hub.db"
    keep.write_text("keep")
    temporary = tmp_path / "screenshots-temp"
    temporary.mkdir()
    (temporary / "capture.log").write_text("temporary")
    cleanup_temporary(tmp_path)
    assert keep.exists()
    assert not temporary.exists()
    assert not list(data.glob("screenshots_demo.db*"))


def test_browser_fallback_order() -> None:
    assert browser_candidates() == (
        ("Microsoft Edge", "msedge"),
        ("Google Chrome", "chrome"),
        ("Chromium", None),
    )

from unittest.mock import MagicMock, patch

import pytest

from innovation_governance_hub.ui.context import app_services


def test_read_context_closes_without_commit():
    session = MagicMock()
    with patch("innovation_governance_hub.ui.context.SessionLocal", return_value=session):
        with app_services(read_only=True):
            pass
    session.commit.assert_not_called()
    session.close.assert_called_once()


def test_write_context_commits_and_closes():
    session = MagicMock()
    with patch("innovation_governance_hub.ui.context.SessionLocal", return_value=session):
        with app_services() as services:
            assert services.documents and services.export
    session.commit.assert_called_once()
    session.close.assert_called_once()


def test_context_rolls_back_on_exception():
    session = MagicMock()
    with patch("innovation_governance_hub.ui.context.SessionLocal", return_value=session):
        with pytest.raises(RuntimeError), app_services():
            raise RuntimeError("falha")
    session.rollback.assert_called_once()
    session.close.assert_called_once()

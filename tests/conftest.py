import pytest


@pytest.fixture(autouse=True)
def _no_session_recording(monkeypatch):
    """Tests never write solving sessions into data/sessions."""
    monkeypatch.setenv('RUBIK_RECORD', '0')

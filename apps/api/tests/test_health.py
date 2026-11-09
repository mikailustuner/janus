import pytest
from fastapi.testclient import TestClient

from janus.main import app, create_app
from janus.settings import Settings, SettingsError, parse_commit

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_shows_the_deployed_commit() -> None:
    settings = Settings.from_env({"JANUS_COMMIT": "2cda4ce0123456789abcdef"})
    with TestClient(create_app(settings, configure_logs=False)) as c:
        assert c.get("/health").json() == {"status": "ok", "commit": "2cda4ce01234"}


def test_health_commit_is_null_without_one() -> None:
    settings = Settings.from_env({})
    with TestClient(create_app(settings, configure_logs=False)) as c:
        assert c.get("/health").json() == {"status": "ok", "commit": None}


@pytest.mark.parametrize("raw", ["xyz", "2CDA4CE", "2cda4c", "2cda4ce; rm", "a" * 41])
def test_commit_must_be_a_git_id(raw: str) -> None:
    with pytest.raises(SettingsError, match="JANUS_COMMIT"):
        parse_commit(raw)

"""Secrets from `NAME_FILE` (deploy: secrets only as mounted files)."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from janus.settings import Settings, SettingsError, secret_value
from janus.simulation import dbrole

# Printable secrets without line breaks or surrounding blanks (what the deploy scripts write).
VALUES = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=0x2FFF, exclude_categories=["Cs"]),
    min_size=1,
    max_size=80,
)
NO_TMP = settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=60)


def _file(tmp_path: Path, content: bytes) -> str:
    path = tmp_path / "secret"
    path.write_bytes(content)
    return str(path)


@NO_TMP
@given(VALUES, st.sampled_from(["", "\n"]))
def test_value_round_trips(tmp_path: Path, value: str, newline: str) -> None:
    path = _file(tmp_path, (value + newline).encode())
    assert secret_value({"X_FILE": path}, "X") == value


def test_only_one_trailing_newline_is_removed(tmp_path: Path) -> None:
    assert secret_value({"X_FILE": _file(tmp_path, b"a\n\n")}, "X") == "a\n"


def test_plain_variable_still_works() -> None:
    assert secret_value({"X": "v"}, "X") == "v"
    assert secret_value({}, "X") == ""
    assert secret_value({"X": "", "X_FILE": ""}, "X") == ""


@NO_TMP
@given(VALUES.filter(lambda v: v.strip() != ""), VALUES)
def test_both_set_is_an_error_without_values(tmp_path: Path, direct: str, filed: str) -> None:
    path = _file(tmp_path, filed.encode())
    with pytest.raises(SettingsError) as err:
        secret_value({"X": direct, "X_FILE": path}, "X")
    assert str(err.value) == "set only one of X and X_FILE"


def test_missing_file_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="X_FILE"):
        secret_value({"X_FILE": str(tmp_path / "nope")}, "X")


@NO_TMP
@given(st.binary(min_size=4, max_size=40).filter(lambda b: b"\n" not in b))
def test_undecodable_file_error_and_context_hide_the_bytes(tmp_path: Path, raw: bytes) -> None:
    bad = b"\xff\xfe" + raw
    with pytest.raises(SettingsError) as err:
        secret_value({"X_FILE": _file(tmp_path, bad)}, "X")
    assert err.value.__cause__ is None and err.value.__suppress_context__
    assert repr(bad) not in str(err.value) and "\\xff" not in str(err.value)


def test_unreadable_path_is_a_directory(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="X_FILE"):
        secret_value({"X_FILE": str(tmp_path)}, "X")


def test_settings_read_the_files(tmp_path: Path) -> None:
    key = base64.urlsafe_b64encode(bytes(range(32))).decode().rstrip("=")
    (tmp_path / "k").write_text(key + "\n")
    (tmp_path / "u").write_text("postgresql://u:p@h:5432/d\n")
    s = Settings.from_env(
        {"JANUS_NOISE_KEY_FILE": str(tmp_path / "k"), "DATABASE_URL_FILE": str(tmp_path / "u")}
    )
    assert s.noise_key == bytes(range(32))
    assert s.database_url == "postgresql://u:p@h:5432/d"


def test_settings_reject_both_forms(tmp_path: Path) -> None:
    (tmp_path / "u").write_text("postgresql://u:p@h/d")
    with pytest.raises(SettingsError, match="DATABASE_URL"):
        Settings.from_env({"DATABASE_URL": "x", "DATABASE_URL_FILE": str(tmp_path / "u")})


def test_note_keys_can_come_from_a_file(tmp_path: Path) -> None:
    key = base64.urlsafe_b64encode(bytes(range(32))).decode().rstrip("=")
    (tmp_path / "n").write_text(f"k1:{key}\n")
    s = Settings.from_env(
        {"JANUS_NOTE_KEYS_FILE": str(tmp_path / "n"), "JANUS_NOTE_SIGNING_KEY_ID": "k1"}
    )
    assert s.note_keys == {"k1": bytes(range(32))}


def test_dbrole_main_reads_files_and_reports_errors_without_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "short-secret-value"  # noqa: S105
    (tmp_path / "pw").write_text(secret + "\n")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("SIMULATOR_DB_PASSWORD", "also")
    monkeypatch.setenv("SIMULATOR_DB_PASSWORD_FILE", str(tmp_path / "pw"))
    assert dbrole.main() == 2
    err = capsys.readouterr().err
    assert "SIMULATOR_DB_PASSWORD" in err and secret not in err

    monkeypatch.delenv("SIMULATOR_DB_PASSWORD")
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.setenv("DATABASE_URL_FILE", str(tmp_path / "missing"))
    assert dbrole.main() == 2
    assert "DATABASE_URL_FILE" in capsys.readouterr().err

    seen: dict[str, str] = {}

    def fake_set(_conn: object, password: str) -> None:
        seen["password"] = password

    class FakeConn:
        def __enter__(self) -> FakeConn:
            return self

        def __exit__(self, *_a: object) -> None:
            return None

    (tmp_path / "url").write_text("postgresql://x\n")
    monkeypatch.setenv("DATABASE_URL_FILE", str(tmp_path / "url"))

    def fake_connect(_url: str, **_kw: object) -> FakeConn:
        return FakeConn()

    monkeypatch.setattr(dbrole.psycopg, "connect", fake_connect)
    monkeypatch.setattr(dbrole, "set_password", fake_set)
    assert dbrole.main() == 0
    assert seen["password"] == secret

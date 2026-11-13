"""Checks of deploy/check_compose.py: secrets as files only, project names, staging defaults."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

DEPLOY = Path(__file__).resolve().parents[3] / "deploy"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_compose", DEPLOY / "check_compose.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


check = _load()
SECRET_NAMES = (
    "postgres_password",
    "database_url",
    "noise_key",
    "simulator_db_password",
    "simulator_database_url",
)


def _hardened(user: str, networks: list[str], **extra: Any) -> dict[str, Any]:
    return {
        "read_only": True,
        "security_opt": ["no-new-privileges:true"],
        "cap_drop": ["ALL"],
        "user": user,
        "mem_limit": "100m",
        "cpus": 0.1,
        "networks": {n: None for n in networks},
        **extra,
    }


def good_config(name: str = "janus-public") -> dict[str, Any]:
    sim = _hardened("10002", ["internal"], secrets=[{"source": "simulator_database_url"}])
    sim.update(pids_limit=64, tmpfs=["/tmp:size=1m,noexec,nosuid,nodev"])  # noqa: S108
    return {
        "name": name,
        "services": {
            "postgres": _hardened(
                "999",
                ["internal"],
                environment={"POSTGRES_PASSWORD_FILE": "/run/secrets/postgres_password"},
                secrets=[{"source": "postgres_password"}],
            ),
            "migrate": _hardened(
                "10001",
                ["internal"],
                secrets=[{"source": "database_url"}, {"source": "simulator_db_password"}],
                profiles=["migrate"],
            ),
            "api": _hardened(
                "10001",
                ["internal"],
                environment={
                    "DATABASE_URL_FILE": "/run/secrets/database_url",
                    "JANUS_NOTE_KEYS": "",
                },
                secrets=[{"source": "database_url"}, {"source": "noise_key"}],
            ),
            "simulator": sim,
            "web": _hardened("1000", ["internal", "edge"]),
            "cloudflared": _hardened("1000", ["edge"]),
        },
        "secrets": {n: {"file": f"/stack/secrets/{n}"} for n in SECRET_NAMES},
        "networks": {
            "internal": {"name": f"{name}-internal", "internal": True},
            "edge": {"name": f"{name}-edge"},
        },
    }


def test_good_config_passes_for_both_projects() -> None:
    assert check.problems(good_config()) == []
    assert check.problems(good_config("janus-staging")) == []


@pytest.mark.parametrize("name", ["janus", "other", ""])
def test_project_names(name: str) -> None:
    cfg = good_config()
    cfg["name"] = name
    assert any("project name" in p for p in check.problems(cfg))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("POSTGRES_PASSWORD", "hunter2"),
        ("JANUS_NOISE_KEY", "abc"),
        ("SOME_API_TOKEN", "t"),
        ("DATABASE_URL", "postgresql://janus:pw@postgres:5432/janus"),
        ("ANYTHING", "postgresql://u:p@h/d"),
    ],
)
def test_secret_looking_environment_is_rejected(key: str, value: str) -> None:
    cfg = good_config()
    cfg["services"]["api"]["environment"][key] = value
    assert any(key in p for p in check.problems(cfg))


def test_url_without_credentials_and_empty_values_are_fine() -> None:
    cfg = good_config()
    env = cfg["services"]["api"]["environment"]
    env["JANUS_PUBLIC_BASE_URL"] = "https://janusmeds.org"
    env["JANUS_NOTE_KEYS"] = ""
    assert check.problems(cfg) == []


def test_undeclared_or_missing_or_extra_secret() -> None:
    cfg = good_config()
    del cfg["secrets"]["noise_key"]
    assert any("noise_key is not declared" in p for p in check.problems(cfg))
    cfg = good_config()
    cfg["services"]["api"]["secrets"].pop()
    assert any("api: secrets must be" in p for p in check.problems(cfg))
    cfg = good_config()
    cfg["services"]["simulator"]["secrets"].append({"source": "database_url"})
    assert any("simulator: secrets must be" in p for p in check.problems(cfg))


def test_secret_without_file_is_rejected() -> None:
    cfg = good_config()
    cfg["secrets"]["noise_key"] = {"environment": "X"}
    assert any("must be a file" in p for p in check.problems(cfg))


def test_network_names_follow_the_project() -> None:
    cfg = good_config("janus-staging")
    cfg["networks"]["edge"]["name"] = "janus-public-edge"
    assert any("edge must be named janus-staging-edge" in p for p in check.problems(cfg))


def _resolve(tmp: Path, **env: str) -> dict[str, Any]:
    stack = tmp / "stack"
    (stack / "secrets").mkdir(parents=True, exist_ok=True)
    for n in SECRET_NAMES:
        (stack / "secrets" / n).write_text("x")
    shutil.copy(DEPLOY / "compose.yml", stack / "compose.yml")
    full = {"JANUS_UID": "1000", "JANUS_GID": "1000", "JANUS_TAG": "t", "PATH": "/usr/bin:/bin"}
    cmd = ["docker", "compose", "--project-directory", str(stack)]
    cmd += ["-f", str(stack / "compose.yml"), "--profile", "migrate", "config", "--format", "json"]
    out = subprocess.run(  # noqa: S603
        cmd, env={**full, **env}, capture_output=True, text=True, check=True, timeout=60
    ).stdout
    return json.loads(out)


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
def test_production_defaults_and_staging_resolution(tmp_path: Path) -> None:
    default = _resolve(tmp_path)
    explicit = _resolve(
        tmp_path,
        JANUS_STACK="janus-public",
        JANUS_NET_INTERNAL="172.31.251.0/24",
        JANUS_NET_EDGE="172.31.250.0/24",
    )
    assert default["name"] == "janus-public"
    assert default["networks"]["internal"]["name"] == "janus-public-internal"
    assert default["networks"]["edge"]["name"] == "janus-public-edge"
    subnet = {k: v["ipam"]["config"][0]["subnet"] for k, v in default["networks"].items()}
    assert subnet == {"internal": "172.31.251.0/24", "edge": "172.31.250.0/24"}
    assert default == explicit
    assert check.problems(default) == []
    staging = _resolve(
        tmp_path,
        JANUS_STACK="janus-staging",
        JANUS_NET_INTERNAL="172.31.254.0/24",
        JANUS_NET_EDGE="172.31.253.0/24",
    )
    assert staging["name"] == "janus-staging"
    assert staging["networks"]["internal"]["ipam"]["config"][0]["subnet"] == "172.31.254.0/24"
    assert check.problems(staging) == []

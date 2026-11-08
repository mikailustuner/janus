"""Note token and QR size: P1-P6, P9, P32 (pure part), P33, P34 (doctor-loop design §6, §13)."""

from __future__ import annotations

import ast
import base64
import dataclasses
import datetime as dt
import hashlib
import hmac
import urllib.parse
from pathlib import Path
from typing import Any

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from janus.memory.vocabulary import load_events
from janus.notes import qr, token
from janus.notes.token import (
    DOMAIN,
    MAC_BYTES,
    Keyring,
    Payload,
    TokenError,
    TokenErrorCode,
    TokenFinding,
    body_length,
    encode_body,
    expiry_for,
    sign,
    verify,
    verify_signature_only,
)
from janus.settings import EVENT_VOCABULARY, Settings, SettingsError
from tests.notes_strategies import keyrings, keys, kids, payloads

BEFORE = dt.date(2000, 1, 1)


def _code(fn: Any) -> TokenErrorCode:
    with pytest.raises(TokenError) as info:
        fn()
    return info.value.code


def _resign(keyring: Keyring, body: bytes, kid: str | None = None) -> str:
    key = keyring.keys[kid or keyring.signing]
    mac = hmac.new(key, DOMAIN + body, hashlib.sha256).digest()[:MAC_BYTES]
    return token.b64encode(body + mac)


# --- P1 ---------------------------------------------------------------------------------------


@given(data=st.data())
def test_p1_round_trip(data: st.DataObject) -> None:
    """Feature: doctor-loop, Property P1. Validates Req 2.1."""
    ring = data.draw(keyrings())
    p = data.draw(payloads(kid=ring.signing))
    t = sign(ring, p)
    assert verify(ring, t, p.issue_week) == p
    assert verify(ring, t, p.expires_on - dt.timedelta(days=1)) == p
    raw = base64.urlsafe_b64decode(t + "=" * (-len(t) % 4))
    assert len(raw) == body_length(p)
    assert set(t) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


# --- P2 ---------------------------------------------------------------------------------------

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


@given(data=st.data())
def test_p2_any_change_invalidates(data: st.DataObject) -> None:
    """Feature: doctor-loop, Property P2 (seed: payload tamper). Validates Req 2.1, 2.2, 2.4."""
    ring = data.draw(keyrings())
    p = data.draw(payloads(kid=ring.signing))
    t = sign(ring, p)
    kind = data.draw(st.sampled_from(["sub", "ins", "del", "kid", "field"]))
    if kind == "sub":
        i = data.draw(st.integers(0, len(t) - 1))
        c = data.draw(st.sampled_from(ALPHABET).filter(lambda c: c != t[i]))
        bad = t[:i] + c + t[i + 1 :]
    elif kind == "ins":
        i = data.draw(st.integers(0, len(t)))
        bad = t[:i] + data.draw(st.sampled_from(ALPHABET)) + t[i:]
    elif kind == "del":
        i = data.draw(st.integers(0, len(t) - 1))
        bad = t[:i] + t[i + 1 :]
    elif kind == "kid":
        others = [k for k in ring.keys if k != ring.signing]
        assume(others)
        other = data.draw(st.sampled_from(others))
        body = encode_body(dataclasses.replace(p, kid=other))
        mac = base64.urlsafe_b64decode(t + "=" * (-len(t) % 4))[-MAC_BYTES:]
        bad = token.b64encode(body + mac)  # kid switched, MAC of the original key
    else:
        q = data.draw(payloads(kid=ring.signing))
        assume(q != p)
        raw = base64.urlsafe_b64decode(t + "=" * (-len(t) % 4))
        bad = token.b64encode(encode_body(q) + raw[-MAC_BYTES:])  # another payload, old MAC
    assume(bad != t)
    assert _code(lambda: verify(ring, bad, p.issue_week)) is TokenErrorCode.invalid_token


# --- P3 ---------------------------------------------------------------------------------------


class Rotation(RuleBasedStateMachine):
    """Feature: doctor-loop, Property P3. Validates Req 2.4."""

    def __init__(self) -> None:
        super().__init__()
        self.keys: dict[str, bytes] = {"k0": b"\x01" * 32}
        self.signing = "k0"
        self.issued: list[tuple[str, str, Payload]] = []  # (kid, token, payload)
        self.counter = 1

    def ring(self) -> Keyring:
        return Keyring(dict(self.keys), self.signing)

    @rule(material=keys)
    def add_key(self, material: bytes) -> None:
        if material in self.keys.values():
            return
        self.keys[f"k{self.counter}"] = material
        self.counter += 1

    @rule(data=st.data())
    def switch_signing(self, data: st.DataObject) -> None:
        self.signing = data.draw(st.sampled_from(sorted(self.keys)))

    @rule(data=st.data())
    def remove_key(self, data: st.DataObject) -> None:
        removable = [k for k in self.keys if k != self.signing]
        if removable:
            del self.keys[data.draw(st.sampled_from(removable))]

    @rule(data=st.data())
    def issue(self, data: st.DataObject) -> None:
        p = data.draw(payloads(kid=self.signing, max_findings=2))
        self.issued.append((self.signing, sign(self.ring(), p), p))

    @invariant()
    def verifies_iff_key_present(self) -> None:
        ring = self.ring()
        for kid, t, p in self.issued:
            if kid in self.keys:
                assert verify(ring, t, p.issue_week) == p
            else:
                assert _code(lambda t=t, p=p: verify(ring, t, p.issue_week)) is (
                    TokenErrorCode.invalid_token
                )


TestRotation = Rotation.TestCase
TestRotation.settings = settings(max_examples=50, stateful_step_count=12)


@given(data=st.data())
def test_p3_never_under_another_key(data: st.DataObject) -> None:
    """Feature: doctor-loop, Property P3 (relabelled key id). Validates Req 2.4."""
    ring = data.draw(keyrings())
    assume(len(ring.keys) >= 2)
    p = data.draw(payloads(kid=ring.signing))
    other = data.draw(st.sampled_from([k for k in ring.keys if k != ring.signing]))
    forged = _resign(ring, encode_body(dataclasses.replace(p, kid=other)), kid=ring.signing)
    assert _code(lambda: verify(ring, forged, p.issue_week)) is TokenErrorCode.invalid_token
    with pytest.raises(ValueError, match="signing key"):
        sign(ring, dataclasses.replace(p, kid=other))


# --- P4 ---------------------------------------------------------------------------------------


@given(
    instant=st.datetimes(
        min_value=dt.datetime(2020, 1, 1),
        max_value=dt.datetime(2060, 12, 31),
        timezones=st.just(dt.UTC),
    ),
    data=st.data(),
)
def test_p4_expiry(instant: dt.datetime, data: st.DataObject) -> None:
    """Feature: doctor-loop, Property P4. Validates Req 2.6."""
    exp = expiry_for(instant)
    assert exp.weekday() == 0
    start = dt.datetime.combine(exp, dt.time(0), dt.UTC)
    assert dt.timedelta(days=28) < start - instant <= dt.timedelta(days=35)
    ring = Keyring({"a": b"\x02" * 32}, "a")
    p = dataclasses.replace(
        data.draw(payloads(kid="a", max_findings=1)), issue_week=token.monday_of(instant.date())
    )
    assert p.expires_on == exp
    t = sign(ring, p)
    assert verify(ring, t, exp - dt.timedelta(days=1)) == p
    for late in (exp, exp + dt.timedelta(days=data.draw(st.integers(0, 400)))):
        assert _code(lambda late=late: verify(ring, t, late)) is TokenErrorCode.token_expired
    assert verify_signature_only(ring, t) == p  # withdrawal ignores expiry


def test_p4_naive_time_refused() -> None:
    with pytest.raises(ValueError):
        expiry_for(dt.datetime(2026, 11, 8, 12, 0))


# --- P5 ---------------------------------------------------------------------------------------


@given(data=st.data())
def test_p5_non_canonical_and_near_miss(data: st.DataObject) -> None:
    """Feature: doctor-loop, Property P5. Validates Req 2.2."""
    ring = Keyring({"a": b"\x03" * 32}, "a")
    p = data.draw(payloads(kid="a", max_findings=3))
    t = sign(ring, p)
    raw = base64.urlsafe_b64decode(t + "=" * (-len(t) % 4))
    variants: list[str] = [t + "=" * (-len(t) % 4 or 4), " " + t, t + "\n", t.replace("-", "+"), ""]
    if len(raw) % 3:  # the last character carries unused bits: set them
        last = ALPHABET.index(t[-1])
        spare = 0b1111 if len(raw) % 3 == 1 else 0b11
        if last & spare == 0:
            variants.append(t[:-1] + ALPHABET[last | 1])
    variants.append(token.b64encode(raw) + "A")  # trailing character
    variants.append(_resign(ring, encode_body(p) + b"\x00"))  # trailing byte, valid MAC
    variants.append(_resign(ring, bytes([2]) + encode_body(p)[1:]))  # unknown version
    for v in variants:
        if v == t:
            continue
        assert _code(lambda v=v: verify(ring, v, p.issue_week)) is TokenErrorCode.invalid_token


# --- P6 ---------------------------------------------------------------------------------------


@given(data=st.data())
def test_p6_compare_digest_once(data: st.DataObject) -> None:
    """Feature: doctor-loop, Property P6. Validates Req 2.5."""
    ring = data.draw(keyrings())
    p = data.draw(payloads(kid=ring.signing, max_findings=2))
    t = sign(ring, p)
    tampered = t[:-2] + ("AA" if t[-2:] != "AA" else "BA")
    calls: list[tuple[int, int]] = []
    real = hmac.compare_digest

    def spy(a: bytes, b: bytes) -> bool:
        calls.append((len(a), len(b)))
        return real(a, b)

    token.hmac.compare_digest = spy  # type: ignore[assignment]
    try:
        for candidate in (t, tampered):
            calls.clear()
            try:
                verify(ring, candidate, p.issue_week)
            except TokenError:
                pass
            assert calls == [(MAC_BYTES, MAC_BYTES)] or (not calls and candidate == tampered)
    finally:
        token.hmac.compare_digest = real  # type: ignore[assignment]


def test_p6_no_equality_on_mac_bytes() -> None:
    tree = ast.parse(Path(token.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and any(
            isinstance(o, (ast.Eq, ast.NotEq)) for o in node.ops
        ):
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            assert not names & {"mac", "expected", "digest"}, ast.unparse(node)


# --- P9 ---------------------------------------------------------------------------------------

K1 = base64.urlsafe_b64encode(b"\x11" * 32).decode().rstrip("=")
K2 = base64.urlsafe_b64encode(b"\x22" * 32).decode().rstrip("=")
SHORT = base64.urlsafe_b64encode(b"\x33" * 16).decode().rstrip("=")


def test_p9_valid_settings() -> None:
    s = Settings.from_env(
        {
            "JANUS_NOTE_KEYS": f"k1:{K1}, k2:{K2}",
            "JANUS_NOTE_SIGNING_KEY_ID": "k2",
            "JANUS_OUTCOME_CONSENT_VERSIONS": "outcome-2026-11",
            "JANUS_PUBLIC_BASE_URL": "https://janus.example",
        }
    )
    assert dict(s.note_keys) == {"k1": b"\x11" * 32, "k2": b"\x22" * 32}
    assert s.note_signing_key_id == "k2"
    assert s.outcome_consent_versions == frozenset({"outcome-2026-11"})
    assert K1 not in repr(s) and "\\x11" not in repr(s)
    assert Settings.from_env({}).note_keys == {}


@pytest.mark.parametrize(
    ("env", "name"),
    [
        ({"JANUS_NOTE_KEYS": f"k1:{SHORT}", "JANUS_NOTE_SIGNING_KEY_ID": "k1"}, "JANUS_NOTE_KEYS"),
        (
            {"JANUS_NOTE_KEYS": "k1:not*base64", "JANUS_NOTE_SIGNING_KEY_ID": "k1"},
            "JANUS_NOTE_KEYS",
        ),
        ({"JANUS_NOTE_KEYS": f"K1:{K1}", "JANUS_NOTE_SIGNING_KEY_ID": "K1"}, "JANUS_NOTE_KEYS"),
        (
            {"JANUS_NOTE_KEYS": f"k1:{K1},k1:{K2}", "JANUS_NOTE_SIGNING_KEY_ID": "k1"},
            "JANUS_NOTE_KEYS",
        ),
        (
            {"JANUS_NOTE_KEYS": f"k1:{K1},k2:{K1}", "JANUS_NOTE_SIGNING_KEY_ID": "k1"},
            "JANUS_NOTE_KEYS",
        ),
        ({"JANUS_NOTE_KEYS": f"k1:{K1}"}, "JANUS_NOTE_SIGNING_KEY_ID"),
        (
            {"JANUS_NOTE_KEYS": f"k1:{K1}", "JANUS_NOTE_SIGNING_KEY_ID": "k9"},
            "JANUS_NOTE_SIGNING_KEY_ID",
        ),
        ({"JANUS_NOTE_SIGNING_KEY_ID": "k1"}, "JANUS_NOTE_SIGNING_KEY_ID"),
        (
            {
                "JANUS_NOTE_KEYS": f"k1:{K1}",
                "JANUS_NOTE_SIGNING_KEY_ID": "k1",
                "JANUS_NOISE_KEY": K1,
            },
            "JANUS_NOTE_KEYS",
        ),
        ({"JANUS_OUTCOME_CONSENT_VERSIONS": "Bad Id"}, "JANUS_OUTCOME_CONSENT_VERSIONS"),
        ({"JANUS_PUBLIC_BASE_URL": "https://janus.example/"}, "JANUS_PUBLIC_BASE_URL"),
        ({"JANUS_PUBLIC_BASE_URL": "https://janus.example/?a=1"}, "JANUS_PUBLIC_BASE_URL"),
        ({"JANUS_PUBLIC_BASE_URL": "http://janus.example"}, "JANUS_PUBLIC_BASE_URL"),
        ({"JANUS_PUBLIC_BASE_URL": "https://" + "a" * 40 + ".example"}, "JANUS_PUBLIC_BASE_URL"),
    ],
)
def test_p9_defects_named_without_key_material(env: dict[str, str], name: str) -> None:
    """Feature: doctor-loop, Property P9. Validates Req 2.3."""
    with pytest.raises(SettingsError) as info:
        Settings.from_env(env)
    message = str(info.value)
    assert name in message
    for secret in (K1, K2, SHORT):
        assert secret not in message


# --- P32 (pure part) --------------------------------------------------------------------------

bases = st.sampled_from(
    [
        "https://janus.example",
        "https://a.example/app",
        "http://localhost:3100",
        "https://x.io:8443/p/q",
    ]
)


@given(base=bases, data=st.data())
def test_p32_token_only_in_fragment(base: str, data: st.DataObject) -> None:
    """Feature: doctor-loop, Property P32 (outcome_url). Validates Req 2.1, 13.2."""
    assert Settings.from_env({"JANUS_PUBLIC_BASE_URL": base}).public_base_url == base
    ring = Keyring({"a": b"\x04" * 32}, "a")
    t = sign(ring, data.draw(payloads(kid="a", max_findings=3)))
    url = qr.outcome_url(base, t)
    parts = urllib.parse.urlsplit(url)
    b = urllib.parse.urlsplit(base)
    assert (parts.scheme, parts.netloc, parts.path, parts.query) == (
        b.scheme,
        b.netloc,
        b.path + "/o",
        "",
    )
    assert parts.fragment == t
    assert t not in url[: url.index("#")]


# --- P33 --------------------------------------------------------------------------------------

LONGEST_EVENT = max(len(k) for k in load_events(EVENT_VOCABULARY).pipc_event_keys().values())


def _worst(n: int) -> Payload:
    findings = tuple(
        TokenFinding(
            row=65,
            index_key="Q9999999999",
            marker_key="Q9999999998",
            index_codes=("Z99ZZ98", "Z99ZZ99"),
            marker_codes=("Z99ZZ98", "Z99ZZ99"),
            event=(f"{i:03d}" + "x" * LONGEST_EVENT)[:LONGEST_EVENT],
            direction="adverse",
            form_confirmed=True,
        )
        for i in range(n)
    )
    return Payload("abcdefgh", b"\xff" * 16, dt.date(2026, 11, 2), "de", "EU", "a" * 32, findings)


def test_p33_guarantee_with_every_field_at_maximum() -> None:
    """Feature: doctor-loop, Property P33 (worst case). Validates Req 2.1."""
    ring = Keyring({"abcdefgh": b"\x05" * 32}, "abcdefgh")
    assert qr.fits(_worst(qr.MIN_GUARANTEED_FINDINGS))
    t, kept = qr.fit_findings(ring, _worst(40))
    assert kept >= qr.MIN_GUARANTEED_FINDINGS
    url = qr.outcome_url("https://" + "a" * (qr.MAX_BASE_URL_BYTES - 8), t)
    assert len(url.encode()) - len(t) == qr.MAX_BASE_URL_BYTES + 3
    version = qr.qr_version(url)
    assert version is not None and version <= qr.MAX_VERSION


@settings(max_examples=60)
@given(data=st.data())
def test_p33_longest_fitting_prefix(data: st.DataObject) -> None:
    """Feature: doctor-loop, Property P33. Validates Req 2.1."""
    ring = Keyring({"a": b"\x06" * 32}, "a")
    p = data.draw(payloads(kid="a", max_findings=60))
    t, kept = qr.fit_findings(ring, p)
    assert verify(ring, t, p.issue_week).findings == p.findings[:kept]
    assert qr.fits(dataclasses.replace(p, findings=p.findings[:kept]))
    if kept < len(p.findings):
        assert not qr.fits(dataclasses.replace(p, findings=p.findings[: kept + 1]))
    if len(p.findings) >= qr.MIN_GUARANTEED_FINDINGS:
        assert kept >= qr.MIN_GUARANTEED_FINDINGS or LONGEST_EVENT < max(
            len(f.event) for f in p.findings
        )


# Byte capacities at level M measured with segno 1.6.6 (design §1); codewords = bytes + 2 or 3.
SEGNO_BYTES_M = {1: 14, 9: 180, 10: 213, 20: 666, 21: 711, 24: 911, 25: 997, 26: 1059, 40: 2331}


@pytest.mark.parametrize(("version", "capacity"), sorted(SEGNO_BYTES_M.items()))
def test_p33_capacity_table_matches_segno(version: int, capacity: int) -> None:
    assert qr.qr_version("x" * capacity) == version
    assert qr.qr_version("x" * (capacity + 1)) == version + 1 if version < 40 else True


# --- P34 --------------------------------------------------------------------------------------


@given(data=st.data())
def test_p34_codec(data: st.DataObject) -> None:
    """Feature: doctor-loop, Property P34. Validates Req 2.1, 2.2."""
    ring = Keyring({"a": b"\x07" * 32}, "a")
    p = data.draw(payloads(kid="a"))
    body = encode_body(p)
    assert len(body) + MAC_BYTES == body_length(p)
    assert verify(ring, _resign(ring, body), p.issue_week) == p
    # Re-signed mutations of the body: a valid MAC never makes a malformed body acceptable.
    i = data.draw(st.integers(0, len(body) - 1))
    value = data.draw(st.integers(0, 255).filter(lambda v: v != body[i]))
    mutated = body[:i] + bytes([value]) + body[i + 1 :]
    try:
        q = verify(ring, _resign(ring, mutated), dt.date(2100, 1, 4))
    except TokenError as exc:
        assert exc.code in (TokenErrorCode.invalid_token, TokenErrorCode.token_expired)
    else:
        assert encode_body(q) == mutated  # anything accepted re-encodes to the same bytes


def test_p34_atc_packing_examples() -> None:
    for code in ("A00AA00", "C08CA01", "Z99ZZ99", "J01DH51"):
        assert token.unpack_atc(token.pack_atc(code)) == code
    with pytest.raises(TokenError):
        token.unpack_atc(b"\xff\xff\xff\xff")


def test_p34_non_minimal_varint_refused() -> None:
    ring = Keyring({"a": b"\x08" * 32}, "a")
    f = TokenFinding(1, "Q5", "Q6", ("C08CA01",), ("C03CA01",), "oedema", "adverse", True)
    p = Payload("a", b"\x01" * 16, dt.date(2026, 11, 2), "en", "TR", "v1", (f,))
    body = encode_body(p)
    i = body.index(bytes([10, 12]))  # Q5 -> 10, Q6 -> 12, one byte each
    padded = body[:i] + bytes([10 | 0x80, 0]) + body[i + 1 :]
    assert (
        _code(lambda: verify(ring, _resign(ring, padded), p.issue_week))
        is TokenErrorCode.invalid_token
    )


def test_kids_strategy_matches_settings_pattern() -> None:
    @given(kids)
    def check(kid: str) -> None:
        assert token.KID_RE.fullmatch(kid)

    check()

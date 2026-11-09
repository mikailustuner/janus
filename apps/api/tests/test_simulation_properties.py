"""Simulation service, pure properties (simulation-service design §9).

S1  the browser fixtures are current (the web test compares its port with them)
S2  no individualised simulation (owner decision 2026-11-09): the request schema has no
    person-specific field and no free text; results are distributions, never one person's values
S3  validation: allow-listed ids and bounded, strict numbers only; unknown fields rejected;
    errors name fields, never values or unknown field names
S4  canonical form and cache key: order- and noise-insensitive, kind- and version-sensitive
S5  rate limits: never more than the limit in any window; retry-after is honest; no address kept;
    bounded memory; entries expire
S6  the allow-list's validation verdicts are the time machine's (compartmental recomputed);
    virtual populations are the cited ones
S7  the httk output reader accepts only its own format
"""

from __future__ import annotations

import csv
import dataclasses
import json
import math
import random
import re
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.paths import repo_root
from janus.simulation import parity
from janus.simulation.allowlist import allowlist
from janus.simulation.compartmental import explore, params_for
from janus.simulation.execute import ModelError, parse_httk
from janus.simulation.ratelimit import Limiter, Window, client_address
from janus.simulation.schemas import (
    DISCLAIMER,
    REQUEST_MODELS,
    VIRTUAL_POPULATION,
    CompartmentalIn,
    InvalidRequestError,
    canonical,
    input_hash,
    parse,
)
from janus.timemachine.build import model_for
from janus.timemachine.pk import auc_inf, cmax
from janus.timemachine.validation import DrugValidation

ALLOW = allowlist()
LIM = ALLOW.limits
NAMES = {
    "kind",
    "compound",
    "population",
    "dose_mg",
    "interval_h",
    "doses",
    "samples",
    "<unknown>",
    "body",
}


def _between(lo: float, hi: float) -> st.SearchStrategy[float]:
    return st.floats(min_value=lo, max_value=hi, allow_nan=False, allow_infinity=False)


@st.composite
def valid_requests(draw: st.DrawFn) -> dict[str, Any]:
    if draw(st.booleans()):
        c = draw(st.sampled_from(list(ALLOW.compartmental.values())))
        interval = draw(st.sampled_from([None, *c.intervals_h]))
        fit = (LIM.horizon_max_h - LIM.horizon_after_last_dose_h) // interval + 1 if interval else 1
        doses = 1 if interval is None else draw(st.integers(2, min(LIM.doses_max, fit)))
        return {
            "kind": "compartmental",
            "compound": c.id,
            "population": draw(st.sampled_from(list(c.populations))),
            "dose_mg": draw(_between(c.dose.low, c.dose.high)),
            "interval_h": interval,
            "doses": doses,
            "samples": draw(
                st.integers(LIM.compartmental_samples_min, LIM.compartmental_samples_max)
            ),
        }
    return {
        "kind": "httk_population",
        "compound": draw(st.sampled_from(list(ALLOW.httk))),
        "samples": draw(st.integers(LIM.population_samples_min, LIM.population_samples_max)),
    }


# --- S2: no individualised simulation ----------------------------------------------------------

PERSON = re.compile(
    r"weight|bw|kg|height|bmi|age|sex|gender|creat|egfr|gfr|kidney|renal|liver|hepat|"
    r"genotype|cyp|pregnan|name|patient|person|birth|race|ethnic|smok|albumin|disease",
    re.IGNORECASE,
)


def test_s2_request_schema_has_no_person_specific_field() -> None:
    for model in REQUEST_MODELS:
        props = model.model_json_schema()["properties"]
        for name in model.model_fields:
            assert not PERSON.search(name), f"{model.__name__}.{name}"
            # No free text: every string is a fixed literal or an id pattern.
            text = json.dumps(props[name])
            if '"string"' in text:
                assert "pattern" in text or "const" in text or "enum" in text, name
        assert model.model_config.get("extra") == "forbid"


@given(valid_requests(), st.sampled_from(["body_weight_kg", "age_years", "egfr", "sex", "name"]))
def test_s2_person_fields_are_refused(body: dict[str, Any], field: str) -> None:
    with pytest.raises(InvalidRequestError) as exc:
        parse({**body, field: 70}, ALLOW)
    assert exc.value.fields == ["<unknown>"]


def test_s2_disclaimer_says_it() -> None:
    assert VIRTUAL_POPULATION == (
        "Virtual population, for research. Not about any person and not a dose recommendation."
    )
    assert DISCLAIMER.startswith(VIRTUAL_POPULATION)
    assert "Research prototype — not a medical device." in DISCLAIMER


@settings(max_examples=15)
@given(valid_requests().filter(lambda b: b["kind"] == "compartmental"))
def test_s2_results_are_distributions_only(body: dict[str, Any]) -> None:
    req = parse(body, ALLOW)
    assert isinstance(req, CompartmentalIn)
    c = ALLOW.compartmental[req.compound]
    out = explore(params_for(c, c.populations[req.population]), req.dose_mg, 48, 100)
    assert not {k for k in out if k.startswith(("point", "cmax", "tmax", "half_life"))}
    for i in range(len(out["hours"])):
        assert out["p5_ng_ml"][i] <= out["p50_ng_ml"][i] <= out["p95_ng_ml"][i]


# --- S3 -------------------------------------------------------------------------------------------


@given(valid_requests())
def test_s3_valid_requests_pass(body: dict[str, Any]) -> None:
    req = parse(json.loads(json.dumps(body)), ALLOW)
    assert req.compound == body["compound"]


@given(valid_requests(), st.data())
def test_s3_out_of_bounds_numbers_are_refused_by_name(
    body: dict[str, Any], data: st.DataObject
) -> None:
    keys = [k for k in ("dose_mg", "samples", "doses", "interval_h") if k in body]
    k = data.draw(st.sampled_from(keys))
    if k == "dose_mg":
        bad: object = data.draw(st.sampled_from([-1.0, 0.0, 1e4, 0.001]))
    elif k == "interval_h":
        bad = data.draw(st.sampled_from([1, 5, 6, 8, 49, 168]))
    else:
        bad = data.draw(st.sampled_from([0, -3, 100_001, 99_999]))
    with pytest.raises(InvalidRequestError) as exc:
        parse({**body, k: bad}, ALLOW)
    assert set(exc.value.fields) <= NAMES
    assert k in exc.value.fields or (k == "doses" and "interval_h" in exc.value.fields)


@given(
    valid_requests(),
    st.text(min_size=1, max_size=30).filter(lambda s: s not in NAMES),
    st.one_of(st.text(max_size=50), st.integers(), st.none()),
)
def test_s3_unknown_fields_are_refused_without_their_name(
    body: dict[str, Any], name: str, value: object
) -> None:
    with pytest.raises(InvalidRequestError) as exc:
        parse({**body, name: value}, ALLOW)
    assert "<unknown>" in exc.value.fields
    assert name not in exc.value.fields
    assert set(exc.value.fields) <= NAMES


@given(valid_requests(), st.data())
def test_s3_strict_types_no_text_reaches_a_model(body: dict[str, Any], data: st.DataObject) -> None:
    k = data.draw(st.sampled_from([k for k in body if k != "kind"]))
    v = body[k]
    wrong = data.draw(
        st.sampled_from([str(v), True, [v], {"x": v}])
        if not isinstance(v, str)
        else st.sampled_from(["../../etc/passwd", "Haloperidol; rm -rf /", "x" * 40, "", 1])
    )
    with pytest.raises(InvalidRequestError) as exc:
        parse({**body, k: wrong}, ALLOW)
    assert set(exc.value.fields) <= NAMES


def test_s3_non_finite_unknown_ids_and_bodies() -> None:
    base = {
        "kind": "compartmental",
        "compound": "amlodipine",
        "population": "adult",
        "dose_mg": 10.0,
        "interval_h": None,
        "doses": 1,
        "samples": 200,
    }
    parse(base, ALLOW)
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(InvalidRequestError):
            parse({**base, "dose_mg": bad}, ALLOW)
    for comp in ("caffeine", "Amlodipine", "amlodipine ", "haloperidol"):
        with pytest.raises(InvalidRequestError):
            parse({**base, "compound": comp}, ALLOW)
    # No older-adult rhein data was verified, so that population does not exist for rhein.
    with pytest.raises(InvalidRequestError) as exc:
        parse({**base, "compound": "rhein", "dose_mg": 38.58, "population": "adult_65plus"}, ALLOW)
    assert exc.value.fields == ["population"]
    # The longest allowed schedule fits the simulated time exactly (14 doses every 24 h + 48 h);
    # a schedule that would not fit is refused, never cut short.
    parse({**base, "interval_h": 24, "doses": 14}, ALLOW)
    tight = dataclasses.replace(ALLOW, limits=dataclasses.replace(LIM, horizon_max_h=300))
    with pytest.raises(InvalidRequestError) as exc:
        parse({**base, "interval_h": 24, "doses": 14}, tight)
    assert exc.value.fields == ["doses"]
    # Only the intervals listed for the compound (amlodipine: once daily).
    with pytest.raises(InvalidRequestError):
        parse({**base, "interval_h": 12, "doses": 3}, ALLOW)
    # Repeated doses need an interval; a single dose has none.
    with pytest.raises(InvalidRequestError):
        parse({**base, "doses": 3}, ALLOW)
    with pytest.raises(InvalidRequestError):
        parse({**base, "interval_h": 24}, ALLOW)
    bad_bodies: list[object] = [[], "x", 1, None]
    for bad_body in bad_bodies:
        with pytest.raises(InvalidRequestError):
            parse(bad_body, ALLOW)


# --- S4 -------------------------------------------------------------------------------------------


@given(valid_requests(), st.randoms(use_true_random=False))
def test_s4_cache_key_ignores_order_and_noise(body: dict[str, Any], rnd: random.Random) -> None:
    items = list(body.items())
    rnd.shuffle(items)
    noisy = {k: (v * (1 + 1e-12) if isinstance(v, float) else v) for k, v in items}
    a = canonical(parse(body, ALLOW))
    try:
        b = canonical(parse(noisy, ALLOW))
    except InvalidRequestError:
        return  # the noise pushed a bound value just outside: refused, not cached
    assert input_hash(a, ALLOW.version) == input_hash(b, ALLOW.version)
    assert input_hash(a, ALLOW.version) != input_hash(a, ALLOW.version + "x")


@given(valid_requests(), valid_requests())
def test_s4_different_runs_have_different_keys(a: dict[str, Any], b: dict[str, Any]) -> None:
    ca, cb = canonical(parse(a, ALLOW)), canonical(parse(b, ALLOW))
    assert (ca == cb) == (input_hash(ca, ALLOW.version) == input_hash(cb, ALLOW.version))


def test_s4_canonical_rounds_to_six_digits() -> None:
    req = parse(
        {
            "kind": "compartmental",
            "compound": "amlodipine",
            "population": "adult",
            "dose_mg": 5.123456789,
            "interval_h": None,
            "doses": 1,
            "samples": 200,
        },
        ALLOW,
    )
    assert canonical(req)["dose_mg"] == 5.12346


# --- S5 -------------------------------------------------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


@settings(max_examples=60)
@given(
    st.lists(
        st.tuples(st.sampled_from(["a", "b", "c"]), st.floats(0, 40, allow_nan=False)),
        max_size=120,
    )
)
def test_s5_never_more_than_the_limit_in_any_window(steps: list[tuple[str, float]]) -> None:
    clock = Clock()
    lim = Limiter(
        per_client=(Window(3, 30), Window(10, 600)), global_=(Window(12, 600),), clock=clock
    )
    allowed: dict[str, list[float]] = {}
    every: list[float] = []
    for client, dt in steps:
        clock.t += dt
        d = lim.check(client)
        if d.allowed:
            allowed.setdefault(client, []).append(clock.t)
            every.append(clock.t)
        else:
            assert d.retry_after >= 1
    for times in allowed.values():
        for t in times:
            assert sum(1 for u in times if t - 30 < u <= t) <= 3
            assert sum(1 for u in times if t - 600 < u <= t) <= 10
    for t in every:
        assert sum(1 for u in every if t - 600 < u <= t) <= 12


@given(st.integers(1, 5), st.floats(1, 100))
def test_s5_retry_after_is_enough(limit: int, window: float) -> None:
    clock = Clock()
    lim = Limiter(per_client=(Window(limit, window),), clock=clock)
    for _ in range(limit):
        assert lim.check("x").allowed
    d = lim.check("x")
    assert not d.allowed
    clock.t += d.retry_after
    assert lim.check("x").allowed


def test_s5_no_address_is_kept_and_memory_is_bounded() -> None:
    clock = Clock()
    lim = Limiter(per_client=(Window(5, 60),), max_keys=50, clock=clock)
    for i in range(500):
        lim.check(f"203.0.113.{i % 256}-{i}")
    assert lim.size() <= 50
    for key in lim._hits:  # pyright: ignore[reportPrivateUsage]
        assert len(key) == 16 and b"203.0.113" not in key
    assert "203.0.113" not in repr(lim)
    clock.t += 61
    lim.check("other")
    assert lim.size() == 1  # everything older than the longest window is gone
    # Two processes (two secrets) give unrelated keys for the same address.
    a = Limiter(per_client=(Window(1, 1),)).key("198.51.100.7")
    assert a != Limiter(per_client=(Window(1, 1),)).key("198.51.100.7")


def test_s5_client_address() -> None:
    cf = {"cf-connecting-ip": " 198.51.100.7 "}
    assert client_address(cf, "172.31.251.4", trust_cf=True) == "198.51.100.7"
    # Without the deployment switch a client-set header is ignored.
    assert client_address(cf, "172.31.251.4", trust_cf=False) == "172.31.251.4"
    assert client_address({}, "172.31.251.4", trust_cf=True) == "172.31.251.4"
    assert client_address({}, None, trust_cf=True) == "unknown"


@given(st.integers(0, 2**64 - 1), st.integers(0, 2**64 - 1), st.integers(0, 2**64 - 1))
def test_s5_ipv6_counts_per_64(prefix: int, a: int, b: int) -> None:
    import ipaddress

    x = str(ipaddress.IPv6Address((prefix << 64) | a))
    y = str(ipaddress.IPv6Address((prefix << 64) | b))
    kx = client_address({"cf-connecting-ip": x}, None, trust_cf=True)
    assert kx == client_address({"cf-connecting-ip": y}, None, trust_cf=True)
    assert kx.endswith("/64")


# --- S6 -------------------------------------------------------------------------------------------


def test_s6_validation_directions_are_the_time_machine_numbers() -> None:
    # time-machine design §8.1: predicted vs observed Cmax and AUC.
    table = {
        "amlodipine": ((3.88, 9.22), (217.7, 303.5)),
        "rhein": ((2970, 3200), (24113, 21300)),
        "risperidone": ((4.49, 14.66), (88.1, 91.3)),
        "metoclopramide": ((30.79, 44.0), (740.4, 314.3)),
        "haloperidol": ((6.62, 0.85), (696.8, 21.8)),
    }
    allv = {c.id: c.validation for c in ALLOW.compartmental.values()} | {
        h.id: h.validation for h in ALLOW.httk.values()
    }
    for drug, ((pc, oc), (pa, oa)) in table.items():
        v = allv[drug]
        assert v.cmax_direction == ("model_lower" if pc < oc else "model_higher"), drug
        assert v.auc_direction == ("model_lower" if pa < oa else "model_higher"), drug


def test_s6_compartmental_verdicts_are_recomputed() -> None:
    root = repo_root() / "data" / "time_machine"
    with (root / "compartmental_pk.csv").open(encoding="utf-8") as f:
        pk = {r["drug"]: r for r in csv.DictReader(f)}
    with (root / "observed_pk.csv").open(encoding="utf-8") as f:
        obs = {r["drug"]: r for r in csv.DictReader(f)}
    for c in ALLOW.compartmental.values():
        m = model_for(pk[c.id])
        o = obs[c.id]
        dose = float(o["dose_mg"])
        v = DrugValidation(
            c.id,
            o["reference_key"],
            float(o["cmax_ng_ml"]),
            float(o["auc_ng_h_ml"]),
            cmax(m, dose) * 1000,
            auc_inf(m, dose) * 1000,
        )
        assert v.credibility.value == c.validation.credibility
        assert round(v.cmax_fold, 2) == c.validation.cmax_fold
        assert round(v.auc_fold, 2) == c.validation.auc_fold
        assert any(s.kind == "validation" and s.dose_mg == dose for s in c.scenarios)
        for s in c.scenarios:
            assert c.dose.contains(s.dose_mg)


def test_s6_httk_verdicts_follow_the_time_machine_table() -> None:
    # time-machine design §8.1: httk 0 of 4 credible; metoclopramide borderline. Server runs
    # exist for the three drugs of the time machine's population layer only.
    verdicts = {h.id: h.validation.credibility for h in ALLOW.httk.values()}
    assert verdicts == {
        "risperidone": "failed",
        "metoclopramide": "borderline",
        "haloperidol": "failed",
    }


def test_s6_virtual_populations_are_the_cited_ones() -> None:
    root = repo_root() / "data" / "time_machine"
    with (root / "compartmental_pk.csv").open(encoding="utf-8") as f:
        cited = {r["drug"]: r["reference_keys"].split("|") for r in csv.DictReader(f)}
    for c in ALLOW.compartmental.values():
        assert c.populations["adult"].cl_factor == 1.0
        for p in c.populations.values():
            assert set(p.reference_keys) <= set(cited[c.id])
            assert 0 < p.cl_factor <= 1
    # Abernethy 1990: elderly vs young amlodipine clearance 19 vs 25 L/h.
    assert ALLOW.compartmental["amlodipine"].populations["adult_65plus"].cl_factor == 19 / 25
    assert set(ALLOW.compartmental["rhein"].populations) == {"adult"}
    assert ALLOW.compartmental["rhein"].f_fixed and not ALLOW.compartmental["amlodipine"].f_fixed
    ages = {p.id: (p.age_low, p.age_high) for p in ALLOW.httk_populations.values()}
    assert ages == {"adult": (20, 50), "adult_65plus": (65, 79)}  # HTTK-Pop has no 80+


def test_s1_browser_fixture_is_current() -> None:
    path = repo_root() / parity.FIXTURE
    committed = json.loads(path.read_text())
    fresh = json.loads(json.dumps(parity.build()))
    assert committed == fresh, "run: python -m janus.simulation.parity"
    shipped = json.loads((repo_root() / parity.EXPLORER).read_text())
    assert shipped == json.loads(json.dumps(parity.explorer(ALLOW))), "run the parity script"


# --- S7 -------------------------------------------------------------------------------------------


@given(st.lists(st.text(alphabet="VQX,0123456789.e-n", max_size=20), max_size=6))
def test_s7_httk_reader_is_strict(lines: list[str]) -> None:
    try:
        out = parse_httk("\n".join(lines))
    except ModelError:
        return
    for q in out["quantiles"]:
        assert len(q) == 3 and q[0] <= q[1] <= q[2]
        assert all(math.isfinite(x) for x in q)


def test_s7_httk_reader_reads_its_format() -> None:
    out = parse_httk("V,R version 4.6.1 (2026-06-24),2.7.4\nQ,0.1,0.2,0.3\nQ,0.2,0.3,0.4\n")
    assert out["versions"] == {"r": "R version 4.6.1 (2026-06-24)", "httk": "2.7.4"}
    assert out["quantiles"] == [[0.1, 0.2, 0.3], [0.2, 0.3, 0.4]]
    for bad in ("Z,1", "T,1,2", "B,70", "Q,1,2", "Q,1,inf,2", "Q,a,b,c", "Q,3,2,1"):
        with pytest.raises(ModelError):
            parse_httk(bad)

"""FAERS onset table for the PIPC rows: statistics, framing, routes of administration, outputs
and API (faers-onset-table design §8). Synthetic intervals only."""

from __future__ import annotations

import csv
import dataclasses
import io
import json
import random
import statistics
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from janus.cascades.model import AtcClass, Pattern
from janus.http_policy.routes import RouteKind, route_kind
from janus.main import create_app
from janus.memory.vocabulary import load_events
from janus.onset_table import dataset as d
from janus.onset_table import table as t
from janus.onset_table.build import class_members, event_pts, key_exclusions, row_notes
from janus.onset_table.router import OnsetTableHolder
from janus.onset_table.router import router as onset_router
from janus.onset_table.routes import RouteGroup, allowed_groups, route_group
from janus.settings import EVENT_VOCABULARY

days_st = st.lists(st.integers(0, 400), max_size=60)


def _reports(days: list[int], day_one: int = 0, same_pair: int = 0) -> tuple[t.ReportInterval, ...]:
    """One report per interval; the first `day_one` rest on a day-01 date, the first
    `same_pair` share one identical date pair, the others have distinct dates."""
    out: list[t.ReportInterval] = []
    for i, x in enumerate(days):
        start = "S0" if i < same_pair else f"S{i}"
        out.append(t.ReportInterval(x, x + i % 3, start, "20260115", i < day_one, False, 1, 1))
    return tuple(out)


def _row(
    position: int,
    days: list[int],
    extra: int = 0,
    cls: str = "statin",
    event: str = "myalgia",
    day_one: int = 0,
    same_pair: int = 0,
) -> t.RowInput:
    return t.RowInput(
        position,
        "Cardiovascular system",
        "Statin",
        "Myalgia",
        "Analgesic",
        f"Table 1, row {position}",
        cls,
        event,
        ("Myalgia",),
        ("Q1", "Q2"),
        len(days) + extra,
        _reports(days, day_one, same_pair),
        {"no_therapy_start": extra} if extra else {},
    )


@given(days_st, st.integers(0, 50))
def test_p1_status_follows_the_thresholds(days: list[int], extra: int) -> None:
    out = t.describe(_row(1, days, extra))
    n = len(days)
    expected = t.status_of(n + extra, n, 1 if n else 0)
    assert out["status"] == expected.value
    assert (out["median_days"] is not None) == (n >= t.COUNT_ONLY_BELOW)
    assert out["small_sample"] == (t.COUNT_ONLY_BELOW <= n < t.SMALL_SAMPLE_BELOW)
    if n < t.SMALL_SAMPLE_BELOW:
        assert out["weibull_shape"] is None and out["weibull_shape_class"] is None
    if expected in (t.Status.count_only, t.Status.no_interval, t.Status.no_candidate_reports):
        assert out["omitted_reason"]
    if expected is t.Status.count_only:
        assert out["zero_day_share"] is None and out["day_one_share"] is None


@given(st.lists(st.integers(0, 400), min_size=10, max_size=60), st.integers(0, 60))
def test_a_dominating_date_cluster_withholds_every_statistic(days: list[int], k: int) -> None:
    same = min(k, len(days))
    out = t.describe(_row(1, days, same_pair=same))
    assert out["largest_date_cluster"] == max(same, 1)
    if same / len(days) > t.CLUSTER_SHARE_MAX:
        assert out["status"] == "cluster_dominated"
        assert out["median_days"] is None and out["weibull_shape"] is None
        assert out["omitted_reason"]
    assert out["reports_in_clusters_ge3"] == (same if same >= 3 else 0)


@given(st.lists(st.integers(0, 400), min_size=1, max_size=80))
def test_exact_median_interval_contains_the_median_with_95_coverage(days: list[int]) -> None:
    ci = t.exact_median_ci(days)
    if len(days) < 6:
        assert ci is None
        return
    assert ci is not None
    low, high, coverage = ci
    assert low <= statistics.median(days) <= high
    assert 0.95 <= coverage <= 1


@given(st.lists(st.integers(0, 400), min_size=10, max_size=60), st.randoms(use_true_random=False))
def test_p2_statistics_do_not_depend_on_report_order(days: list[int], rnd: random.Random) -> None:
    row = _row(1, days, day_one=3)
    shuffled = list(row.reports)
    rnd.shuffle(shuffled)
    other = dataclasses.replace(row, reports=tuple(shuffled))
    assert t.describe(row) == t.describe(other)


@given(days_st)
def test_p3_rows_sharing_class_and_event_get_the_same_numbers(days: list[int]) -> None:
    rows = t.table([_row(9, days), _row(10, days), _row(12, days, event="x")])
    a, b, other = rows
    skip = {"pipc_position", "pipc_locator", "shared_with_positions", "event_key"}
    assert {k: v for k, v in a.items() if k not in skip} == {
        k: v for k, v in b.items() if k not in skip
    }
    assert a["shared_with_positions"] == [10] and b["shared_with_positions"] == [9]
    assert other["shared_with_positions"] == []


@given(days_st, st.integers(0, 20))
def test_p4_count_invariants(days: list[int], extra: int) -> None:
    out = t.describe(_row(1, days, extra))
    assert out["reports_with_interval"] <= out["candidate_reports"]
    assert sum(out["candidates_without_interval_by_reason"].values()) == extra
    if out["usable_share"] is not None:
        assert 0 <= out["usable_share"] <= 1
    assert 0 <= out["zero_day_reports"] <= out["reports_with_interval"]
    if out["median_days"] is not None:
        assert out["q25_days"] <= out["median_days"] <= out["q75_days"]
        assert out["median_ci_low_days"] <= out["median_days"] <= out["median_ci_high_days"]
        assert out["median_ci_degenerate"] == (
            out["median_ci_low_days"] == out["median_ci_high_days"]
        )
        assert out["median_days_earliest_class_start"] >= out["median_days"]


def test_inputs_that_do_not_add_up_are_refused() -> None:
    with pytest.raises(ValueError):
        t.RowInput(1, "", "", "", "", "", "c", "e", (), (), 1, _reports([1, 2]))
    with pytest.raises(ValueError):  # one candidate without an interval and no reason given
        t.RowInput(1, "", "", "", "", "", "c", "e", (), (), 3, _reports([1, 2]))
    with pytest.raises(ValueError):
        t.ReportInterval(5, 4, "s", "20260101", False, False, 1, 1)


def test_a_position_appears_once() -> None:
    with pytest.raises(ValueError):
        t.table([_row(1, [1]), _row(1, [2])])


@given(st.lists(st.integers(0, 400), min_size=12, max_size=40), st.integers(0, 12))
def test_day_one_sensitivity_needs_ten_clean_intervals(days: list[int], drop: int) -> None:
    out = t.describe(_row(1, days, day_one=drop))
    assert out["day_one_reports"] == drop
    assert out["reports_without_day_one"] == len(days) - drop
    has = out["median_days_without_day_one"] is not None
    assert has == (len(days) - drop >= t.SENSITIVITY_MIN)
    assert has != bool(out["sensitivity_omitted_reason"])


@given(st.lists(st.integers(0, 3), min_size=30, max_size=60))
def test_no_shape_when_heaping_or_few_distinct_values_decide_it(days: list[int]) -> None:
    out = t.describe(_row(1, days))
    zero_share = days.count(0) / len(days)
    if zero_share > t.SHAPE_ZERO_SHARE_MAX or len(set(days)) < t.SHAPE_MIN_DISTINCT:
        assert out["weibull_shape"] is None and out["shape_omitted_reason"]


@given(days_st)
def test_p5_every_row_says_descriptive_not_causal_not_incidence(days: list[int]) -> None:
    out = t.describe(_row(1, days))
    assert out["descriptive_only"] is True
    assert out["causal"] is False and out["incidence"] is False
    assert out["counts_are"] == "reports"


def test_route_groups() -> None:
    cases = {
        "Topical": RouteGroup.local,
        "Ophthalmic": RouteGroup.eye,
        "Subcutaneous use": RouteGroup.systemic_or_unknown,
        "Transdermal": RouteGroup.systemic_or_unknown,
        "Respiratory (inhalation)": RouteGroup.nasal_inhaled,
        "nasal j-tube": RouteGroup.systemic_or_unknown,
        "Nasal": RouteGroup.nasal_inhaled,
        "Transplacental": RouteGroup.not_patient,
        "Rectal use": RouteGroup.rectal,
        "Unknown": RouteGroup.systemic_or_unknown,
        "": RouteGroup.systemic_or_unknown,
        None: RouteGroup.systemic_or_unknown,
        "Intra-articular": RouteGroup.joint_lesion,
    }
    assert {k: route_group(k) for k in cases} == cases
    assert allowed_groups("statin") == {RouteGroup.systemic_or_unknown}
    assert RouteGroup.eye in allowed_groups("beta_blocker_index_eye")
    assert RouteGroup.rectal in allowed_groups("laxative")
    assert RouteGroup.nasal_inhaled in allowed_groups("opioid")
    assert RouteGroup.nasal_inhaled not in allowed_groups("corticosteroid_systemic")
    assert RouteGroup.joint_lesion in allowed_groups("corticosteroid_systemic")
    assert all(RouteGroup.not_patient not in allowed_groups(c) for c in ("laxative", "statin"))


@given(st.text(max_size=40))
def test_route_group_ignores_case_and_spacing(text: str) -> None:
    assert route_group(text) == route_group("  " + text.upper() + " ")


def test_curated_onset_files_are_valid() -> None:
    excl = key_exclusions()
    assert excl and all(k.startswith("Q") for ks in excl.values() for k in ks)
    notes = row_notes()
    assert notes and all(1 <= p <= 65 for p in notes)


META: dict[str, Any] = {
    "built_at": "2026-11-09T00:00:00+00:00",
    "faers_receipt_quarters": ["2025Q4", "2026Q1", "2026Q2", "2026Q3"],
    "faers_snapshot_date": "2026-10-28",
    "faers_run_id": "f",
    "faers_onset_run_id": "o",
    "faers_counts_build_id": "b",
    "resolution_dataset": "r",
    "rule_base_version": "v",
    "event_vocabulary_sha256": "s",
    "key_exclusions_sha256": "k",
    "row_notes_sha256": "n",
    "faers_onset_quality": {"usable_pairs": 1},
}


@given(st.lists(days_st, min_size=1, max_size=5))
def test_p6_csv_matches_json_and_version_follows_content(groups: list[list[int]]) -> None:
    rows = t.table([_row(i + 1, g, cls=f"c{i}") for i, g in enumerate(groups)])
    data = d.payload(rows, META)
    parsed = list(csv.DictReader(io.StringIO(d.to_csv(data))))
    assert [int(x["pipc_position"]) for x in parsed] == [r["pipc_position"] for r in rows]
    assert all(x["dataset_version"] == data["version"] for x in parsed)
    assert all(x["causal"] == "false" and x["incidence"] == "false" for x in parsed)
    assert d.payload(rows, META)["version"] == data["version"]
    changed = [dict(rows[0], candidate_reports=rows[0]["candidate_reports"] + 1), *rows[1:]]
    assert d.version(changed) != data["version"]


def test_every_pipc_row_has_one_event_key_with_terms() -> None:
    pts = event_pts(load_events(EVENT_VOCABULARY))
    assert sorted(pts) == list(range(1, 66))
    assert all(terms for _, terms in pts.values())


def test_class_members_use_the_engine_matcher_without_form_extensions() -> None:
    cls = AtcClass(
        "beta",
        (
            Pattern("C07", "include"),
            Pattern("C07AA07", "exclude"),
            Pattern("S01ED", "include", scope="form_extension", evidence_id="vander_zanden_2001"),
        ),
    )
    codes = {"Q1": ["C07AA05"], "Q2": ["C07AA07"], "Q3": ["S01ED01"], "Q4": ["A01AA01", "C07AB02"]}
    assert class_members(codes, {"beta": cls}, ["beta"]) == {"beta": ["Q1", "Q4"]}


# --- routes ------------------------------------------------------------------------------


def _data() -> dict[str, Any]:
    rows = t.table([_row(1, list(range(40))), _row(2, [3], extra=4, cls="other")])
    return d.payload(rows, META)


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    root = tmp_path / "onset_table" / "current"
    root.mkdir(parents=True)
    (root / "faers_onset_pipc.json").write_text(json.dumps(_data()), encoding="utf-8")
    application = create_app(configure_logs=False)
    application.state.onset_table = OnsetTableHolder(tmp_path)
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as cl:
        yield cl


def test_routes_are_medical_get_only() -> None:
    for route in onset_router.routes:
        assert route_kind(route) is RouteKind.medical
        assert getattr(route, "methods", set[str]()) == {"GET"}


def test_routes_serve_table_csv_and_one_row(client: TestClient) -> None:
    body = client.get("/open/faers-onset").json()
    assert body["summary"]["rows"] == 2 and body["causal"] is False
    assert body["rows"][1]["status"] == "count_only" and body["rows"][1]["median_days"] is None
    res = client.get("/open/faers-onset.csv")
    assert res.status_code == 200 and res.headers["x-janus-dataset-version"] == body["version"]
    one = client.get("/open/faers-onset/1").json()
    assert one["row"]["pipc_position"] == 1 and one["caveats"]["descriptive"]
    assert client.get("/open/faers-onset/65").json() == {"error": "unknown_position"}
    bad = client.get("/open/faers-onset/x1")
    assert bad.status_code == 422 and bad.json()["fields"] == ["position"]


def test_routes_answer_503_without_a_table(tmp_path: Path) -> None:
    application = create_app(configure_logs=False)
    application.state.onset_table = OnsetTableHolder(tmp_path)
    with TestClient(application) as cl:
        for path in ("/open/faers-onset", "/open/faers-onset.csv", "/open/faers-onset/1"):
            res = cl.get(path)
            assert res.status_code == 503
            assert res.json() == {"error": "onset_table_unavailable"}

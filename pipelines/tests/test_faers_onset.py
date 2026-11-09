# pyright: reportUnknownMemberType=false
"""faers_onset: date rule, Polars/pure agreement, accounting (time-machine design §6.1, P10-P11)."""

from __future__ import annotations

import datetime as dt
import zipfile
from pathlib import Path

import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.jobs.faers import Quarter
from janus_pipelines.jobs.faers_onset import (
    MAX_DAYS,
    Exclusion,
    Payload,
    classify,
    extract,
    full_date,
)

Q = Quarter(2026, 3)

dates = st.dates(dt.date(2000, 1, 1), dt.date(2030, 12, 31))


def ymd(d: dt.date) -> str:
    return d.strftime("%Y%m%d")


date_text = st.one_of(
    dates.map(ymd),
    dates.map(lambda d: d.strftime("%Y%m")),
    dates.map(lambda d: d.strftime("%Y")),
    st.sampled_from(["", "20260231", "2026133"]),
)


@given(dates)
def test_full_date_round_trip(d: dt.date) -> None:
    assert full_date(ymd(d)) == d


@given(dates)
def test_partial_dates_are_never_complete(d: dt.date) -> None:
    assert full_date(d.strftime("%Y%m")) is None
    assert full_date(d.strftime("%Y")) is None


@given(st.lists(date_text, max_size=4), st.one_of(st.none(), date_text))
def test_classify_interval_is_bounded_and_uses_earliest_start(
    starts: list[str], event: str | None
) -> None:
    out = classify(starts, event)
    if isinstance(out, int):
        assert 0 <= out <= MAX_DAYS
        full = [d for d in map(full_date, starts) if d is not None]
        ev = full_date(event)
        assert ev is not None and full
        assert out == (ev - min(full)).days


def test_classify_examples() -> None:
    assert classify([], "20260101") is Exclusion.no_therapy_start
    assert classify(["2025"], "20260101") is Exclusion.start_date_partial
    assert classify(["20251201"], None) is Exclusion.event_date_missing
    assert classify(["20251201"], "202601") is Exclusion.event_date_partial
    assert classify(["20260102"], "20260101") is Exclusion.negative_interval
    assert classify(["20000101"], "20260101") is Exclusion.interval_over_max
    assert classify(["20251201", "2025"], "20260101") == 31


def _archive(path: Path, ther: list[tuple[str, str, str]], demo: list[tuple[str, str]]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "ASCII/THER26Q3.txt",
            "primaryid$caseid$dsg_drug_seq$start_dt$end_dt$dur$dur_cod\n"
            + "".join(f"{p}$c{p}${s}${d}$$$\n" for p, s, d in ther),
        )
        pids = sorted({p for p, _, _ in ther} | {p for p, _ in demo})
        zf.writestr(
            "ASCII/DRUG26Q3.txt",
            "primaryid$caseid$drug_seq$role_cod$prod_ai$route$dose_form\n"
            + "".join(f"{p}$c{p}$1$PS$X$ORAL$TABLET\n" for p in pids),
        )
        zf.writestr(
            "ASCII/DEMO26Q3.txt",
            "primaryid$caseid$event_dt$fda_dt\n"
            + "".join(f"{p}$c{p}${e}$20260901\n" for p, e in demo),
        )
    return path


report = st.tuples(
    st.lists(date_text, max_size=3),  # therapy start lines of drug 1
    st.one_of(st.none(), date_text),  # event date (None = no DEMO row)
)


@given(st.lists(report, min_size=1, max_size=8))
def test_extract_matches_classify_and_accounts_for_every_pair(
    reports: list[tuple[list[str], str | None]],
) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ther: list[tuple[str, str, str]] = []
        demo: list[tuple[str, str]] = []
        drugs: list[dict[str, object]] = []
        for i, (starts, event) in enumerate(reports):
            pid = f"{i + 1}1"
            ther += [(pid, "1", s) for s in starts]
            if event is not None:
                demo.append((pid, event))
            drugs.append(
                {"primaryid": pid, "drugs": [{"drug_seq": "1", "role": "PS", "ingredients": ["X"]}]}
            )
        rows = root / "rows.parquet"
        pl.DataFrame(drugs).write_parquet(rows)
        payload = Payload(
            rows, {Q.label: _archive(root / "a.zip", ther, demo)}, (Q,), root / "s", "r"
        )
        result = extract(payload)
        assert result.input_rows == len(reports)
        assert result.output_rows + sum(result.excluded.values()) == result.input_rows
        assert result.rows_file is not None
        got = dict(pl.read_parquet(result.rows_file).select("primaryid", "onset_days").iter_rows())
        side = pl.read_parquet(result.side_tables["pairs"])
        assert side.height == result.input_rows
        reasons = dict(side.select("primaryid", "reason").iter_rows())
        for i, (starts, event) in enumerate(reports):
            want = classify(starts, event)
            pid = f"{i + 1}1"
            if isinstance(want, int):
                assert got[pid] == want
                assert reasons[pid] is None
            else:
                assert pid not in got
                assert reasons[pid] == want.value
        routes = dict(side.select("primaryid", "route").iter_rows())
        assert all(r in ("ORAL", None) for r in routes.values())

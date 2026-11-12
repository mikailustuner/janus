"""Hypothesis strategies for doctor-loop tests (design §12). Synthetic codes and keys only."""

from __future__ import annotations

import csv
import datetime as dt
import io
import string
from decimal import Decimal
from typing import Literal

from hypothesis import strategies as st

from janus.cascades import schemas as cs
from janus.integrity.line import IntegrityLine, StaleSource, StatusCounts
from janus.notes import glossary as gl
from janus.notes.model import (
    ItemInfo,
    ItemIngredient,
    NoteInputs,
    RoleIds,
    StatInput,
    StatsContext,
    VersionsOut,
)
from janus.notes.templates import SPECS
from janus.notes.token import (
    EPOCH_MONDAY,
    LANGUAGES,
    MAX_CODES_PER_SIDE,
    NOTE_ID_BYTES,
    REGIONS,
    Keyring,
    Payload,
    TokenFinding,
)

kids = st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=8)
keys = st.binary(min_size=32, max_size=64)
note_ids = st.binary(min_size=NOTE_ID_BYTES, max_size=NOTE_ID_BYTES)
mondays = st.integers(min_value=0, max_value=3000).map(
    lambda w: EPOCH_MONDAY + dt.timedelta(weeks=2000 + w)
)
consents = st.from_regex(r"\A[a-z0-9][a-z0-9.-]{0,31}\Z")
events = st.from_regex(r"\A[a-z0-9][a-z0-9_.-]{0,39}\Z")
ingredient_keys = st.one_of(
    st.integers(min_value=1, max_value=9_999_999_999).map(lambda n: f"Q{n}"),
    st.integers(min_value=1, max_value=999_999).map(lambda n: f"J{n}"),
)


def _atc(a: str, b: int, c: str, d: str, e: int) -> str:
    return f"{a}{b:02d}{c}{d}{e:02d}"


atc_codes = st.builds(
    _atc,
    st.sampled_from(string.ascii_uppercase),
    st.integers(0, 99),
    st.sampled_from(string.ascii_uppercase),
    st.sampled_from(string.ascii_uppercase),
    st.integers(0, 99),
)
code_sets = st.lists(atc_codes, min_size=1, max_size=MAX_CODES_PER_SIDE, unique=True).map(
    lambda cs: tuple(sorted(cs))
)


@st.composite
def token_findings(draw: st.DrawFn, event_pool: list[str] | None = None) -> TokenFinding:
    index_key = draw(ingredient_keys)
    marker_key = draw(ingredient_keys.filter(lambda k: k != index_key))
    event = draw(st.sampled_from(event_pool)) if event_pool else draw(events)
    return TokenFinding(
        row=draw(st.integers(1, 65)),
        index_key=index_key,
        marker_key=marker_key,
        index_codes=draw(code_sets),
        marker_codes=draw(code_sets),
        event=event,
        direction=draw(st.sampled_from(["adverse", "benefit"])),
        form_confirmed=draw(st.booleans()),
    )


@st.composite
def payloads(draw: st.DrawFn, kid: str | None = None, max_findings: int = 12) -> Payload:
    pool = draw(st.lists(events, min_size=1, max_size=6, unique=True))
    return Payload(
        kid=kid if kid is not None else draw(kids),
        note_id=draw(note_ids),
        issue_week=draw(mondays),
        language=draw(st.sampled_from(LANGUAGES)),
        region=draw(st.sampled_from(REGIONS)),
        consent_version=draw(consents),
        findings=tuple(draw(st.lists(token_findings(pool), min_size=1, max_size=max_findings))),
    )


@st.composite
def keyrings(draw: st.DrawFn) -> Keyring:
    ids = draw(st.lists(kids, min_size=1, max_size=4, unique=True))
    material = draw(st.lists(keys, min_size=len(ids), max_size=len(ids), unique=True))
    return Keyring(dict(zip(ids, material, strict=True)), draw(st.sampled_from(ids)))


# --- synthetic glossaries (design §12) ---------------------------------------------------------


GLOSSARY_LANGS = ("en", "tr", "de", "fr", "es", "pt")
SYNTHETIC_PIPC = {
    n: (f"Class A{chr(64 + (n % 26) + 1)}", f"Event {chr(64 + (n % 26) + 1)}", "Class B")
    for n in range(1, 66)
}


def csv_text(header: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(header), lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def sentence_text(spec_id: str, params: tuple[tuple[str, str], ...], lang: str) -> str:
    holes = " ".join("{" + p + "}" for p, _ in params)
    words = spec_id.replace(".", " ").translate(str.maketrans("0123456789", "abcdefghij"))
    return f"[{lang}] {words} {holes}".strip()


def sentence_rows(
    status: str = "accepted", langs: tuple[str, ...] = GLOSSARY_LANGS
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for s in SPECS:
        r = {
            "id": s.id,
            "kind": s.kind,
            "evidence": ";".join(s.evidence),
            "params": ";".join(f"{p}:{t}" for p, t in s.params),
            "status": status,
            "shared": s.shared or "",
            "note": "",
        }
        for lang in GLOSSARY_LANGS:
            r[lang] = sentence_text(s.id, s.params, lang) if lang in langs else ""
        rows.append(r)
    return rows


def cascade_rows(
    status: str = "accepted", pipc: dict[int, tuple[str, str, str]] | None = None
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for n, (a, e, b) in (pipc or SYNTHETIC_PIPC).items():
        r = {
            "position": str(n),
            "en_sha256": gl.cascade_hash(a, e, b),
            "status": status,
            "note": "",
        }
        for lang in GLOSSARY_LANGS[1:]:
            r[f"drug_a_{lang}"] = f"{a} {lang}"
            r[f"adverse_event_{lang}"] = f"{e} {lang}"
            r[f"drug_b_{lang}"] = f"{b} {lang}"
        rows.append(r)
    return rows


def ingredient_row(key: str, names: dict[str, str], status: str = "accepted") -> dict[str, str]:
    return {
        "key": key,
        **{lang: names.get(lang, "") for lang in GLOSSARY_LANGS},
        "en_alt": names.get("en_alt", ""),
        "status": status,
        "edited": "",
        "source": "synthetic",
        "note": "",
    }


def synthetic_glossary(
    ingredients: list[dict[str, str]] | None = None,
    *,
    status: str = "accepted",
    pipc: dict[int, tuple[str, str, str]] | None = None,
) -> gl.Glossary:
    return gl.parse(
        csv_text(gl.INGREDIENT_HEADER, ingredients or []),
        csv_text(gl.CASCADE_HEADER, cascade_rows(status, pipc)),
        csv_text(gl.SENTENCE_HEADER, sentence_rows(status)),
    )


# --- synthetic engine results and note inputs (design §12) -------------------------------------


POOL = [f"Q{100 + i}" for i in range(12)] + ["J1"]
LABELS = {k: f"substance{chr(97 + i)}" for i, k in enumerate(POOL)}
EVENT_POOL = {"cough": "", "rash": "urgent_care_skin", "depression": "crisis_support", "oedema": ""}
WINDOW_ID = "paper:hendrix_2024:window"
SUPPORT_ID = "paper:thinkcascades:x"
EXT_ID = "paper:vander_zanden_2001:x"
PRIORITY_ID = "paper:bmj_2026:e100499"
NOTICE_CODES = ["corrected_notice", "expression_of_concern_notice"]
REGIONS_USER = ["US", "TR", "EU", "OTHER", "UNKNOWN"]
TIMINGS: list[Literal["within_window", "date_unknown", "same_month", "after_window"]] = [
    "within_window",
    "date_unknown",
    "same_month",
    "after_window",
]
PRIORITY_MEASURES: list[Literal["incidence", "adjusted_sequence_ratio"]] = [
    "incidence",
    "adjusted_sequence_ratio",
]


def all_ids(positions: list[int]) -> list[str]:
    return [*(f"rule:pipc:{n}" for n in positions), "dataset:pipc", WINDOW_ID, SUPPORT_ID, EXT_ID,
            PRIORITY_ID, "dataset:faers"]  # fmt: skip


@st.composite
def note_inputs(draw: st.DrawFn, max_items: int = 6, max_findings: int = 5) -> NoteInputs:
    n_items = draw(st.integers(1, max_items))
    items: list[ItemInfo] = []
    codes_of = {k: (f"C0{i % 10}AA0{i % 10}",) for i, k in enumerate(POOL)}
    for i in range(n_items):
        keys = draw(st.lists(st.sampled_from(POOL), min_size=1, max_size=2, unique=True))
        month = draw(st.none() | st.sampled_from(["2021-03", "2023-11", "2024-06"]))
        items.append(
            ItemInfo(i, month, tuple(ItemIngredient(k, codes_of[k], LABELS[k]) for k in keys))
        )
    present = sorted({ing.key for it in items for ing in it.ingredients})
    event_keys = {n: list(EVENT_POOL)[n % len(EVENT_POOL)] for n in range(1, 66)}
    findings: list[cs.FindingOut] = []
    if len(present) >= 2:
        for _ in range(draw(st.integers(0, max_findings))):
            a, b = draw(st.lists(st.sampled_from(present), min_size=2, max_size=2, unique=True))
            position = draw(st.integers(1, 65))
            fid = f"pipc:{position}:{a}:{b}"
            if any(f.finding_id == fid for f in findings):
                continue
            timing = draw(st.sampled_from(TIMINGS))
            months = {
                "within_window": draw(st.integers(1, 12)),
                "after_window": draw(st.integers(13, 60)),
            }.get(timing)
            ext = draw(st.booleans())
            prio = draw(st.none() | st.sampled_from(PRIORITY_MEASURES))
            ids = [f"rule:pipc:{position}", "dataset:pipc"]
            ids += [WINDOW_ID] if timing == "within_window" and draw(st.booleans()) else []
            ids += [PRIORITY_ID] if prio else []
            ids += [SUPPORT_ID] if draw(st.booleans()) else []
            ids += [EXT_ID] if ext else []
            locator = draw(st.booleans())
            ids += ["dataset:faers"] if locator else []
            form = draw(st.booleans())
            a_items = [it.item for it in items if a in {g.key for g in it.ingredients}]
            b_items = [it.item for it in items if b in {g.key for g in it.ingredients}]
            findings.append(
                cs.FindingOut(
                    finding_id=fid,
                    rule_id=f"pipc:{position}",
                    rule_evidence_id=f"rule:pipc:{position}",
                    rule_text=cs.RuleTextOut(
                        system="S",
                        kind="drug_class",
                        drug_a=SYNTHETIC_PIPC[position][0],
                        adverse_event=SYNTHETIC_PIPC[position][1],
                        drug_b=SYNTHETIC_PIPC[position][2],
                        locator=f"Table 1, row {position}",
                    ),
                    index=cs.IndexSideOut(
                        ingredient_key=a,
                        label_en=None,
                        items=a_items,
                        matched_codes=["C08CA01"],
                        form_confirmed=form,
                        start=None,
                        via_form_extension=ext,
                    ),
                    marker=cs.SideOut(
                        ingredient_key=b,
                        label_en=None,
                        items=b_items,
                        matched_codes=["C03CA01"],
                        form_confirmed=form,
                        start=None,
                    ),
                    status="probable" if timing == "within_window" else "possible",
                    timing=timing,
                    months_between=months,
                    low_priority=timing == "after_window",
                    form_confirmed=form,
                    via_form_extension=ext,
                    priority=None
                    if prio is None
                    else cs.PriorityOut(
                        measure=prio,
                        value="11.9",
                        ci_low="11.7",
                        ci_high="12.1",
                        unit="percent" if prio == "incidence" else "ratio",
                        locator="Abstract, Results",
                        evidence_id=PRIORITY_ID,
                    ),
                    abrupt_stop=[],
                    evidence_ids=sorted(ids),
                    excluded_evidence=[],
                    integrity_codes=draw(
                        st.lists(st.sampled_from(NOTICE_CODES), unique=True, max_size=2)
                    ),
                    faers_locator=f"faers:ingredient={a};event={event_keys[position]};region=ALL;scope=suspect"
                    if locator
                    else None,
                )
            )
    chains: list[cs.ChainOut] = []
    if len(findings) >= 2 and draw(st.booleans()):
        f1, f2 = findings[0], findings[1]
        chains.append(
            cs.ChainOut(
                chain_id="|".join(
                    [f1.index.ingredient_key, f1.marker.ingredient_key, f2.marker.ingredient_key]
                ),
                ingredient_keys=[
                    f1.index.ingredient_key,
                    f1.marker.ingredient_key,
                    f2.marker.ingredient_key,
                ],
                links=[
                    cs.LinkOut(
                        index_key=f1.index.ingredient_key,
                        marker_key=f1.marker.ingredient_key,
                        finding_ids=[f1.finding_id],
                    ),
                    cs.LinkOut(
                        index_key=f2.index.ingredient_key,
                        marker_key=f2.marker.ingredient_key,
                        finding_ids=[f2.finding_id],
                    ),
                ],
                status="possible",
            )
        )
    warned = draw(st.sets(st.sampled_from([it.item for it in items])))
    warnings = [
        cs.ItemWarningOut(
            item=it.item,
            ingredient_key=it.ingredients[0].key,
            code="do_not_stop_suddenly",
            text="Do not stop this medicine suddenly.",
        )
        for it in items
        if it.item in warned
    ]
    not_checked = [
        cs.NotCheckedOut(
            item=it.item,
            position=9,
            reason=draw(st.sampled_from(["ambiguous", "homeopathic_product", "no_ingredient_key"])),
        )
        for it in items
        if draw(st.booleans())
    ]
    disabled = draw(st.lists(st.integers(1, 65), max_size=2, unique=True))
    statement = None
    if not findings:
        statement = cs.StatementOut(
            code=draw(st.sampled_from(["no_pattern_found", "rule_base_unavailable"])), text="x"
        )
    result = cs.CascadeResult(
        rule_base_version="a" * 64,
        dataset_version="b" * 64,
        integrity_version="c" * 64,
        as_of_month="2026-11",
        window_months=12,
        findings=findings,
        chains=chains,
        same_product=[],
        item_warnings=warnings,
        not_checked=not_checked,
        rules=cs.RulesOut(
            total=65,
            checked=63 - len(disabled),
            disabled=[
                cs.DisabledOut(rule_id=f"pipc:{n}", reason="all_sources_retracted", removed=[])
                for n in disabled
            ],
            not_matchable=[
                cs.NotMatchableOut(rule_id="pipc:27", role="marker", reason="no_atc_code")
            ],
        ),
        statement=statement,
        notices=[],
    )
    stats: list[StatInput] = []
    seen: set[tuple[str, str, str]] = set()
    for f in findings:
        if f.faers_locator is None:
            continue
        key = (f.index.ingredient_key, event_keys[int(f.rule_id.split(":")[1])], "ALL")
        if key in seen:
            continue
        seen.add(key)
        assessment = draw(
            st.sampled_from(
                [
                    "no_reports",
                    "insufficient_data",
                    "not_disproportionate",
                    "weak",
                    "disproportionate",
                ]
            )
        )
        est = (
            None
            if assessment in ("no_reports",)
            else (draw(st.floats(0, 5000)), 0.5, draw(st.floats(1, 9000)))
        )
        stats.append(
            StatInput(
                finding_ids=(f.finding_id,),
                region="ALL",
                ingredient_key=key[0],
                event_key=key[1],
                reports=0 if assessment == "no_reports" else draw(st.integers(1, 99999)),
                assessment=assessment,
                estimates=est,
                codes=tuple(
                    draw(
                        st.lists(
                            st.sampled_from(
                                ["interval_approximate", "estimate_uses_continuity_correction"]
                            ),
                            unique=True,
                        )
                    )
                ),
                locator=f.faers_locator,
                pts=tuple(
                    draw(st.lists(st.sampled_from(["Cough", "Rash"]), unique=True, max_size=2))
                ),
            )
        )
    ctx = draw(
        st.none()
        | st.just(
            StatsContext(
                dt.date(2026, 10, 1), "2025Q4", "2026Q3", Decimal("84.0"), draw(st.booleans())
            )
        )
    )
    line = IntegrityLine(
        sources_total=3,
        checked_by_doi=2,
        without_doi_check=1,
        by_status=StatusCounts(ok=1, corrected=1),
        oldest_check=dt.date(2026, 11, 1),
        newest_check=dt.date(2026, 11, 7),
        stale_sources=[
            StaleSource(
                source_id="faers", snapshot_date=dt.date(2026, 1, 1), age_days=300, limit_days=182
            )
        ]
        if draw(st.booleans())
        else [],
        integrity_check_stale=False,
        excluded=[],
        no_retracted_used=draw(st.booleans()),
    )
    return NoteInputs(
        result=result,
        items=tuple(items),
        roles=RoleIds(
            window=WINDOW_ID,
            supporting={f"pipc:{n}": (SUPPORT_ID,) for n in range(1, 66)},
            extension=frozenset({EXT_ID}),
        ),
        item_codes={i: frozenset(NOTICE_CODES) for i in all_ids(list(range(1, 66)))},
        stats=tuple(stats),
        stats_context=ctx,
        line=line,
        versions=VersionsOut(
            rule_base_version="a" * 64,
            dataset_version="b" * 64,
            integrity_version="c" * 64,
            counts_build_id="20261108T000000Z-x",
            glossary_version="d" * 64,
        ),
        event_keys=event_keys,
        event_labels={k: {lang: f"{k} {lang}" for lang in GLOSSARY_LANGS} for k in EVENT_POOL},
        safety_lines={k: v for k, v in EVENT_POOL.items() if v},
        user_region=draw(st.sampled_from(REGIONS_USER)),
        rule_texts=dict(SYNTHETIC_PIPC),
        qr=draw(st.none() | st.just((1, 2))),
    )


def note_glossary() -> gl.Glossary:
    """Accepted synthetic glossary with names for part of the pool (others fall back)."""
    rows = [
        ingredient_row(k, {"en": LABELS[k], "de": LABELS[k].capitalize(), "fr": LABELS[k] + "e"})
        for k in POOL[:6]
    ]
    return synthetic_glossary(rows)

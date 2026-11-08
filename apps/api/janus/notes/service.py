"""Note orchestration (doctor-loop design §4.2): re-derive, build, audit. No writes here.

`compose()` runs inside the caller's read-only transaction: it re-runs the cascade engine on the
client's ids and codes (DP1), looks up the FAERS statistics of the findings in the counts file the
caller opened, builds the note in each requested language from the accepted glossary and audits it.
Nothing of the request is logged.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

import psycopg

from janus.cascades.schemas import FindingOut
from janus.cascades.service import Derived, derive
from janus.integrity.citability import cite
from janus.integrity.line import build_line
from janus.integrity.view import build_item
from janus.memory import service as memory
from janus.memory.reader import Session, snapshot_freshness
from janus.memory.schemas import EventRefIn, PairIn
from janus.memory.vocabulary import EventVocabulary
from janus.notes.audit import audit
from janus.notes.build import build_document, claim_ids
from janus.notes.glossary import Glossary
from janus.notes.model import (
    ItemInfo,
    ItemIngredient,
    NoteInputs,
    NoteOut,
    RoleIds,
    StatInput,
    StatsContext,
    VersionsOut,
)
from janus.notes.schemas import NoteIn


class VersionMismatchError(ValueError):
    """A pinned version differs from the served one; carries the pin field paths only."""

    def __init__(self, fields: list[str]) -> None:
        super().__init__("version mismatch")
        self.fields = fields


class NoteLanguageUnavailableError(ValueError):
    def __init__(self, fields: list[str]) -> None:
        super().__init__("note language unavailable")
        self.fields = fields


@dataclass(frozen=True)
class Composed:
    note: NoteOut
    derived: Derived
    ordered: tuple[FindingOut, ...]  # document order: main section, then form-unconfirmed


def ordered_findings(findings: Sequence[FindingOut]) -> tuple[FindingOut, ...]:
    return tuple(
        [f for f in findings if f.form_confirmed] + [f for f in findings if not f.form_confirmed]
    )


def _items(body: NoteIn, derived: Derived) -> tuple[ItemInfo, ...]:
    by_index = {it.index: it for it in derived.items}
    out: list[ItemInfo] = []
    for i, req in enumerate(body.evaluation.items):
        engine = by_index.get(i)
        ingredients = (
            ()
            if engine is None
            else tuple(
                ItemIngredient(g.key, tuple(sorted(g.codes)), g.label_en)
                for g in engine.ingredients
            )
        )
        out.append(ItemInfo(i, req.started, ingredients))
    return tuple(out)


def _roles(derived: Derived) -> RoleIds:
    rb = derived.rule_base
    extension = frozenset(
        p.evidence_id
        for cls in rb.classes.values()
        for p in cls.patterns
        if p.scope == "form_extension" and p.evidence_id
    )
    return RoleIds(
        window=rb.window_evidence_id,
        supporting={r.rule_id: tuple(r.supporting) for r in rb.rules},
        extension=extension,
    )


def _stats(
    findings: Sequence[FindingOut],
    event_keys: dict[int, str],
    regions: Sequence[str],
    session: Session,
    ctx: memory.Context,
) -> tuple[tuple[StatInput, ...], StatsContext]:
    keyed: dict[tuple[str, str, str], list[str]] = {}
    for f in findings:
        if f.faers_locator is None:
            continue
        event = event_keys.get(int(f.rule_id.split(":")[1]))
        if event is None:
            continue
        for region in regions:
            keyed.setdefault((f.index.ingredient_key, event, region), []).append(f.finding_id)
    stats: list[StatInput] = []
    for (key, event, region), fids in keyed.items():
        out = memory.pair(
            session,
            PairIn(ingredient=key, event=EventRefIn(key=event), region=region, scope="suspect"),  # pyright: ignore[reportArgumentType]
            ctx,
        )
        if out.stats is None or out.citation is None:
            continue
        s = out.stats
        est = (
            None
            if s.estimates is None
            else (s.estimates.ror, s.estimates.ror_ci.low, s.estimates.ror_ci.high)
        )
        stats.append(
            StatInput(
                finding_ids=tuple(fids),
                region=region,
                ingredient_key=key,
                event_key=event,
                reports=s.cells.a,
                assessment=s.assessment,
                estimates=est,
                codes=tuple(s.codes),
                locator=out.citation.locator,
                pts=tuple(out.event.pts),
            )
        )
    meta = session.meta
    mapped, every = session.totals().get("ALL", (0, 0))
    share = (
        (Decimal(mapped) * 100 / Decimal(every)).quantize(Decimal("0.1"), ROUND_HALF_EVEN)
        if every
        else Decimal(0)
    )
    fresh = snapshot_freshness(meta.snapshot_date, ctx.today)
    context = StatsContext(
        snapshot_date=dt.date.fromisoformat(meta.snapshot_date),
        first_quarter=meta.window[0],
        last_quarter=meta.window[-1],
        share=share,
        stale=fresh.state == "stale",
    )
    return tuple(stats), context


def compose(
    conn: psycopg.Connection,
    body: NoteIn,
    *,
    today: dt.date,
    vocab: EventVocabulary,
    glossary: Glossary,
    session: Session | None,
    qr: Callable[[Sequence[FindingOut]], tuple[int, int]] | None = None,
) -> Composed:
    """`qr`, when given, receives the findings in document order and returns (covered, total)
    for the note's `outcome_loop` section (the token route signs them there)."""
    event_keys = dict(vocab.pipc_event_keys())
    available = glossary.available_languages()
    missing = [f"languages.{i}" for i, lang in enumerate(body.languages) if lang not in available]
    if missing:
        raise NoteLanguageUnavailableError(missing)
    derived = derive(conn, body.evaluation, today, event_keys)
    res = derived.result
    pins = body.pins
    bad = [
        f"pins.{name}"
        for name, pinned, served in (
            ("rule_base_version", pins.rule_base_version, res.rule_base_version),
            ("integrity_version", pins.integrity_version, res.integrity_version),
            (
                "counts_build_id",
                pins.counts_build_id,
                None if session is None else session.meta.build_id,
            ),
        )
        if pinned is not None and pinned != served
    ]
    if bad:
        raise VersionMismatchError(bad)
    ordered = ordered_findings(res.findings)
    stats: tuple[StatInput, ...] = ()
    stats_context: StatsContext | None = None
    if session is not None:
        ctx = memory.Context(vocab=vocab, today=today, served_version=res.dataset_version)
        regions = ["ALL", *([body.statistics_region] if body.statistics_region else [])]
        stats, stats_context = _stats(ordered, event_keys, regions, session, ctx)
    snapshot = derived.snapshot
    ids = sorted({i for f in res.findings for i in f.evidence_ids} | {"dataset:pipc"})
    item_codes = {i: frozenset(build_item(snapshot, i, today).codes) for i in ids}
    inputs = NoteInputs(
        result=res.model_copy(update={"findings": list(ordered)}),
        items=_items(body, derived),
        roles=_roles(derived),
        item_codes=item_codes,
        stats=stats,
        stats_context=stats_context,
        line=build_line(snapshot, ids, today),
        versions=VersionsOut(
            rule_base_version=res.rule_base_version,
            dataset_version=res.dataset_version,
            integrity_version=res.integrity_version,
            counts_build_id=None if session is None else session.meta.build_id,
            glossary_version=glossary.version,
        ),
        event_keys=event_keys,
        event_labels={k.key: dict(k.labels) for k in vocab.keys},
        safety_lines={k.key: k.safety_line for k in vocab.keys if k.safety_line},
        user_region=body.region,
        rule_texts={
            r.position: (r.drug_a, r.adverse_event, r.drug_b) for r in derived.rule_base.rules
        },
        qr=None if qr is None else qr(ordered),
        component_pairs=derived.component_pairs,
    )
    documents = [build_document(inputs, glossary, lang) for lang in body.languages]
    every = {i for d in documents for i in claim_ids(d.sections)}
    citable = frozenset(cite(snapshot, sorted(every)).kept)
    audited, removals = audit(documents, citable)
    note = NoteOut(
        versions=inputs.versions,
        as_of_month=res.as_of_month,
        removals=removals,
        documents=audited,
    )
    return Composed(note, derived, ordered)

"""Note document builder (doctor-loop design §4.3, §4.4). Pure.

`build_document` turns the engine result, the statistics, the integrity line and the reviewed
glossary into one document in one language. It never invents a sentence: every text comes from an
accepted glossary row, every number from the inputs (through `render`), and every claim carries the
evidence ids its template's roles resolve to. The auditor runs afterwards.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Final

from janus.cascades.schemas import FindingOut
from janus.notes import phrases, render
from janus.notes.glossary import Glossary, Name
from janus.notes.model import (
    SECTION_ORDER,
    CitationNote,
    EstimatesNote,
    IngredientOut,
    MedicineRow,
    NotCheckedRow,
    NoteDocument,
    NoteInputs,
    Section,
    Sentence,
    StatRow,
    Text,
)
from janus.notes.render import Value
from janus.notes.templates import ASSESSMENT_CODES, CATALOGUE

ROW_49: Final = 49  # PIPC row whose Drug B repeats the adverse event (owner decision 2026-11-08)
NOTICE_TEMPLATES: Final = {
    "corrected_notice": "finding.notice.corrected",
    "expression_of_concern_notice": "finding.notice.expression_of_concern",
}


# Timing → order label (doctor-loop DP41, experience DP43).
ORDER_LABEL: Final = {
    "within_window": "fits",
    "after_window": "fits_late",
    "same_month": "not_confirmed",
    "date_unknown": "not_confirmed",
}


class LanguageUnavailableError(ValueError):
    pass


class GlossaryMismatchError(RuntimeError):
    """The glossary's English cascade hash does not match the served rule base."""


class _B:
    def __init__(self, inputs: NoteInputs, glossary: Glossary, lang: str) -> None:
        self.i, self.g, self.lang = inputs, glossary, lang

    # -- primitives --
    def text(self, template: str, values: Mapping[str, Value] | None = None) -> Text:
        body, _ = render.fill(
            CATALOGUE[template], self.g.text(template, self.lang), values or {}, self.lang
        )
        return Text(template=template, text=body)

    def sentence(
        self,
        sid: str,
        template: str,
        values: Mapping[str, Value] | None = None,
        evidence: Sequence[str] = (),
    ) -> Sentence:
        spec = CATALOGUE[template]
        body, numbers = render.fill(spec, self.g.text(template, self.lang), values or {}, self.lang)
        kind = "claim" if spec.kind == "claim" else "fixed"
        ids = sorted(set(evidence)) if kind == "claim" else []
        return Sentence(
            id=sid, template=template, kind=kind, text=body, evidence_ids=ids, numbers=numbers
        )

    def resolve(self, key: str, label_en: str | None) -> Name:
        """Glossary name; an unreviewed label that trips a word list falls back to the code."""
        n = self.g.name(key, self.lang, label_en)
        if n.basis == "not_reviewed" and n.text is not None:
            for lang in {self.lang, "en"}:
                if any(phrases.violations(n.text, lang)):
                    return Name(None, "code_only")
        return n

    def name(self, key: str, label_en: str | None, codes: Sequence[str]) -> str:
        n = self.resolve(key, label_en)
        return n.text if n.text is not None else ", ".join(codes) or key

    def cascade(self, f: FindingOut) -> tuple[str, str, str]:
        position = int(f.rule_id.split(":")[1])
        english = (f.rule_text.drug_a, f.rule_text.adverse_event, f.rule_text.drug_b)
        names = self.g.cascade(position, self.lang, english)
        if names is None:
            raise GlossaryMismatchError(f.rule_id)
        return names

    # -- sections --
    def header(self) -> Section:
        blocks = [
            self.sentence(
                "header:prepared", "header.prepared", {"month": self.i.result.as_of_month}
            ),
            self.sentence("header:purpose", "header.purpose"),
            self.sentence("header:disclaimer", "disclaimer"),
        ]
        return Section(id="header", heading=self.text("header.title"), blocks=list(blocks))

    def safety(self) -> Section | None:
        lines: list[str] = []
        for f in self.i.result.findings:
            key = self.i.event_keys.get(int(f.rule_id.split(":")[1]))
            line = self.i.safety_lines.get(key or "")
            if line and line not in lines:
                lines.append(line)
        if not lines:
            return None
        region = self.i.user_region
        emergency = self.g.text(f"emergency.{region}", self.lang)
        crisis = self.g.text(f"crisis.{region}", self.lang)
        blocks: list[Sentence] = [
            self.sentence(
                "safety:emergency_first", "safety.emergency_first", {"emergency": emergency}
            )
        ]
        for line in sorted(lines):
            values: dict[str, Value] = (
                {"crisis": crisis} if line == "crisis_support" else {"emergency": emergency}
            )
            blocks.append(self.sentence(f"safety:{line}", f"safety.{line}", values))
        return Section(id="safety", heading=self.text("safety.heading"), blocks=list(blocks))

    def medicines(self) -> Section:
        warned = {w.item for w in self.i.result.item_warnings}
        unchecked: dict[int, list[NotCheckedRow]] = {}
        for nc in self.i.result.not_checked:
            unchecked.setdefault(nc.item, []).append(
                NotCheckedRow(
                    position=nc.position,
                    reason=nc.reason,
                    text=self.text(f"not_checked.{nc.reason}"),
                )
            )
        rows: list[MedicineRow] = []
        for item in self.i.items:
            ingredients: list[IngredientOut] = []
            for ing in item.ingredients:
                n = self.resolve(ing.key, ing.label_en)
                tag = None
                if n.basis == "english_fallback":
                    tag = self.text("name.not_translated")
                elif n.basis in ("not_reviewed", "code_only"):
                    tag = self.text("name.not_reviewed")
                combination = any((ing.key, c) in self.i.component_pairs for c in ing.codes)
                ingredients.append(
                    IngredientOut(
                        key=ing.key,
                        name=None if n.text is None else Text(template="name", text=n.text),
                        name_basis=n.basis,
                        tag=tag,
                        atc=list(ing.codes),
                        combination_code=self.text("name.combination_code")
                        if combination
                        else None,
                    )
                )
            started = (
                self.text("medicine.started", {"month": item.started})
                if item.started is not None
                else self.text("medicine.start_unknown")
            )
            rows.append(
                MedicineRow(
                    item=item.item,
                    product_label=self.text("medicine.product_name"),
                    ingredients=ingredients,
                    not_checked=sorted(unchecked.get(item.item, []), key=lambda r: r.position),
                    started=started,
                    abrupt_stop=(
                        self.sentence(f"item:{item.item}:abrupt_stop", "abrupt_stop")
                        if item.item in warned
                        else None
                    ),
                )
            )
        return Section(id="medicines", heading=self.text("medicines.heading"), blocks=list(rows))

    def finding_blocks(self, f: FindingOut) -> list[Sentence]:
        r = self.i.roles
        ids = set(f.evidence_ids)
        fid = f.finding_id
        drug_a, event, drug_b = self.cascade(f)
        index = self.name(f.index.ingredient_key, f.index.label_en, f.index.matched_codes)
        marker = self.name(f.marker.ingredient_key, f.marker.label_en, f.marker.matched_codes)
        rule = [f.rule_evidence_id] if f.rule_evidence_id in ids else []
        pipc = [r.pipc] if r.pipc in ids else []
        out = [
            self.sentence(
                f"{fid}:cascade",
                "finding.cascade",
                {
                    "drug_a": drug_a,
                    "event": event,
                    "drug_b": drug_b,
                    "index": index,
                    "marker": marker,
                    "row": int(f.rule_id.split(":")[1]),
                },
                rule + pipc,
            )
        ]
        # The order as timing wording, never "probable"/"possible" (doctor-loop DP41): taken from
        # the timing, since `possible` also covers a known order after the window.
        out.append(
            self.sentence(f"{fid}:order", f"finding.order.{ORDER_LABEL[f.timing]}", None, rule)
        )
        window = self.i.result.window_months
        if f.timing in ("within_window", "after_window"):
            # The window paper supports the sentence for both; the auditor drops it if the
            # paper is no longer citable (the engine then also lists the pattern as possible).
            out.append(
                self.sentence(
                    f"{fid}:timing",
                    f"finding.timing.{f.timing}",
                    {
                        "index": index,
                        "marker": marker,
                        "months": f.months_between or 0,
                        "window": window,
                    },
                    [*rule, r.window],
                )
            )
        else:
            out.append(self.sentence(f"{fid}:timing", f"finding.timing.{f.timing}", None, rule))
        if f.priority is not None:
            p = f.priority
            values: dict[str, Value] = {
                "value": Decimal(p.value),
                "low": Decimal(p.ci_low),
                "high": Decimal(p.ci_high),
            }
            pid = [p.evidence_id] if p.evidence_id in ids else []
            out.append(
                self.sentence(f"{fid}:priority", f"finding.priority.{p.measure}", values, pid)
            )
        if int(f.rule_id.split(":")[1]) == ROW_49:
            out.append(
                self.sentence(
                    f"{fid}:row49",
                    "finding.row49",
                    {
                        "row": ROW_49,
                        "supplements": self.g.text("label.row49_supplements", self.lang),
                    },
                    rule + pipc,
                )
            )
        supporting = [s for s in r.supporting.get(f.rule_id, ()) if s in ids]
        if supporting:
            out.append(self.sentence(f"{fid}:supporting", "finding.supporting", None, supporting))
        if f.via_form_extension:
            ext = sorted(ids & r.extension)
            out.append(self.sentence(f"{fid}:form_extension", "finding.form_extension", None, ext))
        for code in sorted(set(f.integrity_codes) & set(NOTICE_TEMPLATES)):
            roots = sorted(i for i in ids if code in self.i.item_codes.get(i, frozenset()))
            out.append(self.sentence(f"{fid}:notice:{code}", NOTICE_TEMPLATES[code], None, roots))
        out.append(self.sentence(f"{fid}:review", "finding.review"))
        return out

    def findings(self, confirmed: bool) -> Section | None:
        chosen = [f for f in self.i.result.findings if f.form_confirmed == confirmed]
        if confirmed:
            blocks: list[Sentence] = []
            heading = self.text("findings.heading")
        else:
            if not chosen:
                return None
            blocks = [
                self.sentence(
                    "findings_form_unconfirmed:explanation", "findings_form_unconfirmed.explanation"
                )
            ]
            heading = self.text("findings_form_unconfirmed.heading")
        for f in chosen:
            blocks += self.finding_blocks(f)
        if confirmed and not chosen:
            blocks.append(self.sentence("findings:empty", "section.empty"))
        return Section(
            id="findings" if confirmed else "findings_form_unconfirmed",
            heading=heading,
            blocks=list(blocks),
        )

    def chains(self) -> Section | None:
        if not self.i.result.chains:
            return None
        by_id = {f.finding_id: f for f in self.i.result.findings}
        labels: dict[str, tuple[str | None, list[str]]] = {}
        for f in self.i.result.findings:
            labels[f.index.ingredient_key] = (f.index.label_en, f.index.matched_codes)
            labels[f.marker.ingredient_key] = (f.marker.label_en, f.marker.matched_codes)
        blocks: list[Sentence] = []
        for c in self.i.result.chains:
            names = [self.name(k, *labels.get(k, (None, []))) for k in c.ingredient_keys]
            evidence: list[str] = []
            for link in c.links:
                for fid in link.finding_ids:
                    f = by_id[fid]
                    evidence += [
                        i for i in (f.rule_evidence_id, self.i.roles.pipc) if i in f.evidence_ids
                    ]
            blocks.append(
                self.sentence(
                    f"chain:{c.chain_id}",
                    "chain.sequence",
                    {"sequence": render.join_names(names, self.lang)},
                    evidence,
                )
            )
        return Section(id="chains", heading=self.text("chains.heading"), blocks=list(blocks))

    def statistics(self) -> Section | None:
        findings = {f.finding_id: f for f in self.i.result.findings}
        if not any(f.faers_locator for f in findings.values()):
            return None
        heading = self.text("statistics.heading")
        ctx = self.i.stats_context
        if ctx is None:
            return Section(
                id="statistics",
                heading=heading,
                blocks=[self.sentence("statistics:unavailable", "statistics_unavailable")],
            )
        blocks: list[Sentence | StatRow] = []
        any_pt = False
        faers = [self.i.roles.faers]
        for s in self.i.stats:
            f = findings[s.finding_ids[0]]
            ingredient = self.name(s.ingredient_key, f.index.label_en, f.index.matched_codes)
            event = self.cascade(f)[1]  # the clinical name of the rule's adverse event
            region = self.g.text(f"region.{s.region}", self.lang)
            sid = f"stat:{s.ingredient_key}:{s.event_key}:{s.region}"
            base: dict[str, Value] = {"ingredient": ingredient, "event": event, "region": region}
            sentences: list[Sentence] = []
            if s.assessment == "no_reports" or s.estimates is None:
                sentences.append(
                    self.sentence(f"{sid}:coverage", "stat.coverage.no_reports", base, faers)
                )
            elif s.assessment == "insufficient_data":
                sentences.append(
                    self.sentence(f"{sid}:coverage", "stat.coverage.insufficient", base, faers)
                )
            else:
                ror, low, high = s.estimates
                sentences.append(
                    self.sentence(
                        f"{sid}:ratio",
                        "stat.reports_ratio",
                        {**base, "reports": s.reports, "ror": ror, "low": low, "high": high},
                        faers,
                    )
                )
                if s.assessment in ASSESSMENT_CODES:
                    sentences.append(
                        self.sentence(
                            f"{sid}:assessment", f"stat.assessment.{s.assessment}", None, faers
                        )
                    )
                if "interval_approximate" in s.codes:
                    sentences.append(self.sentence(f"{sid}:interval", "stat.interval_approximate"))
                if "estimate_uses_continuity_correction" in s.codes:
                    sentences.append(
                        self.sentence(f"{sid}:continuity", "stat.continuity_correction")
                    )
            pts = self.text("stat.pts", {"pts": "; ".join(s.pts)}) if s.pts else None
            any_pt = any_pt or bool(s.pts)
            show = (
                s.assessment not in ("no_reports", "insufficient_data") and s.estimates is not None
            )
            blocks.append(
                StatRow(
                    id=sid,
                    finding_ids=list(s.finding_ids),
                    region=s.region,
                    ingredient_key=s.ingredient_key,
                    event_key=s.event_key,
                    reports=s.reports if show else None,
                    assessment=s.assessment,
                    estimates=EstimatesNote(
                        ror=s.estimates[0], low=s.estimates[1], high=s.estimates[2]
                    )
                    if show and s.estimates is not None
                    else None,
                    pts=pts,
                    citation=CitationNote(locator=s.locator),
                    sentences=sentences,
                )
            )
        for code in ("spontaneous_reporting", "not_incidence", "deduplicated_by_case_version_only"):
            blocks.append(self.sentence(f"statistics:{code}", f"stat.limit.{code}"))
        blocks.append(self.sentence("statistics:screening", "stat.screening"))
        blocks.append(self.sentence("statistics:absence", "stat.absence"))
        blocks.append(
            self.sentence(
                "statistics:window",
                "stat.window",
                {"first": ctx.first_quarter, "last": ctx.last_quarter},
            )
        )
        blocks.append(
            self.sentence("statistics:denominator", "stat.denominator", {"share": ctx.share})
        )
        blocks.append(
            self.sentence("statistics:attribution", "stat.attribution", {"date": ctx.snapshot_date})
        )
        if ctx.stale:
            blocks.append(self.sentence("statistics:stale", "stat.source_may_be_outdated"))
        if any_pt:
            blocks.append(self.sentence("statistics:meddra", "stat.meddra_long"))
        return Section(id="statistics", heading=heading, blocks=list(blocks))

    def scope(self) -> Section:
        res = self.i.result
        pipc = [self.i.roles.pipc]
        blocks: list[Sentence] = []
        if res.statement is not None and res.statement.code == "rule_base_unavailable":
            blocks.append(
                self.sentence("scope:rule_base_unavailable", "scope.rule_base_unavailable")
            )
        else:
            blocks.append(
                self.sentence(
                    "scope:checked",
                    "scope.checked",
                    {"checked": res.rules.checked, "total": res.rules.total},
                    pipc,
                )
            )
        not_checked = sorted(
            {d.rule_id for d in res.rules.disabled} | {m.rule_id for m in res.rules.not_matchable},
            key=lambda r: int(r.split(":")[1]),
        )
        texts = self.i.rule_texts
        for rule_id in not_checked:
            position = int(rule_id.split(":")[1])
            english = texts.get(position)
            if english is None:
                continue
            names = self.g.cascade(position, self.lang, english)
            if names is None:
                raise GlossaryMismatchError(rule_id)
            blocks.append(
                self.sentence(
                    f"scope:not_checked:{rule_id}",
                    "scope.not_checked_rule",
                    {"row": position, "drug_a": names[0], "event": names[1], "drug_b": names[2]},
                    pipc,
                )
            )
        if res.statement is not None and res.statement.code == "no_pattern_found":
            blocks.append(self.sentence("scope:no_pattern", "scope.no_pattern", None, pipc))
        return Section(id="scope", heading=self.text("scope.heading"), blocks=list(blocks))

    def integrity(self, used: Sequence[str]) -> Section:
        line = self.i.line
        ids = sorted(set(used))
        blocks = [
            self.sentence(
                "integrity:sources",
                "integrity.sources",
                {"total": line.sources_total, "by_doi": line.checked_by_doi},
                ids,
            ),
            self.sentence(
                "integrity:by_status",
                "integrity.by_status",
                {
                    "ok": line.by_status.ok,
                    "corrected": line.by_status.corrected,
                    "expression_of_concern": line.by_status.expression_of_concern,
                    "unknown": line.by_status.unknown,
                },
                ids,
            ),
        ]
        if line.oldest_check is not None and line.newest_check is not None:
            blocks.append(
                self.sentence(
                    "integrity:checks_between",
                    "integrity.checks_between",
                    {"first": line.oldest_check, "last": line.newest_check},
                    ids,
                )
            )
        for s in line.stale_sources:
            blocks.append(
                self.sentence(
                    f"integrity:stale:{s.source_id}",
                    "integrity.stale_source",
                    {"source": s.source_id, "date": s.snapshot_date},
                    ids,
                )
            )
        if line.no_retracted_used:
            blocks.append(
                self.sentence("integrity:no_retracted", "integrity.no_retracted", None, ids)
            )
        return Section(id="integrity", heading=self.text("integrity.heading"), blocks=list(blocks))

    def outcome_loop(self) -> Section | None:
        if self.i.qr is None:
            return None
        covered, total = self.i.qr
        return Section(
            id="outcome_loop",
            heading=self.text("outcome_loop.heading"),
            blocks=[
                self.sentence("outcome_loop:how", "outcome_loop.how"),
                self.sentence(
                    "outcome_loop:coverage",
                    "outcome_loop.coverage",
                    {"covered": covered, "total": total},
                ),
            ],
        )

    def about(self, with_stats: bool) -> Section:
        v = self.i.versions
        blocks = [
            self.sentence(
                "about:versions",
                "about.versions",
                {
                    "rule_base": v.rule_base_version,
                    "dataset": v.dataset_version,
                    "integrity": v.integrity_version,
                    "counts": v.counts_build_id or "-",
                    "glossary": v.glossary_version,
                },
            ),
            self.sentence("about:pipc", "about.pipc"),
        ]
        if with_stats:
            blocks.append(self.sentence("about:faers", "about.faers"))
        blocks.append(self.sentence("about:glossary_status", "about.glossary_status"))
        return Section(id="about", heading=self.text("about.heading"), blocks=list(blocks))


def claim_ids(sections: Sequence[Section]) -> list[str]:
    out: set[str] = set()
    for s in sections:
        for b in s.blocks:
            sentences = (
                b.sentences if isinstance(b, StatRow) else [b] if isinstance(b, Sentence) else []
            )
            for x in sentences:
                out.update(x.evidence_ids)
    return sorted(out)


def build_document(inputs: NoteInputs, glossary: Glossary, lang: str) -> NoteDocument:
    if lang not in glossary.available_languages():
        raise LanguageUnavailableError(lang)
    b = _B(inputs, glossary, lang)
    stats = b.statistics()
    parts: dict[str, Section | None] = {
        "header": b.header(),
        "safety": b.safety(),
        "medicines": b.medicines(),
        "findings": b.findings(True),
        "findings_form_unconfirmed": b.findings(False),
        "chains": b.chains(),
        "statistics": stats,
        "scope": b.scope(),
    }
    used = claim_ids([s for s in parts.values() if s is not None])
    parts["integrity"] = b.integrity(used)
    parts["outcome_loop"] = b.outcome_loop()
    parts["about"] = b.about(stats is not None)
    sections = [s for sid in SECTION_ORDER if (s := parts.get(sid)) is not None]
    return NoteDocument(language=lang, sections=sections)

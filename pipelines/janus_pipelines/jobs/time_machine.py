# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""Time machine source jobs (time-machine design §4-§5, Req 1-2).

* `tm_molecules` (Wikidata, CC0): checks that each curated constituent
  (`data/time_machine/constituents.csv`) has a referenced "found in taxon" (P703) statement for
  its taxon, matched on the full InChIKey (P235), and records the item, SMILES and reference
  DOIs. LOTUS uploads these statements with "stated in" (P248) = the source article. Also
  reads "physically interacts with" (P129) of constituents and comparator drugs, with the
  Entrez Gene id of the protein (P702 -> P351).
* `tm_bioactivity` (PubChem): measured activities per compound. PubChem's own data is public
  domain, but deposited records keep the depositor's licence (design DP-T5): only values from
  US-government depositors are output; ChEMBL rows (CC BY-SA 3.0) and rows from depositors
  whose licence is not verified are excluded and counted. For PK-interaction genes an excluded
  row is kept as a *pointer* in the metrics (AID, gene, depositor), never its value.
* `tm_labels` (openFDA drug label, CC0): confirms that each comparator drug's US label
  indication names the condition term chosen for it.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import polars as pl

from janus_pipelines.core.canonical import Json, Row, sha256_bytes
from janus_pipelines.core.http import Fetcher, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.validation import ExpectedSchema, Field, SchemaReport

SPARQL = "https://query.wikidata.org/sparql"
PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
OPENFDA_LABEL = "https://api.fda.gov/drug/label.json"

# --- curated inputs --------------------------------------------------------------------------


@dataclass(frozen=True)
class Constituent:
    substance_id: str
    taxon_qids: tuple[str, ...]
    compound: str
    cid: str
    inchikey: str


@dataclass(frozen=True)
class Comparator:
    condition_key: str
    substance_id: str
    drug: str
    label_terms: tuple[str, ...]


_QID = re.compile(r"^Q[0-9]+$")
_CID = re.compile(r"^[0-9]+$")
_IK = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


def read_constituents(path: Path) -> list[Constituent]:
    out: list[Constituent] = []
    with path.open(encoding="utf-8", newline="") as f:
        for i, r in enumerate(csv.DictReader(f), 2):
            taxa = tuple(t for t in r["taxon_qids"].split("|") if t)
            if not all(_QID.match(t) for t in taxa):
                raise ValueError(f"{path.name}:{i}: bad taxon QID")
            if not _CID.match(r["pubchem_cid"]) or not _IK.match(r["inchikey"]):
                raise ValueError(f"{path.name}:{i}: bad CID or InChIKey")
            out.append(
                Constituent(r["substance_id"], taxa, r["compound"], r["pubchem_cid"], r["inchikey"])
            )
    return out


def read_comparators(path: Path) -> list[Comparator]:
    with path.open(encoding="utf-8", newline="") as f:
        return [
            Comparator(
                r["condition_key"], r["substance_id"], r["drug"], tuple(r["label_terms"].split("|"))
            )
            for r in csv.DictReader(f)
        ]


def _qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def _bindings(body: bytes) -> list[dict[str, str]]:
    data = json.loads(body)
    return [{k: v["value"] for k, v in b.items()} for b in data["results"]["bindings"]]


# --- tm_molecules ----------------------------------------------------------------------------


def occurrence_query(cons: Sequence[Constituent]) -> str:
    keys = " ".join(f'"{c.inchikey}"' for c in cons)
    return f"""SELECT ?ik ?c ?taxon ?art ?doi ?smiles WHERE {{
  VALUES ?ik {{ {keys} }}
  ?c wdt:P235 ?ik .
  OPTIONAL {{ ?c wdt:P2017 ?iso }} OPTIONAL {{ ?c wdt:P233 ?can }}
  BIND(COALESCE(?iso, ?can) AS ?smiles)
  OPTIONAL {{ ?c p:P703 ?st . ?st ps:P703 ?taxon .
             ?st prov:wasDerivedFrom/pr:P248 ?art . OPTIONAL {{ ?art wdt:P356 ?doi }} }}
}}"""


def interaction_query(keys: Sequence[str], names: Sequence[str]) -> str:
    """P129 'physically interacts with' -> protein -> encoded by gene -> Entrez id. Compounds
    by InChIKey (constituents) or English label (comparator drugs)."""
    ik = " ".join(f'"{k}"' for k in keys)
    nm = " ".join(f'"{n}"@en' for n in names)
    return f"""SELECT ?key ?c ?protein ?gene ?entrez ?symbol ?ref WHERE {{
  {{ VALUES ?key {{ {ik} }} ?c wdt:P235 ?key . }} UNION
  {{ VALUES ?key {{ {nm} }} ?c rdfs:label ?key . }}
  ?c p:P129 ?st . ?st ps:P129 ?protein .
  OPTIONAL {{ ?st prov:wasDerivedFrom/pr:P248 ?ref }}
  ?protein wdt:P702 ?gene . ?gene wdt:P351 ?entrez ; wdt:P703 wd:Q15978631 .
  OPTIONAL {{ ?gene wdt:P353 ?symbol }}
}}"""


MOLECULE_SCHEMA = ExpectedSchema(
    version="tm-molecules-1",
    fields=(Field("substance_id", frozenset({"str"})), Field("pubchem_cid", frozenset({"str"}))),
)

MOLECULE_ROW: Mapping[str, pl.DataType] = {
    "kind": pl.String(),  # occurrence | interaction
    "substance_id": pl.String(),
    "compound": pl.String(),
    "pubchem_cid": pl.String(),
    "inchikey": pl.String(),
    "wikidata_qid": pl.String(),
    "taxon_qids": pl.List(pl.String()),
    "smiles": pl.String(),
    "reference_dois": pl.List(pl.String()),
    "entrez_gene": pl.String(),
    "gene_symbol": pl.String(),
    "reference_qids": pl.List(pl.String()),
}


def _blank(**kw: Json) -> dict[str, Json]:
    row: dict[str, Json] = {k: None for k in MOLECULE_ROW}
    row["reference_dois"] = []
    row["reference_qids"] = []
    row["taxon_qids"] = []
    row.update(kw)
    return row


def parse_molecules(
    cons: Sequence[Constituent],
    comps: Sequence[Comparator],
    occurrence: bytes,
    interactions: bytes,
) -> ParseResult:
    by_key: dict[str, list[dict[str, str]]] = {}
    for b in _bindings(occurrence):
        by_key.setdefault(b["ik"], []).append(b)
    rows: list[Row] = []
    excluded: Counter[str] = Counter()
    for c in cons:
        hits = by_key.get(c.inchikey, [])
        smiles = next((h["smiles"] for h in hits if "smiles" in h), None)
        item = next((_qid(h["c"]) for h in hits), None)
        if item is None:
            excluded["no_wikidata_item"] += 1
            continue
        if not c.taxon_qids:  # a preparation (vinegar): constituent by definition
            rows.append(
                _blank(
                    kind="occurrence",
                    substance_id=c.substance_id,
                    compound=c.compound,
                    pubchem_cid=c.cid,
                    inchikey=c.inchikey,
                    wikidata_qid=item,
                    smiles=smiles,
                )
            )
            continue
        taxa = {_qid(h["taxon"]) for h in hits if "taxon" in h} & set(c.taxon_qids)
        if not taxa:
            excluded["not_found_in_taxon"] += 1
            continue
        dois = sorted(
            {h["doi"].lower() for h in hits if "doi" in h and _qid(h.get("taxon", "")) in taxa}
        )
        arts = sorted(
            {_qid(h["art"]) for h in hits if "art" in h and _qid(h.get("taxon", "")) in taxa}
        )
        rows.append(
            _blank(
                kind="occurrence",
                substance_id=c.substance_id,
                compound=c.compound,
                pubchem_cid=c.cid,
                inchikey=c.inchikey,
                wikidata_qid=item,
                taxon_qids=sorted(taxa),
                reference_qids=list(arts),
                smiles=smiles,
                reference_dois=dois,
            )
        )
    names = {c.drug: c for c in comps}
    keys = {c.inchikey: c for c in cons}
    grouped: dict[tuple[str, str, str], set[str]] = {}
    symbols: dict[str, str] = {}
    for b in _bindings(interactions):
        key = b["key"]
        grouped.setdefault((key, _qid(b["c"]), b["entrez"]), set()).update(
            {_qid(b["ref"])} if "ref" in b else set()
        )
        if "symbol" in b:
            symbols[b["entrez"]] = b["symbol"]
    n_interactions = 0
    for (key, item, entrez), refs in sorted(grouped.items()):
        if key in keys:
            c = keys[key]
            sub, comp, cid, ik = c.substance_id, c.compound, c.cid, c.inchikey
        elif key in names:
            sub, comp, cid, ik = "", names[key].drug, None, None
        else:
            continue
        n_interactions += 1
        rows.append(
            _blank(
                kind="interaction",
                substance_id=sub,
                compound=comp,
                pubchem_cid=cid,
                inchikey=ik,
                wikidata_qid=item,
                entrez_gene=entrez,
                gene_symbol=symbols.get(entrez),
                reference_qids=sorted(refs),
            )
        )
    n_occ = len(rows) - n_interactions
    return ParseResult(
        rows=rows,
        input_rows=len(cons) + n_interactions,
        excluded=dict(excluded),
        schema=SchemaReport(),
        metrics={
            "constituents": len(cons),
            "occurrence_rows": n_occ,
            "interaction_rows": n_interactions,
            "comparators_with_interactions": sorted(
                {
                    str(r["compound"])
                    for r in rows
                    if r["kind"] == "interaction" and not r["substance_id"]
                }
            ),
        },
    )


@dataclass(frozen=True)
class MoleculePayload:
    constituents: list[Constituent]
    comparators: list[Comparator]
    occurrence: bytes
    interactions: bytes


def _sparql(fetcher: Fetcher, query: str) -> bytes:
    return fetcher.get(
        SPARQL,
        params={"query": query, "format": "json"},
        headers={"Accept": "application/sparql-results+json"},
        read_timeout=120.0,
    ).content


class TmMoleculesJob(Job[MoleculePayload]):
    name = "tm_molecules"
    source_id = "wikidata"
    schema = MOLECULE_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = MOLECULE_ROW

    def fetch(self, ctx: RunContext) -> RawInput[MoleculePayload]:
        cons = read_constituents(ctx.repo_root / "data" / "time_machine" / "constituents.csv")
        comps = read_comparators(ctx.repo_root / "data" / "time_machine" / "comparators.csv")
        fetcher = make_fetcher(require_contact=True)
        retrieved = ctx.now()
        q1 = occurrence_query(cons)
        q2 = interaction_query([c.inchikey for c in cons], sorted({c.drug for c in comps}))
        occ, inter = _sparql(fetcher, q1), _sparql(fetcher, q2)
        return RawInput(
            payload=MoleculePayload(cons, comps, occ, inter),
            source_urls=(SPARQL,),
            source_sha256=sha256_bytes(occ + inter),
            retrieved_at=retrieved,
            snapshot_date=retrieved.date().isoformat(),
            snapshot_date_is_retrieval_time=True,
            raw_files={"occurrence.json": occ, "interactions.json": inter},
            query_sha256={
                "occurrence": sha256_bytes(q1.encode()),
                "interactions": sha256_bytes(q2.encode()),
            },
        )

    def parse(self, raw: RawInput[MoleculePayload]) -> ParseResult:
        p = raw.payload
        return parse_molecules(p.constituents, p.comparators, p.occurrence, p.interactions)


# --- tm_bioactivity --------------------------------------------------------------------------

# Depositors whose records are US-government works (public domain, 17 U.S.C. §105).
PUBLIC_DOMAIN_DEPOSITORS = frozenset({"NCGC", "Tox21", "NCATS", "DTP/NCI", "EPA DSSTox", "ToxCast"})
CHEMBL = "ChEMBL"
POTENCY_NAMES = frozenset({"IC50", "EC50", "Ki", "Kd", "AC50", "Potency", "MIC"})
# Genes whose activity signals a pharmacokinetic interaction (design DP-T7).
PK_GENES: Mapping[str, str] = {
    "8856": "NR1I2 (PXR)",
    "1576": "CYP3A4",
    "1559": "CYP2C9",
    "1565": "CYP2D6",
    "1557": "CYP2C19",
    "1544": "CYP1A2",
    "5243": "ABCB1 (P-gp)",
}

BIO_SCHEMA = ExpectedSchema(
    version="tm-bioactivity-1",
    fields=(Field("pubchem_cid", frozenset({"str"})), Field("aid", frozenset({"str"}))),
)

BIO_ROW: Mapping[str, pl.DataType] = {
    "compound": pl.String(),
    "pubchem_cid": pl.String(),
    "aid": pl.String(),
    "depositor": pl.String(),
    "outcome": pl.String(),
    "entrez_gene": pl.String(),
    "target_accession": pl.String(),
    "activity_name": pl.String(),
    "value_um": pl.Float64(),
    "assay_name": pl.String(),
    "pmid": pl.String(),
}


def parse_assay_rows(compound: str, body: bytes) -> list[dict[str, str]]:
    text = body.decode("utf-8")
    if not text.strip():
        return []
    rows = list(csv.DictReader(io.StringIO(text)))
    for r in rows:
        r["compound"] = compound
    return rows


def classify_depositor(name: str | None) -> str:
    if name in PUBLIC_DOMAIN_DEPOSITORS:
        return "public_domain"
    if name == CHEMBL:
        return "chembl_cc_by_sa"
    return "unverified"


def parse_bioactivity(
    activities: Sequence[dict[str, str]], depositors: Mapping[str, str]
) -> ParseResult:
    out: list[Row] = []
    excluded: Counter[str] = Counter()
    by_class: Counter[str] = Counter()
    pointers: list[dict[str, Json]] = []
    for r in activities:
        value = r.get("Activity Value [uM]", "").strip()
        name = r.get("Activity Name", "").strip()
        if not value or name not in POTENCY_NAMES:
            excluded["no_potency_value"] += 1
            continue
        aid = r["AID"]
        dep = depositors.get(aid)
        cls = classify_depositor(dep)
        by_class[cls] += 1
        gene = r.get("Target GeneID", "").strip()
        if cls != "public_domain":
            excluded[f"depositor_{cls}"] += 1
            if gene in PK_GENES and r.get("Activity Outcome") == "Active":
                pointers.append(
                    {
                        "compound": r["compound"],
                        "pubchem_cid": r["CID"],
                        "aid": aid,
                        "entrez_gene": gene,
                        "gene": PK_GENES[gene],
                        "activity_name": name,
                        "depositor": dep,
                        "licence_class": cls,
                    }
                )
            continue
        out.append(
            {
                "compound": r["compound"],
                "pubchem_cid": r["CID"],
                "aid": aid,
                "depositor": dep,
                "outcome": r.get("Activity Outcome"),
                "entrez_gene": gene or None,
                "target_accession": r.get("Target Accession") or None,
                "activity_name": name,
                "value_um": float(value),
                "assay_name": r.get("Assay Name"),
                "pmid": r.get("PubMed ID") or None,
            }
        )
    return ParseResult(
        rows=out,
        input_rows=len(activities),
        excluded=dict(excluded),
        schema=SchemaReport(),
        metrics={
            "potency_rows_by_licence_class": dict(by_class),
            "pk_interaction_pointers": pointers,
            "licence_rule": "values only from US-government depositors; ChEMBL CC BY-SA 3.0 and "
            "unverified depositors excluded (pointers kept for PK-interaction genes)",
        },
    )


@dataclass(frozen=True)
class BioPayload:
    activities: list[dict[str, str]]
    depositors: dict[str, str]


class TmBioactivityJob(Job[BioPayload]):
    name = "tm_bioactivity"
    source_id = "pubchem"
    schema = BIO_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = BIO_ROW

    def fetch(self, ctx: RunContext) -> RawInput[BioPayload]:
        cons = read_constituents(ctx.repo_root / "data" / "time_machine" / "constituents.csv")
        comps = read_comparators(ctx.repo_root / "data" / "time_machine" / "comparators.csv")
        fetcher = make_fetcher(require_contact=False)
        retrieved = ctx.now()
        targets = {c.compound: c.cid for c in cons}
        for drug in sorted({c.drug for c in comps}):
            body = fetcher.get(f"{PUG}/compound/name/{drug}/cids/TXT").text.split()
            targets[drug] = body[0]
        files: dict[str, bytes] = {}
        activities: list[dict[str, str]] = []
        for compound, cid in sorted(targets.items()):
            body = fetcher.get(
                f"{PUG}/compound/cid/{cid}/assaysummary/CSV", allow_status=frozenset({404})
            ).content
            files[f"assaysummary-{cid}.csv"] = body
            activities += parse_assay_rows(compound, body)
        aids = sorted(
            {a["AID"] for a in activities if a.get("Activity Value [uM]", "").strip()}, key=int
        )
        depositors: dict[str, str] = {}
        for i in range(0, len(aids), 100):
            body = fetcher.get(
                f"{PUG}/assay/aid/{','.join(aids[i : i + 100])}/summary/JSON"
            ).content
            files[f"aid-summary-{i // 100}.json"] = body
            for s in json.loads(body)["AssaySummaries"]["AssaySummary"]:
                depositors[str(s["AID"])] = str(s.get("SourceName", ""))
        files["cids.json"] = json.dumps(targets, sort_keys=True).encode()
        digest = sha256_bytes(b"".join(files[k] for k in sorted(files)))
        return RawInput(
            payload=BioPayload(activities, depositors),
            source_urls=(PUG,),
            source_sha256=digest,
            retrieved_at=retrieved,
            snapshot_date=retrieved.date().isoformat(),
            snapshot_date_is_retrieval_time=True,
            raw_files=files,
        )

    def parse(self, raw: RawInput[BioPayload]) -> ParseResult:
        return parse_bioactivity(raw.payload.activities, raw.payload.depositors)


# --- tm_labels -------------------------------------------------------------------------------

LABEL_SCHEMA = ExpectedSchema(
    version="tm-labels-1",
    fields=(Field("drug", frozenset({"str"})), Field("condition_key", frozenset({"str"}))),
)

LABEL_ROW: Mapping[str, pl.DataType] = {
    "condition_key": pl.String(),
    "drug": pl.String(),
    "set_id": pl.String(),
    "effective_time": pl.String(),
    "term": pl.String(),
    "excerpt": pl.String(),
}


def find_term(indications: str, terms: Sequence[str]) -> tuple[str, str] | None:
    low = indications.lower()
    for t in terms:
        i = low.find(t.lower())
        if i >= 0:
            return t, " ".join(indications[max(0, i - 100) : i + len(t) + 100].split())
    return None


def parse_labels(comps: Sequence[Comparator], labels: Mapping[str, bytes]) -> ParseResult:
    rows: list[Row] = []
    excluded: Counter[str] = Counter()
    for c in comps:
        body = labels.get(c.drug, b"")
        results = json.loads(body).get("results", []) if body else []
        hit: dict[str, Json] | None = None
        for lab in results:
            text = " ".join(lab.get("indications_and_usage", []))
            found = find_term(text, c.label_terms)
            if found:
                hit = {
                    "condition_key": c.condition_key,
                    "drug": c.drug,
                    "set_id": lab.get("set_id"),
                    "effective_time": lab.get("effective_time"),
                    "term": found[0],
                    "excerpt": found[1],
                }
                break
        if hit is None:
            excluded["indication_term_not_in_label"] += 1
        else:
            rows.append(hit)
    return ParseResult(
        rows=rows, input_rows=len(comps), excluded=dict(excluded), schema=SchemaReport()
    )


@dataclass(frozen=True)
class LabelPayload:
    comparators: list[Comparator]
    labels: dict[str, bytes]


class TmLabelsJob(Job[LabelPayload]):
    name = "tm_labels"
    source_id = "openfda_label"
    schema = LABEL_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = LABEL_ROW

    def fetch(self, ctx: RunContext) -> RawInput[LabelPayload]:
        comps = read_comparators(ctx.repo_root / "data" / "time_machine" / "comparators.csv")
        fetcher = make_fetcher(require_contact=False)
        retrieved = ctx.now()
        labels: dict[str, bytes] = {}
        for drug in sorted({c.drug for c in comps}):
            params = {"search": f'openfda.generic_name:"{drug}"', "limit": "20"}
            labels[drug] = fetcher.get(
                OPENFDA_LABEL, params=params, allow_status=frozenset({404})
            ).content
        digest = sha256_bytes(b"".join(labels[k] for k in sorted(labels)))
        return RawInput(
            payload=LabelPayload(comps, labels),
            source_urls=(OPENFDA_LABEL,),
            source_sha256=digest,
            retrieved_at=retrieved,
            snapshot_date=retrieved.date().isoformat(),
            snapshot_date_is_retrieval_time=True,
            raw_files={f"label-{d}.json": b for d, b in labels.items()},
        )

    def parse(self, raw: RawInput[LabelPayload]) -> ParseResult:
        return parse_labels(raw.payload.comparators, raw.payload.labels)

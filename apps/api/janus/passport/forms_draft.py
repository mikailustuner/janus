"""Draft of `data/dose_form_groups.csv` (medication-passport design §5.2, task 3). Dev tool.

Usage: `python -m janus.passport.forms_draft [--out PATH]` with `DATABASE_URL` (a loaded database).
Reads, in one read-only transaction, every distinct (source, published dose form, published route
set) of the current dataset with its product count, proposes a group by the keyword rules below and
writes one row per form: a `*` row when every route set of that form gives the same proposal, else
one row per route set. Every row is `proposed`; the note gives the rule and the product count. The
proposal is a starting point for the pharmacologist's review, not a decision. Prints counts only.

Only openFDA (SPL dose form names) and the BDPM (French pharmaceutical forms) publish a form; both
are open data (CC0; Licence Ouverte, kept as published). TİTCK and the Nomenclátor publish none.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path

from janus.passport.forms import (
    ANY_ROUTE,
    FORMS_FILE,
    HEADER,
    NOT_COMPARED_GROUPS,
    parse,
    route_key,
)

# --- route classes ---------------------------------------------------------------------------
ORAL = frozenset({"ORAL", "orale"})
OROMUCOSAL = frozenset(
    {
        "SUBLINGUAL",
        "BUCCAL",
        "OROPHARYNGEAL",
        "DENTAL",
        "PERIODONTAL",
        "SUBGINGIVAL",
        "TRANSMUCOSAL",
        "sublinguale",
        "voie buccale autre",
        "dentaire",
        "gingivale",
        "buccogingivale",
        "laryngopharyngée",
    }
)
PARENTERAL = frozenset(
    {
        "INTRAVENOUS",
        "INTRAMUSCULAR",
        "SUBCUTANEOUS",
        "INTRADERMAL",
        "PERCUTANEOUS",
        "INFILTRATION",
        "PERINEURAL",
        "EPIDURAL",
        "INTRA-ARTICULAR",
        "INTRACAUDAL",
        "SOFT TISSUE",
        "INTRALESIONAL",
        "INTRATHECAL",
        "SUBMUCOSAL",
        "INTRAVASCULAR",
        "PARENTERAL",
        "INTRA-ARTERIAL",
        "INTRAVITREAL",
        "INTRASYNOVIAL",
        "INTRAOCULAR",
        "INTRACARDIAC",
        "INTRAMEDULLARY",
        "SUBCONJUNCTIVAL",
        "INTRACAVERNOUS",
        "SUBARACHNOID",
        "INTRAVENTRICULAR",
        "RETROBULBAR",
        "INTRACAMERAL",
        "SUPRACHOROIDAL",
        "INTRACORONARY",
        "INTRALYMPHATIC",
        "INTRATUMOR",
        "INTERSTITIAL",
        "INTRACEREBRAL",
        "intraveineuse",
        "sous-cutanée",
        "intramusculaire",
        "intraartérielle",
        "intrathécale",
        "péridurale",
        "intraarticulaire",
        "périneurale",
        "infiltration",
        "intracérébroventriculaire",
        "intravitréenne",
        "intradermique",
        "intralésionnelle",
        "périarticulaire",
        "intracoronaire",
        "sous-conjonctivale",
        "intracaverneuse",
        "intracamérulaire",
        "intra-murale",
        "voie parentérale autre",
        "intratumorale",
        "intraosseuse",
        "intraglandulaire",
        "péritumorale",
        "sous-muqueuse",
        "péribulbaire",
        "intraoculaire",
        "subrétinale",
        "intrapéricardiaque",
        "intralymphatique",
        "intradurale",
        "intracisternale",
        "intraputaminale",
        "péri-aréolaire",
    }
)
SIMPLE_ROUTES: dict[str, frozenset[str]] = {
    "cutaneous": frozenset({"TOPICAL", "CUTANEOUS", "INTRAEPIDERMAL", "cutanée", "épilésionnelle"}),
    "transdermal": frozenset({"TRANSDERMAL", "transdermique"}),
    "ophthalmic": frozenset({"OPHTHALMIC", "CONJUNCTIVAL", "ophtalmique"}),
    "otic": frozenset({"AURICULAR (OTIC)", "auriculaire"}),
    "nasal": frozenset({"NASAL", "nasale"}),
    "inhaled": frozenset({"RESPIRATORY (INHALATION)", "inhalée"}),
    "rectal": frozenset({"RECTAL", "rectale"}),
    "vaginal": frozenset({"VAGINAL", "vaginale"}),
}


def route_class(route: str) -> str | None:
    if route in ORAL:
        return "oral"
    if route in OROMUCOSAL:
        return "oromucosal"
    if route in PARENTERAL:
        return "parenteral"
    for name, members in SIMPLE_ROUTES.items():
        if route in members:
            return name
    return None


def routes_class(routes: Iterable[str]) -> str:
    """One class for a route set: `none` (no route published), the shared class, or `mixed`."""
    classes = {route_class(r) for r in routes}
    if not classes:
        return "none"
    if len(classes) == 1 and None not in classes:
        return next(iter(classes))  # pyright: ignore[reportReturnType]
    return "mixed"


# --- form kinds ------------------------------------------------------------------------------
def _has(form: str, *words: str) -> bool:
    return any(w in form for w in words)


MODIFIED = (
    "extended release",
    "delayed release",
    "libération prolongée",
    "libération modifiée",
    "gastro-résistant",
    "osmotique",
    "liposomal",
    "lipid complex",
    "microsphère",
)
FIXED_OTHER = (
    "kit",
    "trousse",
    "radiopharmaceutique",
    "générateur",
    "implant",
    "intrauterine",
    "plante(s)",
    "tisane",
    "matrice",
    "cellular sheet",
    "globule",
    "granules",
    "bead",
    "crystal",
    "extract",
    "gum",
    "gomme",
    "lozenge",
    "troche",
    "pastille",
    "à sucer",
    "dentifrice",
    "dentaire",
    "mouthwash",
    "bain de bouche",
    "gargarisme",
    "collutoire",
    "irrigant",
    "irrigation",
    "lavage",
    "cardioplégique",
    "dialyse",
    "hémofiltration",
    "hémodialyse",
    "colle",
    "marquage",
    "prick-test",
    "muco-adhésif",
    "solvant pour préparation parentérale",
    "intravésicale",
    "instillation",
)
SOLID = ("tablet", "capsule", "comprimé", "gélule", "pill", "caplet")
LIQUID = (
    "solution",
    "suspension",
    "liquid",
    "liquide",
    "syrup",
    "sirop",
    "elixir",
    "émulsion",
    "emulsion",
    "drops",
    "gouttes",
    "concentrate",
    "tincture",
    "dispersion",
    "spray",
    "pulvérisation",
    "aerosol",
    "aérosol",
    "gas",
    "gaz",
    "oil",
    "douche",
)
SEMISOLID = (
    "cream",
    "crème",
    "ointment",
    "pommade",
    "gel",
    "lotion",
    "paste",
    "pâte",
    "foam",
    "mousse",
    "shampoo",
    "shampooing",
    "salve",
    "liniment",
    "jelly",
    "gelée",
    "soap",
    "stick",
    "bâton",
    "vernis",
    "cloth",
    "swab",
    "sponge",
    "dressing",
    "pansement",
    "compresse",
    "tampon",
    "tape",
    "poultice",
    "disc",
    "rinse",
)
POWDER = (
    "film",
    "wafer",
    "strip",
    "bar, chewable",
    "chewable gel",
    "lyophilisat",
    "granulés",
    "granule",
    "powder",
    "poudre",
)
TO_LIQUID = ("for solution", "for suspension", "pour solution", "pour suspension")


def form_kind(form: str) -> tuple[str, str]:
    """(kind, rule) of a published form, checked in this order. Kinds: `fixed:<group>` (the form
    names the group), `solid`, `solid_mr`, `liquid`, `semisolid`, `patch`, `powder`, `rectal`,
    `insert` (the route decides) and `unknown`. The rule goes into the note."""
    f = form.lower().strip()
    if _has(f, "radiopharmaceutique", "trousse"):
        return ("fixed:other", "radiopharmaceutical kit")
    if _has(f, "par vapeur", "fumigation"):
        return ("unknown", "inhalation by vapour or fumigation")
    if _has(f, "inhalation", "nébuliseur", "inhalant"):
        return ("fixed:inhaled", "inhalation word")
    if _has(f, "injection", "injectable", "perfusion", "parentéral", "parenteral"):
        if "buvable" in f:
            return ("unknown", "injection or oral (one presentation, two routes)")
        return ("fixed:injection", "injection or infusion word")
    if _has(f, *FIXED_OTHER) or f.startswith("pellet"):
        return ("fixed:other", "kit, device, oromucosal, dental, irrigation or similar")
    if _has(f, "collyre", "ophtalm"):
        return ("fixed:ophthalmic", "eye drops word")
    if _has(f, "suppositoire", "suppository", "enema", "lavement"):
        return ("rectal", "suppository or enema")
    if "ovule" in f:
        return ("fixed:vaginal", "pessary word")
    if "buvable" in f:
        if _has(f, "comprimé", "gélule"):
            return ("solid", "tablet for an oral solution or suspension")
        return ("fixed:oral_liquid", "oral liquid word")
    if _has(f, "patch", "transdermal", "système de diffusion", "emplâtre", "plaster"):
        return ("patch", "patch or plaster")
    if _has(f, *SOLID) or f in ("film orodispersible", "film, soluble"):
        if "coated pellets" in f and not _has(f, "delayed", "extended"):
            return ("unknown", "coated pellets: release not stated")
        if _has(f, *MODIFIED):
            return ("solid_mr", "modified-release tablet or capsule")
        return ("solid", "tablet or capsule")
    if _has(f, *POWDER):
        if _has(f, *TO_LIQUID):
            return ("liquid", "powder or granules to make a liquid")
        return ("powder", "film, powder, granules or lyophilisate")
    if _has(f, "spray", "pulvérisation", "aerosol", "aérosol"):
        return ("spray", "spray or aerosol")
    if _has(f, *LIQUID):
        return ("liquid", "liquid or gas")
    if _has(f, *SEMISOLID):
        return ("semisolid", "semisolid or impregnated form")
    if _has(f, "insert", "ring", "dispositif"):
        return ("insert", "insert, ring or device")
    return ("unknown", "no rule")


ROUTE_GROUP: dict[str, dict[str, str]] = {
    # kind -> route class -> group (a route class not listed: unknown)
    "solid": {
        "oral": "oral_solid",
        "oromucosal": "other",
        "vaginal": "vaginal",
        "rectal": "rectal",
    },
    "solid_mr": {"oral": "oral_solid_modified_release", "oromucosal": "other"},
    "liquid": {
        "oral": "oral_liquid",
        "parenteral": "injection",
        "ophthalmic": "ophthalmic",
        "otic": "otic",
        "nasal": "nasal",
        "inhaled": "inhaled",
        "cutaneous": "cutaneous",
        "rectal": "rectal",
        "vaginal": "vaginal",
        "oromucosal": "other",
    },
    "spray": {  # an oral-route spray is a mouth or tongue spray, not an oral liquid
        "oromucosal": "other",
        "oral": "other",
        "nasal": "nasal",
        "inhaled": "inhaled",
        "cutaneous": "cutaneous",
        "ophthalmic": "ophthalmic",
        "rectal": "rectal",
        "vaginal": "vaginal",
    },
    "semisolid": {
        "cutaneous": "cutaneous",
        "ophthalmic": "ophthalmic",
        "nasal": "nasal",
        "otic": "otic",
        "rectal": "rectal",
        "vaginal": "vaginal",
        "oromucosal": "other",
    },
    "patch": {"transdermal": "transdermal", "cutaneous": "cutaneous", "oromucosal": "other"},
    "powder": {"inhaled": "inhaled", "cutaneous": "cutaneous", "oromucosal": "other"},
    "rectal": {"rectal": "rectal", "vaginal": "vaginal"},
    "insert": {
        "vaginal": "vaginal",
        "ophthalmic": "ophthalmic",
        "inhaled": "inhaled",
        "oromucosal": "other",
    },
}
# Kinds that may carry a modified-release word and keep a group (oral solid MR has its own group;
# a transdermal patch is a prolonged-release form by nature; `other` is never compared).
MR_ALLOWED = ("solid_mr", "patch", "fixed:other")


def propose(form: str, routes: Sequence[str]) -> tuple[str | None, str]:
    """(group or None, rule) for one published form and route set."""
    kind, rule = form_kind(form)
    if kind == "unknown":
        return (None, rule)
    if kind not in MR_ALLOWED and _has(form.lower(), *MODIFIED):
        return (None, "modified-release form outside the oral solid groups (Req 6.5)")
    if kind.startswith("fixed:"):
        return (kind.removeprefix("fixed:"), rule)
    parts = {p.strip() for p in form.lower().split(" et ") if p.strip()}
    if len(parts) > 1:
        return (None, "presentation of several different forms")
    rc = routes_class(routes)
    group = ROUTE_GROUP[kind].get(rc)
    if kind == "patch" and group not in ("transdermal", "other") and _has(form.lower(), *MODIFIED):
        return (None, "modified-release patch on a cutaneous route (Req 6.5)")
    return (group, f"{rule}; route {rc}")


def draft_rows(observed: Iterable[tuple[str, str, Sequence[str], int]]) -> list[list[str]]:
    """Rows of the draft table from (source, form, routes, products) observations."""
    by_form: dict[tuple[str, str], list[tuple[str, int]]] = defaultdict(list)
    for source, form, routes, count in observed:
        if form and form.strip():
            by_form[(source, form)].append((route_key(routes), count))
    out: list[list[str]] = []
    for (source, form), sets in sorted(by_form.items()):
        proposals = {rk: propose(form, rk.split("|") if rk else []) for rk, _ in sets}
        counts = Counter[str]()
        for rk, n in sets:
            counts[rk] += n
        if len({g for g, _ in proposals.values()}) == 1:
            group, rule = next(iter(proposals.values()))
            if "; route" in rule:
                rule = rule.split("; route")[0] + "; same for every route set seen"
            note = f"proposed; {rule}; {sum(counts.values())} products"
            out.append([source, form, ANY_ROUTE, group or "", note])
            continue
        for rk in sorted(counts):
            group, rule = proposals[rk]
            out.append([source, form, rk, group or "", f"proposed; {rule}; {counts[rk]} products"])
    return out


def render(rows: Iterable[Sequence[str]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(HEADER)
    w.writerows(rows)
    return buf.getvalue()


_SQL = """
SELECT source_id, dosage_form, routes, count(*)
FROM res_product
WHERE dataset_id = (SELECT dataset_id FROM res_current) AND dosage_form IS NOT NULL
GROUP BY 1, 2, 3
"""


def main(argv: Sequence[str] | None = None) -> int:
    import psycopg

    from janus.settings import Settings

    ap = argparse.ArgumentParser(prog="python -m janus.passport.forms_draft")
    ap.add_argument("--out", type=Path, default=FORMS_FILE)
    args = ap.parse_args(argv)
    settings = Settings.from_env()
    if not settings.database_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    with psycopg.connect(settings.database_url) as conn, conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        observed = [(s, f, list(r), int(n)) for s, f, r, n in conn.execute(_SQL)]
    text = render(draft_rows(observed))
    table = parse(text)  # the draft must load
    args.out.write_text(text, encoding="utf-8")
    covered: Counter[str] = Counter()
    compared: Counter[str] = Counter()
    total: Counter[str] = Counter()
    for s, f, r, n in observed:
        total[s] += n
        g = table.group(s, f, r)
        covered[s] += n if g is not None else 0
        compared[s] += n if g is not None and g not in NOT_COMPARED_GROUPS else 0
    print(f"rows {len(table.rows)}")
    for s in sorted(total):
        print(  # log-guard: ignore (counts per source only)
            f"{s}: {covered[s]} of {total[s]} products with a group ({covered[s] / total[s]:.1%}), "
            f"{compared[s]} in a compared group ({compared[s] / total[s]:.1%})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

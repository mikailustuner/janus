"""Impact report for candidate name rules (drug-resolution design §15.8, task 19, Req 12.11).

`python -m janus.resolution.name_rules_report [--data-dir PATH] [--min-occurrences 20]`

For every candidate salt, ester or hydrate word, every switch of `name_lists` and every candidate
anion-acid row, the report measures what the rule would do to the names of each source (TİTCK,
openFDA, BDPM, Nomenclátor, FAERS) **without enabling anything**: the rule is set for the length
of one evaluation (`name_lists.override`) and restored. It lists

- the names and occurrences a word touches, and how they change (unmapped to mapped, to
  ambiguous; mapped to another key or to ambiguous: the cases the review must look at);
- the **ATC agreement** for sources that publish a code on single-ingredient products (TİTCK,
  Nomenclátor): the share whose mapped ingredient has a code in the same five-character group
  as the published one, with and without the word;
- candidate words found by single-word removal (`discover_words`), ranked by occurrences.

The file `$JANUS_DATA_DIR/resolution/name-rules-<ruleset 8>.json` holds source names (examples),
so it is never written to a tracked path; the program prints counts only. The pharmacologist
agent reads the file and writes `name-rules-review.md`; the owner accepts it before any rule
data is committed (task 20).

TİTCK names are mapped without the TİTCK-code bridge (step 6 of the full ladder): the bridge
needs the whole product set and is not affected by salt words.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from janus.resolution import name_lists
from janus.resolution.anion_acid import AnionAcidRow, AnionAcidTable
from janus.resolution.atc import is_ingredient_level
from janus.resolution.coverage_snapshot import (
    NameResult,
    artifact_rows,
    change_kind,
    check_output_path,
    compare_names,
    faers_counts,
    status_of,
)
from janus.resolution.load import Inputs, gather
from janus.resolution.matching import Match, NameIndex, map_name
from janus.resolution.name_lists import Lang
from janus.resolution.names import fold
from janus.resolution.prepare import build_name_index, eligible_items
from janus.resolution.prepare_eu import UNNAMED, bdpm_ingredients, cima_ingredients
from janus.resolution.prepare_eu import is_homeopathic_name as _is_hom_name


def _seq(row: Mapping[str, Any], key: str) -> list[Any]:
    value: Any = row.get(key)
    return list(cast(Iterable[Any], value)) if value else []


REPORT_VERSION = "name_rules_report-1"

# Candidate words of design §15.2 (measured demand on 2026-11-08). Discovery adds more.
CANDIDATE_WORDS: dict[Lang, tuple[str, ...]] = {
    "fr": tuple(
        (
            "chlorhydrate dichlorhydrate anhydre sodique potassique calcique magnesique fumarate "
            "hemifumarate acetate maleate tartrate propionate digluconate chlorure bromure"
        ).split()
    ),
    "es": tuple(
        (
            "hidrocloruro dihidrocloruro hidrobromuro besilato medoxomilo cilexetilo axetilo "
            "etexilato trihidrato monohidrato dihidrato hemihidrato calcica calcico sodica sodico "
            "potasico magnesico fumarato maleato citrato oxalato mesilato succinato tartrato "
            "sodio potasio calcio"
        ).split()
    ),
    "en": tuple(
        (
            "cypionate enanthate pivalate ditosylate terephthalate probutate glycinate hippurate "
            "mandelate arginine lysine"
        ).split()
    ),
    "tr": (),
}
CONNECTORS: dict[Lang, frozenset[str]] = {
    "tr": frozenset(),
    "en": frozenset(),
    "fr": frozenset({"de", "d", "du", "des"}),
    "es": frozenset({"de", "del"}),
}
# Candidate anion-acid rows (design §15.4); the review decides which stay.
CANDIDATE_ACID_ROWS: tuple[tuple[str, str, str], ...] = (
    ("any", "mycophenolate", "mycophenolic acid"),
    ("any", "folate", "folic acid"),
    ("any", "valproate", "valproic acid"),
    ("any", "alendronate", "alendronic acid"),
    ("any", "zoledronate", "zoledronic acid"),
    ("any", "aminosalicylate", "aminosalicylic acid"),
    ("fr", "mycophenolate", "acide mycophenolique"),
    ("es", "micofenolato", "acido micofenolico"),
)
SWITCHES: dict[str, dict[str, bool]] = {
    "biologic_suffix": {"BIOLOGIC_SUFFIX_ENABLED": True},
    "es_final_vowel": {"ES_FINAL_VOWEL_ENABLED": True},
    "acid_word_order": {"ACID_WORD_ORDER_ENABLED": True},
}


@dataclass(frozen=True)
class SourceNames:
    """The ingredient names of one source and the products that publish an ATC code."""

    source: str
    lang: Lang
    counts: Mapping[str, int]
    single_products: Sequence[tuple[str, str]] = ()  # (published name, published ATC)


@dataclass(frozen=True)
class WordImpact:
    word: str
    lang: Lang
    source: str
    names_touched: int
    occurrences_touched: int
    changes: dict[str, dict[str, int]]  # kind -> {"names": n, "occurrences": n}
    agreement: dict[str, dict[str, int]] | None  # "before"/"after" -> counts, if the source has ATC
    examples: list[tuple[str, str, str]] = field(default_factory=list[tuple[str, str, str]])

    def as_json(self) -> dict[str, Any]:
        return {
            "word": self.word,
            "lang": self.lang,
            "source": self.source,
            "names_touched": self.names_touched,
            "occurrences_touched": self.occurrences_touched,
            "changes": self.changes,
            "atc_agreement": self.agreement,
            "examples": [list(e) for e in self.examples],
        }


# --- pure parts -------------------------------------------------------------------------------


def _result(counts: Mapping[str, int], name: str, m: Match) -> NameResult:
    return NameResult(counts[name], status_of(m), m.keys if m.status == "mapped" else (), m.step)


def touched_names(counts: Mapping[str, int], word: str) -> list[str]:
    """Names that contain `word` as a whole folded token."""
    return sorted(n for n in counts if word in fold(n).split())


def agreement(
    products: Iterable[tuple[str, str]],
    map_fn: Callable[[str], Match],
    codes_of_key: Mapping[str, frozenset[str]],
) -> dict[str, int]:
    """Single-ingredient products with a valid published code: how many map, and how many of
    those map to an ingredient that has a code in the published code's five-character group."""
    n = mapped = agree = 0
    for name, atc in products:
        if not is_ingredient_level(atc):
            continue
        n += 1
        m = map_fn(name)
        if m.status == "mapped":
            mapped += 1
            agree += any(c[:5] == atc[:5] for c in codes_of_key.get(m.keys[0], frozenset()))
    return {"products": n, "mapped": mapped, "agree": agree}


def discover_words(
    counts: Mapping[str, int], map_fn: Callable[[str], Match], lang: Lang
) -> Counter[str]:
    """Words whose removal from an unmapped name makes it map: candidates by occurrences.

    This is an upper bound: it also finds words that are not salts (`vitamin` in `vitamin d`),
    which is why every candidate goes through the review.
    """
    gain: Counter[str] = Counter()
    connectors = CONNECTORS[lang]
    for name, occ in counts.items():
        if map_fn(name).status == "mapped":
            continue
        tokens = fold(name).split()
        if len(tokens) < 2:
            continue
        for i, token in enumerate(tokens):
            rest = tokens[:i] + tokens[i + 1 :]
            while len(rest) > 1 and rest[0] in connectors:
                rest = rest[1:]
            while len(rest) > 1 and rest[-1] in connectors:
                rest = rest[:-1]
            if map_fn(" ".join(rest)).status == "mapped":
                gain[token] += occ
                break
    return gain


def evaluate_word(
    word: str,
    src: SourceNames,
    *,
    build_index: Callable[[], NameIndex],
    label_tokens: frozenset[str],
    codes_of_key: Mapping[str, frozenset[str]],
    labels_of_key: Mapping[str, str],
    env: Mapping[str, Any] | None = None,
    env_index: NameIndex | None = None,
) -> WordImpact:
    """What adding `word` to the salt words of `src.lang` does to the names of `src`.

    "Before" is the state with the environment `env` (e.g. the connectors of the language) and
    without the word; "after" adds the word. The index is rebuilt only if the word occurs in a
    label (salt words also strip labels); otherwise the environment's index is reused.
    """
    lang = src.lang
    env = dict(env or {})
    touched = touched_names(src.counts, word)
    if not touched:
        return WordImpact(word, lang, src.source, 0, 0, {}, None)
    with name_lists.override(**env):
        before_index = env_index or build_index()
        before = {n: map_name(n, before_index, lang=lang) for n in touched}
        with_word = {
            **name_lists.EXTRA_SALT_WORDS,
            lang: name_lists.EXTRA_SALT_WORDS[lang] | {word},
        }
        with name_lists.override(EXTRA_SALT_WORDS=with_word):
            after_index = build_index() if word in label_tokens else before_index
            after = {n: map_name(n, after_index, lang=lang) for n in touched}
            single = [(n, a) for n, a in src.single_products if word in fold(n).split()]
            ag_before: dict[str, int] | None = None
            ag_after: dict[str, int] | None = None
            if single:
                ag_after = agreement(
                    single, lambda n: map_name(n, after_index, lang=lang), codes_of_key
                )
        if single:
            ag_before = agreement(
                single, lambda n: map_name(n, before_index, lang=lang), codes_of_key
            )
    rb = {n: _result(src.counts, n, before[n]) for n in touched}
    ra = {n: _result(src.counts, n, after[n]) for n in touched}
    changes = compare_names(rb, ra)
    kinds = {
        k: {"names": changes["names"][k], "occurrences": changes["occurrences"][k]}
        for k in changes["names"]
    }
    examples: list[tuple[str, str, str]] = []
    for n in touched:
        k = change_kind(rb[n], ra[n])
        if k is not None and len(examples) < 5:
            label = labels_of_key.get(ra[n].keys[0], "") if ra[n].keys else ""
            examples.append((n, k, label))
    ag: dict[str, dict[str, int]] | None = None
    if ag_before is not None and ag_after is not None:
        ag = {"before": ag_before, "after": ag_after}
    return WordImpact(
        word,
        lang,
        src.source,
        len(touched),
        sum(src.counts[n] for n in touched),
        kinds,
        ag,
        examples,
    )


def _mapper(index: NameIndex, lang: Lang) -> Callable[[str], Match]:
    def map_one(name: str) -> Match:
        return map_name(name, index, lang=lang)

    return map_one


def all_results(counts: Mapping[str, int], index: NameIndex, lang: Lang) -> dict[str, NameResult]:
    return {n: _result(counts, n, map_name(n, index, lang=lang)) for n in sorted(counts)}


def evaluate_switch(
    src: SourceNames, build_index: Callable[[], NameIndex], switch: Mapping[str, Any]
) -> dict[str, dict[str, int]]:
    """Change counts for every name of `src` with a switch of `name_lists` on."""
    before = all_results(src.counts, build_index(), src.lang)
    with name_lists.override(**switch):
        after = all_results(src.counts, build_index(), src.lang)
    return compare_names(before, after)


def evaluate_acid_row(
    row: tuple[str, str, str],
    srcs: Sequence[SourceNames],
    build_index: Callable[[AnionAcidTable | None], NameIndex],
) -> dict[str, Any]:
    """Impact of one candidate anion-acid row on the sources of the row's language."""
    lang, anion, acid = row
    table = AnionAcidTable((AnionAcidRow(lang, fold(anion), fold(acid), "candidate"),), "")
    plain = build_index(None)
    with_row = build_index(table)
    tier = with_row.any_label.get(fold(acid))
    keys: set[str] = (set(tier[0]) | set(tier[1])) if tier else set()
    out: dict[str, Any] = {"row": list(row), "acid_resolves_to_keys": len(keys), "sources": {}}
    for src in srcs:
        if lang not in (src.lang, "any"):
            continue
        # names that contain the anion as a whole word: the mapping decides what changes
        sub = {n: c for n, c in src.counts.items() if fold(anion) in fold(n).split()}
        if not sub:
            continue
        rb = all_results(sub, plain, src.lang)
        ra = all_results(sub, with_row, src.lang)
        out["sources"][src.source] = {"names_checked": len(sub), **compare_names(rb, ra)}
    return out


# --- data -------------------------------------------------------------------------------------


def label_tokens_of(rows: Iterable[Mapping[str, Any]]) -> frozenset[str]:
    out: set[str] = set()
    for r in rows:
        for lang in ("en", "tr", "de", "fr", "es"):
            names = [r.get(f"label_{lang}"), *_seq(r, f"aliases_{lang}")]
            for n in names:
                if n:
                    out.update(fold(str(n)).split())
    return frozenset(out)


def load_sources(data_dir: Path) -> list[SourceNames]:
    out: list[SourceNames] = []
    rows = artifact_rows(data_dir, "titck")
    if rows is not None:
        counts: Counter[str] = Counter()
        single: list[tuple[str, str]] = []
        for r in rows:
            ings = [str(i) for i in _seq(r, "ingredients")]
            counts.update(ings)
            if len(ings) == 1 and r.get("atc_code"):
                single.append((ings[0], str(r["atc_code"])))
        out.append(SourceNames("titck", "tr", dict(counts), single))
    rows = artifact_rows(data_dir, "us_ndc")
    if rows is not None:
        counts = Counter()
        for r in rows:
            counts.update(
                str(cast(Mapping[str, Any], a).get("name") or "")
                for a in _seq(r, "active_ingredients")
            )
        counts.pop("", None)
        out.append(SourceNames("openfda_ndc", "en", dict(counts)))
    rows = artifact_rows(data_dir, "eu_fr_bdpm")
    if rows is not None:
        counts = Counter()
        for r in rows:
            ings, _ = bdpm_ingredients(_seq(r, "composition"))
            ns = [i.name for i in ings]
            if not any(_is_hom_name(n) for n in ns):
                counts.update(ns)
        out.append(SourceNames("eu_fr_bdpm", "fr", dict(counts)))
    rows = artifact_rows(data_dir, "eu_es_cima")
    if rows is not None:
        counts = Counter()
        single = []
        for r in rows:
            ings = [i.name for i in cima_ingredients(_seq(r, "ingredients")) if i.name != UNNAMED]
            counts.update(ings)
            if len(ings) == 1 and r.get("atc_code"):
                single.append((ings[0], str(r["atc_code"])))
        out.append(SourceNames("eu_es_cima", "es", dict(counts), single))
    fc = faers_counts(data_dir)
    if fc is not None:
        out.append(SourceNames("faers", "en", fc))
    return out


def build_report(
    data_dir: Path, inputs: Inputs, *, min_occurrences: int = 20, top: int = 120
) -> dict[str, Any]:
    wikidata = inputs.artifacts["wikidata"].rows
    items, _codes, base_check = eligible_items(wikidata, inputs.rules, inputs.curated.rows)
    codes_of_key = {
        q: frozenset(
            c
            for c in (str(x) for x in _seq(r, "atc_codes"))
            if is_ingredient_level(c) and not base_check.is_combination(c)
        )
        for q, r in items.items()
    }
    labels_of_key = {q: str(r.get("label_en") or "") for q, r in items.items()}
    label_tokens = label_tokens_of(items.values())

    def build_index(acid: AnionAcidTable | None = None) -> NameIndex:
        return build_name_index(wikidata, inputs.rules, inputs.synonyms, inputs.curated.rows, acid)

    sources = load_sources(data_dir)
    report: dict[str, Any] = {
        "version": REPORT_VERSION,
        "candidate_words": {k: list(v) for k, v in CANDIDATE_WORDS.items()},
        "connectors": {k: sorted(v) for k, v in CONNECTORS.items()},
        "sources": {},
        "acid_rows": [],
        "switches": {},
    }
    for src in sources:
        env = {"CONNECTORS": {**name_lists.CONNECTORS, src.lang: CONNECTORS[src.lang]}}
        with name_lists.override(**env):
            env_index = build_index()
            discovered = discover_words(src.counts, _mapper(env_index, src.lang), src.lang)
        known = name_lists.BASE_SALT_WORDS | CONNECTORS[src.lang]
        found = [
            (w, c)
            for w, c in discovered.most_common()
            if c >= min_occurrences and w not in known and len(w) >= 3 and not w.isdigit()
        ][:top]
        words = list(dict.fromkeys([*CANDIDATE_WORDS[src.lang], *(w for w, _ in found)]))
        impacts = [
            evaluate_word(
                w,
                src,
                build_index=build_index,
                label_tokens=label_tokens,
                codes_of_key=codes_of_key,
                labels_of_key=labels_of_key,
                env=env,
                env_index=env_index,
            )
            for w in words
        ]
        report["sources"][src.source] = {
            "lang": src.lang,
            "distinct_names": len(src.counts),
            "occurrences": sum(src.counts.values()),
            "discovered": [{"word": w, "occurrences": c} for w, c in found],
            "words": [i.as_json() for i in impacts if i.names_touched],
        }
        for sw_name, sw in SWITCHES.items():
            report["switches"].setdefault(sw_name, {})[src.source] = evaluate_switch(
                src, build_index, sw
            )
    report["acid_rows"] = [
        evaluate_acid_row(row, sources, lambda t: build_index(t)) for row in CANDIDATE_ACID_ROWS
    ]
    return report


def ruleset_id(report: Mapping[str, Any]) -> str:
    keys = {k: report[k] for k in ("version", "candidate_words", "connectors")}
    return hashlib.sha256(json.dumps(keys, sort_keys=True).encode()).hexdigest()[:8]


def print_counts(report: Mapping[str, Any]) -> None:
    for src, s in report["sources"].items():
        gains = sum(
            w["changes"].get("unmapped_to_mapped", {}).get("occurrences", 0) for w in s["words"]
        )
        risky = sum(
            w["changes"].get(k, {}).get("names", 0)
            for w in s["words"]
            for k in ("mapped_to_other_key", "mapped_to_ambiguous", "mapped_to_unmapped")
        )
        print(
            f"{src}: {len(s['words'])} words touch names; if all were accepted +{gains} "
            f"occurrences mapped; names that change key or become ambiguous: {risky}"
        )
    for sw, per in report["switches"].items():
        for src, c in per.items():
            print(f"switch {sw} on {src}: names changed {c['names'] or 'none'}")
    for row in report["acid_rows"]:
        print(f"acid row {row['row']}: resolves to {row['acid_resolves_to_keys']} key(s)")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m janus.resolution.name_rules_report")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--min-occurrences", type=int, default=20)
    args = parser.parse_args(argv)
    from janus.settings import Settings

    data_dir = args.data_dir or Settings.from_env().data_dir
    if data_dir is None:
        print("set --data-dir or JANUS_DATA_DIR", file=sys.stderr)
        return 2
    report = build_report(data_dir, gather(data_dir), min_occurrences=args.min_occurrences)
    out = check_output_path(data_dir / "resolution" / f"name-rules-{ruleset_id(report)}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False), encoding="utf-8"
    )
    print_counts(report)
    print(f"wrote {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

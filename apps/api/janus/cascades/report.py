"""Coverage report CLI (cascade-engine design §7, Req 8.5).

`python -m janus.cascades.report [--data-dir PATH] [--similarity 0.6]` reads the current rule base
and resolution dataset in one read-only transaction and writes
`$JANUS_DATA_DIR/cascades/coverage-<rule base 8>-<dataset 8>.json`. The file holds TİTCK names,
so it is never written inside the repository unless the path is git-ignored. Prints and logs
counts only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import psycopg

from janus.cascades import repository
from janus.cascades.coverage import IngredientRow, KeyRow, ProductRow, build_coverage
from janus.db.pool import Database
from janus.resolution.atc import DATA_DIR, is_ingredient_level
from janus.resolution.model import is_homeopathic_strength
from janus.resolution.prepare_eu import is_homeopathic_name
from janus.settings import Settings

REPO = DATA_DIR.parent


class OutputPathError(ValueError):
    """The report would land in a tracked part of the repository."""


def check_output_path(path: Path, repo: Path = REPO) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(repo.resolve())
    except ValueError:
        return resolved  # outside the repository
    ignored = subprocess.run(  # noqa: S603
        ["git", "-C", str(repo), "check-ignore", "-q", str(resolved)],  # noqa: S607
        check=False,
    )
    if ignored.returncode != 0:
        raise OutputPathError("the coverage report must not be written to a tracked path")
    return resolved


def read_rows(
    conn: psycopg.Connection,
) -> tuple[str, list[ProductRow], list[IngredientRow], list[KeyRow]]:
    row = conn.execute("SELECT dataset_id FROM res_current").fetchone()
    if row is None:
        raise LookupError("no resolution dataset loaded")
    ds = str(row[0])
    raw = conn.execute(
        "SELECT source_id, product_id, published_name, status, qid, key_candidates, atc, strength "
        "FROM res_product_ingredient WHERE dataset_id = %s",
        (ds,),
    ).fetchall()
    homeopathic = {
        (str(r[0]), int(r[1]))
        for r in raw
        if is_homeopathic_strength(r[7]) or is_homeopathic_name(str(r[2]))
    }  # same rule as ProductCandidate.homeopathic (a strength unit or a BDPM name marker)
    products = [
        ProductRow(
            str(r[0]), int(r[1]), str(r[2]), r[3], r[4], (str(r[0]), int(r[1])) in homeopathic
        )
        for r in conn.execute(
            "SELECT source_id, product_id, region, product_type, published_atc FROM res_product "
            "WHERE dataset_id = %s",
            (ds,),
        )
    ]
    ingredients = [
        IngredientRow(
            str(r[0]),
            int(r[1]),
            str(r[2]),
            str(r[3]),
            r[4],
            tuple(r[5]),
            tuple(sorted({a["code"] for a in cast(list[dict[str, Any]], r[6])}))
            if r[3] == "mapped"
            else (),
        )
        for r in raw
    ]
    names: dict[str, set[str]] = {}
    for r in conn.execute(
        "SELECT ref, name_key FROM res_name WHERE dataset_id = %s AND kind = 'ingredient'", (ds,)
    ):
        names.setdefault(str(r[0]), set()).add(str(r[1]))
    keys = [
        KeyRow(
            str(r[0]),
            cast(dict[str, Any], r[1]).get("en"),
            tuple(
                sorted(
                    {
                        a["code"]
                        for a in cast(list[dict[str, Any]], r[2])
                        if is_ingredient_level(a["code"])
                    }
                )
            ),
            tuple(sorted(names.get(str(r[0]), set()))),
        )
        for r in conn.execute(
            "SELECT qid, labels, ingredient_atc FROM res_ingredient WHERE dataset_id = %s", (ds,)
        )
    ]
    return ds, products, ingredients, keys


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m janus.cascades.report")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--similarity", type=float, default=0.6)
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    data_dir = args.data_dir or settings.data_dir
    if not settings.database_url or data_dir is None:
        print("DATABASE_URL and JANUS_DATA_DIR (or --data-dir) are required", file=sys.stderr)
        return 2
    db = Database(settings.database_url)
    db.open()
    try:
        with db.read_only_tx() as conn:
            rb = repository.current_rule_base(conn)
            if rb is None:
                print(  # log-guard: ignore
                    "no rule base loaded (run python -m janus.cascades.load)", file=sys.stderr
                )
                return 1
            ds, products, ingredients, keys = read_rows(conn)
    finally:
        db.close()
    report = build_coverage(rb, products, ingredients, keys, args.similarity)
    report["dataset_version"] = ds
    out = check_output_path(
        Path(data_dir) / "cascades" / f"coverage-{rb.version[:8]}-{ds[:8]}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8"
    )
    s = report["summary"]
    print(f"rules {s['rules']}; not matchable {len(s['not_matchable'])}")
    print(
        f"cannot fire in TR {len(s['cannot_fire_in_tr'])}; in US {len(s['cannot_fire_in_us'])}; "
        f"in EU {len(s['cannot_fire_in_eu'])}"
    )
    print(f"marker classes with OTC share >= 0.5: {len(s['otc_marker_classes'])}")
    print(f"hints: {sum(c['hints_total'] for c in report['classes'].values())} over all classes")
    kinds = Counter(k for c in report["classes"].values() for h in c["hints"] for k in h["kinds"])
    print(f"hint kinds in the listed hints: {dict(sorted(kinds.items()))}")
    print(f"written to the data directory ({out.name})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

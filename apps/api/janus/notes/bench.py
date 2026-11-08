"""Local latency check of the note document (doctor-loop Req 15.1). Not run in CI.

Usage: `python -m janus.notes.bench --names amlodipine,furosemide,... [--repeat 30]` with
`DATABASE_URL` (a loaded dev database) and `JANUS_DATA_DIR` (a counts file). Wording does not
change the work, so the bench uses a placeholder glossary built from the template catalogue (the
real glossary may still be under review). Prints counts and timings only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import statistics
import sys
import time

from janus.cascades.schemas import EvaluateIn
from janus.db.pool import Database
from janus.memory.reader import CountsHolder
from janus.memory.vocabulary import load_events
from janus.notes import glossary as gl
from janus.notes.schemas import NoteIn
from janus.notes.service import compose
from janus.notes.templates import SPECS
from janus.settings import EVENT_VOCABULARY, Settings


def placeholder_glossary(pipc: dict[int, tuple[str, str, str]]) -> gl.Glossary:
    import csv
    import io

    def text(header: tuple[str, ...], rows: list[dict[str, str]]) -> str:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(header), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        return buf.getvalue()

    sentences: list[dict[str, str]] = []
    for s in SPECS:
        holes = " ".join("{" + p + "}" for p, _ in s.params)
        row = {
            "id": s.id,
            "kind": s.kind,
            "evidence": ";".join(s.evidence),
            "params": ";".join(f"{p}:{t}" for p, t in s.params),
            "status": "accepted",
            "shared": s.shared or "",
            "note": "",
        }
        for lang in gl.LANGUAGES:
            row[lang] = f"x {holes}".strip()
        sentences.append(row)
    cascades: list[dict[str, str]] = []
    for n, (a, e, b) in pipc.items():
        row = {"position": str(n), "en_sha256": gl.cascade_hash(a, e, b), "status": "accepted"}
        row["note"] = ""  # placeholder rows only
        for lang in gl.LANGUAGES[1:]:
            row |= {f"drug_a_{lang}": "a", f"adverse_event_{lang}": "e", f"drug_b_{lang}": "b"}
        cascades.append(row)
    return gl.parse(
        text(gl.INGREDIENT_HEADER, []),
        text(gl.CASCADE_HEADER, cascades),
        text(gl.SENTENCE_HEADER, sentences),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", required=True, help="comma-separated English ingredient labels")
    ap.add_argument("--repeat", type=int, default=30)
    args = ap.parse_args(argv)
    settings = Settings.from_env()
    if not settings.database_url or settings.data_dir is None:
        sys.stderr.write("DATABASE_URL and JANUS_DATA_DIR are required\n")
        return 2
    db = Database(settings.database_url, max_size=1)
    db.open()
    vocab = load_events(EVENT_VOCABULARY)
    holder = CountsHolder(settings.data_dir)
    try:
        with db.read_only_tx() as conn:
            row = conn.execute("SELECT dataset_id FROM res_current").fetchone()
            if row is None:
                sys.stderr.write("no resolution dataset loaded\n")
                return 2
            dataset = str(row[0])
            items: list[dict[str, str]] = []
            for i, name in enumerate(n.strip() for n in args.names.split(",")):
                hit = conn.execute(
                    "SELECT qid FROM res_ingredient WHERE dataset_id = %s AND labels->>'en' = %s",
                    (dataset, name),
                ).fetchone()
                if hit is not None:
                    items.append(
                        {"ingredient": str(hit[0]), "started": f"{2015 + i // 6}-{i % 12 + 1:02d}"}
                    )
            from janus.cascades import repository

            rb = repository.current_rule_base(conn)
            if rb is None:
                sys.stderr.write("no rule base loaded\n")
                return 2
            pipc = {r.position: (r.drug_a, r.adverse_event, r.drug_b) for r in rb.rules}
        glossary = placeholder_glossary(pipc)
        body = NoteIn.model_validate(
            {
                "evaluation": EvaluateIn.model_validate(
                    {"dataset_version": dataset, "items": items}
                ).model_dump(),
                "languages": ["en", "de"],
                "region": "EU",
                "statistics_region": "EU",
            }
        )
        times: list[float] = []
        findings = stat_rows = 0
        for _ in range(args.repeat):
            start = time.perf_counter()
            with db.read_only_tx() as conn, holder.current().session() as session:
                out = compose(
                    conn,
                    body,
                    today=dt.date.today(),
                    vocab=vocab,
                    glossary=glossary,
                    session=session,
                )
            times.append((time.perf_counter() - start) * 1000)
            findings = len(out.ordered)
            stat_rows = sum(
                1
                for sec in out.note.documents[0].sections
                for b in sec.blocks
                if getattr(b, "type", "") == "stat"
            )
        times.sort()
        p95 = times[max(0, int(len(times) * 0.95) - 1)]
        print(  # log-guard: ignore (counts and timings only)
            f"items={len(items)} findings={findings} stat_rows={stat_rows} languages=2 "
            f"runs={len(times)} "
            f"p50={statistics.median(times):.0f}ms p95={p95:.0f}ms max={times[-1]:.0f}ms"
        )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

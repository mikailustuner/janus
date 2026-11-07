"""Rule-base loader (cascade-engine design §5, Req 1.1, 1.4, 10.1-10.3).

`python -m janus.cascades.load [--window-months 12] [--data-dir PATH]` validates the curated
files, then writes the rule base, the current pointer and the 65 `rule:pipc:<n>` evidence
records in one transaction. The integrity loader must have run first (the PIPC paper and the
cited papers must be registered). Logs counts and nothing else.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from janus.cascades.model import DEFAULT_WINDOW_MONTHS, RuleBase
from janus.cascades.rulebase import (
    ABRUPT_FILE,
    CLASSES_FILE,
    COMBINATION_FILE,
    PAPERS_FILE,
    PIPC_FILE,
    PIPC_META_FILE,
    PRIORITY_FILE,
    RULES_FILE,
    RuleBaseError,
    RuleBaseInputs,
    build_rule_base,
    ids_used,
    rule_base_content,
)
from janus.db.pool import Database
from janus.integrity.load import register_records
from janus.integrity.model import EvidenceRecord
from janus.observability.logging import LogEvent, configure_logging, log_event
from janus.resolution.atc import DATA_DIR
from janus.settings import Settings

type Hook = Callable[[str], None]

FILES = (
    PIPC_FILE,
    PIPC_META_FILE,
    CLASSES_FILE,
    RULES_FILE,
    PRIORITY_FILE,
    ABRUPT_FILE,
    COMBINATION_FILE,
    PAPERS_FILE,
)


class RuleBaseLoadError(RuntimeError):
    """The rule base cannot be loaded (names the reason, never a value)."""


@dataclass(frozen=True)
class LoadedFiles:
    texts: dict[str, str]
    window_months: int

    def inputs(self) -> RuleBaseInputs:
        t = self.texts
        return RuleBaseInputs(
            pipc_csv=t[PIPC_FILE],
            pipc_meta_json=t[PIPC_META_FILE],
            classes_csv=t[CLASSES_FILE],
            rules_csv=t[RULES_FILE],
            priority_csv=t[PRIORITY_FILE],
            abrupt_csv=t[ABRUPT_FILE],
            combination_csv=t[COMBINATION_FILE],
            papers_csv=t[PAPERS_FILE],
            window_months=self.window_months,
        )

    def audit(self, rb: RuleBase) -> dict[str, Any]:
        return {
            "files": {
                n: hashlib.sha256(self.texts[n].encode("utf-8")).hexdigest() for n in sorted(FILES)
            },
            "window_months": self.window_months,
            "engine_version": rb.engine_version,
        }


def read_files(
    data_dir: Path = DATA_DIR, window_months: int = DEFAULT_WINDOW_MONTHS
) -> LoadedFiles:
    try:
        texts = {n: (data_dir / n).read_text(encoding="utf-8") for n in FILES}
    except OSError as exc:
        raise RuleBaseLoadError("a curated rule-base file cannot be read") from exc
    return LoadedFiles(texts, window_months)


def rule_records(rb: RuleBase, pipc_meta_json: str) -> list[EvidenceRecord]:
    """One `rule` record per PIPC row, resting on the PIPC paper only (DP5)."""
    meta = json.loads(pipc_meta_json)
    url = f"https://doi.org/{meta['doi']}"
    snapshot = dt.date.fromisoformat(meta["snapshot_date"])
    return [
        EvidenceRecord(
            id=r.evidence_id,
            kind="rule",
            source_id="pipc",
            source_url=url,
            license=meta["license"],
            region=None,
            snapshot_date=snapshot,
            snapshot_is_retrieval_time=False,
            doi=None,
            locator=r.locator,
            title=f"PIPC list, Table 1, row {r.position}",
            basis=(rb.source_paper_id,),
        )
        for r in rb.rules
    ]


@dataclass(frozen=True)
class LoadResult:
    version: str
    created: bool
    rules: int


def _registered(conn: psycopg.Connection, ids: Sequence[str]) -> set[str]:
    rows = conn.execute("SELECT id FROM evidence WHERE id = ANY(%s)", (list(ids),)).fetchall()
    return {str(r[0]) for r in rows}


def load(
    db: Database, files: LoadedFiles, today: dt.date, *, hook: Hook | None = None
) -> LoadResult:
    """Validate, then write everything in one transaction; a failure leaves the state as before."""
    rb = build_rule_base(files.inputs())  # RuleBaseError: nothing written
    records = rule_records(rb, files.texts[PIPC_META_FILE])
    cited = sorted(set(ids_used(rb)))
    with db.write_tx() as conn:
        missing = set(cited) - _registered(conn, cited)
        if missing:
            raise RuleBaseLoadError(
                f"{len(missing)} cited evidence record(s) are not registered; "
                "run python -m janus.integrity.load first"
            )
        conn.execute("LOCK TABLE cascade_rule_base_current IN EXCLUSIVE MODE")
        created = (
            conn.execute(
                "INSERT INTO cascade_rule_base (version, content, inputs) VALUES (%s, %s, %s) "
                "ON CONFLICT (version) DO NOTHING",
                (rb.version, Jsonb(rule_base_content(rb)), Jsonb(files.audit(rb))),
            ).rowcount
            == 1
        )
        if hook:
            hook("rule_base")
        register_records(conn, records, today)
        if hook:
            hook("evidence")
        conn.execute(
            "INSERT INTO cascade_rule_base_current (one, version) VALUES (true, %s) "
            "ON CONFLICT (one) DO UPDATE SET version = EXCLUDED.version",
            (rb.version,),
        )
        if hook:
            hook("current")
    return LoadResult(rb.version, created, len(rb.rules))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m janus.cascades.load")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR, help="curated data/ directory")
    parser.add_argument("--window-months", type=int, default=DEFAULT_WINDOW_MONTHS)
    args = parser.parse_args(argv)
    configure_logging()
    settings = Settings.from_env()
    if not settings.database_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    db = Database(settings.database_url)
    db.open()
    try:
        result = load(
            db, read_files(args.data_dir, args.window_months), dt.datetime.now(dt.UTC).date()
        )
    except (RuleBaseError, RuleBaseLoadError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()
    log_event(LogEvent.cascade_load, count=result.rules)
    state = "stored" if result.created else "already stored"
    print(f"rule base {result.version} {state}; {result.rules} rules; current")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

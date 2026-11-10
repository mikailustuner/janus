"""Command line: `janus-pipelines run|promote|status|notice`."""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

from janus_pipelines.core.licensing import LicenceViolationError
from janus_pipelines.core.manifest import Outcome
from janus_pipelines.core.notice import render_notice
from janus_pipelines.core.registry import Registry, UnknownSourceError, load_registry
from janus_pipelines.core.runner import (
    Job,
    PromotionError,
    RunContext,
    ToolUnavailableError,
    promote_run,
    run_job,
)
from janus_pipelines.core.store import Store

REPO_ROOT = Path(__file__).resolve().parents[2]
EXIT_OK, EXIT_FAILED, EXIT_REFUSED, EXIT_NEEDS_REVIEW = 0, 1, 4, 3


# Pipeline name -> (module, class). Imported on demand so one job's dependencies or errors
# never affect the others.
JOBS: dict[str, tuple[str, str]] = {
    "pipc": ("janus_pipelines.jobs.pipc", "PipcJob"),
    "canon": ("janus_pipelines.jobs.canon", "CanonJob"),
    "canon_gold": ("janus_pipelines.jobs.canon_gold", "CanonGoldJob"),
    "titck": ("janus_pipelines.jobs.titck", "TitckJob"),
    "wikidata_ingredients": (
        "janus_pipelines.jobs.wikidata_ingredients",
        "WikidataIngredientsJob",
    ),
    "us_ndc": ("janus_pipelines.jobs.us_ndc", "UsNdcJob"),
    "us_recalls": ("janus_pipelines.jobs.us_recalls", "UsRecallsJob"),
    "us_label_interactions": (
        "janus_pipelines.jobs.us_label_interactions",
        "UsLabelInteractionsJob",
    ),
    "retractions": ("janus_pipelines.jobs.retractions", "RetractionsJob"),
    "eu_fr_bdpm": ("janus_pipelines.jobs.eu_fr_bdpm", "EuFrBdpmJob"),
    "eu_es_cima": ("janus_pipelines.jobs.eu_es_cima", "EuEsCimaJob"),
    "faers": ("janus_pipelines.jobs.faers", "FaersJob"),
    "faers_onset": ("janus_pipelines.jobs.faers_onset", "FaersOnsetJob"),
    "tm_molecules": ("janus_pipelines.jobs.time_machine", "TmMoleculesJob"),
    "tm_bioactivity": ("janus_pipelines.jobs.time_machine", "TmBioactivityJob"),
    "tm_labels": ("janus_pipelines.jobs.time_machine", "TmLabelsJob"),
    "tm_pbpk": ("janus_pipelines.jobs.tm_models", "TmPbpkJob"),
    "tm_admet": ("janus_pipelines.jobs.tm_models", "TmAdmetJob"),
    "onsides": ("janus_pipelines.jobs.onsides", "OnsidesJob"),
    "openfda_label": ("janus_pipelines.jobs.openfda_label", "OpenfdaLabelJob"),
}


def load_job(name: str) -> Job[Any]:
    module, cls = JOBS[name]
    factory = cast(Callable[[], Job[Any]], getattr(importlib.import_module(module), cls))
    return factory()


def registry_path(repo_root: Path) -> Path:
    return repo_root / "pipelines" / "sources.toml"


def data_dir(repo_root: Path) -> Path:
    value = os.environ.get("JANUS_DATA_DIR", "").strip()
    path = Path(value) if value else Path(".data")
    return path if path.is_absolute() else repo_root / path


def code_version(repo_root: Path) -> str:
    env = os.environ.get("JANUS_CODE_VERSION")
    if env:
        return env
    git = shutil.which("git")
    if git is None:
        return "unknown"
    head = subprocess.run(  # noqa: S603 - fixed argv
        [git, "-C", str(repo_root), "rev-parse", "HEAD"], capture_output=True, text=True
    )
    if head.returncode != 0:
        return "unknown"
    dirty = subprocess.run(  # noqa: S603 - fixed argv
        [git, "-C", str(repo_root), "status", "--porcelain"], capture_output=True, text=True
    )
    return head.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")


def committed_meta(repo_root: Path) -> list[dict[str, Any]]:
    """Metadata files of committed artifacts (data/*.meta.json)."""
    out: list[dict[str, Any]] = []
    for path in sorted((repo_root / "data").glob("*.meta.json")):
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def used_sources(repo_root: Path, registry: Registry) -> set[str]:
    used = {str(m["source_id"]) for m in committed_meta(repo_root)}
    root = data_dir(repo_root) / "artifacts"
    if root.is_dir():
        for pipeline_dir in sorted(root.iterdir()):
            manifest = Store(data_dir(repo_root), pipeline_dir.name).current_manifest()
            if manifest is not None:
                used.add(manifest.source_id)
    del registry
    return used


def build_notice(repo_root: Path) -> str:
    registry = load_registry(registry_path(repo_root))
    snapshots = {
        str(m["source_id"]): f"retrieved {m['retrieved_date']} ({m['file']})"
        for m in committed_meta(repo_root)
    }
    return render_notice(registry, used_sources(repo_root, registry), snapshots)


def make_context(repo_root: Path, options: dict[str, str]) -> RunContext:
    return RunContext(
        data_dir=data_dir(repo_root),
        repo_root=repo_root,
        registry=load_registry(registry_path(repo_root)),
        code_version=code_version(repo_root),
        options=options,
    )


def cmd_run(args: argparse.Namespace, repo_root: Path) -> int:
    job = load_job(args.pipeline)
    options: dict[str, str] = {}
    if args.input:
        options["input"] = str(Path(args.input).resolve())
    if args.snapshot_date:
        options["snapshot_date"] = args.snapshot_date
    if args.quarters:
        options["quarters"] = args.quarters
    try:
        result = run_job(job, make_context(repo_root, options))
    except (UnknownSourceError, LicenceViolationError, ToolUnavailableError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    m = result.manifest
    print(f"{m.pipeline} {m.run_id}: {m.outcome.value}")
    print(f"  snapshot {m.snapshot_date}  input {m.counts.input}  output {m.counts.output}")
    if m.counts.excluded:
        print(f"  excluded {json.dumps(m.counts.excluded, sort_keys=True)}")
    if m.metrics:
        print(f"  metrics {json.dumps(m.metrics, sort_keys=True, ensure_ascii=False)}")
    for reason in m.review_reasons:
        print(f"  review: {reason}")
    if result.error:
        print(f"error: {result.error}", file=sys.stderr)
    if result.outcome is Outcome.FAILED:
        return EXIT_FAILED
    if result.outcome is Outcome.NEEDS_REVIEW:
        print("  not promoted; after review run:")
        print(f"  janus-pipelines promote {m.pipeline} {m.run_id} --by NAME")
        return EXIT_NEEDS_REVIEW
    return EXIT_FAILED if result.error else EXIT_OK


def cmd_promote(args: argparse.Namespace, repo_root: Path) -> int:
    job = load_job(args.pipeline)
    try:
        promotion = promote_run(job, make_context(repo_root, {}), args.run_id, args.by)
    except (PromotionError, FileNotFoundError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    print(f"{args.pipeline}: {promotion.run_id} promoted by {promotion.promoted_by}")
    return EXIT_OK


def cmd_status(args: argparse.Namespace, repo_root: Path) -> int:
    names = [args.pipeline] if args.pipeline else sorted(JOBS)
    for name in names:
        manifest = Store(data_dir(repo_root), name).current_manifest()
        if manifest is None:
            print(f"{name}: unavailable (no promoted artifact)")
        else:
            print(
                f"{name}: {manifest.run_id} snapshot {manifest.snapshot_date} "
                f"rows {manifest.counts.output}"
            )
    return EXIT_OK


def cmd_notice(args: argparse.Namespace, repo_root: Path) -> int:
    try:
        text = build_notice(repo_root)
    except UnknownSourceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILED
    target = repo_root / "NOTICE"
    if args.check:
        if target.read_text(encoding="utf-8") != text:
            print("NOTICE is out of date; run `janus-pipelines notice`", file=sys.stderr)
            return EXIT_FAILED
        print("NOTICE is up to date")
        return EXIT_OK
    target.write_text(text, encoding="utf-8")
    print(f"wrote {target}")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="janus-pipelines")
    sub = parser.add_subparsers(dest="command", required=True)
    names = list(JOBS)

    run = sub.add_parser("run", help="run one pipeline")
    run.add_argument("pipeline", choices=names)
    run.add_argument("--input", help="read a local source file instead of downloading")
    run.add_argument("--snapshot-date", help="publication date (YYYY-MM-DD) for --input")
    run.add_argument("--quarters", help="faers only: comma-separated quarters, e.g. 2026Q3,2026Q2")

    promote = sub.add_parser("promote", help="promote a needs_review run")
    promote.add_argument("pipeline", choices=names)
    promote.add_argument("run_id")
    promote.add_argument("--by", required=True, help="who reviewed and promotes the run")

    status = sub.add_parser("status", help="show the current artifact of each pipeline")
    status.add_argument("pipeline", nargs="?", choices=names)

    notice = sub.add_parser("notice", help="generate NOTICE from sources.toml")
    notice.add_argument("--check", action="store_true", help="fail if NOTICE is out of date")

    args = parser.parse_args(argv)
    handlers = {"run": cmd_run, "promote": cmd_promote, "status": cmd_status, "notice": cmd_notice}
    return handlers[args.command](args, REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())

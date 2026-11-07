#!/usr/bin/env python3
"""log-guard: no health data in logs (.kiro/steering/privacy.md).

Parses every Python file under apps/api/ (except .venv) and flags logging calls (logger.*, logging.*,
structlog bind, print) whose arguments mention ingredients, product codes, ATC codes, events,
dates, notes or medical request bodies. Allowed in logs: request id, route, status, latency.

Scans the whole scope on every run, so it does not depend on the hook's stdin payload.
Exit 0: clean. Exit 1: findings (path:line). Suppress a justified line with
"# log-guard: ignore".
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCAN = ROOT / "apps" / "api"
PRAGMA = "log-guard: ignore"

LOG_METHODS = {
    "debug", "info", "warning", "warn", "error", "exception", "critical", "fatal", "log", "bind",
}
SENSITIVE = {
    # products and ingredients
    "ingredient", "ingredients", "inn", "product", "products", "barcode", "gtin", "ndc", "cip",
    "cip13", "cis", "pzn", "atc", "rxcui", "qid", "medication", "medications", "medicine",
    "medicines", "drug", "drugs", "dose", "doses", "strength",
    # events and clinical content
    "event", "events", "meddra", "reaction", "reactions", "symptom", "symptoms", "cascade",
    "cascades", "finding", "findings", "outcome", "outcomes", "note", "notes", "contribution",
    "contributions", "donation", "donations",
    # dates and demographics
    "date", "dates", "onset", "birth", "dob", "age", "sex",
    # request bodies and parameters of medical endpoints
    "body", "payload", "json", "form", "query", "params",
}
SENSITIVE_PAIRS = {("product", "code"), ("national", "code")}


def tokens(text: str) -> list[str]:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return [t.lower() for t in re.split(r"[^A-Za-z0-9]+", text) if t]


def hits(text: str) -> set[str]:
    toks = tokens(text)
    found = {t for t in toks if t in SENSITIVE}
    found |= {f"{a}_{b}" for a, b in zip(toks, toks[1:], strict=False) if (a, b) in SENSITIVE_PAIRS}
    return found


def is_log_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "print"
    if isinstance(func, ast.Attribute) and func.attr in LOG_METHODS:
        base = func.value
        while isinstance(base, ast.Attribute | ast.Call):
            base = base.value if isinstance(base, ast.Attribute) else base.func
        return isinstance(base, ast.Name) and "log" in base.id.lower()
    return False


def names_in(node: ast.AST) -> set[str]:
    found: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            found |= hits(sub.id)
        elif isinstance(sub, ast.Attribute):
            found |= hits(sub.attr)
        elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            found |= hits(sub.value)
        elif isinstance(sub, ast.keyword) and sub.arg:
            found |= hits(sub.arg)
    return found


def check(path: Path) -> list[str]:
    rel = path.relative_to(ROOT)
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [f"{rel}:{exc.lineno}: could not parse ({exc.msg})"]
    lines = source.splitlines()
    out: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and is_log_call(node)):
            continue
        if PRAGMA in lines[node.lineno - 1]:
            continue
        found: set[str] = set()
        for arg in [*node.args, *node.keywords]:
            found |= names_in(arg)
        if found:
            out.append(f"{rel}:{node.lineno}: logging call mentions {', '.join(sorted(found))}")
    return out


def main() -> int:
    files = sorted(p for p in SCAN.rglob("*.py") if ".venv" not in p.parts)
    findings = [f for p in files for f in check(p)]
    if findings:
        msg = "\n".join(
            [f"log-guard: {len(findings)} logging call(s) may include health data (privacy.md):"]
            + [f"  {f}" for f in findings]
            + ["  Log only request id, route, status and latency."]
        )
        print(msg)
        print(msg, file=sys.stderr)
        return 1
    print(f"log-guard: {len(files)} files checked, no health data in logging calls.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

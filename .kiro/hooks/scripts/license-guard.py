#!/usr/bin/env python3
"""license-guard: data/ holds small, redistributable files only.

Fails if data/ contains a file from a "fetch at runtime / cite only, never commit" source
(.kiro/steering/data-sources.md, .kiro/steering/structure.md):
  - TİTCK lists (Ruhsatlı Beşeri Tıbbi Ürünler, SKRS, etkin madde), found by name or by
    their column headers (BARKOD, ÜRÜN ADI, ETKİN MADDE, ATC KODU) in renamed extracts
  - EudraVigilance / adrreports.eu, Hamdard translation, ThinkCascades, WHOCC ATC/DDD index
  - spreadsheets (.xlsx/.xls/.xlsm/.ods): TİTCK publishes .xlsx; store open data as CSV/JSON
  - files over 10 MB ("small files only")

Scans the filesystem (tracked or not), so it does not depend on the hook's stdin payload.
Exit 0: clean. Exit 1: findings.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
MAX_BYTES = 10 * 1024 * 1024

FORBIDDEN_NAME = re.compile(
    r"t[iİı]tck|ruhsatl[iı]|skrs|etk[iİı]n[\s_-]?madde|its[\s_-]?k[iı]lavuz"
    r"|eudravigilance|adrreports|hamdard|thinkcascades|whocc|atc[\s_-]?ddd",
    re.IGNORECASE,
)
SPREADSHEETS = {".xlsx", ".xls", ".xlsm", ".ods"}
TITCK_HEADERS = ["BARKOD", "ÜRÜN ADI", "ETKIN MADDE", "ATC KODU"]


def normalize(text: str) -> str:
    text = text.replace("İ", "I").replace("ı", "i").upper()
    return re.sub(r"[_\-;,\t\"]+", " ", text)


def check(path: Path) -> str | None:
    rel = path.relative_to(ROOT)
    if FORBIDDEN_NAME.search(path.name):
        return f"{rel}: file name matches a never-commit source (TİTCK or cite-only source)"
    if path.suffix.lower() in SPREADSHEETS:
        return f"{rel}: spreadsheet in data/; TİTCK lists are .xlsx and must be fetched at runtime"
    if path.stat().st_size > MAX_BYTES:
        return f"{rel}: larger than 10 MB; data/ is for small redistributable files"
    try:
        head = path.read_bytes()[:8192].decode("utf-8")
    except UnicodeDecodeError:
        return None
    header = normalize(head)
    matched = [h for h in TITCK_HEADERS if h in header]
    if len(matched) >= 2:
        return f"{rel}: looks like a TİTCK list extract (columns: {', '.join(matched)})"
    return None


def main() -> int:
    if not DATA.is_dir():
        print("license-guard: no data/ directory.")
        return 0
    files = sorted(p for p in DATA.rglob("*") if p.is_file() and p.name != "README.md")
    findings = [f for p in files if (f := check(p))]
    if findings:
        msg = "\n".join(
            ["license-guard: data/ contains files that must never be committed:"]
            + [f"  {f}" for f in findings]
            + ["  Fetch these at runtime (pipelines/) and keep them out of data/."]
        )
        print(msg)
        print(msg, file=sys.stderr)
        return 1
    print(f"license-guard: {len(files)} file(s) in data/ checked, none from a never-commit source.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

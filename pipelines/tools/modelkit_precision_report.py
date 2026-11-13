# ruff: noqa: E501 - SVG markup and long report strings
"""Model kit precision (phase B3a): items and frames -> `precision.json` and the risk-coverage SVG.

Inputs (committed): `data/validation/modelkit/items.csv` (one row per reviewed value: source, sample, study, stratum, level,
the two automated verdicts) and `data/validation/modelkit/frames.json` (frame sizes, band weights, coverage per level).
Analysis as pre-registered in `docs/research/modelkit-precision-protocol.md` (`precision_stats`: Wilson, study-level
cluster bootstrap, design effect, cluster-aware lower bound, acceptance >= 0.90).
Usage: uv run --project pipelines python pipelines/tools/modelkit_precision_report.py [--date YYYY-MM-DD]
Research use only. Not for clinical decisions. Expert review has not yet been done."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from janus_pipelines.modelkit.precision_stats import Item, Summary, accepted, summarise

REPO = Path(__file__).resolve().parents[2]
BASE = REPO / "data" / "validation" / "modelkit"
THRESHOLD = 0.90
LABELS = {
    "clinicaltrials_gov": "ClinicalTrials.gov results",
    "pmc_oa": "PubMed Central open-access tables",
    "drugsatfda_review": "Drugs@FDA review tables",
}
COLOURS = {"clinicaltrials_gov": "#2a6fdb", "pmc_oa": "#c2410c", "drugsatfda_review": "#0f8a5f"}


def _r(x: float | None, d: int = 3) -> float | None:
    return None if x is None else round(x, d)


def _pair(x: tuple[float, float] | None) -> list[float | None] | None:
    return None if x is None else [_r(x[0]), _r(x[1])]


def summary_json(s: Summary) -> dict[str, Any]:
    d = asdict(s)
    return {
        "items": s.items,
        "n": s.agreed,
        "k": s.correct,
        "studies": s.studies,
        "precision": _r(s.precision),
        "conservative": _r(s.conservative),
        "wilson": _pair(s.wilson),
        "cluster_bootstrap": _pair(s.bootstrap),
        "design_effect": _r(d["design_effect"], 2),
        "design_effect_estimated": s.design_effect_estimated,
        "n_effective": _r(s.n_effective, 1),
        "wilson_adjusted": _pair(s.wilson_adjusted),
        "cluster_lower": _r(s.cluster_lower),
        "kappa": _r(s.kappa),
        "meets_rule": accepted(s, THRESHOLD),
    }


def load_items(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def items_of(rows: list[dict[str, str]], source: str, sample: str) -> list[dict[str, str]]:
    return [r for r in rows if r["source"] == source and r["sample"] == sample]


def to_items(rows: list[dict[str, str]]) -> list[Item]:
    return [Item(r["study"], r["stratum"], r["verdict_1"], r["verdict_2"]) for r in rows]


def curve(rows: list[dict[str, str]], spec: dict[str, Any], total: int) -> list[dict[str, Any]]:
    """Precision at each level k listed in `coverage`: items at level >= k, bands weighted by frame counts."""
    out: list[dict[str, Any]] = []
    weights = {k: float(v) for k, v in spec["band_weights"].items()}
    for lv, cov in sorted(spec["coverage"].items(), key=lambda kv: int(kv[0])):
        sel = [r for r in rows if r["stratum"] in weights and int(r["level"]) >= int(lv)]
        s = summarise(to_items(sel), weights)
        out.append(
            {"level": int(lv), "coverage_n": cov, "coverage": _r(cov / total), **summary_json(s)}
        )
    return out


def errors(rows: list[dict[str, str]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        if r["verdict_1"] == r["verdict_2"] == "incorrect":
            t = r["error_type_1"] or "other"
            out[t] = out.get(t, 0) + 1
    return dict(sorted(out.items()))


def by_parameter(rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        if r["verdict_1"] == r["verdict_2"] and r["verdict_1"] in ("correct", "incorrect"):
            d = out.setdefault(r["parameter"], {"n": 0, "k": 0})
            d["n"] += 1
            d["k"] += r["verdict_1"] == "correct"
    return dict(sorted(out.items()))


def build(rows: list[dict[str, str]], frames: dict[str, Any], date: str) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    for src, fr in frames.items():
        if src.startswith("_"):
            continue
        total = int(fr["confirmed_values"])
        res: dict[str, Any] = {"label": LABELS[src], "confirmed_values": total, "curves": []}
        for c in fr.get("curves", []):
            rs = [r for r in items_of(rows, src, c["sample"]) if r["stratum"] in c["band_weights"]]
            res["curves"].append(
                {
                    "name": c["name"],
                    "fresh_measurement": c["fresh_measurement"],
                    "frame_values": sum(c["band_weights"].values()),
                    "points": curve(rs, c, total),
                    "errors_agreed": errors(rs),
                    "by_parameter": by_parameter(rs),
                }
            )
        if sh := fr.get("shipped"):
            rs = [r for r in items_of(rows, src, sh["sample"]) if int(r["level"]) >= sh["level"]]
            res["shipped"] = {
                "name": sh["name"],
                "fresh_measurement": sh["fresh_measurement"],
                "level": sh["level"],
                "coverage_n": sh["coverage"],
                "coverage": _r(sh["coverage"] / total),
                **summary_json(summarise(to_items(rs))),
                "errors_agreed": errors(rs),
            }
        for sec in fr.get("secondary", []):
            rs = [r for r in items_of(rows, src, sec["sample"]) if r["stratum"] == sec["stratum"]]
            res.setdefault("secondary", []).append(
                {"name": sec["name"], **summary_json(summarise(to_items(rs)))}
            )
        if acc := fr.get("acceptance"):
            pts = {p["level"]: p for c in res["curves"] for p in c["points"]}
            passing = [lv for lv in acc["levels"] if pts.get(lv, {}).get("meets_rule")]
            res["acceptance"] = {
                "rule": f"cluster-aware lower 95 % bound >= {THRESHOLD:.2f}",
                "levels_tested": acc["levels"],
                "passes_at_level": min(passing) if passing else None,
                "ships": bool(passing),
            }
        sources[src] = res
    return {
        "measured_on": date,
        "protocol": "docs/research/modelkit-precision-protocol.md",
        "method": "docs/research/modelkit-precision.md",
        "truth": "two independent automated review passes per value; expert review has not yet been done",
        "recall": "not yet measured (needs expert annotation, phase B3b)",
        "acceptance_rule": f"a source ships only if the cluster-aware lower 95 % bound of its precision is >= {THRESHOLD:.2f}",
        "interval_note": "wilson assumes independent values; cluster_bootstrap resamples whole studies (4,000 resamples, seed 20261113); cluster_lower = min(bootstrap lower, Wilson lower with n / design effect)",
        "sources": sources,
    }


def svg(result: dict[str, Any]) -> str:
    """Risk-coverage curve: coverage (x) vs precision (y), cluster-aware interval as a bar."""
    w, h, ml, mr, mt, mb = 640, 400, 64, 36, 28, 56
    y0, y1 = 0.0, 1.0

    def x(c: float) -> float:
        return ml + c * (w - ml - mr)

    def y(p: float) -> float:
        return mt + (y1 - max(y0, min(y1, p))) / (y1 - y0) * (h - mt - mb)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
        'aria-labelledby="t d" font-family="system-ui, sans-serif" font-size="12">',
        '<title id="t">Model kit precision: risk-coverage curve</title>',
        '<desc id="d">Precision of confirmed values at each strict-check level against the share of confirmed values kept, '
        "per source, with cluster-aware 95 % intervals. Truth is two automated review passes; expert review has not yet "
        "been done.</desc>",
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
    ]
    for t in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        out.append(
            f'<line x1="{ml}" x2="{w - mr}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#e5e7eb"/>'
        )
        out.append(
            f'<text x="{ml - 8}" y="{y(t) + 4:.1f}" text-anchor="end" fill="#374151">{t:.1f}</text>'
        )
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        out.append(
            f'<text x="{x(t):.1f}" y="{h - mb + 18}" text-anchor="middle" fill="#374151">{int(t * 100)} %</text>'
        )
    out.append(
        f'<line x1="{ml}" x2="{w - mr}" y1="{y(0.9):.1f}" y2="{y(0.9):.1f}" stroke="#6b7280" stroke-dasharray="5 4"/>'
        f'<text x="{w - mr}" y="{y(0.9) - 5:.1f}" text-anchor="end" fill="#374151">acceptance bound 0.90</text>'
    )
    out.append(
        f'<text x="{(ml + w - mr) / 2}" y="{h - 14}" text-anchor="middle" fill="#111827">'
        "coverage: share of confirmed values kept at this level or above</text>"
        f'<text transform="translate(16 {(mt + h - mb) / 2}) rotate(-90)" text-anchor="middle" fill="#111827">'
        "precision (agreed verdicts)</text>"
    )
    legend_y = y(0.68)
    lx = x(0.3)
    for src, res in result["sources"].items():
        col = COLOURS[src]
        for c in res["curves"]:
            pts = [p for p in c["points"] if p["precision"] is not None]
            path = " ".join(f"{x(p['coverage']):.1f},{y(p['precision']):.1f}" for p in pts)
            out.append(f'<polyline points="{path}" fill="none" stroke="{col}" stroke-width="2"/>')
            last_label = -1.0
            for p in pts:
                show = abs(p["coverage"] - last_label) >= 0.04
                last_label = p["coverage"] if show else last_label
                lo = p["cluster_lower"] if p["cluster_lower"] is not None else p["precision"]
                hi = (p["cluster_bootstrap"] or [p["precision"], p["precision"]])[1]
                out.append(
                    f'<line x1="{x(p["coverage"]):.1f}" x2="{x(p["coverage"]):.1f}" y1="{y(lo):.1f}" '
                    f'y2="{y(hi):.1f}" stroke="{col}" stroke-width="1.5" opacity="0.6"/>'
                    f'<circle cx="{x(p["coverage"]):.1f}" cy="{y(p["precision"]):.1f}" r="4" fill="{col}">'
                    f"<title>{res['label']}, level {p['level']}: precision {p['precision']}, coverage "
                    f"{p['coverage']}, n {p['n']} in {p['studies']} studies</title></circle>"
                )
                if show:
                    out.append(
                        f'<text x="{x(p["coverage"]) + 7:.1f}" y="{y(p["precision"]) + 14:.1f}" '
                        f'fill="#374151" font-size="10">L{p["level"]}</text>'
                    )
        if sh := res.get("shipped"):
            cx, cy = x(sh["coverage"]), y(sh["precision"])
            lo = sh["cluster_lower"] or sh["precision"]
            out.append(
                f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{y(lo):.1f}" y2="{y(sh["cluster_bootstrap"][1]):.1f}" '
                f'stroke="{col}" stroke-width="1.5"/>'
                f'<rect x="{cx - 5:.1f}" y="{cy - 5:.1f}" width="10" height="10" fill="#ffffff" stroke="{col}" '
                f'stroke-width="2"><title>{res["label"]}, shipped (level {sh["level"]}): precision {sh["precision"]}'
                f", n {sh['n']} in {sh['studies']} studies</title></rect>"
            )
        out.append(
            f'<rect x="{lx}" y="{legend_y + 2}" width="12" height="4" fill="{col}"/>'
            f'<text x="{lx + 18}" y="{legend_y + 8}" fill="#111827">{res["label"]}</text>'
        )
        legend_y += 16
    out.append(
        f'<rect x="{lx + 1}" y="{legend_y}" width="10" height="10" fill="#ffffff" stroke="#374151" stroke-width="2"/>'
        f'<text x="{lx + 18}" y="{legend_y + 9}" fill="#111827">shipped setting (ClinicalTrials.gov census)</text>'
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    rows = load_items(BASE / "items.csv")
    frames = json.loads((BASE / "frames.json").read_text("utf-8"))
    result = build(rows, frames, args.date)
    (BASE / "precision.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False) + "\n", "utf-8"
    )
    (REPO / "docs" / "research" / "modelkit-risk-coverage.svg").write_text(svg(result), "utf-8")
    print(json.dumps(result, indent=1)[:4000])


if __name__ == "__main__":
    main()

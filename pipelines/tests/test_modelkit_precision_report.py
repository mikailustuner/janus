"""The B3a precision report tool: curve per level, shipped point, acceptance, SVG."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "modelkit_precision_report.py"


def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("modelkit_precision_report", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def row(study: str, stratum: str, level: int, v1: str, v2: str | None = None) -> dict[str, str]:
    return {
        "source": "pmc_oa", "sample": "S", "item_id": f"{study}-{level}", "study": study,
        "drug": "d",
        "parameter": "cmax", "stratum": stratum, "level": str(level), "verdict_1": v1,
        "verdict_2": v2 or v1, "error_type_1": "value" if v1 == "incorrect" else "",
        "error_type_2": "",
    }  # fmt: skip


FRAMES = {
    "pmc_oa": {
        "confirmed_values": 100,
        "curves": [
            {
                "name": "c",
                "sample": "S",
                "fresh_measurement": True,
                "band_weights": {"L2": 20, "L0-1": 80},
                "coverage": {"0": 100, "2": 20},
            }
        ],
        "acceptance": {"levels": [2]},
    }
}


def test_curve_levels_coverage_and_acceptance() -> None:
    m = tool()
    rows = [row(f"a{i}", "L2", 2, "correct") for i in range(60)] + [
        row(f"b{i}", "L0-1", 0, "incorrect" if i % 2 else "correct") for i in range(20)
    ]
    out = m.build(rows, FRAMES, "2026-11-13")["sources"]["pmc_oa"]
    l0, l2 = out["curves"][0]["points"]
    assert (l2["level"], l2["coverage"], l2["n"], l2["precision"]) == (2, 0.2, 60, 1.0)
    assert l0["precision"] == pytest.approx(0.6)
    assert out["acceptance"]["ships"] and out["acceptance"]["passes_at_level"] == 2
    assert out["curves"][0]["errors_agreed"] == {"value": 10}
    svg = m.svg(m.build(rows, FRAMES, "2026-11-13"))
    assert svg.startswith("<svg") and "acceptance bound 0.90" in svg


def test_unagreed_items_do_not_count_and_empty_sources_have_no_precision() -> None:
    m = tool()
    out = m.build([row("a", "L2", 2, "correct", "incorrect")], FRAMES, "d")["sources"]["pmc_oa"]
    l2 = out["curves"][0]["points"][1]
    assert l2["n"] == 0 and l2["precision"] is None and not out["acceptance"]["ships"]

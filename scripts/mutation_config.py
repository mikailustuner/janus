"""Append the mutmut configuration for one target to apps/api/pyproject.toml (CI only, never
committed). Usage: python3 scripts/mutation_config.py cascades|resolution

mutmut copies the whole package (`source_paths`) so that imports resolve, and mutates only the
target's pure modules (every other file is listed in `do_not_mutate`). Only tests that need no
database run for each mutant. docs/testing.md, "Mutation testing".
"""

from __future__ import annotations

import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1] / "apps" / "api"

TARGETS: dict[str, tuple[list[str], list[str]]] = {
    "cascades": (
        [f"janus/cascades/{m}.py" for m in (
            "chains", "coverage", "engine", "exposure", "inputs", "patterns", "rulebase", "timing",
        )],
        [f"tests/test_cascades_{t}_properties.py" for t in (
            "chains", "coverage", "engine", "evidence", "patterns", "rulebase", "rules", "timing",
        )],
    ),
    "resolution": (
        [f"janus/resolution/{m}.py" for m in (
            "anion_acid", "atc", "canonical", "gs1", "matching", "name_lists", "names", "ndc",
        )],
        [f"tests/{t}.py" for t in (
            "test_anion_acid_properties", "test_aceponate_correction", "test_atc_properties",
            "test_gs1_properties", "test_matching_properties", "test_names_lang_properties",
            "test_names_properties", "test_ndc_properties", "test_enabled_rule_data",
        )],
    ),
}  # fmt: skip


def main(target: str) -> None:
    mutate, tests = TARGETS[target]
    others = sorted(
        str(p.relative_to(API))
        for p in (API / "janus").rglob("*.py")
        if str(p.relative_to(API)) not in mutate
    )
    lines = [
        "",
        "[tool.mutmut]",
        'source_paths = ["janus/"]',
        "pytest_add_cli_args_test_selection = [" + ", ".join(f'"{t}"' for t in tests) + "]",
        "do_not_mutate = [" + ", ".join(f'"{o}"' for o in others) + "]",
        "",
    ]
    with (API / "pyproject.toml").open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"{target}: {len(mutate)} modules mutated, {len(tests)} test files")


if __name__ == "__main__":
    main(sys.argv[1])

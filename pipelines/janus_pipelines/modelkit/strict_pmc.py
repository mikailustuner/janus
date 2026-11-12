"""Strict publication check for confirmed PMC table values (structure first, selective prediction).

Runs after the two document readers agree. It types the table itself: the header rows, the stub
(first column) and the column of the cell, and abstains unless the cell is a plain number in a column
whose header names no other analyte, drug, statistic or group type, in a table whose caption, header
and footnotes name only the drug, and (level 3) in an article whose methods name no other pool drug.
It reads no value for the evidence and shares no code with the two readers (identity table and
`norm` only). Each rule has a code; `level` maps them to the pre-registered levels. Research use only.
Not for clinical decisions.
"""

from __future__ import annotations

import re
from typing import Final

from janus_pipelines.modelkit.pmc_jats import Article, Table
from janus_pipelines.modelkit.resolver import IdentityTable, norm

_NUMBER: Final = re.compile(
    r"^\s*\d+(?:\.\d+)?\s*(?:(?:±|\+/-|\+-)\s*\d+(?:\.\d+)?|\(\s*\d+(?:\.\d+)?\s*%?\s*\))?\s*$"
)
_DECIMAL_COMMA: Final = re.compile(r"\d,\d")
_ANALYTE: Final = re.compile(
    r"metabolite|unbound|\bfree\b|\btotal\b|enantiomer|racem|glucuronide|hydroxy|desmethyl|active moiety|"
    r"\b[RS]-[A-Za-z]|\(\s*[RS+-]\s*\)|\bM-?\d{1,2}\b|\bM-?[IVX]+\b|conjugate",
    re.I,
)
_STATISTIC: Final = re.compile(
    r"\bcv\b|%|\bn\b|\bno\.|number|\bp\b|p[- ]value|ratio|\bgmr\b|\bci\b|confidence|interval|range|\bmin\b|\bmax\b"
    r"|minimum|maximum|\bsd\b|\bse\b|\bsem\b|standard|difference|change|rho|correlation|\brse\b|\bkel\b|lambda|"
    r"\bic50\b|\bec50\b|\bki\b|in vitro|target|predicted|simulated|model",
    re.I,
)
_POPULATION: Final = re.compile(
    r"renal|hepatic|impair|cirrho|elderly|older|geriatric|child|pediatric|paediatric|infant|neonat|adolescent|"
    r"obese|pregnan|dialysis|esrd|poor metabo|critically ill|icu\b",
    re.I,
)
_COMBINATION: Final = re.compile(
    r"\+|\bplus\b|combination|combined|fixed[- ]dose|\bfdc\b|co-?administ|coadminist|together with|cocktail|"
    r"(?<=[a-z])\s*/\s*(?=[a-z]{4})",
    re.I,
)
_PRODUCT: Final = re.compile(
    r"extended|sustained|controlled|delayed|modified|prolonged|\b(?:xr|er|sr|cr|xl|la)\b|depot|patch|transdermal|"
    r"liposom|inhal|intranasal|nasal|topical|intramuscular|subcutaneous|\bim\b|\bsc\b|implant|microsphere",
    re.I,
)
_SPECIES: Final = re.compile(
    r"\b(?:rats?|mice|mouse|dogs?|monkeys?|rabbits?|pigs?|minipigs?|beagle|primate|animal)\b", re.I
)

LEVELS: Final = {
    1: frozenset({"not_a_plain_number", "decimal_comma", "statistic_column", "analyte_word", "species_word", "other_drug_in_table"}),
    2: frozenset({"population_word", "combination_word", "product_word", "drug_not_named_in_table", "coadministered_claimed"}),
    3: frozenset({"other_drug_in_methods"}),
}  # fmt: skip


def _first_data_row(t: Table) -> int:
    if t.head_rows:
        return t.head_rows
    for i, row in enumerate(t.grid):
        if any(_NUMBER.match(c) for c in row[1:]):
            return i
    return len(t.grid)


def check(
    article: Article,
    table: Table,
    row: int,
    col: int,
    drug_key: str,
    ids: IdentityTable,
    coadministered: bool = False,
) -> tuple[str, ...]:
    """Codes of the strict rules the confirmed value in cell (row, col) fails."""
    if not (0 <= row < len(table.grid)) or not (0 <= col < len(table.grid[row])):
        return ("not_located",)
    fails: list[str] = []
    cell = table.grid[row][col]
    h = _first_data_row(table)
    header = " ; ".join(table.grid[i][col] for i in range(min(h, row)) if col < len(table.grid[i]))
    stub = table.grid[row][0] if col > 0 else ""
    scope = " ; ".join([table.label, table.caption, header, table.footnotes])
    if not _NUMBER.match(cell):
        fails.append("not_a_plain_number")
    if _DECIMAL_COMMA.search(cell):
        fails.append("decimal_comma")
    if _STATISTIC.search(header) or _STATISTIC.search(re.sub(r"\(.*?\)", " ", stub)):
        fails.append("statistic_column")
    if _ANALYTE.search(" ; ".join([table.caption, header, stub])):
        fails.append("analyte_word")
    if _SPECIES.search(scope):
        fails.append("species_word")
    named = ids.drugs_in(" ; ".join([table.caption, header, stub]))
    if any(k != drug_key for k in named):
        fails.append("other_drug_in_table")
    if _POPULATION.search(" ; ".join([table.caption, header, stub])):
        fails.append("population_word")
    if _COMBINATION.search(" ; ".join([table.caption, header])):
        fails.append("combination_word")
    if _PRODUCT.search(" ; ".join([table.caption, header, stub])):
        fails.append("product_word")
    if drug_key not in named and norm(drug_key) not in norm(article.title):
        fails.append("drug_not_named_in_table")
    if coadministered:
        fails.append("coadministered_claimed")
    if any(k != drug_key for k in ids.drugs_in(article.methods + " ; " + article.title)):
        fails.append("other_drug_in_methods")
    return tuple(fails)


def level(fails: tuple[str, ...]) -> int:
    if "not_located" in fails:
        return 0
    got = 0
    for lv in sorted(LEVELS):
        if any(f in LEVELS[lv] for f in fails):
            break
        got = lv
    return got

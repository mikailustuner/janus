"""Language word lists and switches of the name rules (drug-resolution design §15.2). Data only.

The Phase 1 lists are the `BASE_*` sets and apply to every language. Phase 2 additions are per
language (`EXTRA_*`, `CONNECTORS`) and are empty until the owner has accepted the review sheet
(`.kiro/specs/drug-resolution/name-rules-review.md`, Req 12.11). The three `*_ENABLED` switches are
likewise off until then. Changing anything here changes `names.rules_version()` and therefore the
dataset version (Req 5.7, 9.8). Tests set these names to try rule data; code reads them at call
time through this module, never through a `from` import.
"""

from __future__ import annotations

import sys
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Literal

type Lang = Literal["tr", "en", "fr", "es"]
LANGS: tuple[Lang, ...] = ("tr", "en", "fr", "es")

# Folded tokens. Words where the counter-ion changes the substance are deliberately absent:
# oxide/hydroxide/carbonate (metal compounds), mononitrate/dinitrate (isosorbide).
BASE_SALT_WORDS: frozenset[str] = frozenset(
    """
    hidroklorur hidroklorid hcl hci dihidroklorur monohidroklorur hidrobromur
    hydrochloride dihydrochloride monohydrochloride hydrobromide
    mesilat dimesilat besilat mesylate dimesylate besylate tosilat tosylate
    maleat dimaleat maleate fumarat hemifumarat fumarate sitrat citrate
    tartarat tartrat bitartarat bitartrat tartrate bitartrate suksinat succinate
    sulfat hemisulfat bisulfat sulphate sulfate hemisulfate bisulfate fosfat phosphate
    asetat acetate nitrat nitrate laktat lactate glukonat gluconate klorur chloride
    bromur bromide oksalat oxalate pamoat embonat pamoate sakkarat saccharate
    aspartat aspartate hiklat hyclate olamin olamine erbumin erbumine
    propiyonat propionat dipropiyonat dipropionat propionate dipropionate
    ksinafoat xinafoate medoksomil medoxomil asetonid acetonide aksetil axetil
    valerat valerate benzoat benzoate dekanoat decanoate palmitat palmitate
    trometamol trometamin tromethamine meglumin meglumine dietilamin diethylamine
    tert butilamin butylamine baz base
    sodyum sodium disodyum disodium potasyum potassium dipotasyum dipotassium
    kalsiyum calcium magnezyum magnesium
    monohidrat dihidrat trihidrat tetrahidrat pentahidrat hekzahidrat heptahidrat
    hemihidrat seskihidrat hidrat anhidr anhidrit anhidroz
    monohydrate dihydrate trihydrate tetrahydrate pentahydrate hexahydrate heptahydrate
    hemihydrate sesquihydrate hydrate anhydrous
    sileksetil cilexetil proksetil proxetil pivoksil pivoxil dipivoksil dipivoxil mofetil
    anhidrat anhidrus susuz oktahidrat hemiheptahidrat hemipentahidrat dekahidrat
    octahydrate hemiheptahydrate hemipentahydrate decahydrate hbr trifenatat trifenatate
    ksinofoat diglukonat digluconate dietilamonyum diethylammonium dimeglumin dimeglumine
    malat malate etabonat etabonate aseponat aceponate hemisuksinat hemisuccinate mezilat
    hidrojen hydrogen
    """.split()
)
# Pharmacologist review 2026-11-07: furoate is not a salt word (fluticasone/mometasone furoate
# have codes of their own); butylbromide, mono-/di-/trinitrate, disoproxil and alafenamide must
# never be added (they distinguish substances).

# If stripping would leave only these, the counter-ion is the substance or the leftover is not
# a substance on its own (sodium vs potassium bicarbonate, zinc acetate vs zinc gluconate,
# sodium calcium edetate vs edetate disodium): keep the name unchanged.
BASE_NOT_ALONE: frozenset[str] = frozenset(
    """
    carbonate karbonat bicarbonate bikarbonat oxide oksit hydroxide hidroksit peroxide peroksit
    fluoride florur iodide iyodur silicate silikat trisilicate trisilikat glycerophosphate
    gliserofosfat levulinate levulinat edetate edetat hypochlorite hipoklorit perchlorate
    perklorat nitrite nitrit thiosulfate tiyosulfat sulfide sulfur dibasic monobasic tribasic
    dibazik monobazik tribazik dl zinc cinko iron demir ferrous ferric ferro ferri silver gumus
    aluminium aluminum aluminyum copper bakir bismuth bizmut lithium lityum mercury civa
    ammonium amonyum methyl metil ethyl etil dimethyl dimetil diethyl dietil benzyl benzil
    butyl butil propyl propil ii iii
    """.split()
)

_NONE: frozenset[str] = frozenset()

# Phase 2 additions per language (Req 12.2). Empty until task 21.
EXTRA_SALT_WORDS: dict[Lang, frozenset[str]] = {"tr": _NONE, "en": _NONE, "fr": _NONE, "es": _NONE}
EXTRA_NOT_ALONE: dict[Lang, frozenset[str]] = {"tr": _NONE, "en": _NONE, "fr": _NONE, "es": _NONE}
# Connector words, removed only at the start or end of a name once salt words are gone (Req 12.3).
CONNECTORS: dict[Lang, frozenset[str]] = {"tr": _NONE, "en": _NONE, "fr": _NONE, "es": _NONE}

# Switches of the Phase 2 rewrite rules (Req 12.5, 12.8). Off until the review.
BIOLOGIC_SUFFIX_ENABLED = False
ES_FINAL_VOWEL_ENABLED = False
ACID_WORD_ORDER_ENABLED = False

# The unsplit check ignores spans made only of salt or connector words in these languages (new
# sources, nothing to preserve; Req 12.12). Turkish and English keep the Phase 1 behaviour.
UNSPLIT_GUARD_LANGS: frozenset[str] = frozenset({"fr", "es"})


@contextmanager
def override(**changes: Any) -> Generator[None]:
    """Set attributes of this module for the duration of a block and restore them afterwards.

    Used by the rule-impact report and by tests to try rule data before it is committed.
    """
    old = {k: getattr(sys.modules[__name__], k) for k in changes}
    for k, v in changes.items():
        setattr(sys.modules[__name__], k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(sys.modules[__name__], k, v)

"""FROZEN copy of the Phase 1 janus.resolution.names (2026-11-08). Do not edit.

One reviewed correction only: `aceponate` and `aseponat` left the salt list on 2026-11-08
(name-rules review, owner decision 2).

The oracle of drug-resolution P34: for `tr` and `en` and names without Phase 2 words, the
language-aware functions must return exactly what these functions return.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata

# Letters that NFKD does not decompose.
_EXTRA = str.maketrans({"æ": "ae", "œ": "oe", "ø": "o", "đ": "d", "ł": "l", "\u0131": "i"})
_NON_KEY = re.compile(r"[^a-z0-9%+]+")


def fold(text: str) -> str:
    """Lower-case, Turkish-aware, without diacritics; only `[a-z0-9%+]` and single spaces."""
    s = unicodedata.normalize("NFKC", text)
    # Turkish: dotted capital I, ASCII I and dotless i all fold to "i".
    s = s.replace("\u0130", "i").replace("I", "i").replace("\u0131", "i")
    s = s.casefold().translate(_EXTRA)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.translate(_EXTRA)
    return " ".join(_NON_KEY.sub(" ", s).split())


# Folded tokens. Words where the counter-ion changes the substance are deliberately absent:
# oxide/hydroxide/carbonate (metal compounds), mononitrate/dinitrate (isosorbide).
SALT_WORDS: frozenset[str] = frozenset(
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
    malat malate etabonat etabonate hemisuksinat hemisuccinate mezilat
    hidrojen hydrogen
    """.split()
)
# Pharmacologist review 2026-11-07: furoate is not a salt word (fluticasone/mometasone furoate
# have codes of their own); butylbromide, mono-/di-/trinitrate, disoproxil and alafenamide must
# never be added (they distinguish substances).

# If stripping would leave only these, the counter-ion is the substance or the leftover is not
# a substance on its own (sodium vs potassium bicarbonate, zinc acetate vs zinc gluconate,
# sodium calcium edetate vs edetate disodium): keep the name unchanged.
NOT_ALONE: frozenset[str] = frozenset(
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
_HYDRATE = re.compile(r"^[0-9]*h2o$")
_HYDRATE_WORD = re.compile(r"^(?:[a-z]*hidrat|[a-z]*hydrate|anhidr[a-z]*|anhydrous|susuz)$")


def _is_hydrate(token: str) -> bool:
    """`2h2o`, or a hydrate/anhydrous word from `SALT_WORDS`."""
    if _HYDRATE.match(token):
        return True
    return token in SALT_WORDS and _HYDRATE_WORD.match(token) is not None


def strip_salts(folded: str) -> str:
    """Remove salt words from a folded name.

    Hydrate words are always removed (water of crystallisation is never the substance). Other
    salt words are removed unless that would leave nothing, or only words in `NOT_ALONE`; then
    the hydrate-free name is returned ("kalsiyum klorür dihidrat" → "kalsiyum klorur").
    """
    tokens = folded.split()
    base = [t for t in tokens if not _is_hydrate(t)] or tokens
    keep = [t for t in base if t not in SALT_WORDS]
    if not keep or all(t in NOT_ALONE for t in keep):
        return " ".join(base)
    return " ".join(keep)


# Whole-token rewrites before spaces are removed: Roman numerals would otherwise collapse
# (iron ii / iron iii), and Turkish "asit" should meet English "acid".
TOKEN_RULES: dict[str, str] = {"ii": "2", "iii": "3", "iv": "4", "asit": "acid"}

# Applied in order, repeatedly, until nothing changes (so the key is idempotent).
SPELLING_RULES: tuple[tuple[str, str], ...] = (
    (r"ph", "f"),
    (r"th", "t"),
    (r"ch", "k"),
    (r"x", "ks"),
    (r"qu", "k"),
    (r"c(?=[eiy])", "s"),
    (r"c", "k"),
    (r"y", "i"),
    (r"z", "s"),
    (r"w", "v"),
    (r"ae", "e"),
    (r"oe", "e"),
    (r"([a-z0-9])\1+", r"\1"),
    (r"e$", ""),
    (r"d$", "t"),  # Turkish final devoicing: hidroklorotiyazit / hydrochlorothiazide
)
_COMPILED = tuple((re.compile(p), r) for p, r in SPELLING_RULES)


def spelling_key(folded: str) -> str:
    """Spelling-insensitive key of a folded name (spaces removed)."""
    tokens = [TOKEN_RULES.get(t, t) for t in folded.split()]
    s = re.sub(r"[^a-z0-9]", "", "".join(tokens))
    for _ in range(32):
        before = s
        for pattern, repl in _COMPILED:
            s = pattern.sub(repl, s)
        if s == before:
            return s
    raise AssertionError("spelling rules did not reach a fixed point")  # pragma: no cover


RULES_VERSION = hashlib.sha256(
    json.dumps(
        {
            "salt_words": sorted(SALT_WORDS),
            "not_alone": sorted(NOT_ALONE),
            "hydrate": _HYDRATE.pattern,
            "tokens": TOKEN_RULES,
            "spelling": SPELLING_RULES,
        },
        sort_keys=True,
    ).encode()
).hexdigest()

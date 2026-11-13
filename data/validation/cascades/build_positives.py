"""Apply protocol 3.1 (ingredient choice, duplicates) to the extracted candidates.

usage: python3 build_positives.py WD_JSON XML_DIR OUT_DIR

WD_JSON: the Wikidata ingredient snapshot exported to JSON (list of {qid,label,aliases,atc,rxcui});
XML_DIR: Europe PMC fullTextXML of the five sources (PMCxxxx.xml), see README.md.
"""
import csv, json, re, sys, xml.etree.ElementTree as ET
sys.path.insert(0, sys.argv[0].rsplit('/', 1)[0])
from positive_extraction import ROWS

WD, XML_DIR, OUT = sys.argv[1:4]
SRC_XML = {'DOH22': 'PMC9485823', 'ADR23': 'PMC10682291', 'CHEN23': 'PMC10350531',
           'TC22': 'PMC9477172', 'OMA24': 'PMC11365892'}
# ingredient names used here -> Wikidata label
NAME_FIX = {'oxybutynin': '(RS)-oxybutynin', 'levothyroxine': 'levothyroxine sodium', 'glibenclamide': 'glyburide',
            'ursodeoxycholic acid': 'ursodiol', 'sulpiride': '(RS)-sulpiride', 'ferrous fumarate': 'iron(II) fumarate',
            'cyclophosphamide': '(RS)-cyclophosphamide', 'rabeprazole': '(RS)-rabeprazole', 'timolol': '(S)-(−)-timolol',
            'solifenacin': 'solifenacin succinate', 'warfarin': 'rac-warfarin', 'lactulose': 'β-lactulose',
            'acetylsalicylic acid': 'aspirin', 'chlortalidone': 'chlorthalidone', 'butylscopolamine': 'butylscopolamine bromide',
            'anethole trithione': 'anethol trithione', 'pioglitazone': '(RS)-pioglitazone',
            'rosiglitazone': '(RS)-rosiglitazone', 'ropinirole': 'ropinirol'}
DISPLAY = {v.lower(): k for k, v in NAME_FIX.items()}
DISPLAY.update({'regular insulin': 'insulin (human)', 'l-thyroxine': 'levothyroxine', 'rac-salbutamol': 'salbutamol', 'aspirin': 'acetylsalicylic acid'})
# ingredients without an ATC code in the Wikidata snapshot: code checked in the WHO ATC/DDD index (atcddd.fhi.no) on 2026-11-13
ATC_EXTRA = {'carbamazepine': 'N03AF01', 'mirogabalin': 'N02BF03'}

wd = json.load(open(WD))
def combo(label, code):
    return '/' in label or ' and ' in label or label.lower().startswith('atc') or int(code[5:7]) >= 50

items_by_name, by_code = {}, {}
for it in wd:
    lab = it['label'] or ''
    if not lab: continue
    items_by_name.setdefault(lab.lower(), it)
    for code in it['atc']:
        if len(code) == 7 and code[5:7].isdigit() and not combo(lab, code):
            by_code.setdefault(code, []).append(it)

def display(it):
    lab = it['label']
    if lab.lower() in DISPLAY: return DISPLAY[lab.lower()]
    return re.sub(r'^((\([^)]*\)\W?)+|rac-)', '', lab).lower()

def code_item(code):
    its = by_code[code]
    return sorted(its, key=lambda i: (i['label'][:1].isupper(), not i['rxcui'], len(i['label']), i['label']))[0]

def ingredient(name, ctx):
    if name in ATC_EXTRA:
        return name, ATC_EXTRA[name], 'WHO ATC/DDD index'
    it = items_by_name.get(NAME_FIX.get(name, name).lower())
    if it is None:
        raise SystemExit(f'no Wikidata item for {name}')
    codes = sorted(c for c in it['atc'] if len(c) == 7)
    pick = [c for c in codes if ctx and any(c.startswith(p) for p in ctx.split('|'))] or codes
    if ctx and not any(c.startswith(p) for c in pick for p in ctx.split('|')):
        print('WARN context mismatch', name, ctx, codes)
    return name, pick[0], 'Wikidata'

def body_text(src):
    root = ET.parse(f'{XML_DIR}/{SRC_XML[src]}.xml').getroot()
    parts = [root.find('.//abstract'), root.find('.//body'), root.find('.//floats-group')]
    return ' '.join(' '.join(''.join(p.itertext()).split()) for p in parts if p is not None)

def row_text(src, table, row):
    root = ET.parse(f'{XML_DIR}/{SRC_XML[src]}.xml').getroot()
    for tw in root.iter('table-wrap'):
        lab = tw.find('label')
        if lab is None or ' '.join(''.join(lab.itertext()).split()) != table: continue
        n = 0
        for tb in tw.iter('tbody'):
            for tr in tb.iter('tr'):
                n += 1
                if n == row: return ' '.join(''.join(tr.itertext()).split())
    raise SystemExit(f'row not found {src} {table} {row}')

# salt or counter-ion words: a mention such as 'tiotropium bromide' does not name the bromide ingredient
SALT_WORDS = {'bromide', 'bromides', 'chloride', 'iodide', 'sodium', 'potassium', 'calcium', 'magnesium', 'sulfate',
              'sulphate', 'acetate', 'citrate', 'phosphate', 'nitrate', 'carbonate', 'hydrochloride', 'fumarate'}

def item_names(it):
    names = {it['label']} | {a for a in it['aliases'] if a.islower() or a[:1].isupper() and a[1:].islower()} | {display(it)}
    return {n.strip().lower() for n in names if n and len(n.strip()) >= 5 and re.fullmatch(r"[A-Za-z][A-Za-z \-']+", n.strip())
            and n.strip().lower() not in SALT_WORDS}

ALL_NAMES = sorted({n for it in wd if it['label'] for n in item_names(it)}, key=len, reverse=True)

def class_members(prefixes):
    out = {}
    for code in sorted(by_code):
        if any(code.startswith(p) for p in prefixes.split('|')):
            for it in by_code[code]:
                for n in item_names(it):
                    out.setdefault(n, (code, it))
    return out

_spans = {}
def covered_spans(low):
    """spans of every ingredient name in the text, to drop a mention that is part of a longer name"""
    if low not in _spans:
        sp = []
        for g in ALL_NAMES:
            k = low.find(g)
            while k != -1:
                e = k + len(g)
                if (k == 0 or not low[k - 1].isalpha()) and (e == len(low) or not low[e].isalpha()):
                    sp.append((k, e, g))
                k = low.find(g, k + 1)
        _spans[low] = sp
    return _spans[low]

def first_named(text, members):
    best = None
    low = text.lower()
    spans = covered_spans(low)
    for n, (code, it) in members.items():
        for m in re.finditer(r'(?<![a-z])' + re.escape(n) + r'(?![a-z])', low):
            s0, e0 = m.start(), m.end()
            # skip a mention inside a longer name of an ingredient outside the class
            if any(k <= s0 and e0 <= e and (e - k) > (e0 - s0) and g not in members for k, e, g in spans):
                continue
            # skip a name the source states is excluded from the class
            if re.search(r'(excluding|except|other than|not)\W+$', low[max(0, s0 - 30):s0]):
                continue
            if best is None or s0 < best[0]:
                best = (s0, code, it)
            break
    return best

def resolve_side(c, side):
    name, kind, ctx = c[side], c[side + 'k'], c[side + 'c']
    if kind == 'i':
        n, code, ref = ingredient(name, ctx)
        return n, code, 'ingredient', 'ingredient named in source', ref
    members = class_members(ctx)
    hit = first_named(row_text(c['src'], c['table'], c['row']), members)
    if hit:
        return display(hit[2]), hit[1], 'class', 'class: ingredient named first (same table row)', 'Wikidata'
    hit = first_named(body_text(c['src']), members)
    if hit:
        return display(hit[2]), hit[1], 'class', 'class: ingredient named first (source text)', 'Wikidata'
    code = sorted(members.values(), key=lambda v: v[0])[0][0] if members else None
    if code is None: raise SystemExit(f'empty class {ctx}')
    return display(code_item(code)), code, 'class', 'class: lowest ATC code in class', 'Wikidata'

cands, pairs = [], {}
for i, c in enumerate(ROWS, 1):
    rec = dict(cand_id=f'C{i:03d}', source_id=c['src'],
               locator=f"{c['table'].title()}, row {c['row']} ({c['label']})",
               a_as_named=c['a'], a_named_as='ingredient' if c['ak'] == 'i' else 'class', a_atc_class=c['ac'],
               adverse_event=c['ev'], b_as_named=c['b'], b_named_as='ingredient' if c['bk'] == 'i' else 'class',
               b_atc_class=c['bc'], association=c['assoc'], decision='include' if c['dec'] == 'in' else 'exclude',
               reason=c['reason'], drug_a='', atc_a='', drug_b='', atc_b='', rule_applied='')
    if c['dec'] == 'in':
        a = resolve_side(c, 'a'); b = resolve_side(c, 'b')
        rule = f'A: {a[3]}; B: {b[3]}'
        rec.update(drug_a=a[0], atc_a=a[1], drug_b=b[0], atc_b=b[1], rule_applied=rule)
        key = (a[0].lower(), b[0].lower())
        p = pairs.setdefault(key, dict(drug_a=a[0], atc_a=a[1], drug_b=b[0], atc_b=b[1], events=[], a_named_as=a[2],
                                       b_named_as=b[2], class_a_label=(f"{c['a']} ({c['ac']})" if a[2] == 'class' else a[1][:5]),
                                       class_b_label=(f"{c['b']} ({c['bc']})" if b[2] == 'class' else b[1][:5]),
                                       rule_applied=rule, sources=[], locators=[], atc_ref=sorted({a[4], b[4]})))
        if c['ev'] not in p['events']: p['events'].append(c['ev'])
        if c['src'] not in p['sources']: p['sources'].append(c['src'])
        p['locators'].append(f"{c['src']}: {rec['locator']}")
    cands.append(rec)

with open(f'{OUT}/positive_candidates.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(cands[0])); w.writeheader(); w.writerows(cands)
cols = ['pair_id', 'drug_a', 'atc_a', 'adverse_event', 'drug_b', 'atc_b', 'a_named_as', 'b_named_as', 'class_a_label',
        'class_b_label', 'n_sources', 'sources', 'locators', 'rule_applied', 'atc_reference']
with open(f'{OUT}/positive_pairs.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(cols)
    for n, key in enumerate(sorted(pairs), 1):
        p = pairs[key]
        w.writerow([f'P{n:03d}', p['drug_a'], p['atc_a'], ' / '.join(p['events']), p['drug_b'], p['atc_b'], p['a_named_as'],
                    p['b_named_as'], p['class_a_label'], p['class_b_label'], len(p['sources']), ';'.join(p['sources']),
                    ';'.join(p['locators']), p['rule_applied'], ';'.join(p['atc_ref'])])
print('candidates', len(cands), 'included rows', sum(r['decision'] == 'include' for r in cands), 'pairs', len(pairs))

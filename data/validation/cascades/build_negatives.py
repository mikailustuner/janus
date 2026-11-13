"""Build the negative pairs of the cascade reference set (protocol section 3.2).

For every positive pair (A, B) two negatives (A, B') are drawn. B' is drawn uniformly from the WHO ATC
ingredient codes in the Wikidata snapshot that share B's first ATC level and differ from B at the third
level. B' is drawn again when:
  (a) an adverse event listed for A in OnSIDES appears in the indications section of a US label of B'
      (a possible cascade);
  (b) (A, B') is a positive pair;
and, as recorded judgement calls, when B' is A or B, when (A, B') was already drawn, or when no
single-ingredient US label of B' is found (rule (a) cannot be checked).

Inputs are open data: OnSIDES v3.1.1 (CC BY 4.0), Wikidata (CC0) and openFDA drug labels (CC0).
US label indications are read from LABEL_CACHE; with --fetch, names missing from the cache are looked up
in the openFDA label API and added to it. The committed cache makes a rerun deterministic and offline.

usage:
  uv run --no-project --with pyarrow python data/validation/cascades/build_negatives.py \
      --positives data/validation/cascades/positive_pairs.csv \
      --wikidata DIR_WITH_wikidata_ingredients_rows.parquet \
      --onsides DIR_WITH_onsides_parquet_files \
      --label-cache data/validation/cascades/us_label_indications.json \
      --out data/validation/cascades/negative_pairs.csv [--fetch]
"""
import argparse, csv, json, random, re, sys, time, urllib.parse, urllib.request

import pyarrow.parquet as pq

SEED = 20261113
DRAWS_PER_PAIR = 2
MAX_DRAWS = 200
LABELS_PER_DRUG = 5
OPENFDA = 'https://api.fda.gov/drug/label.json'
# names used in the reference set -> OnSIDES ingredient name
ONSIDES_SYNONYMS = {'valproic acid': 'valproate', 'insulin (human)': 'insulin, regular, human'}


def display(label):
    return re.sub(r'^((\([^)]*\)\W?)+|rac-)', '', label).lower()


def load_atc_pool(wikidata_dir):
    """code -> (name, rxcuis) for single-ingredient 7-character ATC codes."""
    pool = {}
    for row in pq.read_table(f'{wikidata_dir}/rows.parquet').to_pylist():
        label = row['label_en']
        if not label: continue
        for code in row['atc_codes'] or []:
            if len(code) != 7 or not code[5:].isdigit(): continue
            if '/' in label or ' and ' in label or int(code[5:]) >= 50: continue  # combinations
            cand = (label[:1].isupper(), not row['rxcuis'], len(label), label)
            if code not in pool or cand < pool[code][0]:
                pool[code] = (cand, display(label), list(row['rxcuis'] or []))
    return {c: (v[1], v[2]) for c, v in sorted(pool.items())}


def load_onsides(onsides_dir):
    """rxnorm ingredient id -> set of lower-case MedDRA term names, from single-ingredient labels."""
    terms = {r['meddra_id']: r['name'].lower() for r in pq.read_table(f'{onsides_dir}/meddra.parquet').to_pylist()}
    names = {}
    for r in pq.read_table(f'{onsides_dir}/ingredients.parquet').to_pylist():
        names.setdefault(r['name'].lower(), r['rxnorm_id'])
    effects = {}
    t = pq.read_table(f'{onsides_dir}/rows.parquet', columns=['ingredient_ids', 'effects'])
    for ids, eff in zip(t.column('ingredient_ids').to_pylist(), t.column('effects').to_pylist()):
        if len(ids) != 1: continue
        s = effects.setdefault(ids[0], set())
        s.update(terms[e['meddra_id']] for e in eff if e['meddra_id'] in terms)
    return names, effects


def fetch_label(name):
    q = urllib.parse.urlencode({'search': f'openfda.generic_name:"{name}"', 'limit': 25})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(f'{OPENFDA}?{q}', timeout=30) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429: return {'name': name, 'set_ids': [], 'indications': ''}  # not found / bad query
            time.sleep(5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5 * (attempt + 1))
    else:
        raise SystemExit(f'openFDA lookup failed for {name}')
    keep = []
    for res in data.get('results', []):
        gn = res.get('openfda', {}).get('generic_name', [])
        if len(gn) != 1 or re.search(r'\band\b|,|/', gn[0], re.I): continue  # single-ingredient labels only
        if not re.search(r'(?<![a-z])' + re.escape(name) + r'(?![a-z])', gn[0].lower()): continue
        text = ' '.join(res.get('indications_and_usage', []))
        if text: keep.append((res['set_id'], text))
    keep = sorted(keep)[:LABELS_PER_DRUG]
    time.sleep(0.3)
    return {'name': name, 'set_ids': [k[0] for k in keep], 'indications': ' '.join(k[1] for k in keep)}


def main():
    ap = argparse.ArgumentParser()
    for a in ('--positives', '--wikidata', '--onsides', '--label-cache', '--out'):
        ap.add_argument(a, required=True)
    ap.add_argument('--fetch', action='store_true', help='look up names missing from the cache in openFDA')
    args = ap.parse_args()

    positives = list(csv.DictReader(open(args.positives, newline='')))
    pos_names = {(p['drug_a'].lower(), p['drug_b'].lower()) for p in positives}
    pos_codes = {(p['atc_a'], p['atc_b']) for p in positives}
    pool = load_atc_pool(args.wikidata)
    codes = sorted(pool)
    onsides_names, onsides_effects = load_onsides(args.onsides)
    try:
        cache = json.load(open(args.label_cache))
    except FileNotFoundError:
        cache = {'source': OPENFDA, 'licence': 'CC0 1.0', 'retrieved': time.strftime('%Y-%m-%d'), 'labels': {}}

    def indications(name):
        if name not in cache['labels']:
            if not args.fetch:
                raise SystemExit(f'{name} not in label cache; rerun with --fetch')
            cache['labels'][name] = fetch_label(name)
            with open(args.label_cache, 'w') as f:  # keep what was fetched if a later lookup fails
                json.dump(cache, f, indent=1, sort_keys=True, ensure_ascii=False)
        return cache['labels'][name]['indications'].lower()

    def a_events(drug, atc):
        d = ONSIDES_SYNONYMS.get(drug.lower(), drug.lower())
        rxs = [rx for n, rx in onsides_names.items() if n == d or n.startswith(d + ' ')]  # salts, e.g. lithium carbonate
        rxs = rxs or pool.get(atc, ('', []))[1]
        ev = set()
        for r in rxs: ev |= onsides_effects.get(r, set())
        return ev

    rng = random.Random(SEED)
    out, drawn, n = [], set(), 0
    for p in sorted(positives, key=lambda r: r['pair_id']):
        a, atc_a, atc_b = p['drug_a'], p['atc_a'], p['atc_b']
        events = sorted(a_events(a, atc_a))
        cands = [c for c in codes if c[0] == atc_b[0] and c[:4] != atc_b[:4]]
        for _ in range(DRAWS_PER_PAIR):
            reasons, chosen = [], None
            for draw in range(1, MAX_DRAWS + 1):
                code = rng.choice(cands)
                name = pool[code][0]
                if name == a.lower() or code == atc_a: reasons.append(f'{name}:same_as_a'); continue
                if name == p['drug_b'].lower(): reasons.append(f'{name}:same_as_b'); continue
                if (a.lower(), name) in pos_names or (atc_a, code) in pos_codes:
                    reasons.append(f'{name}:positive_pair'); continue
                if (a.lower(), name) in drawn: reasons.append(f'{name}:duplicate_negative'); continue
                text = indications(name)
                if not text: reasons.append(f'{name}:no_us_label'); continue
                hit = next((e for e in events if re.search(r'(?<![a-z])' + re.escape(e) + r'(?![a-z])', text)), None)
                if hit: reasons.append(f'{name}:a_event_is_indication({hit})'); continue
                chosen = (code, name, draw)
                break
            n += 1
            if chosen: drawn.add((a.lower(), chosen[1]))
            out.append({'neg_id': f'N{n:03d}', 'from_pair_id': p['pair_id'], 'drug_a': a, 'atc_a': atc_a,
                        'drug_b_prime': chosen[1] if chosen else '', 'atc_b_prime': chosen[0] if chosen else '',
                        'draws': chosen[2] if chosen else MAX_DRAWS, 'redraw_reasons': ';'.join(reasons),
                        'a_onsides_events': len(events)})
    with open(args.label_cache, 'w') as f:
        json.dump(cache, f, indent=1, sort_keys=True, ensure_ascii=False)
    with open(args.out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    missing = sum(1 for r in out if not r['drug_b_prime'])
    print(f'negatives: {len(out)} rows, {missing} without a valid draw after {MAX_DRAWS} draws', file=sys.stderr)


if __name__ == '__main__':
    main()

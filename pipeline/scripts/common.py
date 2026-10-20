import re, unicodedata, difflib
import pandas as pd
import geopandas as gpd

ROOT = __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__)))  # .../pipeline
RAW = f'{ROOT}/raw'
GB = f'{RAW}/gb'
DATA = f'{ROOT}/data'
SUB = f'{DATA}/sub'

STOP = {'municipality', 'municipal', 'city', 'district', 'province', 'region', 'county', 'state',
        'oblast', 'canton', 'zone', 'governorate', 'prefecture', 'department', 'of', 'the', 'autonomous',
        'okrug', 'krai', 'republic', 'territory', 'capital', 'special', 'division', 'opstina', 'distrikt',
        'regione', 'kanton', 'provincia', 'reg', 'dist', 'mun', 'prov', 'metropolis', 'metropolitan'}


def fold(s):
    s = str(s)
    s = s.replace('ł', 'l').replace('Ł', 'L').replace('đ', 'dj').replace('Đ', 'Dj').replace('ə', 'e')
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s


def norm(s):
    s = fold(s).lower()
    s = re.sub(r"[`'’\.\(\)]", '', s)
    toks = re.split(r'[^a-z0-9]+', s)
    toks = [t for t in toks if t and t not in STOP]
    return ''.join(toks)


def match_names(geo_names, data_names, aliases=None, cutoff=0.86, verbose=True, label=''):
    """Return dict geo_name -> data_name."""
    aliases = aliases or {}
    dn = {norm(d): d for d in data_names}
    out = {}
    for g in geo_names:
        if g in aliases:
            a = aliases[g]
            if a is None:
                continue
            out[g] = a
            continue
        k = norm(g)
        if k in dn:
            out[g] = dn[k]
            continue
        cand = difflib.get_close_matches(k, list(dn.keys()), n=1, cutoff=cutoff)
        if cand:
            out[g] = dn[cand[0]]
    if verbose:
        used = set(out.values())
        miss_g = [g for g in geo_names if g not in out and aliases.get(g, 1) is not None]
        miss_d = [d for d in data_names if d not in used]
        if miss_g or miss_d:
            print(f'[{label}] geo unmatched ({len(miss_g)}):', miss_g[:40])
            print(f'[{label}] data unused ({len(miss_d)}):', miss_d[:40])
    return out


def read_sub(name):
    df = pd.read_csv(f'{SUB}/{name}.csv')
    if 'pct' not in df.columns:
        df['pct'] = df['muslims'] / df['total'] * 100
    return df

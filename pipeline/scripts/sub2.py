"""Loaders for the finer 2026-10 datasets: Australia LGAs, Canada economic regions, Indonesia regencies."""
import sys, re, difflib, warnings
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, geopandas as gpd
from shapely import make_valid
from common import RAW, DATA

S2 = f'{DATA}/sub2'
GB = f'{RAW}/gb'


def _gb(code):
    g = gpd.read_file(f'{GB}/geoBoundaries-{code}_simplified.geojson')
    g['geometry'] = g.geometry.apply(make_valid)
    return g


def _k(s):
    return re.sub(r'[^a-z]', '', s.lower())


def _inherit(g, prov_col):
    """Units without data (post-census splits, lakes) join the touching data unit of the same province
    with which they share the longest border (else the nearest one)."""
    gm = g.to_crs(3857)
    miss = gm.index[gm.unit.isna()]
    for i in miss:
        geom = gm.at[i, 'geometry']
        cand = gm[gm.unit.notna() & (gm[prov_col] == gm.at[i, prov_col])]
        if not len(cand):
            cand = gm[gm.unit.notna()]
        sh = cand.geometry.apply(lambda c: geom.boundary.intersection(c.boundary).length if geom.touches(c) or geom.intersects(c) else 0)
        j = sh.idxmax() if sh.max() > 0 else cand.geometry.distance(geom).idxmin()
        for c in ('unit', 'pct', 'muslims'):
            g.at[i, c] = g.at[j, c]
        g.at[i, 'inherit'] = g.at[j, 'gname']
    return g


# ------------------------------------------------------------------ Australia, LGAs (ABS Census 2021, G14)
def australia():
    rows = [l.split(';') for l in open(f'{S2}/AUS_LGA.txt').read().strip().splitlines()]
    d = pd.DataFrame(rows, columns=['code', 'name', 'muslims', 'total'])
    d[['muslims', 'total']] = d[['muslims', 'total']].astype(float)
    d['pct'] = d.muslims / d.total * 100
    g = _gb('AUS-ADM2')
    g['gname'] = g.shapeName

    def kk(s):
        s = re.sub(r' (Regional|Shire|City|Council|Municipality|Town|Rural)$', '', s)
        return _k(s)
    dk = {kk(n): i for i, n in enumerate(d.name)}
    dk2 = {_k(re.sub(r'\s*\(.*\)', '', n)): i for i, n in enumerate(d.name)}
    idx, used = [], set()
    for n in g.gname:
        i = dk.get(kk(n))
        if i is None:
            i = dk2.get(_k(re.sub(r'\s*\(.*\)', '', n)))
        if i is None:
            m = difflib.get_close_matches(kk(n), list(dk), n=1, cutoff=0.85)
            i = dk[m[0]] if m else None
        idx.append(i)
    g['row'] = idx
    print('AUS: matched', g.row.notna().sum(), 'of', len(g), '| unmatched:', g.gname[g.row.isna()].tolist())
    unused = set(range(len(d))) - set(g.row.dropna().astype(int))
    print('AUS: data rows without a shape:', d.name.iloc[sorted(unused)].tolist())
    g['unit'] = [d.name.iloc[int(i)] if i == i and i is not None else None for i in g.row]
    g['pct'] = [d.pct.iloc[int(i)] if i == i and i is not None else np.nan for i in g.row]
    g['muslims'] = [d.muslims.iloc[int(i)] if i == i and i is not None else np.nan for i in g.row]
    g['prov'] = 'AUS'
    g['inherit'] = None
    if g.unit.isna().any():
        g = _inherit(g, 'prov')
    g['unit'] = g.unit.str.replace(r' \((NSW|Vic\.|Qld|SA|WA|Tas\.|NT|ACT)\)$', '', regex=True)
    g['dflt'] = False
    return g[['gname', 'unit', 'pct', 'muslims', 'dflt', 'geometry']]


# ------------------------------------------------------------------ Canada, economic regions (StatCan 2021)
def canada():
    v = {}
    for x in open(f'{S2}/CAN_ER.txt').read().strip().split('|'):
        c, m, t = x.split(';'); v[c] = (float(m), float(t))
    names = dict(x.split(';', 1) for x in open(f'{S2}/CAN_ER_names.txt').read().strip().split('|'))
    codes = sorted(v)
    g = _gb('CAN-ADM2')
    assert len(g) == len(codes), (len(g), len(codes))
    g['code'] = codes
    g['gname'] = g.shapeName
    bad = []
    for n, c in zip(g.gname, g.code):
        a, b = _k(n.split(' / ')[0].rstrip('*')), _k(names.get(c, ''))
        if not (a[:6] == b[:6] or difflib.SequenceMatcher(None, a, b).ratio() > 0.6):
            bad.append((n, c, names.get(c)))
    print('CAN: name/code disagreements:', bad)
    g['muslims'] = [v[c][0] for c in g.code]
    g['pct'] = [v[c][0] / v[c][1] * 100 for c in g.code]
    def nm(c, n):
        if ' / ' in n:
            return n.split(' / ')[0]
        if n.endswith('*'):
            return names.get(c, n.rstrip('*'))
        return n
    g['unit'] = [nm(c, n).replace('--', '–') for c, n in zip(g.code, g.gname)]
    g['dflt'] = False
    return g[['gname', 'unit', 'pct', 'muslims', 'dflt', 'geometry']]


# ------------------------------------------------------------------ Indonesia, regencies & cities (BPS SP2010)
IDN_PROV = {'Aceh': 11, 'North Sumatra': 12, 'West Sumatra': 13, 'Riau': 14, 'Jambi': 15, 'South Sumatra': 16,
            'Bengkulu': 17, 'Lampung': 18, 'Bangka-Belitung Islands': 19, 'Riau Islands': 21,
            'Jakarta Special Capital Region': 31, 'West Java': 32, 'Central Java': 33,
            'Special Region of Yogyakarta': 34, 'East Java': 35, 'Banten': 36, 'Bali': 51, 'West Nusa Tenggara': 52,
            'East Nusa Tenggara': 53, 'West Kalimantan': 61, 'Central Kalimantan': 62, 'South Kalimantan': 63,
            'East Kalimantan': 64, 'North Kalimantan': 64, 'North Sulawesi': 71, 'Central Sulawesi': 72,
            'South Sulawesi': 73, 'Southeast Sulawesi': 74, 'Gorontalo': 75, 'West Sulawesi': 76, 'Maluku': 81,
            'North Maluku': 82, 'West Papua': 91, 'Papua': 94}


def indonesia():
    rows = []
    for x in open(f'{S2}/IDN_SP2010_kab.txt').read().strip().split('|'):
        a, m, t = x.split(';')
        code, name = a.split('. ', 1)
        rows.append((int(code), name.strip(), float(m), float(t)))
    d = pd.DataFrame(rows, columns=['code', 'name', 'muslims', 'total'])
    d['prov'] = d.code // 100
    d['kota'] = (d.code % 100) >= 71
    d['key'] = d.name.map(_k)
    g = _gb('IDN-ADM2'); a1 = _gb('IDN-ADM1')
    g['gname'] = g.shapeName
    pt = gpd.GeoDataFrame(g[['gname']], geometry=g.geometry.representative_point(), crs=4326)
    j = gpd.sjoin(pt, a1[['shapeName', 'geometry']], predicate='within', how='left')
    j = j[~j.index.duplicated()]
    g['prov_name'] = j.shapeName
    if g.prov_name.isna().any():   # islands whose point misses the simplified province outline
        miss = g.prov_name.isna()
        nn = gpd.sjoin_nearest(pt[miss].to_crs(3857), a1[['shapeName', 'geometry']].to_crs(3857))
        nn = nn[~nn.index.duplicated()]
        g.loc[miss, 'prov_name'] = nn.shapeName
    g['prov'] = g.prov_name.map(IDN_PROV)
    ALIAS = {'Siau Tagulandang Biaro': 'SIAU TAGULANDANG BIARO', 'Pangkajene Dan Kepulauan': 'PANGKAJENE KEPULAUAN',
             'Toli-Toli': 'TOLI-TOLI', 'Kota Banjar Baru': 'BANJAR BARU', 'Kota Tidore Kepulauan': 'TIDORE KEPULAUAN',
             'Labuhan Batu Selatan': 'LABUHAN BATU SELATAN', 'Kota Pangkal Pinang': 'PANGKAL PINANG',
             'Mempawah': 'PONTIANAK', 'Kepulauan Selayar': 'SELAYAR'}
    g.loc[g.gname == 'Kepulauan Seribu', 'prov'] = 31
    idx = []
    for n, p in zip(g.gname, g.prov):
        kota = n.startswith('Kota ') and n != 'Kota Baru'
        base = n[5:] if kota else n
        cand = d[(d.prov == p) & (d.kota == kota)]
        key = _k(ALIAS.get(n, base))
        hit = cand.index[cand.key == key]
        if not len(hit):
            m = difflib.get_close_matches(key, cand.key.tolist(), n=1, cutoff=0.82)
            hit = cand.index[cand.key == m[0]] if m else []
        idx.append(hit[0] if len(hit) else None)
    g['row'] = idx
    dup = g.row.dropna()[g.row.dropna().duplicated(keep=False)]
    print('IDN: matched', g.row.notna().sum(), 'of', len(g), '| duplicate matches:',
          g.loc[dup.index, 'gname'].tolist())
    print('IDN: unmatched shapes:', g.gname[g.row.isna()].tolist())
    unused = sorted(set(d.index) - set(g.row.dropna().astype(int)))
    print('IDN: data rows without a shape:', d.loc[unused, ['code', 'name']].values.tolist())

    def title(r):
        nm = r['name'].title().replace(' Dan ', ' dan ')
        return ('Kota ' + nm) if r.kota else nm
    g['unit'] = [title(d.loc[int(i)]) if i == i and i is not None else None for i in g.row]
    g['pct'] = [d.muslims[int(i)] / d.total[int(i)] * 100 if i == i and i is not None else np.nan for i in g.row]
    g['muslims'] = [d.muslims[int(i)] if i == i and i is not None else np.nan for i in g.row]
    g['inherit'] = None
    # regencies created after 2010 take the value of the regency they were split from
    PARENT = {'Banggai Laut': 'Banggai Kepulauan', 'Buton Selatan': 'Buton', 'Buton Tengah': 'Buton',
              'Kolaka Timur': 'Kolaka', 'Konawe Kepulauan': 'Konawe', 'Mahakam Hulu': 'Kutai Barat', 'Malaka': 'Belu',
              'Mamuju Tengah': 'Mamuju', 'Manokwari Selatan': 'Manokwari', 'Morowali Utara': 'Morowali',
              'Muna Barat': 'Muna', 'Musi Rawas Utara': 'Musi Rawas', 'Pangandaran': 'Ciamis',
              'Pegunungan Arfak': 'Manokwari', 'Penukal Abab Lematang Ilir': 'Muara Enim',
              'Pesisir Barat': 'Lampung Barat', 'Pulau Taliabu': 'Kepulauan Sula'}
    for ch, par in PARENT.items():
        i = g.index[g.gname == ch]; j = g.index[g.gname == par]
        assert len(i) == 1 and len(j) == 1, (ch, par)
        for c in ('unit', 'pct', 'muslims'):
            g.at[i[0], c] = g.at[j[0], c]
        g.at[i[0], 'inherit'] = par
    g = _inherit(g, 'prov')
    inh = g[g.inherit.notna()]
    print('IDN: inherited:', dict(zip(inh.gname, inh.inherit)))
    g['dflt'] = False
    return g[['gname', 'unit', 'pct', 'muslims', 'dflt', 'geometry']]


if __name__ == '__main__':
    for f in (australia, canada, indonesia):
        r = f()
        print(f.__name__, len(r), 'units; muslims', int(r.drop_duplicates('unit').muslims.sum()))

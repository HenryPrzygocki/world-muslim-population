"""Export the map data for the interactive web version."""
import sys, json, math, warnings
sys.path.insert(0, __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'pipeline', 'scripts'))
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, geopandas as gpd
from shapely.ops import polylabel, unary_union
from shapely.geometry import MultiPolygon
from shapely import make_valid
from common import DATA, RAW
from mapkit import clean_unit, cluster_communities, load_communities

OUT = __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), 'build')
import os
os.makedirs(OUT, exist_ok=True)
EE = '+proj=eqearth +lon_0=11 +datum=WGS84 +units=m +no_defs'

nat = gpd.read_file(f'{DATA}/units_national.gpkg')
sub = gpd.read_file(f'{DATA}/units_sub.gpkg')
reg = pd.read_csv(f'{DATA}/sources_registry.csv')

# ---- sources table
srcs = []
src_idx = {}
def sidx(s):
    s = str(s) if s == s else ''
    if s not in src_idx:
        src_idx[s] = len(srcs); srcs.append(s)
    return src_idx[s]
year_of = dict(zip(reg.iso3, reg.year.astype(str)))


def anchor(g_ll):
    """polylabel of the largest part, computed in Equal Earth metres; returns lon, lat, radius_km."""
    g = gpd.GeoSeries([g_ll], crs=4326).to_crs(EE).iloc[0]
    parts = [p for p in getattr(g, 'geoms', [g]) if p.geom_type == 'Polygon']
    if not parts:
        return None
    poly = max(parts, key=lambda p: p.area)
    try:
        c = polylabel(poly, tolerance=max(300, math.sqrt(poly.area) / 60))
    except Exception:
        c = poly.representative_point()
    r = poly.exterior.distance(c)
    for h in poly.interiors:
        r = min(r, h.distance(c))
    ll = gpd.GeoSeries([c], crs=EE).to_crs(4326).iloc[0]
    return round(ll.x, 4), round(ll.y, 4), round(r / 1000, 1)


# ---- national map units
natc = nat[nat.geometry.notna()].copy()
recs = []
for r in natc.itertuples():
    recs.append({'i': len(recs), 'n': r.ADMIN, 'c': r.ADM0_A3, 'p': None if r.pct != r.pct else round(float(r.pct), 2),
                 'm': None if r.muslims != r.muslims else int(r.muslims), 's': sidx(r.src), 'geometry': r.geometry})
g = gpd.GeoDataFrame(recs, crs=4326)
g.to_file(f'{OUT}/countries.geojson', driver='GeoJSON')

# ---- data basis of each unit: c census/register, e ethnicity-based, m modelled estimate, f fallback value
ESTIMATE = {'NGA', 'CIV', 'CMR', 'TCD', 'TGO', 'SLE', 'LBR', 'ERI', 'CAF', 'MOZ', 'TZA', 'MDG', 'EGY', 'SEN', 'SUR',
            'FRA', 'DEU', 'BEL', 'GRC'}
ETHNIC = {'RUS', 'CHN', 'KGZ', 'MNG', 'KOS', 'UAOCC'}
GHA_NEW = {'Ahafo', 'Bono', 'Bono East', 'North East', 'Oti', 'Savannah', 'Western North'}
BEN_CENSUS = {'Alibori', 'Donga', 'Borgou', 'Couffo'}
def basis(iso, unit, src, dflt):
    if dflt: return 'f'
    if 'ESTIMATE' in str(src) or iso in ESTIMATE: return 'm'
    if iso in ETHNIC: return 'e'
    if (iso == 'GHA' and unit in GHA_NEW) or (iso == 'BEN' and unit not in BEN_CENSUS) or \
       (iso == 'ROU' and unit == 'Tulcea') or (iso == 'MMR' and unit == 'Rakhine'): return 'm'
    return 'c'

# ---- parent province of each unit (for cards and search), from Natural Earth admin-1
A1 = gpd.read_file(f'{RAW}/ne_10m_admin_1_states_provinces.geojson')[['adm0_a3', 'name', 'name_en', 'name_alt', 'region', 'geometry']]
PARENT_FIELD = {'IND': 'name', 'PAK': 'name_en', 'IDN': 'name_en', 'BGD': 'name', 'CAN': 'name', 'AUS': 'name',
                'CHN': 'name', 'ETH': 'name', 'GRC': 'name', 'ESP': 'region', 'GBR': 'region'}
A1p = A1[A1.adm0_a3.isin(list(PARENT_FIELD))].copy()
A1p['parent'] = [r[PARENT_FIELD[r.adm0_a3]] for _, r in A1p.iterrows()]
A1p['parent'] = A1p.parent.replace({'Sind': 'Sindh', 'K.P.': 'Khyber Pakhtunkhwa'})
fold = lambda x: ''.join(ch for ch in str(x).lower() if ch.isalnum())

# ---- subnational units
recs = []
for r in sub.itertuples():
    if r.geometry is None or r.geometry.is_empty:
        continue
    geom = r.geometry
    parts = [q for q in getattr(geom, 'geoms', [geom]) if q.geom_type == 'Polygon']
    if len(parts) > 1:      # drop coastal slivers / tiny islets (< ~2 km²); the national fill still covers them
        big = max(parts, key=lambda q: q.area)
        keep = [q for q in parts if q is big or q.area * 111 ** 2 * math.cos(math.radians(q.centroid.y)) > 2]
        geom = MultiPolygon(keep) if len(keep) > 1 else keep[0]
    a = anchor(r.geometry) if not r.dflt else None
    nm = clean_unit(r.unit) if r.unit else ''
    par = None
    if a and r.iso in PARENT_FIELD:
        hitp = A1p[(A1p.adm0_a3 == r.iso) & A1p.geometry.contains(gpd.points_from_xy([a[0]], [a[1]])[0])]
        if len(hitp) and isinstance(hitp.parent.iloc[0], str) and fold(hitp.parent.iloc[0]) != fold(nm):
            par = hitp.parent.iloc[0]
    recs.append({'i': len(recs), 'n': nm, 'r': par, 'q': basis(r.iso, nm, r.src, r.dflt), 'c': r.iso, 'p': round(float(r.pct), 2),
                 'm': None if r.muslims != r.muslims else int(round(r.muslims)), 'e': int(bool(r.cnt_est)),
                 'd': int(bool(r.dflt)), 's': sidx(r.src),
                 'lx': a[0] if a else None, 'ly': a[1] if a else None, 'lr': a[2] if a else None,
                 'geometry': geom})
g = gpd.GeoDataFrame(recs, crs=4326)
from shapely.geometry.polygon import orient
def _norm(q):
    q = make_valid(q)
    ps = [p for p in getattr(q, 'geoms', [q]) if p.geom_type == 'Polygon'] + \
         [pp for p in getattr(q, 'geoms', []) if p.geom_type == 'MultiPolygon' for pp in p.geoms]
    ps = [orient(p, 1.0) for p in ps]
    return MultiPolygon(ps) if len(ps) > 1 else ps[0]
g['geometry'] = g.geometry.apply(_norm)
g.to_file(f'{OUT}/units.geojson', driver='GeoJSON')
print('units', len(g))

# ---- lines and lakes
big = set()
a = nat.to_crs(EE).assign(a=lambda d: d.geometry.area / 1e6).groupby('ADM0_A3').a.sum()
big = (set(a[a >= 1.2e6].index) - set(sub.iso)) | {'PRY'}
a1 = gpd.read_file(f'{RAW}/ne_10m_admin_1_states_provinces_lines.geojson')
a1 = a1[a1.ADM0_A3.isin(big)][['geometry']]
a1.to_file(f'{OUT}/provlines.geojson', driver='GeoJSON')
dl = gpd.read_file(f'{RAW}/ne_10m_admin_0_boundary_lines_disputed_areas.geojson')[['geometry']]
dl.to_file(f'{OUT}/disputed.geojson', driver='GeoJSON')
lk = gpd.read_file(f'{RAW}/ne_10m_lakes.geojson')
lk = lk[lk.scalerank <= 5][['geometry']]
lk.to_file(f'{OUT}/lakes.geojson', driver='GeoJSON')

# ---- country labels
c0 = gpd.read_file(f'{RAW}/ne_10m_admin_0_countries.geojson')
from world import RENAME, LABEL_POS
natd = nat.dissolve(by='ADMIN', aggfunc={'pct': 'first', 'muslims': 'first', 'ADM0_A3': 'first'})
area = natd.to_crs(EE).geometry.area / 1e6
subiso = set(sub.iso) - {'ROU'}
labels = []
SKIP = {'Antarctica', 'Bir Tawil', 'Brazilian Island', 'Siachen Glacier', 'Southern Patagonian Ice Field',
        'Cyprus No Mans Area', 'Baykonur Cosmodrome', 'Dhekelia Sovereign Base Area', 'Akrotiri Sovereign Base Area',
        'US Naval Base Guantanamo Bay', 'Scarborough Reef', 'Serranilla Bank', 'Bajo Nuevo Bank (Petrel Is.)',
        'Spratly Islands', 'Coral Sea Islands', 'Ashmore and Cartier Islands', 'Clipperton Island',
        'Indian Ocean Territories', 'Heard Island and McDonald Islands'}
for adm, r in natd.iterrows():
    if adm in SKIP:
        continue
    cr = c0[c0.ADMIN == adm]
    if adm in LABEL_POS:
        x, y = LABEL_POS[adm]
    elif len(cr):
        x, y = float(cr.LABEL_X.iloc[0]), float(cr.LABEL_Y.iloc[0])
    else:
        p = r.geometry.representative_point(); x, y = p.x, p.y
    name = RENAME.get(adm, (cr.NAME.iloc[0] if len(cr) else adm).upper())
    labels.append({'n': name, 'full': adm, 'c': r.ADM0_A3, 'x': round(x, 3), 'y': round(y, 3), 'a': round(float(area[adm])),
                   'p': None if r.pct != r.pct else round(float(r.pct), 2),
                   'm': None if r.muslims != r.muslims else int(r.muslims), 'sub': int(r.ADM0_A3 in subiso)})

# ---- communities
com = load_communities()
def cl_json(R):
    cl = cluster_communities(com, R)
    return [{'n': r.name, 'x': round(r.lon, 3), 'y': round(r.lat, 3), 'm': int(r.muslims), 'b': r.basis,
             'k': r.n, 'mem': r.members, 'c': r.country} for r in cl.itertuples()]
us = pd.read_csv(f'{DATA}/usa_metros_arda2020.csv')
metros = [{'n': r.city, 'full': r.name, 'x': round(r.lon, 3), 'y': round(r.lat, 3), 'm': int(r.adherents),
           'k': int(r.congregations)} for r in us.itertuples() if r.adherents >= 300]

# ---- short country names, search regions (provinces), cities, country totals, sources table, CSV
cs = gpd.read_file(f'{RAW}/ne_10m_admin_0_countries.geojson', ignore_geometry=True)
short = dict(zip(cs.ADM0_A3, cs.NAME_LONG))
short.update({'PSX': 'Palestine', 'KOS': 'Kosovo', 'SOL': 'Somaliland', 'CYN': 'Northern Cyprus', 'TWN': 'Taiwan',
              'SAH': 'Western Sahara', 'USA': 'United States', 'GBR': 'United Kingdom', 'COD': 'DR Congo',
              'COG': 'Republic of the Congo', 'CIV': "Côte d'Ivoire", 'CZE': 'Czechia', 'MKD': 'North Macedonia',
              'SWZ': 'Eswatini', 'TLS': 'Timor-Leste', 'CPV': 'Cabo Verde', 'BHS': 'The Bahamas', 'GMB': 'The Gambia',
              'KOR': 'South Korea', 'PRK': 'North Korea', 'LAO': 'Laos', 'RUS': 'Russia', 'SRB': 'Serbia',
              'TZA': 'Tanzania', 'HKG': 'Hong Kong', 'MAC': 'Macau', 'UAOCC': 'Ukraine'})
for l in labels:
    l['short'] = short.get(l['c'], l['full'])
ug = g  # units as written
regions = []
for (iso, par), grp in A1p.groupby(['adm0_a3', 'parent']):
    if not isinstance(par, str) or not (ug[ug.c == iso].r == par).any():
        continue
    b = grp.total_bounds
    alts = set()
    for _, rr in grp.iterrows():
        for v in [rr['name'], rr['name_en']] + (str(rr['name_alt']).split('|') if isinstance(rr['name_alt'], str) else []):
            if isinstance(v, str) and v and fold(v) != fold(par): alts.add(v.strip())
    if len(grp) > 3: alts = set()          # a grouping field (e.g. Spanish community): its member names are not aliases
    regions.append({'n': par, 'alt': sorted(alts)[:6], 'c': iso, 'b': [round(float(v), 3) for v in b]})
# an alias that is the start of another region's name (e.g. "Jawa" for Jakarta) is ambiguous: drop it
for r in regions:
    others = [fold(x['n']) for x in regions if x is not r] + [fold(a) for x in regions if x is not r for a in x['alt']]
    r['alt'] = [a for a in r['alt'] if not any(o != fold(a) and o.startswith(fold(a)) for o in others)]
pp = gpd.read_file(f'{RAW}/ne_10m_populated_places_simple.geojson')
pp = pp[(pp.pop_max >= 750000) | (pp.adm0cap == 1)]
cities = []
for r in pp.itertuples():
    alt = {r.nameascii} - {r.name}
    if isinstance(r.namealt, str) and r.namealt: alt |= set(r.namealt.split('|'))
    cities.append({'n': r.name, 'alt': sorted(a for a in alt if a)[:4], 'x': round(r.longitude, 3), 'y': round(r.latitude, 3),
                   'pop': int(r.pop_max)})
# national totals as the sum of mapped areas (only where every area has a published count)
usum = {}
for iso, grp in ug.groupby('c'):
    if grp.m.isna().any() or (grp.q == 'm').any() or (grp.p <= 0).any() or (grp.e == 1).any():
        continue
    pop = (grp.m / grp.p * 100).sum()
    usum[iso] = {'m': int(grp.m.sum()), 'p': round(float(grp.m.sum() / pop * 100), 2), 'y': year_of.get(iso, '')}
cn = dict(zip(reg.iso3, reg.notes.fillna('')))
def rbasis(r):
    s_, n_ = str(r.source), str(r.notes)
    if 'ESTIMATE' in s_ or n_.startswith('Estimate'): return 'Modelled estimate'
    if 'Partly' in n_: return 'Census + estimate'
    if 'ethnic' in s_.lower(): return 'Census (ethnicity)'
    return 'Census / register'
regtab = [{'c': r.iso3, 'name': short.get(r.iso3, {'LAT': 'Latin America & Caribbean (circles)', 'PSE': 'Palestine'}.get(r.iso3, r.iso3)),
           'level': str(r.level), 'source': str(r.source).replace('ESTIMATE — ', '').replace('ESTIMATE ', ''),
           'year': str(r.year), 'basis': rbasis(r)} for r in reg.itertuples()]
regtab.sort(key=lambda d: d['name'])
# downloadable table of every unit
cn_short = lambda iso: short.get(iso, iso)
csv = ug.drop(columns='geometry').copy()
csv['country'] = csv.c.map(cn_short); csv['source'] = csv.s.map(lambda i: srcs[i]); csv['year'] = csv.c.map(year_of)
csv['basis'] = csv.q.map({'c': 'census/register', 'e': 'ethnicity-based', 'm': 'modelled estimate', 'f': 'fallback value'})
csv['unit'] = csv.n.where(csv.n != '', 'Rest of ' + csv.country)
csv = csv[['country', 'c', 'unit', 'r', 'p', 'm', 'e', 'basis', 'source', 'year']].rename(columns={
    'c': 'iso3', 'r': 'province', 'p': 'share_muslim_pct', 'm': 'muslims', 'e': 'count_is_share_x_population'})
csv.sort_values(['country', 'unit']).to_csv(f'{OUT}/units.csv', index=False)
com_drop = {'Trinidad & Tobago', 'Suriname', 'Guyana'}    # circles that only repeat a national total

extra = {'labels': labels, 'comW': cl_json(45), 'comR': cl_json(12), 'metros': metros, 'sources': srcs,
         'years': year_of, 'regsrc': dict(zip(reg.iso3, reg.source)),
         'regions': regions, 'cities': cities, 'usum': usum, 'reg': regtab, 'short': short}
extra['comW'] = [c for c in extra['comW'] if c['n'] not in com_drop]
extra['comR'] = [c for c in extra['comR'] if c['n'] not in com_drop]
json.dump(extra, open(f'{OUT}/extra.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('labels', len(labels), 'comW', len(extra['comW']), 'comR', len(extra['comR']), 'metros', len(metros), 'srcs', len(srcs))

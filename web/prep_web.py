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
    recs.append({'n': r.ADMIN, 'c': r.ADM0_A3, 'p': None if r.pct != r.pct else round(float(r.pct), 2),
                 'm': None if r.muslims != r.muslims else int(r.muslims), 's': sidx(r.src), 'geometry': r.geometry})
g = gpd.GeoDataFrame(recs, crs=4326)
g.to_file(f'{OUT}/countries.geojson', driver='GeoJSON')

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
    recs.append({'n': clean_unit(r.unit) if r.unit else '', 'c': r.iso, 'p': round(float(r.pct), 2),
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

extra = {'labels': labels, 'comW': cl_json(45), 'comR': cl_json(12), 'metros': metros, 'sources': srcs,
         'years': year_of, 'regsrc': dict(zip(reg.iso3, reg.source))}
json.dump(extra, open(f'{OUT}/extra.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('labels', len(labels), 'comW', len(extra['comW']), 'comR', len(extra['comR']), 'metros', len(metros), 'srcs', len(srcs))

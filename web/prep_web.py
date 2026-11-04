"""Export the map data for the interactive web version."""
import sys, json, math, warnings
sys.path.insert(0, __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'pipeline', 'scripts'))
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, geopandas as gpd
from shapely.ops import polylabel, unary_union
from shapely.geometry import MultiPolygon
from shapely import make_valid
from common import DATA, RAW
from mapkit import clean_unit, cluster_communities, load_communities, RENAME, LABEL_POS

OUT = __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), 'build')
import os
os.makedirs(OUT, exist_ok=True)
EE = '+proj=eqearth +lon_0=11 +datum=WGS84 +units=m +no_defs'

nat = gpd.read_file(f'{DATA}/units_national.gpkg')
sub = gpd.read_file(f'{DATA}/units_sub.gpkg')
# Cyprus is one island with one figure: Pew's 2020 estimate covers the whole island (population 1.30 million: the Republic,
# the Turkish Cypriot-administered north, the UN buffer zone and the UK Sovereign Base Areas). It is drawn as one area with
# that figure, and the de facto line (northern edge of the buffer zone) is kept as a dashed line.
CY_PARTS = ['CYN', 'CNM', 'ESB', 'WSB']
_cyn = unary_union([make_valid(q) for q in nat[nat.ADM0_A3 == 'CYN'].geometry])
_cyrest = unary_union([make_valid(q) for q in nat[nat.ADM0_A3.isin(['CYP', 'CNM', 'ESB', 'WSB'])].geometry])
CY_LINE = _cyn.boundary.intersection(_cyrest.buffer(0.0008))
_cy = nat.ADM0_A3 == 'CYP'
assert _cy.sum() == 1 and nat.loc[_cy, 'muslims'].notna().all()
_cyx = nat.ADM0_A3.isin(CY_PARTS)
for col in ['ADMIN', 'pct', 'muslims', 'src', 'basis', 'year']:
    nat.loc[_cyx, col] = nat.loc[_cy, col].iloc[0]
nat.loc[_cyx, 'ADM0_A3'] = 'CYP'
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
# one shape per country code: Natural Earth splits some countries into map units (Belgium's three regions, the UK's four
# nations, Bosnia's entities...) that carry the same national figure, and drawing them separately leaves seams
natc = natc.dissolve(by='ADM0_A3', as_index=False, aggfunc={'ADMIN': 'first', 'pct': 'first', 'muslims': 'first', 'src': 'first',
                                                         'basis': 'first', 'year': 'first'})
recs = []
for r in natc.itertuples():
    recs.append({'i': len(recs), 'n': r.ADMIN, 'c': r.ADM0_A3, 'p': None if r.pct != r.pct else round(float(r.pct), 2),
                 'm': None if r.muslims != r.muslims else int(r.muslims), 's': sidx(r.src),
                 'q': r.basis, 'y': None if r.year != r.year else int(r.year), 'geometry': r.geometry})
g = gpd.GeoDataFrame(recs, crs=4326)
g.to_file(f'{OUT}/countries.geojson', driver='GeoJSON')

# ---- data basis of each unit: c census/register, s published estimate (non-official body), e ethnicity-based,
#      n no figure collected. Every value is a published figure or arithmetic on published figures.
ETHNIC = {'RUS', 'CHN', 'UAOCC'}
PUBLISHED_EST = {'ESP', 'USA'}
def basis(iso, unit, src, dflt, pct):
    if dflt or pct != pct: return 'n'
    if iso in ETHNIC: return 'e'
    if iso in PUBLISHED_EST: return 's'
    return 'c'

# ---- parent province of each unit (for cards and search), from Natural Earth admin-1
A1 = gpd.read_file(f'{RAW}/ne_10m_admin_1_states_provinces.geojson')[['adm0_a3', 'name', 'name_en', 'name_alt', 'region', 'geometry']]
PARENT_FIELD = {'IND': 'name', 'PAK': 'name_en', 'IDN': 'name_en', 'BGD': 'name', 'CAN': 'name', 'AUS': 'name',
                'ETH': 'name', 'GRC': 'name', 'ESP': 'region', 'GBR': 'region'}
A1p = A1[A1.adm0_a3.isin(list(PARENT_FIELD))].copy()
A1p['parent'] = [r[PARENT_FIELD[r.adm0_a3]] for _, r in A1p.iterrows()]
A1p['parent'] = A1p.parent.replace({'Sind': 'Sindh', 'K.P.': 'Khyber Pakhtunkhwa'})
fold = lambda x: ''.join(ch for ch in str(x).lower() if ch.isalnum())

# ---- first-level division of each unit, for the border hierarchy: lines between units of different first-level divisions
#      are drawn stronger than lines inside one. Where the units are themselves the first level (U.S. and Brazilian states,
#      Kenyan counties, Russian federal subjects...) each unit is its own parent, so all its borders are first-level lines.
BORDER_PARENT = {'AUS': 'name', 'BGD': 'name', 'CAN': 'name', 'ETH': 'name', 'IDN': 'name', 'IND': 'name', 'SRB': 'name',
                 'GBR': 'geonunit', 'ESP': 'region', 'PHL': 'region', 'MWI': 'region', 'UGA': 'region', 'LKA': 'region',
                 'BFA': 'region'}
A1b = gpd.read_file(f'{RAW}/ne_10m_admin_1_states_provinces.geojson')[['adm0_a3', 'name', 'region', 'geonunit', 'geometry']]
A1b = A1b[A1b.adm0_a3.isin(list(BORDER_PARENT))].copy()
A1b['bp'] = [r[BORDER_PARENT[r.adm0_a3]] for _, r in A1b.iterrows()]
BIH2 = gpd.read_file(f'{RAW}/gb/geoBoundaries-BIH-ADM2_simplified.geojson')[['shapeName', 'geometry']]   # cantons, RS, Brčko
def border_parent(iso, geom, i):
    p = geom.representative_point()
    if iso == 'BIH':
        cand = BIH2.assign(bp=BIH2.shapeName)
    elif iso in BORDER_PARENT:
        cand = A1b[(A1b.adm0_a3 == iso) & A1b.bp.notna()]
    else:
        return f'u{i}'
    h = cand[cand.geometry.contains(p)]
    if not len(h):            # just outside the parent outlines (coast, simplified edges): the nearest one
        h = cand.iloc[[int(cand.geometry.distance(p).values.argmin())]]
    return iso + ':' + h.bp.iloc[0]

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
    recs.append({'i': len(recs), 'n': nm, 'r': par, 'pk': border_parent(r.iso, r.geometry, len(recs)), 'q': basis(r.iso, nm, r.src, r.dflt, r.pct), 'c': r.iso, 'p': None if r.pct != r.pct else round(float(r.pct), 2),
                 'm': None if r.muslims != r.muslims else int(round(r.muslims)),
                 'd': int(bool(r.dflt)), 's': sidx(r.src), 'y': None if r.year != r.year else int(r.year),
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

# ---- speculative layer (shown only in speculative mode): survey-based regional estimates, see pipeline/scripts/speculative.py
spec = gpd.read_file(f'{DATA}/units_spec.gpkg')
precs = []
for r in spec.itertuples():
    a = anchor(r.geometry)
    precs.append({'i': len(precs), 'n': r.unit, 'c': r.iso, 'p': round(float(r.pct), 1), 'lo': round(float(r.lo), 1), 'hi': round(float(r.hi), 1),
                  'ns': int(r.n), 'y': str(r.year), 's': sidx(r.src), 'lx': a[0] if a else None, 'ly': a[1] if a else None,
                  'lr': a[2] if a else None, 'geometry': r.geometry})
gpd.GeoDataFrame(precs, crs=4326).to_file(f'{OUT}/spec.geojson', driver='GeoJSON')
print('speculative regions', len(precs))

# ---- states / provinces of large countries without regional figures: drawn as fine dashed lines only (the whole country
#      carries its national figure and is what gets highlighted). Natural Earth admin-1, clipped to the country; pieces of the
#      country no state covers join the state that shares the longest border with them (else the nearest), so the states tile
#      the country exactly and the lines are the country's own arcs.
a = nat.to_crs(EE).assign(a=lambda d: d.geometry.area / 1e6).groupby('ADM0_A3').a.sum()
big = ((set(a[a >= 1.2e6].index) - set(sub.iso)) | {'PRY'}) - {'ATA'}
A1s = gpd.read_file(f'{RAW}/ne_10m_admin_1_states_provinces.geojson')
def polys(q):
    q = make_valid(q)
    return [p for p in getattr(q, 'geoms', [q]) if p.geom_type == 'Polygon'] + \
           [pp for p in getattr(q, 'geoms', []) if p.geom_type == 'MultiPolygon' for pp in p.geoms]
srecs = []
for iso in sorted(big):
    cpoly = make_valid(natc[natc.ADM0_A3 == iso].geometry.iloc[0])
    st = A1s[(A1s.adm0_a3 == iso) & A1s.name.notna()]
    parts = [unary_union(polys(make_valid(q).intersection(cpoly))) for q in st.geometry]
    for p in polys(cpoly.difference(unary_union(parts))):
        shared = [p.boundary.intersection(q.boundary).length if not q.is_empty else 0 for q in parts]
        j = int(np.argmax(shared)) if max(shared) > 0 else int(np.argmin([p.distance(q) for q in parts]))
        parts[j] = unary_union([parts[j], p])
    for q in parts:
        if not q.is_empty:
            srecs.append({'c': iso, 'geometry': MultiPolygon(polys(q)) if len(polys(q)) > 1 else polys(q)[0]})
states = gpd.GeoDataFrame(srecs, crs=4326)
states.to_file(f'{OUT}/states.geojson', driver='GeoJSON')
print('states', len(states), 'in', ', '.join(sorted(big)))

# ---- lines and lakes
dl = gpd.read_file(f'{RAW}/ne_10m_admin_0_boundary_lines_disputed_areas.geojson')[['geometry']]
dl = pd.concat([dl, gpd.GeoDataFrame(geometry=[CY_LINE], crs=4326)], ignore_index=True)
dl.to_file(f'{OUT}/disputed.geojson', driver='GeoJSON')
lk = gpd.read_file(f'{RAW}/ne_10m_lakes.geojson')
lk = lk[lk.scalerank <= 5][['geometry']]
lk.to_file(f'{OUT}/lakes.geojson', driver='GeoJSON')

# ---- country labels
c0 = gpd.read_file(f'{RAW}/ne_10m_admin_0_countries.geojson')
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
_pcap = gpd.read_file(f'{RAW}/ne_10m_populated_places_simple.geojson', ignore_geometry=True)
CAPITALS = {fold(n) for n in _pcap[_pcap.adm0cap == 1].name} | {fold(n) for n in _pcap[_pcap.adm0cap == 1].nameascii}
def cl_json(R):     # 'cap': the circle holds a national capital (labelled as soon as its country's name is, if there is room)
    cl = cluster_communities(com, R)
    return [{'n': r.name, 'x': round(r.lon, 3), 'y': round(r.lat, 3), 'm': None if r.basis == 'unsized' else int(r.muslims), 'b': r.basis,
             'k': r.n, 'mem': r.members, 'c': r.country, 'cap': int(any(fold(x) in CAPITALS for x in r.members.split(', ')))}
            for r in cl.itertuples()]
us = pd.read_csv(f'{DATA}/usa_metros_arda2020.csv')
metros = [{'n': r.city, 'full': r.name, 'x': round(r.lon, 3), 'y': round(r.lat, 3), 'm': int(r.adherents),
           'k': int(r.congregations)} for r in us.itertuples() if r.adherents >= 300]

# ---- short country names, search regions (provinces), cities, country totals, sources table, CSV
cs = gpd.read_file(f'{RAW}/ne_10m_admin_0_countries.geojson', ignore_geometry=True)
short = dict(zip(cs.ADM0_A3, cs.NAME_LONG))
short.update({'PSX': 'Palestine', 'KOS': 'Kosovo', 'SOL': 'Somaliland', 'TWN': 'Taiwan',
              'SAH': 'Western Sahara', 'USA': 'United States', 'GBR': 'United Kingdom', 'COD': 'DR Congo',
              'COG': 'Republic of the Congo', 'CIV': "Côte d'Ivoire", 'CZE': 'Czechia', 'MKD': 'North Macedonia',
              'SWZ': 'Eswatini', 'TLS': 'Timor-Leste', 'CPV': 'Cabo Verde', 'BHS': 'The Bahamas', 'GMB': 'The Gambia',
              'KOR': 'South Korea', 'PRK': 'North Korea', 'LAO': 'Laos', 'RUS': 'Russia', 'SRB': 'Serbia',
              'TZA': 'Tanzania', 'HKG': 'Hong Kong', 'MAC': 'Macau', 'UAOCC': 'Ukraine', 'GUF': 'French Guiana',
              'GLP': 'Guadeloupe', 'MTQ': 'Martinique', 'REU': 'Réunion', 'MYT': 'Mayotte', 'BES': 'Caribbean Netherlands',
              'CXR': 'Christmas Island', 'CCK': 'Cocos (Keeling) Islands'})
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
pp = pp[(pp.pop_max >= 750000) | (pp.adm0cap == 1) | (pp.featurecla.str.contains('Admin-1', na=False) & (pp.pop_max >= 200000))]
cities = []
for r in pp.itertuples():
    alt = {r.nameascii} - {r.name}
    if isinstance(r.namealt, str) and r.namealt: alt |= set(r.namealt.split('|'))
    cities.append({'n': r.name, 'alt': sorted(a for a in alt if a)[:4], 'x': round(r.longitude, 3), 'y': round(r.latitude, 3),
                   'pop': int(r.pop_max), 'c': r.adm0_a3})
# national totals as the sum of mapped areas (only where every area has a published count)
usum = {}
_ann = (ug.c == 'RUS') & ug.n.isin(['Crimea', 'Sevastopol'])     # occupied Ukraine (recoded by prep_status.py)
for iso, grp in ug[~ug.c.isin(['ROU']) & ~_ann].groupby('c'):   # partial coverage: no national sum
    if grp.m.isna().any() or grp.p.isna().any() or (grp.p.fillna(0) <= 0).any():
        continue
    pop = (grp.m / grp.p * 100).sum()
    usum[iso] = {'m': int(grp.m.sum()), 'p': round(float(grp.m.sum() / pop * 100), 2), 'y': year_of.get(iso, '')}
cn = dict(zip(reg.iso3, reg.notes.fillna('')))
def rbasis(r):
    if r.iso3 in ('RUS', 'CHN'): return 'Census (ethnicity)'
    if r.iso3 in ('ESP', 'USA'): return 'Published estimate'
    if r.iso3 == 'LAT': return 'Census + documented communities'
    return 'Census / register'
regtab = [{'c': r.iso3, 'name': short.get(r.iso3, {'LAT': 'Latin America & Caribbean (circles)', 'PSE': 'Palestine'}.get(r.iso3, r.iso3)),
           'level': str(r.level), 'source': str(r.source).replace('ESTIMATE — ', '').replace('ESTIMATE ', ''),
           'year': str(r.year), 'basis': rbasis(r), 'note': cn.get(r.iso3, '')} for r in reg.itertuples()]
regtab.sort(key=lambda d: d['name'])
# downloadable table of every unit
cn_short = lambda iso: short.get(iso, iso)
csv = ug.drop(columns='geometry').copy()
csv['country'] = csv.c.map(cn_short); csv['source'] = csv.s.map(lambda i: srcs[i]); csv['year'] = csv.c.map(year_of)
csv['year'] = [str(int(y)) if y == y and y is not None else yr for y, yr in zip(csv.y, csv.year)]
csv['basis'] = csv.q.map({'c': 'census/register', 's': 'published estimate', 'e': 'ethnicity-based', 'n': 'no figure collected'})
csv.loc[csv.q == 'n', 'source'] = ''; csv.loc[csv.q == 'n', 'year'] = ''
csv['unit'] = csv.n.where(csv.n != '', 'Rest of ' + csv.country)
_occ = (csv.c == 'RUS') & csv.n.isin(['Crimea', 'Sevastopol'])      # occupied Ukraine (see prep_status.py)
csv.loc[_occ, 'country'] = 'Ukraine (Russian-occupied)'; csv.loc[_occ, 'c'] = 'UKR'
csv.loc[_occ, 'year'] = np.where(csv.loc[_occ, 'n'] == 'Crimea', '2014', '')
csv = csv[['country', 'c', 'unit', 'r', 'p', 'm', 'basis', 'source', 'year']].rename(columns={
    'c': 'iso3', 'r': 'province', 'p': 'share_muslim_pct', 'm': 'muslims'})
csv.sort_values(['country', 'unit']).to_csv(f'{OUT}/units.csv', index=False)
com_drop = {'Trinidad & Tobago', 'Suriname', 'Guyana'}    # markers that only stood for a whole country

# how each country's area figures were made, shown on every card (default: published for the area by the statistics office)
HOW = {
    'BRA': 'State total published by the 2010 census (IBGE) — not a sum of the cities on the map.',
    'USA': 'State total published by the 2020 U.S. Religion Census, which counts mosque adherents — not a sum of the metro areas.',
    'ESP': 'UCIDE’s count of Muslims in the province ÷ INE’s official population.',
    'RUS': 'Sum of the traditionally Muslim nationalities the 2010 census counted here ÷ residents who stated a nationality.',
    'UAOCC': 'Sum of the Muslim nationalities Russia’s 2014 census counted here ÷ residents who stated a nationality.',
    'CHN': 'Sum of the ten traditionally Muslim nationalities the 2010 census counted here ÷ residents.',
    'ISR': 'Central Bureau of Statistics count of Muslims in the district ÷ district population.',
}
extra = {'labels': labels, 'comW': cl_json(45), 'comR': cl_json(12), 'metros': metros, 'sources': srcs, 'how': HOW,
         'years': year_of, 'regsrc': dict(zip(reg.iso3, reg.source)),
         'regions': regions, 'cities': cities, 'usum': usum, 'reg': regtab, 'short': short}
extra['comW'] = [c for c in extra['comW'] if c['n'] not in com_drop]
extra['comR'] = [c for c in extra['comR'] if c['n'] not in com_drop]
json.dump(extra, open(f'{OUT}/extra.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('labels', len(labels), 'comW', len(extra['comW']), 'comR', len(extra['comR']), 'metros', len(metros), 'srcs', len(srcs))

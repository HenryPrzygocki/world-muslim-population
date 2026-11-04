"""Speculative layer: regional estimates for countries without official regional figures (shown only when the reader
turns speculative mode on). Nothing here is an official statistic.

Source: Afrobarometer Round 10 merged data (38 countries, release 25 Feb 2026; surveys 2024-25). For each country and
province/region: the weighted share of respondents (adult citizens, 18+) who gave a Muslim religion (Afrobarometer's
condensed religion variable RELIG_COND = Muslim), with the household-level within-country weight (withinwt_hh). The 95%
range is a Wilson interval on the effective sample size (Kish). Regions are not smoothed, modelled or rescaled: a region
with few respondents simply has a wide range. Where the map's outlines are coarser than the survey's regions (a region
split after the outlines were drawn), the respondents of the survey regions are pooled.

Step 1 (needs pipeline/raw/afrobarometer/*.sav, see fetch_raw.sh) writes data/speculative/afrobarometer_r10.csv;
step 2 (always) builds data/units_spec.gpkg from that table and the outlines."""
import os, sys, re, glob, math, difflib, unicodedata, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, geopandas as gpd
from shapely import make_valid
from shapely.ops import unary_union
from shapely.geometry import MultiPolygon
from common import RAW, DATA, GB

OUT_CSV = f'{DATA}/speculative/afrobarometer_r10.csv'
SRC = ('Afrobarometer Round 10 survey ({year}): share of adult respondents in the region who said they are Muslim '
       '(weighted; {n} respondents)')

# country -> (Afrobarometer name, outlines, {survey region: map region}); outlines: 'ne' = Natural Earth admin-1, or a
# geoBoundaries file. Survey regions mapped to the same map region are pooled.
SPEC = {
    'NGA': ('Nigeria', 'ne', {'FCT': 'Federal Capital Territory'}),
    'GHA': ('Ghana', 'GHA-ADM1', {}),
    'CMR': ('Cameroon', 'ne', {}),
    'TCD': ('Chad', 'TCD-ADM1', {'BARH-EL-GAZAL': 'Bahr el Gazel'}),
    'CIV': ("Côte d'Ivoire", 'CIV-ADM2', {'ABIDJAN': "District Autonome D'Abidjan", 'YAMOUSSOUKRO': 'District Autonome De Yamoussoukro',
                                          'LA ME': 'Me', 'GRAND-PONTS': 'Grands Ponts'}),
    'TGO': ('Togo', 'ne', {'LOMÉ COMMUNE': 'Maritime'}),
    'SLE': ('Sierra Leone', 'ne', {'NORTH WEST': 'Northern'}),
    'LBR': ('Liberia', 'ne', {}),
    'MOZ': ('Mozambique', 'ne', {'Maputo City': 'Maputo City', 'Maputo Province': 'Maputo'}),
    'TZA': ('Tanzania', 'ne', {'Songwe': 'Mbeya', 'Pemba Kaskazini': 'Kaskazini-Pemba', 'Pemba Kusini': 'Kusini-Pemba',
                               'Unguja Kaskazini': 'Kaskazini-Unguja', 'Unguja Kusini': 'Zanzibar South and Central',
                               'Mjini Magharibi': 'Zanzibar West'}),
    'MDG': ('Madagascar', 'ne', {'FITOVINANY': 'Vatovavy-Fitovinany', 'VATOVAVY': 'Vatovavy-Fitovinany',
                                 'MATSIATRA AMBONY': 'Haute Matsiatra'}),
    'MUS': ('Mauritius', 'ne', {}),
    'SEN': ('Senegal', 'ne', {}),
    'MLI': ('Mali', 'ne', {'MENAKA': 'Gao', 'TAOUDENIT': 'Timbuktu', 'TOMBOUCTOU': 'Timbuktu'}),
    'MRT': ('Mauritania', 'ne', {'NOUAKCHOTT-NORD': 'Nouakchott', 'NOUAKCHOTT-OUEST': 'Nouakchott', 'NOUAKCHOTT-SUD': 'Nouakchott'}),
    'BEN': ('Benin', 'BEN-ADM1', {'COUFFO': 'Kouffo'}),
}
OFFICIAL = {'BEN': {'Alibori', 'Donga', 'Borgou', 'Kouffo'}}    # regions with an official figure on the map: not estimated


def fold(s):
    s = unicodedata.normalize('NFKD', str(s))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z]', '', s)


def outlines(iso, src):
    """map regions of a country: GeoDataFrame with 'region' (display name) and 'keys' (folded names it answers to)"""
    if src == 'ne':
        a = gpd.read_file(f'{RAW}/ne_10m_admin_1_states_provinces.geojson')
        a = a[a.adm0_a3 == iso][['name', 'name_en', 'name_alt', 'geometry']].copy()
        a['region'] = [e if isinstance(e, str) and e else n for e, n in zip(a.name_en, a.name)]
        if iso == 'MOZ':      # Natural Earth names both the city and the province "Maputo": the smaller one is the city
            m = a.region == 'Maputo'
            a.loc[a[m].geometry.area.idxmin(), 'region'] = 'Maputo City'
        a['keys'] = [{fold(r.region), fold(r['name'])} | ({fold(x) for x in r.name_alt.split('|')} if isinstance(r.name_alt, str) else set())
                     for _, r in a.iterrows()]
    else:
        a = gpd.read_file(f'{GB}/geoBoundaries-{src}_simplified.geojson')
        a['region'] = a.shapeName.str.replace(r' Region$', '', regex=True)
        a['keys'] = [{fold(r)} for r in a.region]
    a['geometry'] = a.geometry.apply(make_valid)
    a = a[['region', 'keys', 'geometry']]            # one shape per region name (some files split a region in pieces)
    keys = a.groupby('region')['keys'].agg(lambda ks: set().union(*ks))
    a = a[['region', 'geometry']].dissolve(by='region', as_index=False)
    a['keys'] = a.region.map(keys)
    return a.reset_index(drop=True)


# display names: drop Natural Earth's " State" suffix (Nigeria), fix geoBoundaries spellings
DISPLAY = {'Atlanique': 'Atlantique', 'Oueme': 'Ouémé', 'Kouffo': 'Couffo', 'Atakora': 'Atacora',
           "District Autonome D'Abidjan": 'Abidjan', 'District Autonome De Yamoussoukro': 'Yamoussoukro', 'Me': 'La Mé',
           'Goh': 'Gôh', 'Loh-Djiboua': 'Lôh-Djiboua', 'Bagoue': 'Bagoué', 'Belier': 'Bélier', 'Bere': 'Béré',
           'Gbeke': 'Gbêkê', 'Gbokle': 'Gbôklê', 'Guemon': 'Guémon', 'Indenie-Djuablin': 'Indénié-Djuablin',
           'Marahoue': 'Marahoué', 'Sud-Comoe': 'Sud-Comoé', 'San Pedro': 'San-Pédro', "N'Djamena Region": "N'Djamena",
           'Federal Capital Territory': 'Federal Capital Territory (Abuja)'}
def display(r):
    return DISPLAY.get(r, re.sub(r' State$', '', r))


def wilson(p, n, z=1.96):
    if n <= 0:
        return np.nan, np.nan
    d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - h) / d), min(1.0, (c + h) / d)


def estimates():
    import pyreadstat
    f = glob.glob(f'{RAW}/afrobarometer/*.sav')
    assert f, 'Afrobarometer Round 10 data missing: run pipeline/fetch_raw.sh'
    df, meta = pyreadstat.read_sav(f[0], usecols=['COUNTRY', 'REGION', 'RELIG_COND', 'withinwt_hh', 'DATEINTR'])
    vl = meta.variable_value_labels
    df['country'] = df.COUNTRY.map(vl['COUNTRY']); df['ab'] = df.REGION.map(vl['REGION'])
    df['mus'] = (df.RELIG_COND == 2).astype(float); df['w'] = df.withinwt_hh
    rows, misses = [], {}
    for iso, (cname, src, alias) in SPEC.items():
        g = df[df.country == cname].copy(); assert len(g), cname
        a = outlines(iso, src)
        key2reg = {k: r for r, ks in zip(a.region, a['keys']) for k in ks}
        def to_region(ab):
            if ab in alias:            # an alias names the map region by any of its names
                return key2reg.get(fold(alias[ab]), alias[ab])
            k = fold(ab)
            if k in key2reg:
                return key2reg[k]
            m = difflib.get_close_matches(k, list(key2reg), n=1, cutoff=0.85)
            return key2reg[m[0]] if m else None
        g['region'] = g.ab.map(to_region)
        miss = sorted(g[g.region.isna()].ab.unique())
        if miss:
            misses[iso] = miss; continue
        year = '–'.join(sorted({str(d.year) for d in pd.to_datetime(g.DATEINTR)}))
        for reg, x in g.groupby('region'):
            if reg in OFFICIAL.get(iso, ()):
                continue
            w = x.w.values; p = float(np.average(x.mus, weights=w)); neff = w.sum() ** 2 / (w ** 2).sum()
            lo, hi = wilson(p, neff)
            rows.append({'iso': iso, 'region': reg, 'survey_regions': ', '.join(sorted(x.ab.unique())), 'n': len(x),
                         'n_eff': round(neff, 1), 'pct': round(p * 100, 1), 'lo': round(lo * 100, 1), 'hi': round(hi * 100, 1),
                         'year': year})
    assert not misses, misses
    out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, 'w') as fh:
        fh.write('# Speculative estimates (not official): Afrobarometer Round 10 merged data, release 25 Feb 2026. pct = weighted share of\n'
                 '# respondents (adult citizens) whose religion is Muslim (RELIG_COND); lo/hi = 95% Wilson interval on n_eff. See speculative.py.\n')
        out.to_csv(fh, index=False)
    print('estimates:', len(out), 'regions in', out.iso.nunique(), 'countries')


def build():
    est = pd.read_csv(OUT_CSV, comment='#')
    nat = gpd.read_file(f'{DATA}/units_national.gpkg')
    recs = []
    for iso, g in est.groupby('iso'):
        a = outlines(iso, SPEC[iso][1]).set_index('region')
        cpoly = make_valid(unary_union([make_valid(q) for q in nat[nat.ADM0_A3 == iso].geometry]))
        parts = {r: make_valid(a.geometry[r]).intersection(cpoly) for r in g.region}
        if iso not in OFFICIAL:   # the regions tile the country: pieces no region covers join the neighbour with the longest border
            full = {r: make_valid(geom).intersection(cpoly) for r, geom in a.geometry.items()}
            resid = cpoly.difference(unary_union(list(full.values())))
            for p in getattr(resid, 'geoms', [resid]):
                if p.is_empty or p.geom_type != 'Polygon':
                    continue
                shared = {r: p.boundary.intersection(q.boundary).length for r, q in parts.items()}
                r = max(shared, key=shared.get) if max(shared.values()) > 0 else min(parts, key=lambda r: parts[r].distance(p))
                parts[r] = unary_union([parts[r], p])
        for r in g.itertuples():
            q = parts[r.region]
            ps = [x for x in getattr(q, 'geoms', [q]) if x.geom_type == 'Polygon']
            if not ps:
                continue
            recs.append({'iso': iso, 'unit': display(r.region), 'pct': r.pct, 'lo': r.lo, 'hi': r.hi, 'n': r.n, 'year': r.year,
                         'src': SRC.format(year=r.year, n=r.n), 'geometry': MultiPolygon(ps) if len(ps) > 1 else ps[0]})
    out = gpd.GeoDataFrame(recs, crs=4326)
    out.to_file(f'{DATA}/units_spec.gpkg', driver='GPKG')
    print('speculative units:', len(out))


if __name__ == '__main__':
    if glob.glob(f'{RAW}/afrobarometer/*.sav'):
        estimates()
    build()

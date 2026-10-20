"""Assemble the world layer of statistical units with Muslim-share values (WGS84)."""
import sys, json, warnings
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import shape, Polygon, MultiPolygon, Point
from shapely.ops import unary_union
from shapely import make_valid
from common import *
import sub2
S2 = f'{DATA}/sub2'


def read2(name):
    df = pd.read_csv(f'{S2}/{name}.csv')
    if 'pct' not in df.columns and 'muslims' in df.columns:
        df['pct'] = df['muslims'] / df['total'] * 100
    return df

NE0 = gpd.read_file(f'{RAW}/ne_10m_admin_0_map_units.geojson')
NE1 = gpd.read_file(f'{RAW}/ne_10m_admin_1_states_provinces.geojson')
NE1 = NE1[NE1.geometry.notna()].copy()

# ---------------------------------------------------------------- national baseline
pew = pd.read_csv(f'{DATA}/pew2020.csv')
pew['pct'] = pew.muslims_2020 / pew.total_2020 * 100
pew_alias = {'Cape Verde': 'Cabo Verde', 'Macao': 'Macao S.A.R', 'Palestinian territories': 'Palestine',
             'Tanzania': 'United Republic of Tanzania', 'Timor-Leste': 'East Timor',
             'United States': 'United States of America', 'U.S. Virgin Islands': 'United States Virgin Islands',
             'Channel Islands': 'Jersey', 'Czech Republic': 'Czechia', 'Hong Kong': 'Hong Kong S.A.R.',
             'St. Lucia': 'Saint Lucia', 'St. Vincent and the Grenadines': 'Saint Vincent and the Grenadines',
             'French Guiana': None, 'Guadeloupe': None, 'Martinique': None, 'Mayotte': None, 'Reunion': None}
admins = NE0.ADMIN.unique().tolist()
nat = {}
mm = match_names(pew.country.tolist(), admins, aliases=pew_alias, cutoff=0.8, verbose=False)
natcnt = {}
for _, r in pew.iterrows():
    if r.country in mm:
        nat[mm[r.country]] = (r.pct, 'Pew Research Center 2020 estimate')
        natcnt[mm[r.country]] = r.muslims_2020
nat['Guernsey'] = nat['Jersey']
extra = {  # territories not separately estimated by Pew
    'Somaliland': (99.8, 'as Somalia (Pew 2020)'), 'Northern Cyprus': (97.0, 'estimate'),
    'Liechtenstein': (5.9, 'Liechtenstein census 2020'), 'Gibraltar': (4.0, 'Gibraltar census 2012'),
    'San Marino': (0.1, 'estimate'), 'Monaco': (0.5, 'estimate'), 'Andorra': (1.0, 'estimate'), 'Vatican': (0.0, ''),
    'Greenland': (0.1, 'estimate'), 'Faroe Islands': (0.1, 'estimate'), 'Aland': (0.3, 'estimate'),
    'Isle of Man': (0.2, 'estimate'), 'Bermuda': (0.7, 'estimate'), 'Cayman Islands': (0.2, 'estimate'),
    'Turks and Caicos Islands': (0.1, 'estimate'), 'Anguilla': (0.3, 'estimate'), 'Montserrat': (0.1, 'estimate'),
    'Antigua and Barbuda': (0.6, 'estimate'), 'Saint Kitts and Nevis': (0.3, 'estimate'), 'Dominica': (0.2, 'estimate'),
    'Saint Barthelemy': (0.1, 'estimate'), 'Saint Martin': (0.8, 'estimate'), 'Sint Maarten': (0.8, 'estimate'),
    'Saint Pierre and Miquelon': (0.0, ''), 'Pitcairn Islands': (0.0, ''), 'Falkland Islands': (0.0, ''),
    'Saint Helena': (0.0, ''), 'Norfolk Island': (0.0, ''), 'Cook Islands': (0.0, ''), 'Niue': (0.0, ''),
    'Wallis and Futuna': (0.0, ''), 'Tuvalu': (0.0, ''), 'Nauru': (0.0, ''), 'American Samoa': (0.0, ''),
    'Palau': (0.2, 'estimate'), 'Northern Mariana Islands': (0.2, 'estimate'), 'Marshall Islands': (0.1, 'estimate'),
    'Baykonur Cosmodrome': (70.0, 'as Kazakhstan (Kyzylorda)'), 'Dhekelia Sovereign Base Area': (3.0, 'as Cyprus (south)'),
    'Akrotiri Sovereign Base Area': (3.0, 'as Cyprus (south)'), 'US Naval Base Guantanamo Bay': (0.1, ''),
    'British Virgin Islands': (1.2, 'estimate'),
    'Indian Ocean Territories': (30.0, 'ABS 2021 census (Christmas & Cocos Is.)'),
}
nat.update(extra)
nat['Cyprus'] = (3.0, 'estimate (Republic-controlled area; Pew national incl. north 24.4%)')
NODATA = {'Antarctica', 'Bir Tawil', 'Brazilian Island', 'Siachen Glacier', 'Spratly Islands', 'Scarborough Reef',
          'Bajo Nuevo Bank (Petrel Is.)', 'Serranilla Bank', 'Clipperton Island', 'Coral Sea Islands',
          'Ashmore and Cartier Islands', 'Southern Patagonian Ice Field', 'Cyprus No Mans Area',
          'Heard Island and McDonald Islands', 'French Southern and Antarctic Lands', 'South Georgia and the Islands',
          'British Indian Ocean Territory', 'United States Minor Outlying Islands'}

base = NE0[['ADMIN', 'ADM0_A3', 'GEOUNIT', 'GU_A3', 'NAME', 'LABELRANK', 'POP_EST', 'geometry']].copy()
vals, srcs = [], []
for _, r in base.iterrows():
    if r.ADMIN in NODATA:
        vals.append(np.nan); srcs.append('no permanent population'); continue
    v = nat.get(r.ADMIN) or nat.get(r.GEOUNIT)
    if v is None:
        print('!! no national value for', r.ADMIN, r.GEOUNIT)
        vals.append(np.nan); srcs.append('')
    else:
        vals.append(v[0]); srcs.append(v[1])
base['pct'] = vals; base['src'] = srcs
base['level'] = 0
base['iso'] = base.ADM0_A3
base['unit'] = base.GEOUNIT
base['muslims'] = base.ADMIN.map(natcnt)


# ---------------------------------------------------------------- helpers
def ne1(iso, region_field=None):
    g = NE1[NE1.adm0_a3 == iso].copy()
    if region_field:
        g = g.dissolve(by=region_field, as_index=False)
        g['name'] = g[region_field]; g['name_en'] = g[region_field]
    g['disp'] = [e if isinstance(e, str) and e else n for e, n in zip(g.name_en, g.name)]
    return g[['name', 'disp', 'geometry']].rename(columns={'name': 'gname'})


def gbf(code, field='shapeName'):
    g = gpd.read_file(f'{GB}/geoBoundaries-{code}_simplified.geojson')
    g['geometry'] = g.geometry.apply(make_valid)
    g['disp'] = g[field].astype(str).str.replace(r' (Region|Municipality|Canton|City|District|Province)$', '', regex=True)
    return g[[field, 'disp', 'geometry']].rename(columns={field: 'gname'})


def attach(g, df, iso, aliases=None, default=None, key='unit', label=None, cutoff=0.86, src=''):
    m = match_names(g.gname.tolist(), df[key].astype(str).tolist(), aliases=aliases, cutoff=cutoff,
                    label=label or iso)
    lut = dict(zip(df[key].astype(str), df.pct))
    cnt = dict(zip(df[key].astype(str), df.muslims)) if 'muslims' in df.columns else {}
    g = g.copy()
    g['unit'] = g['disp'].fillna(g.gname) if 'disp' in g.columns else g.gname
    g['pct'] = [lut.get(m.get(n)) if n in m else default for n in g.gname]
    g['pct'] = g.pct.astype(float)
    g['dflt'] = [n not in m for n in g.gname]
    g['muslims'] = [cnt.get(m.get(n), np.nan) if n in m else np.nan for n in g.gname]
    # several geo units matched to one data row (e.g. new districts of an old one): show them as that one unit
    tgt = pd.Series([m.get(n) for n in g.gname], index=g.index)
    multi = tgt.notna() & tgt.duplicated(keep=False)
    g.loc[multi, 'unit'] = tgt[multi]
    g['iso'] = iso; g['src'] = src; g['level'] = 1
    return g


SUBS = []
POP = {   # resident population, latest official estimate (2021-2024), for approximate counts
    'DEU': {'Nordrhein-Westfalen': 18139116, 'Baden-Württemberg': 11280257, 'Bayern': 13369393, 'Hessen': 6391360,
            'Niedersachsen': 8140242, 'Berlin': 3755251, 'Hamburg': 1892122, 'Bremen': 684864,
            'Rheinland-Pfalz': 4159150, 'Saarland': 992666, 'Schleswig-Holstein': 2953270, 'Sachsen': 4089467,
            'Thüringen': 2126846, 'Sachsen-Anhalt': 2186643, 'Brandenburg': 2573135, 'Mecklenburg-Vorpommern': 1628378},
    'FRA': {'Île-de-France': 12317279, "Provence-Alpes-Côte-d'Azur": 5127840, 'Auvergne-Rhône-Alpes': 8114361,
            'Grand Est': 5561287, 'Hauts-de-France': 5987172, 'Occitanie': 6053548, 'Bourgogne-Franche-Comté': 2800194,
            'Centre-Val de Loire': 2573295, 'Corse': 349465, 'Normandie': 3327077, 'Nouvelle-Aquitaine': 6069352,
            'Pays de la Loire': 3873096, 'Bretagne': 3394567},
    'ESP': {'Melilla': 85170, 'Ceuta': 83517, 'Murcia': 1568000, 'Cataluña': 8012000, 'La Rioja': 323000,
            'Islas Baleares': 1232000, 'Aragón': 1346000, 'Foral de Navarra': 678000, 'Madrid': 7000000,
            'Valenciana': 5216000, 'Andalucía': 8600000, 'Canary Is.': 2238000, 'Castilla-La Mancha': 2084000,
            'País Vasco': 2227000, 'Extremadura': 1054000, 'Castilla y León': 2390000, 'Cantabria': 590000,
            'Asturias': 1009000, 'Galicia': 2705000},
    'NLD': {'Drenthe': 497000, 'Flevoland': 434000, 'Friesland': 654000, 'Gelderland': 2110000, 'Groningen': 590000,
            'Limburg': 1118000, 'Noord-Brabant': 2600000, 'Noord-Holland': 2950000, 'Overijssel': 1180000,
            'Zuid-Holland': 3800000, 'Utrecht': 1390000, 'Zeeland': 390000},
    'BEL': {'Capital Region': 1241000, 'Flemish': 6774000, 'Walloon': 3682000},
    'AUT': {'Wien': 1931000, 'Vorarlberg': 400000, 'Salzburg': 560000, 'Oberösterreich': 1505000, 'Tirol': 764000,
            'Niederösterreich': 1698000, 'Steiermark': 1252000, 'Kärnten': 563000, 'Burgenland': 297000},
    'CHE': {'Basel-Stadt': 196000, 'Glarus': 41000, 'Solothurn': 280000, 'Sankt Gallen': 518000, 'Aargau': 703000,
            'Schaffhausen': 84000, 'Thurgau': 286000, 'Zürich': 1564000, 'Genève': 507000, 'Basel-Landschaft': 292000,
            'Vaud': 822000, 'Ticino': 354000, 'Bern': 1047000, 'Lucerne': 420000, 'Uri': 37000, 'Schwyz': 164000,
            'Obwalden': 38600, 'Nidwalden': 44000, 'Zug': 129000, 'Fribourg': 330000, 'Appenzell Ausserrhoden': 55600,
            'Appenzell Innerrhoden': 16300, 'Graubünden': 201000, 'Valais': 353000, 'Neuchâtel': 176000, 'Jura': 74000},
}
_al = {'DEU': {'Saxony': 'Sachsen', 'Bavaria': 'Bayern', 'Rhineland-Palatinate': 'Rheinland-Pfalz', 'Lower Saxony': 'Niedersachsen',
               'North Rhine-Westphalia': 'Nordrhein-Westfalen', 'Mecklenburg-Western Pomerania': 'Mecklenburg-Vorpommern',
               'Free Hanseatic Bremen': 'Bremen', 'Hesse': 'Hessen', 'Thuringia': 'Thüringen', 'Saxony-Anhalt': 'Sachsen-Anhalt'},
       'AUT': {'Lower Austria': 'Niederösterreich', 'Upper Austria': 'Oberösterreich', 'Tyrol': 'Tirol', 'Carinthia': 'Kärnten',
               'Styria': 'Steiermark', 'Vienna': 'Wien'},
       'CHE': {'Grisons': 'Graubünden', 'St. Gallen': 'Sankt Gallen', 'Geneva': 'Genève'},
       'NLD': {'North Brabant': 'Noord-Brabant', 'South Holland': 'Zuid-Holland', 'North Holland': 'Noord-Holland'}}
for _iso, _d in _al.items():
    for _en, _loc in _d.items():
        POP[_iso][_en] = POP[_iso][_loc]
POP['FRA'].update({'Guadeloupe': 384000, 'Guyane française': 286000, 'Martinique': 360000, 'Mayotte': 310000, 'Réunion': 885000})
POP['NLD'].update({'Bonaire': 22000, 'Sint Eustatius': 3200, 'Saba': 2000})
LAYER = {}
PARTIAL = {'ROU'}


def add(g):
    g = g[g.pct.notna()].copy()
    g['geometry'] = g.geometry.apply(make_valid)
    iso = g.iso.iloc[0]
    g['layer'] = LAYER.get(iso, 0); LAYER[iso] = LAYER.get(iso, 0) + 1
    if 'dflt' not in g.columns:
        g['dflt'] = False
    if 'muslims' not in g.columns:
        g['muslims'] = np.nan
    if iso in POP:                      # approximate counts from share x population
        pop = POP[iso]
        est = [pop.get(u, np.nan) * p / 100 for u, p in zip(g.unit, g.pct)]
        miss = [u for u in g.unit if u not in pop]
        if miss:
            print('  [pop] no population for', iso, miss)
        g['muslims'] = [m if m == m else e for m, e in zip(g.muslims, est)]
        g['cnt_est'] = True
    if 'cnt_est' not in g.columns:
        g['cnt_est'] = False
    SUBS.append(g[['iso', 'unit', 'pct', 'src', 'level', 'layer', 'dflt', 'muslims', 'cnt_est', 'geometry']])


reg = pd.read_csv(f'{DATA}/sources_registry.csv')
SRC = dict(zip(reg.iso3, reg.source))

# ---------------------------------------------------------------- India (districts, Census 2011)
d = gpd.read_file(f'{RAW}/2011_Dist.shp').to_crs(4326)
c = pd.read_csv(f'{RAW}/india-districts-census-2011.csv')
c['pct'] = c.Muslims / c.Population * 100
d = d.merge(c[['District code', 'pct', 'Muslims']], left_on='censuscode', right_on='District code', how='left')
d['muslims'] = d.Muslims
d['unit'] = d.DISTRICT; d['iso'] = 'IND'; d['src'] = SRC['IND']; d['level'] = 2
add(d)

# ---------------------------------------------------------------- United Kingdom (local authorities)
uk = gpd.read_file(f'{RAW}/gbr/geogLA2021UK.json').set_crs(4326, allow_override=True)
ew = pd.read_csv(f'{SUB}/GBR_EW.csv'); sn = pd.read_csv(f'{SUB}/GBR_SN.csv')
lut = dict(zip(ew.code, ew.pct)); lut.update(dict(zip(sn.code, sn.pct)))
uk['pct'] = [lut.get(cd, 0.5 if cd.startswith('S') else 0.3 if cd.startswith('N') else np.nan) for cd in uk.AREACD]
uk['dflt'] = [cd not in lut for cd in uk.AREACD]
ukc = dict(x.split(',') for x in open(f'{SUB}/GBR_EW_counts.txt').read().strip().split(';'))
ukc = {k: float(v) for k, v in ukc.items()}
UKPOP = {'S12000049': 622820, 'S12000036': 514990, 'S12000033': 224190, 'S12000042': 148820, 'S12000011': 96580,
         'S12000038': 183810, 'S12000045': 108900, 'S12000029': 327750, 'S12000050': 341370, 'S12000039': 88340,
         'S12000014': 158380, 'S12000030': 92530, 'S12000040': 183820, 'N09000003': 345420}
for cd, p in lut.items():
    if cd in UKPOP:
        ukc[cd] = round(UKPOP[cd] * p / 100, -1)
uk['muslims'] = [ukc.get(cd, np.nan) for cd in uk.AREACD]
uk['unit'] = uk.AREANM; uk['iso'] = 'GBR'; uk['src'] = SRC['GBR']; uk['level'] = 2
add(uk)

# ---------------------------------------------------------------- Russia (federal subjects)
add(attach(ne1('RUS'), read_sub('RUS'), 'RUS', default=0.9, src=SRC['RUS'], cutoff=0.95))

# ---------------------------------------------------------------- China (provinces + Xinjiang prefectures + Linxia)
add(attach(ne1('CHN'), read_sub('CHN'), 'CHN', default=0.15, src=SRC['CHN']))


def decode_echarts(fn):
    j = json.load(open(fn))
    feats = []
    for f in j['features']:
        geom = f['geometry']; polys = []
        if geom['type'] == 'Polygon':
            parts = [geom['coordinates']]; offs = [geom['encodeOffsets']]
        else:
            parts = geom['coordinates']; offs = geom['encodeOffsets']
        for rings, ro in zip(parts, offs):
            dec = []
            for ring, o in zip(rings, ro):
                px, py = o; pts = []
                for i in range(0, len(ring), 2):
                    x = ord(ring[i]) - 64; y = ord(ring[i + 1]) - 64
                    x = (x >> 1) ^ (-(x & 1)); y = (y >> 1) ^ (-(y & 1))
                    x += px; y += py; px, py = x, y
                    pts.append((x / 1024, y / 1024))
                dec.append(pts)
            if len(dec[0]) >= 3:
                polys.append(Polygon(dec[0], [r for r in dec[1:] if len(r) >= 3]))
        feats.append({'name': f['properties']['name'], 'geometry': make_valid(MultiPolygon(polys) if len(polys) > 1 else polys[0])})
    return gpd.GeoDataFrame(feats, crs=4326)


ec = pd.concat([decode_echarts(f'{RAW}/chn/xinjiang.json'), decode_echarts(f'{RAW}/chn/gansu.json')])
zh = {'乌鲁木齐': 'Urumqi', '克拉玛依': 'Karamay', '吐鲁番': 'Turpan', '哈密': 'Hami', '昌吉': 'Changji',
      '博尔塔拉': 'Bortala', '巴音郭楞': 'Bayingolin', '阿克苏': 'Aksu', '克孜勒苏': 'Kizilsu', '喀什': 'Kashgar',
      '和田': 'Hotan', '伊犁': 'Ili', '塔城': 'Tacheng', '阿勒泰': 'Altay', '临夏': 'Linxia',
      '石河子': 'Shihezi', '阿拉尔': 'Aral', '图木舒克': 'Tumxuk', '五家渠': 'Wujiaqu'}
def zhname(n):
    for k, v in zh.items():
        if n.startswith(k):
            return v
    return None
ec['key'] = ec.name.apply(zhname)
ec = ec[ec.key.notna()]
xj = read_sub('CHN_xinjiang')
xlut = dict(zip(xj.unit, xj.pct)); xlut.update({'Shihezi': 3, 'Aral': 8, 'Tumxuk': 65, 'Wujiaqu': 2})
cty = gbf('CHN-ADM2')
cty['pt'] = cty.geometry.representative_point()
pts = gpd.GeoDataFrame(cty[['gname']], geometry=cty.pt, crs=4326)
j = gpd.sjoin(pts, ec[['key', 'geometry']], how='inner', predicate='within')
cty = cty.loc[j.index].assign(key=j.key.values)
pref = cty.dissolve(by='key', as_index=False)
pref['pct'] = pref.key.map(xlut)
pref['unit'] = pref.key; pref['iso'] = 'CHN'; pref['src'] = SRC['CHN']; pref['level'] = 2
print('China prefectures:', len(pref), sorted(pref.key))
add(pref)

# ---------------------------------------------------------------- Indonesia (38 provinces)
ia = gbf('IDN-ADM1'); i2 = gbf('IDN-ADM2')
papua_new = {
    'Papua Selatan': ['Merauke', 'Boven Digoel', 'Mappi', 'Asmat'],
    'Papua Tengah': ['Nabire', 'Paniai', 'Mimika', 'Dogiyai', 'Deiyai', 'Intan Jaya', 'Puncak', 'Puncak Jaya'],
    'Papua Pegunungan': ['Jayawijaya', 'Lanny Jaya', 'Nduga', 'Mamberamo Tengah', 'Yalimo', 'Yahukimo',
                         'Pegunungan Bintang', 'Tolikara'],
    'Papua Barat Daya': ['Sorong', 'Kota Sorong', 'Raja Ampat', 'Sorong Selatan', 'Maybrat', 'Tambrauw'],
}
newmap = {norm(r): p for p, rs in papua_new.items() for r in rs}
pap = ia[ia.gname.isin(['Papua', 'West Papua'])]
i2['pt'] = i2.geometry.representative_point()
inpap = gpd.sjoin(gpd.GeoDataFrame(i2[['gname']], geometry=i2.pt, crs=4326), pap.rename(columns={'gname': 'old'}),
                  predicate='within')
rp = i2.loc[inpap.index].assign(old=inpap.old.values)
def newprov(r):
    k = norm(r.gname)
    if k in newmap:
        return newmap[k]
    return 'Papua' if r.old == 'Papua' else 'Papua Barat'
rp['prov'] = rp.apply(newprov, axis=1)
print('Papua regencies:', rp.groupby('prov').size().to_dict())
pp = rp[['prov', 'geometry']].dissolve(by='prov', as_index=False).rename(columns={'prov': 'gname'})[['gname', 'geometry']]
pp['disp'] = pp.gname
ia2 = pd.concat([ia[~ia.gname.isin(['Papua', 'West Papua'])], pp], ignore_index=True)
idn_alias = {'Bangka-Belitung Islands': 'Kepulauan Bangka Belitung', 'Central Java': 'Jawa Tengah',
             'Central Kalimantan': 'Kalimantan Tengah', 'Central Sulawesi': 'Sulawesi Tengah', 'East Java': 'Jawa Timur',
             'East Kalimantan': 'Kalimantan Timur', 'East Nusa Tenggara': 'Nusa Tenggara Timur',
             'Jakarta Special Capital Region': 'DKI Jakarta', 'North Kalimantan': 'Kalimantan Utara',
             'North Maluku': 'Maluku Utara', 'North Sulawesi': 'Sulawesi Utara', 'North Sumatra': 'Sumatera Utara',
             'Riau Islands': 'Kepulauan Riau', 'South Kalimantan': 'Kalimantan Selatan',
             'South Sulawesi': 'Sulawesi Selatan', 'South Sumatra': 'Sumatera Selatan',
             'Southeast Sulawesi': 'Sulawesi Tenggara', 'Special Region of Yogyakarta': 'DI Yogyakarta',
             'West Java': 'Jawa Barat', 'West Kalimantan': 'Kalimantan Barat', 'West Nusa Tenggara': 'Nusa Tenggara Barat',
             'West Sulawesi': 'Sulawesi Barat', 'West Sumatra': 'Sumatera Barat'}
idk = sub2.indonesia(); idk['iso'] = 'IDN'; idk['src'] = SRC['IDN']; idk['level'] = 2
add(idk)

# ---------------------------------------------------------------- Philippines (provinces)
ph_alias = {'NCR, City of Manila, First District': 'Metropolitan Manila', 'NCR, Fourth District': 'Metropolitan Manila',
            'NCR, Second District': 'Metropolitan Manila', 'NCR, Third District': 'Metropolitan Manila',
            'City of Isabela': 'Basilan', 'Cotabato City': 'Maguindanao', 'Cotabato': 'North Cotabato',
            'Isabela': 'Isabela'}
add(attach(gbf('PHL-ADM2'), read_sub('PHL'), 'PHL', aliases=ph_alias, src=SRC['PHL'], cutoff=0.95))

# ---------------------------------------------------------------- South & SE Asia, misc. NE admin-1 based
lka_alias = {'Ampāra': 'Ampara', 'Anurādhapura': 'Anuradhapura', 'Gālla': 'Galle', 'Hambantŏṭa': 'Hambantota',
             'Kaḷutara': 'Kalutara', 'Kilinŏchchi': 'Kilinochchi', 'Kuruṇægala': 'Kurunegala', 'Kægalla': 'Kegalle',
             'Kŏḷamba': 'Colombo', 'Mahanuvara': 'Kandy', 'Mannārama': 'Mannar', 'Maḍakalapuva': 'Batticaloa',
             'Mulativ': 'Mullaitivu', 'Mātale': 'Matale', 'Mātara': 'Matara', 'Mŏṇarāgala': 'Moneragala',
             'Nuvara Ĕliya': 'Nuwara Eliya', 'Puttalama': 'Puttalam', 'Pŏḷŏnnaruva': 'Polonnaruwa',
             'Trikuṇāmalaya': 'Trincomalee', 'Vavuniyāva': 'Vavuniya', 'Yāpanaya': 'Jaffna'}
add(attach(ne1('LKA'), read_sub('LKA'), 'LKA', aliases=lka_alias, src=SRC['LKA']))
add(attach(ne1('THA'), read_sub('THA'), 'THA', src=SRC['THA'], cutoff=0.95))
add(attach(ne1('MYS'), read_sub('MYS'), 'MYS', src=SRC['MYS']))
mmr = read_sub('MMR')
g = ne1('MMR')
add(attach(g, mmr, 'MMR', src=SRC['MMR']))
add(attach(gbf('BGD-ADM2'), read_sub('BGD'), 'BGD', src=SRC['BGD'], cutoff=0.7,
           aliases={'Brahamanbaria': 'Brahmanbaria', 'Chittagong': 'Chattogram', 'Comilla': 'Cumilla',
                    'Nawabganj': 'Chapai Nawabganj', 'Netrakona': 'Netrokona'}))
pak_alias = {'Karachi': 'Karachi South', 'Nawabshah': 'Shaheed Benazirabad', 'Naushehro Feroze': 'Naushahro Feroze',
             'Jafarabad': 'Jaffarabad', 'Kachhi': 'Kacchi'}
pk = attach(gbf('PAK-ADM2'), read_sub('PAK'), 'PAK', aliases=pak_alias, src=SRC['PAK'], default=97.8, cutoff=0.9)
pk.loc[pk.gname == 'Islamabad Capital Territory', 'pct'] = 95.5
pk.loc[pk.gname == 'Islamabad Capital Territory', 'dflt'] = False
add(pk)
add(attach(gbf('NPL-ADM1'), read_sub('NPL'), 'NPL', aliases={'Province 1': 'Koshi', 'Province 2': 'Madhesh',
                                                           'Sudurpaschim': 'Sudurpashchim'}, src=SRC['NPL']))

# ---------------------------------------------------------------- Central Asia, Caucasus, Mongolia, Middle East
add(attach(ne1('KAZ'), read_sub('KAZ'), 'KAZ', aliases={'Almaty City': 'Almaty (city)'}, src=SRC['KAZ']))
add(attach(ne1('KGZ'), read_sub('KGZ'), 'KGZ', aliases={'Chuy': 'Chüy'}, src=SRC['KGZ']))
add(attach(ne1('GEO'), read_sub('GEO'), 'GEO', aliases={'Racha-Lechkhumi-Kvemo Svaneti': 'Racha-Lochkhumi-Kvemo Svaneti'},
           src=SRC['GEO']))
add(attach(ne1('MNG'), read_sub('MNG'), 'MNG', default=0.1, src=SRC['MNG']))
add(attach(ne1('ISR'), read_sub('ISR'), 'ISR', aliases={'HaDarom': 'Southern', 'HaMerkaz': 'Central',
                                                       'HaZafon': 'Northern'}, src=SRC['ISR']))
psx = ne1('PSX'); psx['unit'] = psx.gname; psx['pct'] = psx.gname.map({'Gaza Strip': 99.0, 'West Bank': 85.0})
psx['iso'] = 'PSX'; psx['src'] = SRC['PSE']; psx['level'] = 1
add(psx)
add(attach(ne1('EGY'), read_sub('EGY'), 'EGY', default=97.5, src=SRC['EGY']))

# ---------------------------------------------------------------- Africa
add(attach(gbf('KEN-ADM1'), read_sub('KEN'), 'KEN', src=SRC['KEN'], cutoff=0.8,
           aliases={'Elgeyo-Marakwet': 'ELGEYO/MARAKWET', 'Taita Taveta': 'TAITA/TAVETA', 'Tharaka': 'THARAKA-NITHI'}))
add(attach(gbf('ETH-ADM2'), read_sub('ETH'), 'ETH', src=SRC['ETH'], cutoff=0.95))
add(attach(ne1('NGA'), read_sub('NGA'), 'NGA', src=SRC['NGA']))
uga_parent = {'Agago': 'Pader', 'Alebtong': 'Lira', 'Amolatar': 'Lira', 'Amudat': 'Nakapiripirit', 'Amuria': 'Katakwi',
              'Amuru': 'Gulu', 'Abim': 'Kotido', 'Budaka': 'Pallisa', 'Bududa': 'Mbale', 'Buhweju': 'Bushenyi',
              'Buikwe': 'Mukono', 'Bukedea': 'Kumi', 'Bukomansimbi': 'Masaka', 'Bukwa': 'Kapchorwa',
              'Bulambuli': 'Sironko', 'Buliisa': 'Masindi', 'Butaleja': 'Tororo', 'Butambala': 'Mpigi',
              'Buvuma': 'Mukono', 'Buyende': 'Kamuli', 'Dokolo': 'Lira', 'Gomba': 'Mpigi', 'Ibanda': 'Mbarara',
              'Isingiro': 'Mbarara', 'Kaabong': 'Kotido', 'Kaliro': 'Kamuli', 'Kalungu': 'Masaka', 'Kibale': 'Kibaale',
              'Kibuku': 'Pallisa', 'Kiryandongo': 'Masindi', 'Koboko': 'Arua', 'Kole': 'Apac', 'Kween': 'Kapchorwa',
              'Kyankwanzi': 'Kiboga', 'Kyegegwa': 'Kyenjojo', 'Lamwo': 'Kitgum', 'Luuka': 'Iganga', 'Luweero': 'Luwero',
              'Lwengo': 'Masaka', 'Lyantonde': 'Rakai', 'Manafwa': 'Mbale', 'Maracha': 'Arua', 'Mitooma': 'Bushenyi',
              'Mityana': 'Mubende', 'Nakaseke': 'Luwero', 'Namayingo': 'Bugiri', 'Namutumba': 'Iganga',
              'Napak': 'Moroto', 'Ngora': 'Kumi', 'Ntoroko': 'Bundibugyo', 'Nwoya': 'Gulu', 'Otuke': 'Lira',
              'Oyam': 'Apac', 'Rubirizi': 'Bushenyi', 'Serere': 'Soroti', 'Sheema': 'Bushenyi', 'Zombo': 'Nebbi',
              'Kitgum': 'Kitgum'}
add(attach(ne1('UGA'), read_sub('UGA'), 'UGA', aliases=uga_parent, src=SRC['UGA'], cutoff=0.9))
tz_alias = {'Kaskazini-Pemba': 'Pemba North', 'Kusini-Pemba': 'Pemba South', 'Kaskazini-Unguja': 'Zanzibar North'}
add(attach(ne1('TZA'), read_sub('TZA'), 'TZA', aliases=tz_alias, src=SRC['TZA']))
add(attach(gbf('MWI-ADM2'), read_sub('MWI'), 'MWI', src=SRC['MWI']))
add(attach(gbf('MOZ-ADM1'), read_sub('MOZ'), 'MOZ', src=SRC['MOZ']))
add(attach(gbf('GHA-ADM1'), read_sub('GHA'), 'GHA', src=SRC['GHA']))
add(attach(gbf('CIV-ADM1'), read_sub('CIV'), 'CIV', src=SRC['CIV'], cutoff=0.7,
           aliases={"District Autonome D'Abidjan": 'Abidjan', 'District Autonome De Yamoussoukro': 'Yamoussoukro'}))
bf = read2('BFA')
bfg = attach(gbf('BFA-ADM2'), bf, 'BFA', src=SRC['BFA'], cutoff=0.9)
est = dict(zip(bf.unit, bf.est)); breg = dict(zip(bf.unit, bf.region))
m_ = match_names(bfg.gname.tolist(), bf.unit.tolist(), cutoff=0.9, verbose=False)
bfg['k'] = bfg.gname.map(m_)
bfg.loc[bfg.k.map(est) == 1, 'unit'] = bfg.k.map(breg)      # modelled regions shown as one unit
bfg.loc[bfg.k.map(est) == 1, 'src'] = ('ESTIMATE — region not published in accessible RGPH 2006 tables; '
                                       'modelled to the 2006 census national total (60.5%)')
add(bfg.drop(columns='k'))
add(attach(gbf('CMR-ADM1'), read_sub('CMR'), 'CMR', src=SRC['CMR'],
           aliases={'Far North': 'Extrême-Nord', 'North': 'Nord', 'East': 'Est', 'South': 'Sud', 'West': 'Ouest',
                    'North-West': 'Nord-Ouest', 'South-West': 'Sud-Ouest'}))
add(attach(gbf('TCD-ADM1'), read_sub('TCD'), 'TCD', src=SRC['TCD'], default=97.0,
           aliases={"N'Djamena Region": "Ville de N'Djamena"}))
add(attach(gbf('TGO-ADM1'), read_sub('TGO'), 'TGO', src=SRC['TGO']))
add(attach(gbf('BEN-ADM1'), read_sub('BEN'), 'BEN', src=SRC['BEN'], cutoff=0.75,
           aliases={'Atakora': 'Atacora', 'Atlanique': 'Atlantique', 'Kouffo': 'Couffo', 'Oueme': 'Ouémé'}))
add(attach(ne1('SLE'), read_sub('SLE'), 'SLE', src=SRC['SLE']))
add(attach(gbf('LBR-ADM1'), read_sub('LBR'), 'LBR', src=SRC['LBR'], default=2.0, aliases={'Gbarpolu': 'Gbapolu'}))
add(attach(gbf('ERI-ADM1'), read_sub('ERI'), 'ERI', src=SRC['ERI'],
           aliases={'Northen Red Sea Region': 'Semenawi Keyih Bahri', 'Southern Red Sea Region': 'Debubawi Keyih Bahri'}))
add(attach(gbf('CAF-ADM1'), read_sub('CAF'), 'CAF', src=SRC['CAF'], default=2.0))
add(attach(gbf('ZAF-ADM1'), read2('ZAF'), 'ZAF', src=SRC['ZAF'], aliases={'Nothern Cape': 'Northern Cape'}))
add(attach(ne1('MDG'), read_sub('MDG'), 'MDG', src=SRC['MDG'], default=0.8))
add(attach(gbf('GNB-ADM1'), read2('GNB'), 'GNB', src=SRC['GNB']))
add(attach(gbf('GIN-ADM1'), read2('GIN'), 'GIN', src=SRC['GIN']))
add(attach(ne1('SEN'), read_sub('SEN'), 'SEN', src=SRC['SEN'], default=98.0))

# ---------------------------------------------------------------- Europe
add(attach(ne1('BGR'), read_sub('BGR'), 'BGR', src=SRC['BGR']))
add(attach(ne1('ALB'), read_sub('ALB'), 'ALB', src=SRC['ALB']))
mk_alias = {'Drugovo': 'Kičevo', 'Oslomej': 'Kičevo', 'Vraneštica': 'Kičevo', 'Zajas': 'Kičevo', 'Brod': 'Makedonski Brod',
            'Kavadartsi': 'Kavadarci', 'Strumitsa': 'Strumica', 'Mavrovo and Rostusa': 'Mavrovo and Rostuša',
            'Vrapcište': 'Vrapčište', 'Čučer Sandevo': 'Čučer-Sandevo', 'Centar župa': 'Centar Župa'}
mk = attach(ne1('MKD'), read_sub('MKD'), 'MKD', aliases=mk_alias, src=SRC['MKD'])
mk.loc[mk.gname == 'Skopje', 'pct'] = 21.0
mk.loc[mk.gname == 'Skopje', 'dflt'] = False
add(mk)
add(attach(gbf('MNE-ADM1'), read_sub('MNE'), 'MNE', src=SRC['MNE']))
srb = gbf('SRB-ADM2'); srb['gname'] = srb.gname.str.replace(r' (Municipality|City|Municipal\*)$', '', regex=True)
add(attach(srb, read_sub('SRB'), 'SRB', src=SRC['SRB'], default=0.5, cutoff=0.9))
kos_alias = {'Kosovska Mitrovica': 'Mitrovicë', 'Štrpce': 'Shtërpcë', 'Novo Brdo': 'Novobërdë', 'Klina': 'Klinë',
             'Đakovica': 'Gjakovë', 'Vitina': 'Viti', 'Lipljan': 'Lipjan'}
add(attach(ne1('KOS'), read_sub('KOS'), 'KOS', aliases=kos_alias, default=98.0, src=SRC['KOS'], cutoff=0.95))
add(attach(gbf('BIH-ADM2'), read_sub('BIH'), 'BIH', src=SRC['BIH'], cutoff=0.6,
           aliases={'Bosnian-Podrinje Canton Goražde': 'Bosnian Podrinje', 'Brcko District': 'Brčko'}))
gr = ne1('GRC'); grv = {'Attiki': 7.0, 'Kentriki Makedonia': 3.0, 'Anatoliki Makedonia kai Thraki': 2.0, 'Ayion Oros': 0.0}
gr['unit'] = gr.gname; gr['dflt'] = ~gr.gname.isin(list(grv)); gr['pct'] = gr.gname.map(grv).fillna(2.5); gr['iso'] = 'GRC'; gr['src'] = SRC['GRC']; gr['level'] = 1
add(gr)
add(attach(gbf('GRC-ADM3'), read_sub('GRC'), 'GRC', src=SRC['GRC'], default=None, cutoff=0.9,
           aliases={'Mykis': 'Myki', 'Arrianon': 'Arriana', 'Iasmou': 'Iasmos', 'Maronias-Sapon': 'Maroneia-Sapes',
                    'Avdiron': 'Avdira', 'Topirou': 'Topeiros', 'Soufliou': 'Soufli'}))
add(attach(ne1('DEU'), read_sub('DEU'), 'DEU', src=SRC['DEU']))
add(attach(ne1('AUT'), read_sub('AUT'), 'AUT', src=SRC['AUT']))
add(attach(ne1('CHE'), read_sub('CHE'), 'CHE', src=SRC['CHE']))
nl = attach(ne1('NLD'), read_sub('NLD'), 'NLD', src=SRC['NLD'])
nl.loc[nl.gname.isin(['Bonaire', 'St. Eustatius', 'Saba']), 'pct'] = 0.5
add(nl)
add(attach(ne1('BEL', 'region'), read_sub('BEL'), 'BEL', src=SRC['BEL'],
           aliases={'Capital Region': 'Brussels', 'Flemish': 'Flanders', 'Walloon': 'Wallonia'}))
fra = attach(ne1('FRA', 'region'), read_sub('FRA'), 'FRA', src=SRC['FRA'])
fra.loc[fra.gname == 'Guadeloupe', 'pct'] = 0.37; fra.loc[fra.gname == 'Martinique', 'pct'] = 0.22
fra.loc[fra.gname == 'Guyane française', 'pct'] = 0.92; fra.loc[fra.gname == 'Mayotte', 'pct'] = 98.8
fra.loc[fra.gname == 'Réunion', 'pct'] = 4.2
fra.loc[fra.gname.isin(['Guadeloupe', 'Martinique', 'Guyane française', 'Mayotte', 'Réunion']), 'dflt'] = False
add(fra)
# Spain: community totals (UCIDE 2019 scaled to 2024) distributed over provinces by UCIDE's provincial counts
esp_c = read_sub('ESP')
_ca = {'Principado de Asturias': 'Asturias', 'Comunidad Foral de Navarra': 'Foral de Navarra',
       'Comunidad de Madrid': 'Madrid', 'Región de Murcia': 'Murcia', 'Comunidad Valenciana': 'Valenciana'}
cpct = {_ca.get(u, u): p for u, p in zip(esp_c.unit, esp_c.pct)}
ep = read2('ESP_prov')
ccnt = {k: cpct[k] * POP['ESP'][k] / 100 for k in ep.ccaa.unique()}
ush = ep.groupby('ccaa').ucide.sum()
ep['muslims'] = [ccnt[c] * u / ush[c] for c, u in zip(ep.ccaa, ep.ucide)]
ep['pct'] = ep.muslims / ep['pop'] * 100
ESPN = {'Alava': 'Álava', 'Almeria': 'Almería', 'Avila': 'Ávila', 'Balears, Illes': 'Illes Balears', 'Caceres': 'Cáceres',
        'Cadiz': 'Cádiz', 'Castellon': 'Castellón', 'Cordoba': 'Córdoba', 'Coruna': 'A Coruña', 'Jaen': 'Jaén',
        'Leon': 'León', 'Malaga': 'Málaga', 'Palmas, Las': 'Las Palmas', 'Rioja, La': 'La Rioja'}
es = gbf('ESP-ADM2')
es = es.merge(ep[['unit', 'pct', 'muslims']], left_on='gname', right_on='unit', how='left')
assert es.pct.notna().all(), es.gname[es.pct.isna()].tolist()
es['unit'] = es.gname.map(lambda n: ESPN.get(n, n))
for u, pp in zip(es.unit, es.gname.map(dict(zip(ep.unit, ep['pop'])))):
    POP['ESP'][u] = pp
es['dflt'] = False; es['iso'] = 'ESP'; es['src'] = SRC['ESP']; es['level'] = 2
add(es)
add(attach(gbf('HRV-ADM1'), read2('HRV'), 'HRV', src=SRC['HRV'], aliases={'City of Zagreb': 'Grad Zagreb', 'Zagreb County': 'Zagreb County'}))
rou = ne1('ROU'); rou['unit'] = rou.gname; rou['pct'] = np.where(rou.gname == 'Constanta', 5.6, np.where(rou.gname == 'Tulcea', 0.8, np.nan))
rou['muslims'] = np.where(rou.gname == 'Constanta', 36725, np.nan); rou['iso'] = 'ROU'; rou['src'] = SRC['ROU']; rou['level'] = 1
add(rou)

# ---------------------------------------------------------------- Americas & Oceania
add(attach(ne1('USA'), read_sub('USA'), 'USA', src=SRC['USA']))
cn = sub2.canada(); cn['iso'] = 'CAN'; cn['src'] = SRC['CAN']; cn['level'] = 2
add(cn)
au = sub2.australia(); au['iso'] = 'AUS'; au['src'] = SRC['AUS']; au['level'] = 2
add(au)
add(attach(gbf('SUR-ADM1'), read_sub('SUR'), 'SUR', src=SRC['SUR']))
add(attach(gbf('GUY-ADM1'), read2('GUY'), 'GUY', src=SRC['GUY'], cutoff=0.8))
add(attach(gbf('KHM-ADM1'), read2('KHM'), 'KHM', src=SRC['KHM'], cutoff=0.8,
           aliases={'Bantey Meanchey': 'Banteay Meanchey', 'Ratanakiri Province': 'Ratanakiri'}))

subs = gpd.GeoDataFrame(pd.concat(SUBS, ignore_index=True), crs=4326)
print('subunits:', len(subs), 'countries:', subs.iso.nunique())

# ---------------------------------------------------------------- clip to Natural Earth outlines, fill residual slivers
iso_fix = {'PSX': 'PSX'}
out = []
for iso, g in subs.groupby('iso'):
    cpoly = make_valid(unary_union(base[base.ADM0_A3 == iso].geometry.values))
    layers = sorted(g.layer.unique())
    pieces = []; covered = None
    for L in reversed(layers):           # finer / later layers take precedence
        gl = g[g.layer == L].copy()
        gl['geometry'] = gl.geometry.intersection(cpoly)
        if covered is not None:
            gl['geometry'] = gl.geometry.difference(covered)
        gl = gl[~gl.geometry.is_empty]
        lu = unary_union(gl.geometry.values)
        covered = lu if covered is None else unary_union([covered, lu])
        pieces.append(gl)
    pg = gpd.GeoDataFrame(pd.concat(pieces, ignore_index=True), crs=4326)
    if iso not in PARTIAL:
        resid = cpoly.difference(covered)
        if not resid.is_empty:
            rr = gpd.GeoDataFrame(geometry=list(getattr(resid, 'geoms', [resid])), crs=4326)
            rr = rr[rr.geometry.area > 1e-9]
            if len(rr):
                near = gpd.sjoin_nearest(rr.to_crs(3857), pg[['pct', 'unit', 'src', 'level', 'layer', 'dflt', 'muslims', 'cnt_est', 'geometry']].to_crs(3857),
                                         how='left').to_crs(4326)
                near = near[~near.index.duplicated()]
                near['iso'] = iso
                pg = pd.concat([pg, near[['iso', 'unit', 'pct', 'src', 'level', 'layer', 'dflt', 'muslims', 'cnt_est', 'geometry']]], ignore_index=True)
    out.append(pg)
subs = gpd.GeoDataFrame(pd.concat(out, ignore_index=True), crs=4326)
subs = subs[~subs.geometry.is_empty]
def safe_union(geoms):
    geoms = [make_valid(g) for g in geoms]
    try:
        return make_valid(unary_union(geoms))
    except Exception:
        try:
            return make_valid(unary_union([g.buffer(0) for g in geoms]))
        except Exception:
            polys = []
            for g in geoms:
                polys += [p for p in getattr(g, 'geoms', [g]) if p.geom_type == 'Polygon']
            return MultiPolygon(polys)
subs['dflt'] = subs.dflt.fillna(False).astype(bool)
subs.loc[subs.dflt, 'unit'] = ''          # unmatched units sharing a fallback value: merged, unlabelled
subs.loc[subs.dflt, 'muslims'] = np.nan
rows = []
for k, grp in subs.groupby(['iso', 'unit', 'pct', 'level', 'layer', 'dflt']):
    mu = grp.muslims.dropna()
    rows.append({'iso': k[0], 'unit': k[1], 'pct': k[2], 'level': k[3], 'layer': k[4], 'dflt': k[5],
                 'src': grp.src.iloc[0], 'muslims': mu.iloc[0] if len(mu) else np.nan,
                 'cnt_est': bool(grp.cnt_est.fillna(False).any()),
                 'geometry': safe_union(grp.geometry.values)})
subs = gpd.GeoDataFrame(rows, crs=4326)
# keep only polygonal parts
def polyonly(g):
    if g.geom_type in ('Polygon', 'MultiPolygon'):
        return g
    ps = [p for p in getattr(g, 'geoms', []) if p.geom_type in ('Polygon', 'MultiPolygon')]
    return unary_union(ps) if ps else None
subs['geometry'] = subs.geometry.apply(polyonly)
subs = subs[subs.geometry.notna() & ~subs.geometry.is_empty]

DISPLAY_FIX = {'Province 1': 'Koshi', 'Province 2': 'Madhesh', 'Sudurpaschim': 'Sudurpashchim',
    'NCR, City of Manila, First': 'Metro Manila', 'NCR, Fourth': 'Metro Manila', 'NCR, Second': 'Metro Manila',
    'NCR, Third': 'Metro Manila', "District Autonome D'Abidjan": 'Abidjan', 'District Autonome De Yamoussoukro': 'Yamoussoukro',
    'KT': 'Kembata Tembaro', 'Region 14': 'Addis Ababa', 'Oromia': 'Oromia Zone', 'Hareri': 'Harari', 'Selti': 'Silte',
    'Zone 1': 'Afar Zone 1', 'Zone 2': 'Afar Zone 2', 'Zone 3': 'Afar Zone 3', 'Zone 4': 'Afar Zone 4', 'Zone 5': 'Afar Zone 5',
    'North Shewa(R3)': 'North Shewa (Amhara)', 'North Shewa(R4)': 'North Shewa (Oromia)', 'Valle Du Bandama': 'Vallée du Bandama',
    'Comoe': 'Comoé', 'Denguele': 'Denguélé', 'Goh-Djiboua': 'Gôh-Djiboua', 'Sassandra-Marahoue': 'Sassandra-Marahoué',
    'Bosnian-Podrinje Goražde': 'Bosnian Podrinje', 'Brcko': 'Brčko', 'Northen Red Sea': 'Northern Red Sea',
    'Nothern Cape': 'Northern Cape', 'Atlanique': 'Atlantique', 'Gabu': 'Gabú', 'Central': 'Central', 'Eastern': 'Eastern',
    'Kemashi': 'Kamashi', 'Gedio': 'Gedeo', 'Awi/Agew': 'Awi', 'Ilubabor': 'Illubabor', 'Brahamanbaria': 'Brahmanbaria',
    'Region of Murcia': 'Murcia', 'Boke': 'Boké', 'Labe': 'Labé', 'Nzerekore': 'Nzérékoré',
    'Bantey Meanchey': 'Banteay Meanchey', 'Kratie': 'Kratié', 'Takeo': 'Takéo', 'Barina-Waini': 'Barima-Waini',
    'Bale': 'Balé', 'Comoe': 'Comoé', 'Leraba': 'Léraba', 'Kenedougou': 'Kénédougou', 'Passore': 'Passoré',
    'Kourweogo': 'Kourwéogo', 'Zadar County': 'Zadar', 'Constanta': 'Constanța', 'Autonomous Republic of Crimea': 'Crimea', 'Jewish': 'Jewish Autonomous Oblast', 'Magadan': 'Magadan', 'Maga Buryatdan': 'Magadan'}
subs['unit'] = subs.unit.astype(str).str.strip().map(lambda u: DISPLAY_FIX.get(u, u))
subs.loc[(subs.iso == 'ETH') & subs.unit.isin(['Central', 'Eastern', 'Southern', 'Western', 'North Western']), 'unit'] = \
    subs.loc[(subs.iso == 'ETH') & subs.unit.isin(['Central', 'Eastern', 'Southern', 'Western', 'North Western']), 'unit'] + ' Tigray'
base.to_file(f'{DATA}/units_national.gpkg', driver='GPKG')
subs.to_file(f'{DATA}/units_sub.gpkg', driver='GPKG')
print('done', len(base), len(subs))

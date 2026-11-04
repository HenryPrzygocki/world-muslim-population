"""Assemble the world layer of statistical units with Muslim-share values (WGS84)."""
import sys, warnings
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import MultiPolygon
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
pew_alias = {  # (French overseas departments are matched by their own map units below)
'Cape Verde': 'Cabo Verde', 'Macao': 'Macao S.A.R', 'Palestinian territories': 'Palestine',
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
extra = {  # territories Pew does not list: only figures with a source; everything else has no value
    'Somaliland': (nat['Somalia'][0], 'Pew Research Center 2020 estimate for Somalia (covers Somaliland)'),
    'Liechtenstein': (5.9, 'Liechtenstein census 2020'), 'Gibraltar': (4.0, 'Gibraltar census 2012'),
    'Northern Cyprus': (nat['Cyprus'][0], 'Pew Research Center 2020 estimate for the whole island of Cyprus'),
    'Dhekelia Sovereign Base Area': (nat['Cyprus'][0], 'Pew Research Center 2020 estimate for the whole island of Cyprus'),
    'Akrotiri Sovereign Base Area': (nat['Cyprus'][0], 'Pew Research Center 2020 estimate for the whole island of Cyprus'),
}
nat.update(extra)
nat['Cyprus'] = (nat['Cyprus'][0], 'Pew Research Center 2020 estimate for the whole island of Cyprus')
NODATA = {'Antarctica', 'Bir Tawil', 'Brazilian Island', 'Siachen Glacier', 'Spratly Islands', 'Scarborough Reef',
          'Bajo Nuevo Bank (Petrel Is.)', 'Serranilla Bank', 'Clipperton Island', 'Coral Sea Islands',
          'Ashmore and Cartier Islands', 'Southern Patagonian Ice Field', 'Cyprus No Mans Area',
          'Heard Island and McDonald Islands', 'French Southern and Antarctic Lands', 'South Georgia and the Islands',
          'British Indian Ocean Territory', 'United States Minor Outlying Islands'}

GEOU = {}   # map units inside a country that have their own Pew figure, or none
for _pn, _gu in [('French Guiana', 'French Guiana'), ('Guadeloupe', 'Guadeloupe'), ('Martinique', 'Martinique'),
                 ('Mayotte', 'Mayotte'), ('Reunion', 'Reunion')]:
    _r = pew[pew.country == _pn]
    if len(_r): GEOU[_gu] = (float(_r.pct.iloc[0]), 'Pew Research Center 2020 estimate'); natcnt[_gu] = float(_r.muslims_2020.iloc[0])
GEOU['Caribbean Netherlands'] = (np.nan, 'no figure')
# territories Pew does not cover: published census counts (data/territories.csv); year of every non-Pew national figure
NATYEAR = {'Liechtenstein': 2020, 'Gibraltar': 2012}
for _t in pd.read_csv(f'{DATA}/territories.csv', comment='#').itertuples():
    GEOU[_t.geounit] = (_t.muslims / _t.total * 100, _t.source); natcnt[_t.geounit] = _t.muslims; NATYEAR[_t.geounit] = _t.year
base = NE0[['ADMIN', 'ADM0_A3', 'GEOUNIT', 'GU_A3', 'NAME', 'LABELRANK', 'POP_EST', 'geometry']].copy()
# overseas departments with their own figure are map units of their own (own code, name and label)
OVERSEAS = {'French Guiana': 'GUF', 'Martinique': 'MTQ', 'Guadeloupe': 'GLP', 'Reunion': 'REU', 'Mayotte': 'MYT',
            'Caribbean Netherlands': 'BES', 'Christmas Island': 'CXR', 'Cocos (Keeling) Islands': 'CCK'}
_ov = base.GEOUNIT.isin(list(OVERSEAS))
base.loc[_ov, 'ADM0_A3'] = base.loc[_ov, 'GEOUNIT'].map(OVERSEAS)
_ovadmin = base.loc[_ov, 'ADMIN'].copy()
vals, srcs, yrs = [], [], []
for _, r in base.iterrows():
    yrs.append(NATYEAR.get(r.GEOUNIT, NATYEAR.get(r.ADMIN)))
    if r.ADMIN in NODATA:
        vals.append(np.nan); srcs.append('no permanent population'); continue
    v = GEOU.get(r.GEOUNIT) if r.GEOUNIT in GEOU else (nat.get(r.ADMIN) or nat.get(r.GEOUNIT))
    if v is None:
        print('!! no national value for', r.ADMIN, r.GEOUNIT)
        vals.append(np.nan); srcs.append('')
    else:
        vals.append(v[0]); srcs.append(v[1])
base['pct'] = vals; base['src'] = srcs
# kind of national figure: p Pew estimate, c census, n none; year of the figure
base['basis'] = ['n' if p != p else 'p' if s_.startswith('Pew') else 'c' for p, s_ in zip(base.pct, base.src)]
base['year'] = [2020 if b == 'p' else y if b == 'c' else np.nan for b, y in zip(base.basis, yrs)]
assert not ((base.basis == 'c') & base.year.isna()).any(), base[(base.basis == 'c') & base.year.isna()].ADMIN.tolist()
base.loc[_ov, 'ADMIN'] = base.loc[_ov, 'GEOUNIT'].replace({'Reunion': 'Réunion'})
base['level'] = 0
base['iso'] = base.ADM0_A3
base['unit'] = base.GEOUNIT
base['muslims'] = [natcnt.get(g_) if g_ in GEOU else natcnt.get(a_) for a_, g_ in zip(base.ADMIN, base.GEOUNIT)]


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
    if 'year' in df.columns:
        yr = dict(zip(df[key].astype(str), df.year))
        g['year'] = [yr.get(m.get(n), np.nan) if n in m else np.nan for n in g.gname]
    # several geo units matched to one data row (e.g. new districts of an old one): show them as that one unit
    tgt = pd.Series([m.get(n) for n in g.gname], index=g.index)
    multi = tgt.notna() & tgt.duplicated(keep=False)
    g.loc[multi, 'unit'] = tgt[multi]
    g['iso'] = iso; g['src'] = src; g['level'] = 1
    return g


SUBS = []
LAYER = {}
PARTIAL = {'ROU'}


def add(g):
    if 'dflt' not in g.columns:
        g['dflt'] = False
    g = g[g.pct.notna() | g.dflt.astype(bool)].copy()
    g['geometry'] = g.geometry.apply(make_valid)
    iso = g.iso.iloc[0]
    g['layer'] = LAYER.get(iso, 0); LAYER[iso] = LAYER.get(iso, 0) + 1
    if 'muslims' not in g.columns:
        g['muslims'] = np.nan
    if 'year' not in g.columns:
        g['year'] = np.nan                      # per-area source year where it differs from the country's
    SUBS.append(g[['iso', 'unit', 'pct', 'src', 'level', 'layer', 'dflt', 'muslims', 'year', 'geometry']])


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
ni = pd.read_csv(f'{S2}/GBR_NI_2021.csv', comment='#')          # NISRA Census 2021, MS-B20 (Muslim ÷ all usual residents)
lut = dict(zip(ew.code, ew.pct)); lut.update(dict(zip(sn.code, sn.pct))); lut.update(dict(zip(ni.code, ni.muslims / ni.total * 100)))
uk['pct'] = [lut.get(cd, np.nan) for cd in uk.AREACD]
uk['dflt'] = [cd not in lut for cd in uk.AREACD]
ukc = dict(x.split(',') for x in open(f'{SUB}/GBR_EW_counts.txt').read().strip().split(';'))
ukc = {k: float(v) for k, v in ukc.items()}; ukc.update(dict(zip(ni.code, ni.muslims.astype(float))))
uk['muslims'] = [ukc.get(cd, np.nan) for cd in uk.AREACD]
uk['unit'] = uk.AREANM; uk['iso'] = 'GBR'; uk['src'] = SRC['GBR']; uk['level'] = 2
uk['year'] = [2022 if cd.startswith('S') else 2021 for cd in uk.AREACD]
add(uk)

# ---------------------------------------------------------------- Russia (federal subjects)
# 2010 census, every federal subject: traditionally Muslim nationalities ÷ persons who stated a nationality (sub2.py)
_ru = sub2.russia_2010().set_index('ne')
_g = NE1[(NE1.adm0_a3 == 'RUS') & NE1.name.notna()][['name', 'geometry']].rename(columns={'name': 'gname'}).copy()
_g['unit'] = [_ru.unit.get(n, n) for n in _g.gname]
_g['pct'] = [_ru.pct.get(n, np.nan) for n in _g.gname]
_g['muslims'] = [_ru.muslims.get(n, np.nan) for n in _g.gname]
_g['src'] = SRC['RUS']; _g['dflt'] = False
# Crimea (annexed by Russia, internationally recognised as Ukraine): Russia's 2014 census of the peninsula, table 4.6
# "Population of selected nationalities" — Crimean Tatars 228,830 + Tatars 42,082 + Azerbaijanis 3,715 of 1,819,434
# persons who stated a nationality. Sevastopol: no figure collected.
_ci = _g.gname == 'Crimea'
_g.loc[_ci, 'pct'] = (228830 + 42082 + 3715) / 1819434 * 100; _g.loc[_ci, 'muslims'] = 228830 + 42082 + 3715
_g.loc[_ci, 'src'] = ('Rosstat — 2014 census of the Crimean Federal District, table 4.6 (Crimean Tatars, Tatars and '
                      'Azerbaijanis, the Muslim nationalities the table lists, ÷ persons who stated a nationality)')
_g.loc[_ci, 'year'] = 2014
_g.loc[_g.gname == 'Sevastopol', 'dflt'] = True
_miss = _g[_g.pct.isna() & ~_g.dflt].gname.tolist()
assert _miss == [], _miss
_g['iso'] = 'RUS'; _g['level'] = 1
add(_g)

# ---------------------------------------------------------------- China (provinces)
# 2010 census, every province: the ten traditionally Muslim nationalities ÷ total population (sub2.py)
_cn = sub2.china_2010().set_index('ne')
_g = NE1[(NE1.adm0_a3 == 'CHN') & NE1.name.isin(_cn.index)][['name', 'geometry']].rename(columns={'name': 'gname'}).copy()
assert len(_g) == 31, len(_g)
_g['unit'] = [_cn.unit[n] for n in _g.gname]; _g['pct'] = [_cn.pct[n] for n in _g.gname]
_g['muslims'] = [_cn.muslims[n] for n in _g.gname]
_g['src'] = SRC['CHN']; _g['dflt'] = False; _g['iso'] = 'CHN'; _g['level'] = 1
add(_g)

# ---------------------------------------------------------------- Indonesia (regencies and cities)
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
# NSO 2010 census (49 provinces with a published religion table) and 2000 census for the others it does not cover;
# 0.1 rows in THA.csv were placeholders and are not used
_k = lambda x: ''.join(ch for ch in str(x).lower() if ch.isalnum())
_t10 = pd.read_csv(f'{S2}/THA_2010.csv'); _t10['pct'] = _t10.pct_published; _t10['year'] = 2010
_t00 = read_sub('THA'); _t00 = _t00[(_t00.pct != 0.1) & ~_t00.unit.map(_k).isin(set(_t10.unit.map(_k)))].copy()
_t00['muslims'] = np.nan; _t00['year'] = 2000
_th = pd.concat([_t10[['unit', 'pct', 'muslims', 'year']], _t00[['unit', 'pct', 'muslims', 'year']]], ignore_index=True)
add(attach(ne1('THA'), _th, 'THA', src=SRC['THA'], cutoff=0.95))
add(attach(ne1('MYS'), read_sub('MYS'), 'MYS', src=SRC['MYS']))
mmr = read_sub('MMR')
g = ne1('MMR')
add(attach(g, mmr, 'MMR', src=SRC['MMR']))
add(attach(gbf('BGD-ADM2'), read_sub('BGD'), 'BGD', src=SRC['BGD'], cutoff=0.7,
           aliases={'Brahamanbaria': 'Brahmanbaria', 'Chittagong': 'Chattogram', 'Comilla': 'Cumilla',
                    'Nawabganj': 'Chapai Nawabganj', 'Netrakona': 'Netrokona'}))
add(attach(gbf('NPL-ADM1'), read_sub('NPL'), 'NPL', aliases={'Province 1': 'Koshi', 'Province 2': 'Madhesh',
                                                           'Sudurpaschim': 'Sudurpashchim'}, src=SRC['NPL']))

# ---------------------------------------------------------------- Central Asia, Caucasus, Mongolia, Middle East
add(attach(ne1('KAZ'), read_sub('KAZ'), 'KAZ', aliases={'Almaty City': 'Almaty (city)'}, src=SRC['KAZ']))
add(attach(ne1('GEO'), read_sub('GEO').query("unit != 'Abkhazia'"), 'GEO', aliases={'Racha-Lechkhumi-Kvemo Svaneti': 'Racha-Lochkhumi-Kvemo Svaneti'},
           src=SRC['GEO']))
add(attach(ne1('ISR'), read_sub('ISR'), 'ISR', aliases={'HaDarom': 'Southern', 'HaMerkaz': 'Central',
                                                       'HaZafon': 'Northern'}, src=SRC['ISR']))

# ---------------------------------------------------------------- Africa
add(attach(gbf('KEN-ADM1'), read_sub('KEN'), 'KEN', src=SRC['KEN'], cutoff=0.8,
           aliases={'Elgeyo-Marakwet': 'ELGEYO/MARAKWET', 'Taita Taveta': 'TAITA/TAVETA', 'Tharaka': 'THARAKA-NITHI'}))
add(attach(gbf('ETH-ADM2'), read_sub('ETH'), 'ETH', src=SRC['ETH'], cutoff=0.95))
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
add(attach(gbf('MWI-ADM2'), read_sub('MWI'), 'MWI', src=SRC['MWI']))
bf = read2('BFA'); bf = bf[bf.est == 0]
add(attach(gbf('BFA-ADM2'), bf, 'BFA', src=SRC['BFA'], cutoff=0.9))
add(attach(gbf('BEN-ADM1'), read_sub('BEN').query("basis.str.contains('census')", engine='python'), 'BEN', src=SRC['BEN'], cutoff=0.75,
           aliases={'Atakora': 'Atacora', 'Atlanique': 'Atlantique', 'Kouffo': 'Couffo', 'Oueme': 'Ouémé'}))
add(attach(gbf('ZAF-ADM1'), read2('ZAF'), 'ZAF', src=SRC['ZAF'], aliases={'Nothern Cape': 'Northern Cape'}))
add(attach(gbf('GNB-ADM1'), read2('GNB'), 'GNB', src=SRC['GNB']))
add(attach(gbf('GIN-ADM1'), read2('GIN'), 'GIN', src=SRC['GIN']))

# ---------------------------------------------------------------- Europe
add(attach(ne1('BGR'), read_sub('BGR'), 'BGR', src=SRC['BGR']))
add(attach(ne1('ALB'), read_sub('ALB'), 'ALB', src=SRC['ALB']))
mk_alias = {'Drugovo': 'Kičevo', 'Oslomej': 'Kičevo', 'Vraneštica': 'Kičevo', 'Zajas': 'Kičevo', 'Brod': 'Makedonski Brod',
            'Kavadartsi': 'Kavadarci', 'Strumitsa': 'Strumica', 'Mavrovo and Rostusa': 'Mavrovo and Rostuša',
            'Vrapcište': 'Vrapčište', 'Čučer Sandevo': 'Čučer-Sandevo', 'Centar župa': 'Centar Župa'}
mk = attach(ne1('MKD'), read_sub('MKD'), 'MKD', aliases=mk_alias, src=SRC['MKD'])
add(mk)
# MONSTAT 2023 census, table 2 (religion by municipality). The boundaries predate the 2018/2022 splits, so Podgorica is
# shown with Tuzi and Zeta (sums of the three); the four municipalities whose counts are suppressed ("z") are shown
# together: Montenegro's total minus the published counts (14 Muslims) over their summed population.
_me = read2('MNE_2023')
_comb = 'Andrijevica, Plužine, Šavnik and Žabljak'
add(attach(gbf('MNE-ADM1'), _me, 'MNE', src=SRC['MNE'],
           aliases={'Podgorica Municipality': 'Podgorica (incl. Tuzi and Zeta)', 'Andrijevica Municipality': _comb,
                    'Plužine Municipality': _comb, 'Šavnik Municipality': _comb, 'Žabljak Municipality': _comb}))
srb = gbf('SRB-ADM2'); srb['gname'] = srb.gname.str.replace(r' (Municipality|City|Municipal\*)$', '', regex=True)
add(attach(srb, read_sub('SRB'), 'SRB', src=SRC['SRB'], default=None, cutoff=0.9))
# Bosnia and Herzegovina: 2013 census, religion by municipality (BHAS final results, table 4.3), Islamic ÷ total.
# geoBoundaries names a few municipalities differently (entity parts, a typo, Višegrad labelled "Republika Srpska").
_bh = pd.read_csv(f'{S2}/BIH_2013.csv', comment='#'); _bh['pct'] = _bh.muslims / _bh.total * 100
_g = gpd.read_file(f'{GB}/geoBoundaries-BIH-ADM3_simplified.geojson'); _g['geometry'] = _g.geometry.apply(make_valid)
_x = _g.geometry.representative_point().x
BIH_FIX = {'Republika Srpska': ('VIŠEGRAD', 'Višegrad'), 'Kupra na Uni': ('KRUPA NA UNI', 'Krupa na Uni'),
           'Kupres': ('KUPRES - RS', 'Kupres (RS)'), 'Kupres (BiH)': ('KUPRES - F BiH', 'Kupres (FBiH)'),
           'Trnovo (BiH)': ('TRNOVO - F BiH', 'Trnovo (FBiH)'), 'Foča': ('FOČA - RS', 'Foča'), 'Foča-Ustikolina': ('FOČA - F BiH', 'Foča-Ustikolina'),
           'Pale': ('PALE - RS', 'Pale'), 'Pale-Prača': ('PALE - F BiH', 'Pale-Prača'), 'Centar': ('CENTAR SARAJEVO', 'Centar Sarajevo'),
           'Stari Grad': ('STARI GRAD SARAJEVO', 'Stari Grad Sarajevo'), 'Mostar': ('GRAD MOSTAR', 'Mostar'),
           'Prozor-Rama': ('PROZOR', 'Prozor-Rama'), 'Doboj East': ('DOBOJ-ISTOK', 'Doboj Istok'),
           'Ustiprača': ('NOVO GORAŽDE', 'Novo Goražde'), 'Brcko District': ('BRČKO', 'Brčko')}
_bk = {norm(u): u for u in _bh.unit}
def _bih_key(n, x):
    if n == 'Novi Grad':                       # two municipalities: Novi Grad (RS, west) and Novi Grad Sarajevo
        return ('NOVI GRAD', 'Novi Grad') if x < 17.5 else ('NOVI GRAD SARAJEVO', 'Novi Grad Sarajevo')
    return BIH_FIX.get(n) or (_bk.get(norm(n)), n)
_k = [_bih_key(n, x) for n, x in zip(_g.shapeName, _x)]
_g['key'] = [k[0] for k in _k]; _g['unit'] = [k[1] for k in _k]
assert _g.key.notna().all() and sorted(_g.key) == sorted(_bh.unit), set(_g.key) ^ set(_bh.unit)
_bl = _bh.set_index('unit')
_g['pct'] = _g.key.map(_bl.pct); _g['muslims'] = _g.key.map(_bl.muslims)
_g['src'] = SRC['BIH']; _g['dflt'] = False; _g['iso'] = 'BIH'; _g['level'] = 2
add(_g[['unit', 'pct', 'muslims', 'src', 'dflt', 'iso', 'level', 'geometry']].copy())
# Spain: UCIDE count of Muslims by province (31 Dec 2017) ÷ INE official population (1 Jan 2018)
ep = read2('ESP_prov')
ep['muslims'] = ep.ucide; ep['pct'] = ep.ucide / ep.ine_pop_2018 * 100
ESPN = {'Alava': 'Álava', 'Almeria': 'Almería', 'Avila': 'Ávila', 'Balears, Illes': 'Illes Balears', 'Caceres': 'Cáceres',
        'Cadiz': 'Cádiz', 'Castellon': 'Castellón', 'Cordoba': 'Córdoba', 'Coruna': 'A Coruña', 'Jaen': 'Jaén',
        'Leon': 'León', 'Malaga': 'Málaga', 'Palmas, Las': 'Las Palmas', 'Rioja, La': 'La Rioja'}
es = gbf('ESP-ADM2')
es = es.merge(ep[['unit', 'pct', 'muslims']], left_on='gname', right_on='unit', how='left')
assert es.pct.notna().all(), es.gname[es.pct.isna()].tolist()
es['unit'] = es.gname.map(lambda n: ESPN.get(n, n))
es['dflt'] = False; es['iso'] = 'ESP'; es['src'] = SRC['ESP']; es['level'] = 2
add(es)
add(attach(gbf('HRV-ADM1'), read2('HRV'), 'HRV', src=SRC['HRV'], aliases={'City of Zagreb': 'Grad Zagreb', 'Zagreb County': 'Zagreb County'}))
rou = ne1('ROU'); rou['unit'] = rou.gname; rou['pct'] = np.where(rou.gname == 'Constanta', 36725 / 656000 * 100, np.nan)   # INS 2021 census: 36,725 Muslims; population 656.0 thousand
rou['muslims'] = np.where(rou.gname == 'Constanta', 36725, np.nan); rou['iso'] = 'ROU'; rou['src'] = SRC['ROU']; rou['level'] = 1
add(rou)

# ---------------------------------------------------------------- Americas & Oceania
add(attach(ne1('USA'), read_sub('USA'), 'USA', src=SRC['USA']))
# Brazil: 2010 census, SIDRA table 137, Islamismo ÷ total resident population, every state (the 2022 census tables put
# Islam inside "outras religiosidades")
_br = pd.read_csv(f'{S2}/BRA_2010.csv', comment='#'); _br['pct'] = _br.muslims / _br.total * 100
_g = NE1[NE1.adm0_a3 == 'BRA'][['name', 'geometry']].rename(columns={'name': 'gname'}).copy()
_bm = dict(zip(_br.unit, zip(_br.pct, _br.muslims)))
assert sorted(_g.gname) == sorted(_bm), set(_g.gname) ^ set(_bm)
_g['unit'] = _g.gname; _g['pct'] = [_bm[n][0] for n in _g.gname]; _g['muslims'] = [_bm[n][1] for n in _g.gname]
_g['src'] = SRC['BRA']; _g['dflt'] = False; _g['iso'] = 'BRA'; _g['level'] = 1
add(_g)
cn = sub2.canada(); cn['iso'] = 'CAN'; cn['src'] = SRC['CAN']; cn['level'] = 2
add(cn)
au = sub2.australia(); au['iso'] = 'AUS'; au['src'] = SRC['AUS']; au['level'] = 2
add(au)
add(attach(gbf('GUY-ADM1'), read2('GUY'), 'GUY', src=SRC['GUY'], cutoff=0.8))
add(attach(gbf('KHM-ADM1'), read2('KHM'), 'KHM', src=SRC['KHM'], cutoff=0.8,
           aliases={'Bantey Meanchey': 'Banteay Meanchey', 'Ratanakiri Province': 'Ratanakiri'}))

subs = gpd.GeoDataFrame(pd.concat(SUBS, ignore_index=True), crs=4326)
print('subunits:', len(subs), 'countries:', subs.iso.nunique())

# ---------------------------------------------------------------- clip to Natural Earth outlines, fill residual slivers
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
                near = gpd.sjoin_nearest(rr.to_crs(3857), pg[['pct', 'unit', 'src', 'level', 'layer', 'dflt', 'muslims', 'year', 'geometry']].to_crs(3857),
                                         how='left').to_crs(4326)
                near = near[~near.index.duplicated()]
                near['iso'] = iso
                pg = pd.concat([pg, near[['iso', 'unit', 'pct', 'src', 'level', 'layer', 'dflt', 'muslims', 'year', 'geometry']]], ignore_index=True)
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
_named = (subs.iso == 'RUS') & (subs.unit == 'Sevastopol')     # keeps its name (recoded to occupied Ukraine)
subs.loc[subs.dflt & ~_named, 'unit'] = ''          # unmatched units sharing a fallback value: merged, unlabelled
subs.loc[subs.dflt, 'muslims'] = np.nan
rows = []
for k, grp in subs.groupby(['iso', 'unit', 'pct', 'level', 'layer', 'dflt'], dropna=False):
    mu = grp.muslims.dropna()
    rows.append({'iso': k[0], 'unit': k[1], 'pct': k[2], 'level': k[3], 'layer': k[4], 'dflt': k[5],
                 'src': grp.src.iloc[0], 'muslims': mu.iloc[0] if len(mu) else np.nan,
                 'year': grp.year.dropna().iloc[0] if grp.year.notna().any() else np.nan,
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

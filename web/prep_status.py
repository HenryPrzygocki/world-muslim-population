"""Neutral treatment of contested territories for the web map:
- Crimea & Sevastopol returned to de jure Ukraine; Russian-occupied area (DeepState, 2026-10-17) as its own layer
- Kurdistan Region of Iraq as an outlined autonomous region
- territories of disputed status (Taiwan, Kosovo, Somaliland, W. Sahara) and China's SARs flagged"""
import json, warnings
warnings.filterwarnings('ignore')
import geopandas as gpd, pandas as pd
from shapely.ops import unary_union
from shapely import make_valid

B = __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), 'build')
c = gpd.read_file(f'{B}/countries.geojson')
u = gpd.read_file(f'{B}/units.geojson')

crimea = unary_union([make_valid(g) for g in u[u.n.isin(['Crimea', 'Sevastopol']) & (u.c == 'RUS')].geometry])
crimea_b = crimea.buffer(0.002)
ri = c.index[c.c == 'RUS']
c.loc[ri, 'geometry'] = [make_valid(g).difference(crimea_b) for g in c.loc[ri, 'geometry']]
ui = c.index[c.c == 'UKR'][0]
c.loc[ui, 'geometry'] = make_valid(unary_union([make_valid(c.loc[ui, 'geometry']), crimea]))
u.loc[u.n.isin(['Crimea', 'Sevastopol']) & (u.c == 'RUS'), 'c'] = 'UAOCC'
c.to_file(f'{B}/countries.geojson', driver='GeoJSON')
u.to_file(f'{B}/units.geojson', driver='GeoJSON')

dejure = make_valid(c.loc[ui, 'geometry']).buffer(0)
occ = gpd.read_file(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), 'raw_occ', 'occ.geojson')).geometry.iloc[0]
occ = make_valid(occ).intersection(dejure)
gpd.GeoDataFrame({'n': ['Russian-occupied Ukraine']}, geometry=[occ], crs=4326).to_file(f'{B}/occupied.geojson', driver='GeoJSON')

a1 = gpd.read_file(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'pipeline', 'raw', 'ne_10m_admin_1_states_provinces.geojson'))
kri = unary_union(a1[(a1.adm0_a3 == 'IRQ') & a1.name.isin(['Dihok', 'Arbil', 'As-Sulaymaniyah'])].geometry)
gpd.GeoDataFrame({'n': ['Kurdistan Region']}, geometry=[kri], crs=4326).to_file(f'{B}/kri.geojson', driver='GeoJSON')

X = json.load(open(f'{B}/extra.json'))
STATUS = {
    'TWN': ('disputed', 'Taiwan', 'Governed by the Republic of China (Taipei); claimed by the People’s Republic of China. '
            'Its status is disputed, so it is drawn neither as a sovereign state nor as a province of China.'),
    'KOS': ('disputed', 'Kosovo', 'Declared independence from Serbia in 2008; recognised by about half of UN members, '
            'not by Serbia.'),
    'SOL': ('disputed', 'Somaliland', 'Self-governing since 1991; internationally regarded as part of Somalia.'),
    'SAH': ('disputed', 'Western Sahara', 'Non-self-governing territory (UN list); mostly administered by Morocco, '
            'claimed by the Sahrawi Arab Democratic Republic.'),
    'FLK': ('disputed', 'Falkland Islands (Malvinas)', 'British Overseas Territory; claimed by Argentina as the Islas Malvinas.'),
    'PRI': ('dep', 'Puerto Rico', 'Unincorporated territory of the United States; residents are US citizens.'),
    'HKG': ('sar', 'Hong Kong', 'Special Administrative Region of China; separate statistics.'),
    'MAC': ('sar', 'Macau', 'Special Administrative Region of China; separate statistics.'),
}
for l in X['labels']:
    if l['c'] in STATUS:
        l['st'], l['n'], _ = STATUS[l['c']]
X['labels'] += [
    {'n': 'Northern Ireland', 'full': 'Northern Ireland', 'c': 'NIR', 'x': -6.75, 'y': 54.62, 'a': 14100, 'p': None, 'm': None, 'sub': 0, 'st': 'dep'}]
for _c, _n in [('GUF', 'French Guiana'), ('GLP', 'Guadeloupe'), ('MTQ', 'Martinique'), ('REU', 'Réunion'), ('MYT', 'Mayotte')]:
    STATUS[_c] = ('dep', _n, 'Overseas department and region of France (part of the EU).')
STATUS['BES'] = ('dep', 'Caribbean Netherlands', 'Bonaire, Sint Eustatius and Saba: special municipalities of the Netherlands.')
for l in X['labels']:
    if l['c'] in STATUS and l['c'] in ('GUF', 'GLP', 'MTQ', 'REU', 'MYT', 'BES'):
        l['st'], l['n'], _ = STATUS[l['c']]
STATUS['NIR'] = ('dep', 'Northern Ireland', 'Part of the United Kingdom; under the 1998 Good Friday Agreement it may join Ireland if a majority votes for it.')
X['notes'] = {k: v[2] for k, v in STATUS.items()}
X['notes']['UAOCC'] = ('Internationally recognised as part of Ukraine; annexed and administered by Russia since 2014. '
                       'Crimea’s value is from Russia’s 2014 census of the peninsula: Crimean Tatars, Tatars and Azerbaijanis '
                       'as a share of residents who stated a nationality.')
X['years']['UAOCC'] = '2014'
X['notes']['CYP'] = ('Pew’s estimate covers the whole island (1.3 million people): the Republic of Cyprus, the north '
                     '(administered by Turkish Cypriots, recognised only by Turkey) and the UK Sovereign Base Areas, so the '
                     'island is shown as one area. The dashed line is the de facto line north of the UN buffer zone.')
X['notes']['OCC'] = ('Under Russian military occupation (Crimea and parts of Donetsk and Luhansk since 2014, more since '
                     '2022); internationally recognised as part of Ukraine. Line of control: DeepState map, 17 Oct 2026.')
X['notes']['KRI'] = ('Kurdistan Region — the autonomous region of Iraq (Erbil, Duhok, Sulaymaniyah, Halabja). '
                     'No separate religion figures; the value shown is Iraq’s national estimate.')
X['status'] = {k: v[0] for k, v in STATUS.items()}
json.dump(X, open(f'{B}/extra.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('crimea moved; occupied km2 ≈', round(gpd.GeoSeries([occ], crs=4326).to_crs('+proj=eqearth').area.iloc[0] / 1e6))

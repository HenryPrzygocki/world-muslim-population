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


# ------------------------------------------------------------------ Russia, federal subjects (2010 census, ethnicity)
# Rosstat, All-Russian Population Census 2010, vol. 4 (national composition), as reproduced by Demoscope Weekly
# (one page per region); the raw rows are in data/sub2/RUS_2010_demoscope.txt and every nationality column sums
# exactly to the national total. Share = persons of traditionally Muslim nationalities ÷ persons who stated a
# nationality (Rosstat's own basis for national-composition percentages).
RUS_MUSLIM = ['Абазины', 'Аварцы Всего', 'Агулы', 'Адыгейцы', 'Азербайджанцы', 'Арабы', 'Афганцы', 'Балкарцы', 'Башкиры',
              'Даргинцы Всего', 'Дунгане', 'Ингуши', 'Кабардинцы', 'Казахи', 'Каракалпаки', 'Карачаевцы', 'Киргизы',
              'Крымские татары', 'Кумыки', 'Курды Всего', 'Лакцы', 'Лезгины', 'Ногайцы Всего', 'Персы', 'Рутульцы',
              'Табасараны', 'Таджики', 'Талыши', 'Татары Всего', 'Турки', 'Турки-месхетинцы', 'Туркмены', 'Уйгуры',
              'Узбеки', 'Цахуры', 'Черкесы', 'Чеченцы Всего', 'Шапсуги', 'Хемшилы']
RUS_MINUS = ['в т.ч. Кряшены']      # Orthodox Christian Tatars, counted within "Tatars"
# Natural Earth admin-1 name -> (display name, Demoscope region options to add, options to subtract)
RUS_REG = {
    'Adygey': ('Adygea', [31]), 'Gorno-Altay': ('Altai Republic', [65]), 'Altay': ('Altai Krai', [69]), 'Amur': ('Amur', [86]),
    "Arkhangel'sk": ('Arkhangelsk', [22], [23]), "Astrakhan'": ('Astrakhan', [34]), 'Bashkortostan': ('Bashkortostan', [44]),
    'Belgorod': ('Belgorod', [2]), 'Bryansk': ('Bryansk', [3]), 'Buryat': ('Buryatia', [66]), 'Chechnya': ('Chechnya', [42]),
    'Chelyabinsk': ('Chelyabinsk', [64]), 'Chukchi Autonomous Okrug': ('Chukotka', [90]), 'Chuvash': ('Chuvashia', [49]),
    'Dagestan': ('Dagestan', [37]), 'Ingush': ('Ingushetia', [38]), 'Irkutsk': ('Irkutsk', [75]), 'Ivanovo': ('Ivanovo', [6]),
    'Kamchatka': ('Kamchatka', [82]), 'Kabardin-Balkar': ('Kabardino-Balkaria', [39]),
    'Karachay-Cherkess': ('Karachay-Cherkessia', [40]), 'Krasnodar': ('Krasnodar', [33]), 'Kemerovo': ('Kemerovo', [77]),
    'Kaliningrad': ('Kaliningrad', [25]), 'Kurgan': ('Kurgan', [59]), 'Khabarovsk': ('Khabarovsk', [85]),
    'Khanty-Mansiy': ('Khanty-Mansi', [62]), 'Kirov': ('Kirov', [52]), 'Khakass': ('Khakassia', [68]),
    'Kalmyk': ('Kalmykia', [32]), 'Kaluga': ('Kaluga', [7]), 'Komi': ('Komi', [21]), 'Kostroma': ('Kostroma', [8]),
    'Karelia': ('Karelia', [20]), 'Kursk': ('Kursk', [9]), 'Krasnoyarsk': ('Krasnoyarsk', [72]), 'Leningrad': ('Leningrad Oblast', [26]),
    'Lipetsk': ('Lipetsk', [10]), 'Maga Buryatdan': ('Magadan', [87]), 'Mariy-El': ('Mari El', [45]), 'Mordovia': ('Mordovia', [46]),
    'Moskva': ('Moscow', [19]), 'Moskovskaya': ('Moscow Oblast', [11]), 'Murmansk': ('Murmansk', [27]), 'Nenets': ('Nenets', [23]),
    'Novgorod': ('Novgorod', [28]), 'Nizhegorod': ('Nizhny Novgorod', [53]), 'Novosibirsk': ('Novosibirsk', [78]),
    'Omsk': ('Omsk', [79]), 'Orenburg': ('Orenburg', [54]), 'Orel': ('Oryol', [12]), "Perm'": ('Perm', [50]), 'Penza': ('Penza', [55]),
    "Primor'ye": ('Primorsky', [84]), 'Pskov': ('Pskov', [29]), 'Rostov': ('Rostov', [36]), "Ryazan'": ('Ryazan', [13]),
    'Sakha (Yakutia)': ('Sakha (Yakutia)', [81]), 'Sakhalin': ('Sakhalin', [88]), 'Samara': ('Samara', [56]),
    'Saratov': ('Saratov', [57]), 'North Ossetia': ('North Ossetia–Alania', [41]), 'Smolensk': ('Smolensk', [14]),
    'City of St. Petersburg': ('Saint Petersburg', [30]), "Stavropol'": ('Stavropol', [43]), 'Sverdlovsk': ('Sverdlovsk', [60]),
    'Tatarstan': ('Tatarstan', [47]), 'Tambov': ('Tambov', [15]), 'Tomsk': ('Tomsk', [80]), 'Tula': ('Tula', [17]),
    "Tver'": ('Tver', [16]), 'Tuva': ('Tuva', [67]), "Tyumen'": ('Tyumen', [61], [62, 63]), 'Udmurt': ('Udmurtia', [48]),
    "Ul'yanovsk": ('Ulyanovsk', [58]), 'Volgograd': ('Volgograd', [35]), 'Vladimir': ('Vladimir', [4]), 'Vologda': ('Vologda', [24]),
    'Voronezh': ('Voronezh', [5]), 'Yamal-Nenets': ('Yamalo-Nenets', [63]), "Yaroslavl'": ('Yaroslavl', [18]),
    'Yevrey': ('Jewish Autonomous Oblast', [89]), 'Chita': ('Zabaykalsky', [70]),
}


def russia_2010():
    rows = {}
    for l in open(f'{S2}/RUS_2010_demoscope.txt', encoding='utf-8'):
        if l.startswith('#') or not l.strip():
            continue
        n, rest = l.strip().split('|')
        rows[int(n)] = {k: int(v) for k, v in (kv.split('=') for kv in rest.split(';'))}
    sub_okrug = {23, 51, 62, 63, 71, 73, 74, 76, 83}
    top = [n for n in rows if n not in sub_okrug and n != 1]
    for k in rows[1]:                                   # transcription check: regions add up to the national total
        assert sum(rows[n].get(k, 0) for n in top) == rows[1][k], k
    def mus(r):
        return sum(r.get(k, 0) for k in RUS_MUSLIM) - sum(r.get(k, 0) for k in RUS_MINUS)
    out = []
    for ne, spec in RUS_REG.items():
        disp, plus = spec[0], spec[1]; minus = spec[2] if len(spec) > 2 else []
        m = sum(mus(rows[i]) for i in plus) - sum(mus(rows[i]) for i in minus)
        st = sum(rows[i]['STATED'] for i in plus) - sum(rows[i]['STATED'] for i in minus)
        out.append({'ne': ne, 'unit': disp, 'muslims': m, 'stated': st, 'pct': m / st * 100})
    return pd.DataFrame(out)


# ------------------------------------------------------------------ China, provinces (2010 census, ethnicity)
# NBS, 2010 Population Census of China, table 1-6 "Population by region, sex and nationality" (all persons).
CHN_MUSLIM = ['回族', '维吾尔族', '哈萨克族', '东乡族', '柯尔克孜族', '撒拉族', '塔吉克族', '乌孜别克族', '保安族', '塔塔尔族']
CHN_PROV = {'北京': 'Beijing', '天津': 'Tianjin', '河北': 'Hebei', '山西': 'Shanxi', '内蒙古': 'Inner Mongol', '辽宁': 'Liaoning',
            '吉林': 'Jilin', '黑龙江': 'Heilongjiang', '上海': 'Shanghai', '江苏': 'Jiangsu', '浙江': 'Zhejiang', '安徽': 'Anhui',
            '福建': 'Fujian', '江西': 'Jiangxi', '山东': 'Shandong', '河南': 'Henan', '湖北': 'Hubei', '湖南': 'Hunan',
            '广东': 'Guangdong', '广西': 'Guangxi', '海南': 'Hainan', '重庆': 'Chongqing', '四川': 'Sichuan', '贵州': 'Guizhou',
            '云南': 'Yunnan', '西藏': 'Xizang', '陕西': 'Shaanxi', '甘肃': 'Gansu', '青海': 'Qinghai', '宁夏': 'Ningxia', '新疆': 'Xinjiang'}
CHN_DISP = {'Inner Mongol': 'Inner Mongolia', 'Xizang': 'Tibet (Xizang)'}


def china_2010():
    x = pd.read_excel(f'{S2}/CHN_2010_census_table_1-6.xls', header=None)
    hdr = x.iloc[3].ffill()
    cols = {re.sub(r'\s+', '', str(hdr[j])): j for j in range(1, x.shape[1]) if x.iloc[4, j] in ('小计', '合计')}
    out, tot = [], None
    for i in range(5, x.shape[0]):
        r = re.sub(r'\s+', '', str(x.iloc[i, 0]))
        if r in ('nan', ''):
            continue
        v = [x.iloc[i, cols[m]] for m in CHN_MUSLIM]
        m = float(sum(0 if (a != a or a == '-') else a for a in v)); t = float(x.iloc[i, cols['合计']])
        if r == '全国':
            tot = (m, t); continue
        out.append({'ne': CHN_PROV[r], 'unit': CHN_DISP.get(CHN_PROV[r], CHN_PROV[r]), 'muslims': m, 'total': t, 'pct': m / t * 100})
    d = pd.DataFrame(out)
    assert abs(d.muslims.sum() - tot[0]) < 1 and len(d) == 31, (d.muslims.sum(), tot)
    return d

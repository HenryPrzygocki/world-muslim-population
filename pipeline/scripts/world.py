"""Page 1: the world poster (Equal Earth)."""
import sys, pickle, warnings, math, textwrap
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Rectangle, FancyBboxPatch, Circle
from shapely.geometry import Point
from style import *
from geo import pt, sphere, graticule
from common import DATA, ROOT
from mapkit import *

L = pickle.load(open(f'{DATA}/layers.pkl', 'rb'))

W = 60.0
M = 1.25
HEAD = 4.1
BAND = 9.4
SPH = sphere()
xmin, ymin, xmax, ymax = SPH.bounds
padx = (xmax - xmin) * 0.004; pady = (ymax - ymin) * 0.006
XL, XR, YB, YT = xmin - padx, xmax + padx, ymin - pady, ymax + pady
MW = W - 2 * M
MH = MW * (YT - YB) / (XR - XL)
H = M + BAND + 0.5 + MH + HEAD + M * 0.6
PT_PER_M = MW * 72 / (XR - XL)
MAP_Y0 = M + BAND + 0.5
COM_K = 0.06          # world page: circle radius (pt) = COM_K * sqrt(Muslims)

nat = L['national'].copy(); sub = L['sub'].copy()
nat['k'] = nat.pct.apply(klass); sub['k'] = sub.pct.apply(klass)
SUBISO = set(sub.iso)
PARTIAL = {'ROU'}
nat_only = nat[~nat.ADM0_A3.isin(SUBISO - PARTIAL)]
# province lines only where they help orientation: large countries without subnational data (+ Paraguay)
_area = nat.assign(a=nat.geometry.area / 1e6).groupby('ADM0_A3').a.sum()
BIG_NODATA = (set(_area[_area >= 1.2e6].index) - SUBISO) | {'PRY'}
N_UNITS = int((~sub.dflt.astype(bool)).sum())


def world_page(preview=False):
    print(f'page {W} x {H:.2f} in; map {MW:.1f} x {MH:.2f} in; 1pt = {1/PT_PER_M/1000:.1f} km')
    fig = plt.figure(figsize=(W, H), facecolor=PAPER)
    ax = fig.add_axes([M / W, MAP_Y0 / H, MW / W, MH / H])
    ax.set_xlim(XL, XR); ax.set_ylim(YB, YT); ax.set_aspect('equal'); ax.axis('off')
    cv = Canvas(ax, PT_PER_M)

    # ---------------------------------------------------------------- background
    cv.fill([SPH], OCEAN, 0)
    cv.lines(graticule(15), GRAT, 0.35, 0.5)

    # ---------------------------------------------------------------- choropleth
    ant = nat[nat.ADMIN == 'Antarctica']
    cv.fill(ant.geometry, ICE, 1, ec='#C9D6DE', lw=0.25)
    cv.fill(L['iceshelf'].geometry, '#EAF1F5', 1.05, ec='#C9D6DE', lw=0.2)
    cv.fill(nat[(nat.k < 0) & (nat.ADMIN != 'Antarctica')].geometry, NODATA, 1.1)
    EDGE_LW = 0.12
    for k in range(12):     # every country's national value underneath (safety net under subnational units)
        cv.fill(nat[nat.k == k].geometry, COLORS[k], 2, lw=EDGE_LW)
    for k in range(12):
        cv.fill(sub[sub.k == k].geometry, COLORS[k], 3, lw=EDGE_LW)
    cv.lines(sub.geometry, '#FFFFFF', 0.22, 4, rings=True, alpha=0.55)
    a1 = L['admin1']
    a1 = a1[a1.ADM0_A3.isin(BIG_NODATA)]
    natk = dict(zip(nat.ADM0_A3, nat.k))
    a1k = a1.ADM0_A3.map(natk).fillna(0).astype(int)
    dark = a1k.apply(lambda k: lum(COLORS[k]) < 0.3 if k >= 0 else False)
    cv.lines(a1[~dark].geometry, '#7E7E76', 0.2, 4.1, alpha=0.55, ls=(0, (2.4, 1.5)))
    cv.lines(a1[dark].geometry, '#FFFFFF', 0.2, 4.1, alpha=0.38, ls=(0, (2.4, 1.5)))
    cv.fill(L['lakes'].geometry, LAKE, 5, ec=COAST, lw=0.2)
    cv.lines(L['rivers'].geometry, RIVER, 0.32, 5.1, alpha=0.9)
    cv.lines(L['coast'].geometry, COAST, 0.38, 6)
    cv.lines(L['borders'].geometry, '#FFFFFF', 1.25, 6.4, alpha=0.75)
    cv.lines(L['borders'].geometry, BORDER, 0.55, 6.5)
    cv.lines(L['disputed'].geometry, '#FFFFFF', 1.1, 6.4, alpha=0.6)
    cv.lines(L['disputed'].geometry, BORDER, 0.5, 6.5, ls=(0, (3, 2.2)))
    cv.lines([SPH.exterior], OCEAN_EDGE, 1.1, 7, cap='butt')

    ALLU = gpd.GeoDataFrame(pd.concat([sub[['pct', 'k', 'geometry']], nat_only[['pct', 'k', 'geometry']]],
                                      ignore_index=True), geometry='geometry')
    SIDX = ALLU.sindex

    def colour_at(x, y):
        for i in SIDX.query(Point(x, y), predicate='intersects'):
            k = ALLU.k.iloc[i]
            return COLORS[k] if k >= 0 else NODATA
        return OCEAN

    # ---------------------------------------------------------------- country labels (highest priority)
    ctry = L['countries'].copy()
    SKIP_LABEL = {'Antarctica', 'Bir Tawil', 'Brazilian Island', 'Siachen Glacier', 'Southern Patagonian Ice Field',
                  'Cyprus No Mans Area', 'Baykonur Cosmodrome', 'Dhekelia Sovereign Base Area',
                  'Akrotiri Sovereign Base Area', 'US Naval Base Guantanamo Bay', 'Scarborough Reef', 'Serranilla Bank',
                  'Bajo Nuevo Bank (Petrel Is.)', 'Spratly Islands', 'Coral Sea Islands', 'Ashmore and Cartier Islands',
                  'Clipperton Island', 'Indian Ocean Territories', 'Heard Island and McDonald Islands'}
    SIZE = {0: 26, 1: 26, 2: 24, 3: 18, 4: 13.5, 5: 10, 6: 7.5, 7: 5.6, 8: 4.6, 9: 4.0, 10: 3.4}
    nat_val = dict(zip(nat.ADMIN, nat.pct))
    nat_cnt = pd.read_csv(f'{DATA}/pew2020.csv')
    natg = nat.dissolve(by='ADMIN')
    cntd = dict(zip(natg.index, natg.muslims if 'muslims' in natg.columns else [np.nan] * len(natg)))

    def main_extent(g):
        parts = sorted(getattr(g, 'geoms', [g]), key=lambda p: p.area, reverse=True)
        b = parts[0].bounds
        return (b[2] - b[0]) * PT_PER_M, (b[3] - b[1]) * PT_PER_M, sum(p.area for p in parts) * PT_PER_M ** 2
    EXT = {k: main_extent(g) for k, g in natg.geometry.items() if g is not None}
    SMALL = []
    natg_main = {k: (max(getattr(g, 'geoms', [g]), key=lambda p: p.area) if g is not None else None)
                 for k, g in natg.geometry.items()}
    ctry['area'] = ctry.ADMIN.map(lambda a: EXT.get(a, (0, 0, 0))[2])
    for _, r in ctry.sort_values(['LABELRANK', 'area'], ascending=[True, False]).iterrows():
        if r.ADMIN in SKIP_LABEL:
            continue
        name = RENAME.get(r.ADMIN, r.NAME.upper())
        lx, ly_ = LABEL_POS.get(r.ADMIN, (r.LABEL_X, r.LABEL_Y))
        x, y = pt(lx, ly_)
        size = SIZE.get(int(r.LABELRANK), 3.4)
        wpt, hpt, apt = EXT.get(r.ADMIN, (0, 0, 0))
        words = name.split(' ')
        lines_ = [name]
        if len(name) > 11 and len(words) > 1:
            half = len(words) // 2 + (len(words) % 2)
            lines_ = [' '.join(words[:half]), ' '.join(words[half:])]
        v = nat_val.get(r.ADMIN)
        c = cntd.get(r.ADMIN)
        iso_has_sub = r.ADM0_A3 in SUBISO and r.ADM0_A3 not in PARTIAL
        size = min(size, max(0.22 * math.sqrt(apt), 3.0))   # no oversized names on mid-sized countries
        if iso_has_sub:
            size *= 0.8                       # leave room for the unit labels underneath
        tiny = apt < 30 and v is not None and v == v and v >= 1 and r.ADMIN not in (
            'Vatican', 'Monaco', 'San Marino', 'Liechtenstein', 'Andorra', 'Gibraltar')
        vl = value_line(v, c) if (v is not None and v == v) else ''
        if tiny:
            SMALL.append((r.ADMIN, x, y, v))
            size = min(size, 4.2)
            hl = (PAPER, max(1.0, size * 0.22), 0.85)
            R = 4.4 / PT_PER_M
            cv.block((x - R, y - R, x + R, y + R))
            for side in (1, -1):
                xo = x + side * 5.4 / PT_PER_M
                ha = 'left' if side > 0 else 'right'
                b1 = cv.tbox(xo, y + size * 0.32 / PT_PER_M, ' '.join(lines_), COND_SB, size, ha=ha)
                b2 = cv.tbox(xo, y - size * 0.68 / PT_PER_M, vl, COND_M, size * 0.8, ha=ha)
                if (cv.free(b1) and cv.free(b2)) or side < 0:
                    break
            cv.place(xo, y + size * 0.32 / PT_PER_M, ' '.join(lines_), COND_SB, size, ha=ha, force=True,
                     color=INK, z=25, halo=hl)
            cv.place(xo, y - size * 0.68 / PT_PER_M, vl, COND_M, size * 0.8, ha=ha, force=True, color=INK, z=25,
                     halo=hl)
            continue
        country_label(cv, lines_, x, y, size, natg_main.get(r.ADMIN), colour_at,
                      value=None if iso_has_sub else vl, minsize=3.0 if apt > 400 else 2.6)
    for nm_, x, y, v in SMALL:
        R = 3.0 / PT_PER_M
        ax.add_patch(Circle((x, y), R, facecolor=COLORS[klass(v)], edgecolor=INK, lw=0.5, zorder=22))
        ax.add_patch(Circle((x, y), R * 1.45, facecolor='none', edgecolor='#FFFFFF', lw=0.8, zorder=21.9, alpha=0.8))

    # ---------------------------------------------------------------- water labels
    OCEANS = {'NORTH PACIFIC OCEAN': [(-150, 27), (152, 30)], 'SOUTH PACIFIC OCEAN': [(-125, -32)],
              'NORTH ATLANTIC OCEAN': [(-42, 33)], 'SOUTH ATLANTIC OCEAN': [(-17, -26)],
              'INDIAN OCEAN': [(80, -25)], 'ARCTIC OCEAN': [(-20, 84.5)], 'SOUTHERN OCEAN': [(40, -61), (-120, -62)]}
    for nmz, pos in OCEANS.items():
        for lon, lat in pos:
            x, y = pt(lon, lat)
            cv.place(x, y, nmz, SERIF_I, 26, ls=2, force=True, color=WATER_TXT, z=8, alpha=0.95)
    mar = L['marine']
    mar = mar[(mar.featurecla.isin(['sea', 'bay', 'gulf', 'channel', 'strait', 'sound'])) & (mar.scalerank <= 3)]
    MAR_SKIP = {'Sargasso Sea', 'Luzon Strait', 'Davis Strait', 'Drake Passage', 'Irish Sea', 'Bahía de Campeche',
                'Bellingshausen Sea', 'Amundsen Sea', 'Scotia Sea', 'Gulf of Bothnia', 'Gulf of Finland'}
    seen = set()
    for _, r in mar.sort_values('scalerank').iterrows():
        nmz = str(r['name']).strip()
        if nmz in MAR_SKIP or nmz in seen or nmz == 'None':
            continue
        seen.add(nmz)
        x, y = pt(r.rp.x, r.rp.y)
        s = {1: 11.5, 2: 8.5, 3: 6.5}.get(int(r.scalerank), 6)
        lab = nmz.replace(' ', '\n') if len(nmz) > 14 and s >= 8 else nmz
        cv.place(x, y, lab, SERIF_I, s, lsp=0.9, color=WATER_TXT, z=8, alpha=0.95)

    # ---------------------------------------------------------------- highlighted regions (italic call-outs)
    for nmz, lon, lat, s in REGIONS:
        x, y = pt(lon, lat)
        col, a = ink_for(colour_at(x, y))
        cv.place(x, y, nmz, COND_I, s, color=col, alpha=a, z=24)

    # ---------------------------------------------------------------- Latin America & Caribbean communities
    cl = cluster_communities(load_communities(), 45)
    nlab = draw_communities(cv, cl, pt, COM_K, lab_min=300, tiny=1.5,
                            fs=lambda r: 4.6 if r.basis == 'unsized' and r.muslims > 1e5 else (
                                3.6 if r.basis == 'unsized' else float(np.clip(3.2 + 1.5 * math.log10(max(r.muslims, 30) / 300), 3.0, 7.5))))
    print('community clusters', len(cl), 'labelled', nlab)

    # ---------------------------------------------------------------- unit labels (lowest priority)
    nm = unit_labels(cv, sub, minsize=0.9 if preview else 0.7, maxsize=5.5)
    print('unit labels', nm)

    header(fig)
    band(fig, cl)
    return fig


RENAME = {'United States of America': 'UNITED STATES', 'Democratic Republic of the Congo': 'DR CONGO',
          'Republic of the Congo': 'CONGO', 'Central African Republic': 'CENTRAL AFRICAN REP.',
          'United Republic of Tanzania': 'TANZANIA', 'Bosnia and Herzegovina': 'BOSNIA & HERZ.',
          'United Arab Emirates': 'U.A.E.', 'Russian Federation': 'RUSSIA', 'Russia': 'RUSSIA', 'eSwatini': 'ESWATINI',
          'Equatorial Guinea': 'EQ. GUINEA', 'South Sudan': 'SOUTH SUDAN', 'Dominican Republic': 'DOMINICAN REP.',
          'Solomon Islands': 'SOLOMON IS.', 'North Macedonia': 'N. MACEDONIA', 'Northern Cyprus': 'N. CYPRUS',
          'Falkland Islands': 'FALKLAND IS.', 'French Southern and Antarctic Lands': 'FR. S. & ANT. LANDS',
          'Saint Vincent and the Grenadines': 'ST VINCENT & GREN.', 'Trinidad and Tobago': 'TRINIDAD & TOBAGO',
          'Antigua and Barbuda': 'ANTIGUA & BARBUDA', 'Saint Kitts and Nevis': 'ST KITTS & NEVIS',
          'São Tomé and Principe': 'SÃO TOMÉ & PRÍNCIPE', 'Federated States of Micronesia': 'MICRONESIA',
          'Turks and Caicos Islands': 'TURKS & CAICOS', 'Papua New Guinea': 'PAPUA NEW GUINEA',
          'Republic of Serbia': 'SERBIA', 'Czechia': 'CZECHIA', 'East Timor': 'TIMOR-LESTE',
          'Hong Kong S.A.R.': 'HONG KONG', 'Macao S.A.R': 'MACAO', 'Palestine': 'PALESTINE',
          'The Bahamas': 'BAHAMAS', 'Guinea-Bissau': 'GUINEA-BISSAU', 'Western Sahara': 'WESTERN SAHARA'}

LABEL_POS = {'United Kingdom': (-4.1, 57.15), 'India': (78.2, 21.4), 'Norway': (9.0, 61.6),
             'Croatia': (16.0, 45.45)}

REGIONS = [('Xinjiang', 84.0, 39.6, 9.5), ('Ningxia', 106.2, 37.6, 5.0), ('Linxia', 103.0, 35.2, 3.6),
           ('Kashmir', 75.4, 33.9, 5.0), ('Kerala', 76.4, 10.2, 4.2), ('Assam', 92.6, 26.0, 4.2),
           ('Lakshadweep', 72.7, 11.2, 3.0), ('Bangsamoro', 124.6, 6.3, 5.0), ('Aceh', 96.8, 4.3, 4.6),
           ('Deep South', 101.5, 6.3, 3.6), ('Rakhine', 93.5, 20.2, 4.2), ('Zanzibar', 40.0, -6.1, 4.0),
           ('Tatarstan', 50.8, 55.6, 5.0), ('Bashkortostan', 56.5, 54.0, 5.0), ('Dagestan', 47.0, 42.6, 4.6),
           ('Chechnya', 45.7, 43.35, 3.6), ('Crimea', 34.2, 45.3, 4.0), ('Adjara', 42.1, 41.6, 3.2),
           ('W. Thrace', 25.3, 41.15, 3.0), ('Sandžak', 20.1, 43.15, 3.0),
           ('Bayan-Ölgii', 89.6, 48.6, 4.0), ('Mangochi', 35.4, -14.4, 3.2), ('Cabo Delgado', 39.4, -12.6, 4.0),
           ('Hararghe', 41.6, 8.9, 4.0), ('Bale', 40.2, 6.9, 4.0), ('West Nile', 31.2, 3.1, 3.2),
           ('Ceuta', -5.32, 35.95, 2.6), ('Melilla', -2.94, 35.3, 2.6), ('Mayotte', 45.15, -12.95, 2.8),
           ('Sabah', 116.9, 5.3, 4.0), ('Sarawak', 113.5, 2.4, 4.6), ('Chittagong Hill Tracts', 92.15, 22.3, 2.6),
           ('Thar', 70.4, 25.0, 3.6), ('Bortala', 81.6, 44.9, 2.8), ('Kizilsu', 75.6, 39.5, 2.8),
           ('Hotan', 81.0, 37.0, 3.6), ('Kashgar', 77.2, 38.4, 3.6), ('Altay', 88.6, 47.4, 3.2), ('Ili', 82.3, 43.6, 3.0)]


def ftext(fig, x, y, s, fp, size, color=INK, ha='left', va='baseline', **kw):
    return fig.text(x / W, y / H, s, fontproperties=fp, fontsize=size, color=color, ha=ha, va=va, **kw)


def header(fig):
    top = H - M * 0.6
    ftext(fig, M, top - 1.55, 'WORLD MUSLIM POPULATION', SANS_BL, 104, color=INK)
    ftext(fig, M + 0.05, top - 2.55,
          'Share of Muslims in the population of every country, and of provinces and districts wherever census, '
          'survey or registry data allow', SANS_L, 33, color=INK2)
    ftext(fig, M + 0.05, top - 3.35,
          f'Subnational detail for {len(SUBISO)} countries  ·  ≈{round(N_UNITS, -2):,} statistical units  ·  zoom in: every unit '
          'carries its name, share and — where known — number of Muslims  ·  regional close-ups on pages 2–6', SANS_M, 21,
          color=ACCENT)
    ftext(fig, W - M, top - 1.35, '2026 EDITION', SANS_XB, 40, color=ACCENT, ha='right')
    ftext(fig, W - M, top - 2.2, 'Equal Earth projection  ·  data as of October 2026', SANS, 20, color=INK2, ha='right')
    ftext(fig, W - M, top - 2.85, 'National baseline: Pew Research Center (2020 estimates, publ. 2025)', SANS, 20,
          color=INK2, ha='right')
    fig.add_artist(plt.Line2D([M / W, (W - M) / W], [(top - 3.75) / H] * 2, color=INK, lw=1.4))


def box_ax(fig, x0, y0, w, h):
    a = fig.add_axes([x0 / W, y0 / H, w / W, h / H]); a.set_xlim(0, w); a.set_ylim(0, h); a.axis('off')
    return a


def band(fig, cl):
    by0, by1 = M, M + BAND
    fig.add_artist(plt.Line2D([M / W, (W - M) / W], [(by1 + 0.18) / H] * 2, color=INK, lw=1.4))
    # --- A. legend
    A = box_ax(fig, M, by0, 15.2, BAND)
    A.text(0, BAND - 0.55, 'SHARE OF THE POPULATION THAT IS MUSLIM', fontproperties=SANS_B, fontsize=21, color=INK,
           va='top')
    A.text(0, BAND - 1.25, 'Latest census, survey or registry data for each statistical unit (%)',
           fontproperties=SANS_L, fontsize=15.5, color=INK2, va='top')
    sw, sh, gx, ly = 1.16, 0.62, 0.07, BAND - 3.15
    for i in range(12):
        x0 = i * (sw + gx) + (0.42 if i >= 7 else 0)
        A.add_patch(Rectangle((x0, ly), sw, sh, facecolor=COLORS[i], edgecolor='#00000022' if i == 0 else 'none',
                              lw=0.6))
        A.text(x0 + sw / 2, ly - 0.22, LABELS[i], fontproperties=COND_SB, fontsize=15, color=INK, ha='center',
               va='top')
    mx = 7 * (sw + gx) + 0.21
    A.plot([mx, mx], [ly - 0.15, ly + sh + 0.55], color=INK, lw=1.5)
    A.text(mx, ly + sh + 0.62, '50%', fontproperties=SANS_B, fontsize=13, color=INK, ha='center', va='bottom')
    A.annotate('', xy=(0.0, ly + sh + 0.35), xytext=(mx - 0.25, ly + sh + 0.35),
               arrowprops=dict(arrowstyle='->', color=BROWN, lw=1.3))
    A.text((mx - 0.25) / 2, ly + sh + 0.45, 'MUSLIM MINORITY', fontproperties=SANS_SB, fontsize=12.5, color=BROWN,
           ha='center', va='bottom')
    xr = 12 * (sw + gx) + 0.42 - gx
    A.annotate('', xy=(xr, ly + sh + 0.35), xytext=(mx + 0.25, ly + sh + 0.35),
               arrowprops=dict(arrowstyle='->', color=ACCENT, lw=1.3))
    A.text((mx + 0.25 + xr) / 2, ly + sh + 0.45, 'MUSLIM MAJORITY', fontproperties=SANS_SB, fontsize=12.5,
           color=ACCENT, ha='center', va='bottom')
    sy = ly - 1.25
    A.text(0, sy + 0.12, 'MUSLIM COMMUNITIES — LATIN AMERICA & CARIBBEAN', fontproperties=SANS_SB, fontsize=12.5,
           color=INK, va='bottom')
    base_y = sy - 1.22; cx = 0.05
    for n_, lab in ((1000, '1,000'), (10000, '10,000'), (50000, '50,000'), (250000, '250,000')):
        rr = COM_K * math.sqrt(n_) / 72
        cx += max(rr, 0.12)
        A.add_patch(Circle((cx, base_y + rr), rr, facecolor=COLORS[4], alpha=0.5, edgecolor='none'))
        A.add_patch(Circle((cx, base_y + rr), rr, facecolor='none', edgecolor=COLORS[6], lw=0.9))
        A.text(cx, base_y - 0.12, lab, fontproperties=COND_M, fontsize=11, color=INK, va='top', ha='center')
        cx += max(rr, 0.12) + 0.22
    A.text(3.35, sy - 0.18, 'Circle area proportional to number of Muslims (one scale);', fontproperties=SANS,
           fontsize=12.2, color=INK, va='top')
    A.text(3.35, sy - 0.5, 'neighbouring cities are grouped (e.g. Greater São Paulo).', fontproperties=SANS,
           fontsize=12.2, color=INK, va='top')
    A.add_patch(Circle((3.52, sy - 1.02), 0.11, facecolor=COLORS[4], alpha=0.5, edgecolor=COLORS[6], lw=0.9))
    A.text(3.75, sy - 1.02, 'Census count (Brazil 2010, Chile 2024)', fontproperties=SANS, fontsize=12.2, color=INK,
           va='center')
    A.add_patch(Circle((3.52, sy - 1.42), 0.11, facecolor=COLORS[4], alpha=0.5, edgecolor=COLORS[6], lw=0.9,
                       ls=(0, (2.2, 1.3))))
    A.text(3.75, sy - 1.42, 'Estimate (Pew 2020 total shared by city)', fontproperties=SANS, fontsize=12.2,
           color=INK, va='center')
    A.add_patch(Rectangle((3.42, sy - 1.92), 0.2, 0.2, facecolor=PAPER, edgecolor=COLORS[6], lw=0.9))
    A.add_patch(Circle((3.52, sy - 1.82), 0.045, facecolor=COLORS[6]))
    A.text(3.75, sy - 1.82, 'Community, no reliable count (Argentina, Coquimbo)', fontproperties=SANS, fontsize=12.2,
           color=INK, va='center')
    rx = 10.45
    A.plot([rx, rx + 0.7], [sy + 0.2, sy + 0.2], color=BORDER, lw=1.6)
    A.text(rx + 0.9, sy + 0.2, 'International boundary', fontproperties=SANS, fontsize=12.2, color=INK, va='center')
    A.plot([rx, rx + 0.7], [sy - 0.32, sy - 0.32], color=BORDER, lw=1.4, ls=(0, (3, 2.2)))
    A.text(rx + 0.9, sy - 0.32, 'Disputed / de facto', fontproperties=SANS, fontsize=12.2, color=INK, va='center')
    A.add_patch(Rectangle((rx, sy - 1.04), 0.7, 0.4, facecolor=COLORS[9], edgecolor='none'))
    A.plot([rx + 0.35, rx + 0.35], [sy - 1.04, sy - 0.64], color='#FFFFFF', lw=0.9, alpha=0.8)
    A.text(rx + 0.9, sy - 0.84, 'Unit boundary', fontproperties=SANS, fontsize=12.2, color=INK, va='center')
    A.add_patch(Rectangle((rx, sy - 1.56), 0.7, 0.4, facecolor=NODATA, edgecolor='none'))
    A.text(rx + 0.9, sy - 1.36, 'No permanent population', fontproperties=SANS, fontsize=12.2, color=INK, va='center')
    A.add_patch(FancyBboxPatch((0.0, 1.45), 14.6, 1.25, boxstyle='round,pad=0.02,rounding_size=0.15',
                               facecolor='#EAF2EC', edgecolor=ACCENT, lw=1.1))
    A.text(0.3, 2.32, 'EXPLORE THE DETAIL', fontproperties=SANS_B, fontsize=13.5, color=ACCENT, va='center')
    A.text(0.3, 1.83, 'Fully vector: zoom in and every unit shows name, share and (where known) number of Muslims, e.g. '
           '“2.1% · 85k”.\nSearch (Ctrl+F / Cmd+F) any place, e.g. “Malappuram”, “Tatarstan”. Pages 2–6: regional '
           'close-ups.', fontproperties=SANS, fontsize=12.6, color=INK, va='center', linespacing=1.3)
    A.text(0, 0.35, 'Values are shares of all residents. Where the census asks about ethnicity but not religion (Russia, '
           'China,\nKyrgyzstan, Mongolia), traditionally Muslim nationalities are counted — the convention used by Pew. '
           '≈ marks counts\nderived from share × population.',
           fontproperties=SANS_LI, fontsize=12.2, color=INK2, va='bottom', linespacing=1.3)

    # --- B. headline numbers
    pew = pd.read_csv(f'{DATA}/pew2020.csv')
    tot_m = 2022590461
    Bx = M + 16.2
    B = box_ax(fig, Bx, by0, 8.8, BAND)
    B.text(0, BAND - 0.55, 'THE GLOBAL PICTURE, 2020', fontproperties=SANS_B, fontsize=21, color=INK, va='top')
    B.text(0, BAND - 1.25, 'Pew Research Center estimates', fontproperties=SANS_L, fontsize=15.5, color=INK2, va='top')
    B.text(0, BAND - 1.65, '2.02', fontproperties=SANS_BL, fontsize=92, color=ACCENT, va='top')
    B.text(3.45, BAND - 2.15, 'billion\nMuslims', fontproperties=SANS_SB, fontsize=25, color=ACCENT, va='top',
           linespacing=1.0)
    B.text(0, BAND - 3.55, '25.6% of humanity  ·  up from 23.9% in 2010', fontproperties=SANS_M, fontsize=16,
           color=INK, va='top')
    regions = [('Asia-Pacific', 1187663747), ('Middle East–N. Africa', 414112362), ('Sub-Saharan Africa', 368641903),
               ('Europe', 45505934), ('North America', 5913163), ('Latin America–Caribbean', 753352)]
    ry = BAND - 4.45
    B.text(0, ry, 'Where the world’s Muslims live', fontproperties=SANS_SB, fontsize=15, color=INK, va='top')
    for i, (nmz, v) in enumerate(regions):
        yy = ry - 0.72 - i * 0.66
        share = v / tot_m
        B.add_patch(Rectangle((3.3, yy - 0.2), 4.7 * share / 0.6, 0.4, facecolor=ACCENT if i < 3 else COLORS[3],
                              edgecolor='none'))
        B.text(3.15, yy, nmz, fontproperties=COND, fontsize=13.5, color=INK, ha='right', va='center')
        lab = f'{share*100:.1f}%  ({v/1e6:,.0f} M)' if v > 5e6 else f'{share*100:.2f}%  ({v/1e6:.1f} M)'
        B.text(3.3 + 4.7 * share / 0.6 + 0.12, yy, lab, fontproperties=COND_M, fontsize=12.5, color=INK2, va='center')

    # --- C. top countries
    Cx = Bx + 9.6
    C = box_ax(fig, Cx, by0, 10.6, BAND)
    C.text(0, BAND - 0.55, 'LARGEST MUSLIM POPULATIONS', fontproperties=SANS_B, fontsize=21, color=INK, va='top')
    C.text(0, BAND - 1.25, 'Millions of Muslims, 2020 (bar) and share of national population',
           fontproperties=SANS_L, fontsize=15.5, color=INK2, va='top')
    pew['pct'] = pew.muslims_2020 / pew.total_2020 * 100
    topc = pew.sort_values('muslims_2020', ascending=False).head(15)
    mxv = topc.muslims_2020.max()
    for i, (_, r) in enumerate(topc.iterrows()):
        yy = BAND - 2.05 - i * 0.475
        wv = 6.0 * r.muslims_2020 / mxv
        C.add_patch(Rectangle((2.65, yy - 0.18), wv, 0.36, facecolor=COLORS[klass(r.pct)], edgecolor='#00000018',
                              lw=0.4))
        C.text(2.5, yy, r.country, fontproperties=COND_M, fontsize=13.5, color=INK, ha='right', va='center')
        C.text(2.65 + wv + 0.1, yy, f'{r.muslims_2020/1e6:,.0f}', fontproperties=COND_SB, fontsize=12.5, color=INK,
               va='center')
        C.text(10.4, yy, f'{r.pct:.0f}%', fontproperties=COND, fontsize=12.5, color=INK2, va='center', ha='right')
    C.text(10.4, BAND - 1.62, 'share', fontproperties=COND_I, fontsize=11.5, color=INK2, ha='right', va='center')

    # --- D. data-basis mini map
    Dx = Cx + 11.2
    D = fig.add_axes([Dx / W, (by0 + 1.15) / H, 11.0 / W, (BAND - 2.6) / H])
    D.set_xlim(XL, XR); D.set_ylim(YB, YT); D.set_aspect('equal'); D.axis('off')
    D.add_patch(PathPatch(poly_path([SPH]), facecolor='#EEF3F6', edgecolor='#C9D6DE', lw=0.6))
    basis_of = {}
    for k, (isos, col, _) in BASIS.items():
        for i in isos:
            basis_of[i] = col
    for _, r in nat.iterrows():
        if r.geometry is None:
            continue
        col = basis_of.get(r.ADM0_A3, '#DADAD4' if r.pct == r.pct else '#F4F4F2')
        D.add_patch(PathPatch(poly_path([r.geometry]), facecolor=col, edgecolor='#FFFFFF', lw=0.15))
    fig.text(Dx / W, (by0 + BAND - 0.55) / H, 'HOW DETAILED IS THE DATA?', fontproperties=SANS_B, fontsize=21,
             color=INK, va='top')
    fig.text(Dx / W, (by0 + BAND - 1.25) / H, 'Basis of the values shown, by country', fontproperties=SANS_L,
             fontsize=15.5, color=INK2, va='top')
    items = [(c, l) for _, (_, c, l) in BASIS.items()] + [('#DADAD4', 'National estimate only (Pew 2020)')]
    for i, (c, l) in enumerate(items):
        xx = Dx + (i % 2) * 5.6; yy = by0 + 0.75 - (i // 2) * 0.5
        fig.add_artist(Rectangle((xx / W, (yy - 0.14) / H), 0.42 / W, 0.3 / H, facecolor=c, edgecolor='none',
                                 transform=fig.transFigure))
        fig.text((xx + 0.55) / W, (yy + 0.01) / H, l, fontproperties=COND, fontsize=12.5, color=INK, va='center')

    # --- E. about / sources
    Ex = Dx + 11.6
    E = box_ax(fig, Ex, by0, W - M - Ex, BAND)
    E.text(0, BAND - 0.55, 'ABOUT THIS MAP', fontproperties=SANS_B, fontsize=21, color=INK, va='top')
    about = (
        "A redrawn and updated version of Edin Radončić’s 2015 map “World Muslim Population”. Every country starts from "
        "Pew Research Center’s 2020 estimates; wherever official statistics break the population down by religion "
        "(or by ethnicity, where religion is not asked), that national value is replaced by provincial, district "
        "or municipal figures. India: 640 districts (2011 census). United Kingdom: 374 local authorities "
        "(2021/22). Philippines, Bangladesh, Sri Lanka, Malaysia, Kazakhstan, North Macedonia, Bulgaria, Albania, "
        "Kenya, Malawi, Uganda, Ethiopia, Russia, China, Indonesia and others use census or registry tables; "
        "West, Central and East African regions without a religion question since independence use transparent "
        "estimates tied to national survey totals and are marked on the data-basis map. "
        "Dates differ between countries (2000–2024): treat each unit as the latest official snapshot, not a "
        "single-year estimate.")
    E.text(0, BAND - 1.3, textwrap.fill(about, 84), fontproperties=SANS, fontsize=13.6, color=INK, va='top',
           linespacing=1.36)
    E.text(0, 1.75, 'MAIN SOURCES', fontproperties=SANS_B, fontsize=13.5, color=INK, va='top')
    srcs = ('Pew Research Center (2025) Religious Composition 2010–2020 · Census of India 2011 · ONS Census 2021, '
            "Scotland's Census 2022 · Rosstat 2010/2021 · NBS China 2010/2020 · BPS Indonesia 2010 · PSA 2020 · "
            'BBS 2022 · DCS Sri Lanka 2012/2024 · DOSM 2020 · KNBS 2019 · CSA Ethiopia 2007 · NSO Malawi 2018 · UBOS 2014 · '
            'Geostat 2014 · BNS Kazakhstan 2021 · SSO N. Macedonia 2021 · NSI Bulgaria 2021 · INSTAT 2023 · RZS 2022 · '
            'MONSTAT · Statistics Canada 2021 · U.S. Religion Census 2020 · ABS 2021 · CBS Israel · UCIDE 2017/2019 · IBGE 2010 · '
            'INE Chile 2024 · Stats SA 2022 · DZS Croatia 2021 · NIS Cambodia 2019 · and others (full table on the last page).  Boundaries: Natural Earth, geoBoundaries, ONS, DataMeet.')
    E.text(0, 1.25, textwrap.fill(srcs, 118), fontproperties=COND, fontsize=11.4, color=INK2, va='top',
           linespacing=1.3)
    ftext(fig, M, M * 0.42, 'Cartography & data compilation, October 2026. Concept after Edin Radončić (2015). '
          'Boundaries do not imply endorsement of any territorial claim; disputed areas are shown with dashed lines.',
          SANS_L, 12, color=INK2)
    ftext(fig, W - M, M * 0.42, 'Values: share of Muslims in the total population of each unit  ·  page 1 of 7',
          SANS_L, 12, color=INK2, ha='right')


BASIS = {
    'census_new': (['IND', 'BGD', 'PHL', 'LKA', 'MYS', 'NPL', 'KAZ', 'KEN', 'MWI', 'UGA', 'ALB', 'MKD', 'BGR',
                    'SRB', 'GBR', 'USA', 'CAN', 'AUS', 'RUS', 'CHN', 'GEO', 'MNG', 'KGZ', 'AUT', 'CHE', 'ISR', 'MMR',
                    'BIH', 'MNE', 'NLD', 'ESP', 'HRV', 'KHM', 'ZAF', 'ROU'], '#2F8346', 'Census / register, subnational'),
    'census_old': (['ETH', 'THA', 'PAK', 'IDN', 'BEN', 'GHA', 'GUY', 'GIN', 'GNB', 'BFA'], '#93C66E', 'Older census or registry, subnational'),
    'estimate': (['NGA', 'TZA', 'CIV', 'CMR', 'TCD', 'TGO', 'SLE', 'LBR', 'ERI', 'CAF', 'MOZ', 'MDG',
                  'EGY', 'SEN', 'SUR', 'FRA', 'DEU', 'BEL', 'GRC', 'KOS'], '#D3A35C',
                 'Subnational estimate (no recent religion census)'),
}

if __name__ == '__main__':
    f = world_page(preview=True)
    f.savefig(ROOT + '/out/preview.png', dpi=40, facecolor=PAPER)

"""Regional close-up pages (pages 2–6)."""
import sys, warnings, math, textwrap, pickle
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, PathPatch, FancyBboxPatch
from shapely.geometry import box, Point, LineString
from shapely import make_valid
from pyproj import Transformer
from style import *
from common import DATA, RAW, ROOT
from mapkit import *
import geo

PW = 33.1          # page width (in), A1 long side
PM = 0.9           # margin
PHEAD = 2.05
PBAND = 3.0

_SRC = {}


def src(name):
    if name in _SRC:
        return _SRC[name]
    if name == 'nat':
        g = gpd.read_file(f'{DATA}/units_national.gpkg')
    elif name == 'sub':
        g = gpd.read_file(f'{DATA}/units_sub.gpkg')
    elif name == 'coast':
        g = gpd.read_file(f'{RAW}/ne_10m_coastline.geojson')
    elif name == 'borders':
        g = gpd.read_file(f'{RAW}/ne_10m_admin_0_boundary_lines_land.geojson')
    elif name == 'disputed':
        g = gpd.read_file(f'{RAW}/ne_10m_admin_0_boundary_lines_disputed_areas.geojson')
    elif name == 'admin1':
        g = gpd.read_file(f'{RAW}/ne_10m_admin_1_states_provinces_lines.geojson')
    elif name == 'lakes':
        g = gpd.read_file(f'{RAW}/ne_10m_lakes.geojson')
        g = g[g.scalerank <= 9]
    elif name == 'rivers':
        g = gpd.read_file(f'{RAW}/ne_10m_rivers_lake_centerlines.geojson')
        g = g[(g.scalerank <= 9) & (g.featurecla != 'Lake Centerline')]
    elif name == 'marine':
        g = gpd.read_file(f'{RAW}/ne_10m_geography_marine_polys.geojson')
    elif name == 'countries':
        g = gpd.read_file(f'{RAW}/ne_10m_admin_0_countries.geojson')
    elif name == 'places':
        g = gpd.read_file(f'{RAW}/ne_10m_populated_places_simple.geojson')
    g = g[g.geometry.notna()].copy()
    _SRC[name] = g
    return g


def prep(name, clipbox, crs, tol, kind='poly'):
    g = src(name)
    g = g[g.intersects(clipbox)].copy()
    if not len(g):
        return g.set_crs(4326, allow_override=True).to_crs(crs)
    g['geometry'] = [make_valid(x).intersection(clipbox) for x in g.geometry]
    g = g[~g.geometry.is_empty]
    g = g.set_crs(4326, allow_override=True).to_crs(crs)
    g['geometry'] = g.geometry.simplify(tol, preserve_topology=True)
    if kind == 'poly':
        g = g[g.geometry.geom_type.isin(['Polygon', 'MultiPolygon', 'GeometryCollection'])]
        g['geometry'] = [polys_only(x) for x in g.geometry]
        g = g[g.geometry.notna()]
    return g


def polys_only(g):
    if g.geom_type in ('Polygon', 'MultiPolygon'):
        return g
    ps = [p for p in getattr(g, 'geoms', []) if p.geom_type in ('Polygon', 'MultiPolygon')]
    if not ps:
        return None
    from shapely.ops import unary_union
    return unary_union(ps)


def big_nodata():
    nat = src('nat')
    sub = src('sub')
    a = nat.to_crs('+proj=eqearth +datum=WGS84').assign(a=lambda d: d.geometry.area / 1e6).groupby('ADM0_A3').a.sum()
    return (set(a[a >= 1.2e6].index) - set(sub.iso)) | {'PRY'}


# ------------------------------------------------------------------ one map panel (main map or inset)
def draw_panel(fig, rect_in, page_h, spec, bbox, crs, title_inset=None, frame_lw=1.2, min_label=None, max_label=None,
               communities=None, metros=None, country_labels=True, sea_labels=True, inset_marks=()):
    """rect_in: (x, y, w, h) in inches on a page of width PW and height page_h."""
    x_in, y_in, w_in, h_in = rect_in
    T = Transformer.from_crs(4326, crs, always_xy=True)
    lons = np.r_[np.linspace(bbox[0], bbox[2], 60), np.full(60, bbox[2]), np.linspace(bbox[2], bbox[0], 60), np.full(60, bbox[0])]
    lats = np.r_[np.full(60, bbox[1]), np.linspace(bbox[1], bbox[3], 60), np.full(60, bbox[3]), np.linspace(bbox[3], bbox[1], 60)]
    px, py = T.transform(lons, lats)
    x0, x1, y0, y1 = px.min(), px.max(), py.min(), py.max()
    # adjust to the panel's aspect ratio (expand the short side)
    asp = h_in / w_in
    if (y1 - y0) / (x1 - x0) < asp:
        c = (y0 + y1) / 2; hh = (x1 - x0) * asp / 2; y0, y1 = c - hh, c + hh
    else:
        c = (x0 + x1) / 2; ww = (y1 - y0) / asp / 2; x0, x1 = c - ww, c + ww
    ppm = w_in * 72 / (x1 - x0)
    ax = fig.add_axes([x_in / PW, y_in / page_h, w_in / PW, h_in / page_h])
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal'); ax.axis('off')
    pad = 0.6 / ppm * 0
    cv = Canvas(ax, ppm, extent=(x0, y0, x1, y1), clip=True)
    # clip region in lon/lat: generous
    Ti = Transformer.from_crs(crs, 4326, always_xy=True)
    cx_, cy_ = np.meshgrid(np.linspace(x0, x1, 25), np.linspace(y0, y1, 25))
    lo, la = Ti.transform(cx_.ravel(), cy_.ravel())
    dlo, dla = (max(lo) - min(lo)) * 0.08 + 0.5, (max(la) - min(la)) * 0.08 + 0.5
    clipbox = box(max(-180, min(lo) - dlo), max(-89, min(la) - dla), min(180, max(lo) + dlo), min(89, max(la) + dla))
    tol = 0.1 / ppm
    nat = prep('nat', clipbox, crs, tol)
    sub = prep('sub', clipbox, crs, tol)
    nat['k'] = nat.pct.apply(klass); sub['k'] = sub.pct.apply(klass)
    subiso = set(src('sub').iso)
    # background
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=OCEAN, edgecolor='none', zorder=0))
    grat = []
    for lon in range(-180, 181, 5):
        la_ = np.linspace(-80, 80, 400)
        gx, gy = T.transform(np.full_like(la_, lon), la_)
        grat.append(LineString(np.column_stack([gx, gy])))
    for lat in range(-80, 81, 5):
        lo_ = np.linspace(clipbox.bounds[0], clipbox.bounds[2], 400)
        gx, gy = T.transform(lo_, np.full_like(lo_, lat))
        grat.append(LineString(np.column_stack([gx, gy])))
    cv.lines(grat, GRAT, 0.4, 0.5)
    cv.fill(nat[nat.k < 0].geometry, NODATA, 1.1)
    for k in range(12):
        cv.fill(nat[nat.k == k].geometry, COLORS[k], 2, lw=0.15)
    for k in range(12):
        cv.fill(sub[sub.k == k].geometry, COLORS[k], 3, lw=0.15)
    cv.lines(sub.geometry, '#FFFFFF', 0.45, 4, rings=True, alpha=0.75)
    bn = spec.get('admin1_isos', big_nodata())
    a1 = prep('admin1', clipbox, crs, tol, 'line')
    if len(a1):
        a1 = a1[a1.ADM0_A3.isin(bn)]
        cv.lines(a1.geometry, '#7E7E76', 0.4, 4.1, alpha=0.6, ls=(0, (3, 2)))
    lakes = prep('lakes', clipbox, crs, tol)
    cv.fill(lakes.geometry, LAKE, 5, ec=COAST, lw=0.3)
    rv = prep('rivers', clipbox, crs, tol, 'line')
    cv.lines(rv.geometry, RIVER, 0.5, 5.1, alpha=0.9)
    cv.lines(prep('coast', clipbox, crs, tol, 'line').geometry, COAST, 0.6, 6)
    bl = prep('borders', clipbox, crs, tol, 'line')
    cv.lines(bl.geometry, '#FFFFFF', 2.2, 6.4, alpha=0.8)
    cv.lines(bl.geometry, BORDER, 0.9, 6.5)
    dl = prep('disputed', clipbox, crs, tol, 'line')
    if len(dl):
        cv.lines(dl.geometry, '#FFFFFF', 1.8, 6.4, alpha=0.7)
        cv.lines(dl.geometry, BORDER, 0.8, 6.5, ls=(0, (4, 3)))
    for (ib, lab) in inset_marks:
        ipx, ipy = T.transform([ib[0], ib[2], ib[2], ib[0], ib[0]], [ib[1], ib[1], ib[3], ib[3], ib[1]])
        ax.plot(ipx, ipy, color=INK, lw=0.9, zorder=40, solid_joinstyle='miter')
        cv.block((min(ipx), min(ipy), max(ipx), max(ipy)))
        cv.place(min(ipx), max(ipy) + 2 / ppm, lab, SANS_SB, 6.5, ha='left', va='bottom', color=INK, z=41,
                 halo=(PAPER, 1.5, 0.9), force=True)

    allu = gpd.GeoDataFrame(pd.concat([sub[['k', 'geometry']], nat[~nat.ADM0_A3.isin(subiso - {'ROU'})][['k', 'geometry']]],
                                      ignore_index=True), geometry='geometry')
    sidx = allu.sindex

    def colour_at(x, y):
        for i in sidx.query(Point(x, y), predicate='intersects'):
            k = int(allu.k.iloc[i])
            return COLORS[k] if k >= 0 else NODATA
        return OCEAN

    xy = lambda lon, lat: T.transform(lon, lat)

    # ---- country labels
    if country_labels:
        ctry = src('countries')
        natd = nat.dissolve(by='ADMIN', aggfunc={'pct': 'first', 'muslims': 'first', 'ADM0_A3': 'first'})
        from world import RENAME, LABEL_POS
        rows = []
        for adm, r in natd.iterrows():
            g = r.geometry
            if g is None or g.is_empty:
                continue
            vis = g.intersection(box(x0, y0, x1, y1))
            if vis.is_empty:
                continue
            main = max(getattr(vis, 'geoms', [vis]), key=lambda p: p.area) if vis.geom_type != 'Polygon' else vis
            if main.geom_type != 'Polygon':
                continue
            area_pt = vis.area * ppm * ppm
            if area_pt < 150:
                continue
            cr = ctry[ctry.ADMIN == adm]
            name = RENAME.get(adm, (cr.NAME.iloc[0] if len(cr) else adm).upper())
            lonlat = LABEL_POS.get(adm, (cr.LABEL_X.iloc[0], cr.LABEL_Y.iloc[0]) if len(cr) else None)
            if spec.get('label_pos', {}).get(adm):
                lonlat = spec['label_pos'][adm]
            if lonlat is not None:
                lx, ly = T.transform(*lonlat)
                if not main.contains(Point(lx, ly)):
                    lonlat = None
            if lonlat is None:
                from shapely.ops import polylabel
                p = polylabel(main, tolerance=math.sqrt(main.area) / 40)
                lx, ly = p.x, p.y
            rows.append((area_pt, adm, name, lx, ly, main, r))
        rows.sort(key=lambda t: -t[0])
        for area_pt, adm, name, lx, ly, main, r in rows:
            has_sub = r.ADM0_A3 in subiso and r.ADM0_A3 != 'ROU'
            size = float(np.clip(0.1 * math.sqrt(area_pt), 7.5, 30))
            if has_sub:
                size *= 0.72
            words = name.split(' ')
            lines_ = [name]
            if len(name) > 12 and len(words) > 1:
                half = len(words) // 2 + (len(words) % 2)
                lines_ = [' '.join(words[:half]), ' '.join(words[half:])]
            v = r.pct
            vl = None if has_sub or v != v else value_line(v, r.muslims)
            country_label(cv, lines_, lx, ly, size, main, colour_at, value=vl, minsize=6, z=25)

    # ---- sea labels
    if sea_labels:
        mar = src('marine')
        mar = mar[mar.featurecla.isin(['sea', 'bay', 'gulf', 'channel', 'strait', 'sound', 'ocean']) & (mar.scalerank <= 6)]
        mar = mar[mar.intersects(clipbox)]
        seen = set()
        for _, r in mar.sort_values('scalerank').iterrows():
            nm = str(r['name']).strip()
            if nm in seen or nm == 'None' or nm in spec.get('skip_seas', ()):
                continue
            seen.add(nm)
            rp = r.geometry.intersection(clipbox)
            if rp.is_empty:
                continue
            p = rp.representative_point()
            mx, my = T.transform(p.x, p.y)
            s = {0: 24, 1: 21, 2: 18, 3: 15, 4: 13, 5: 11, 6: 10}.get(int(r.scalerank), 10)
            if r.featurecla == 'ocean':
                nm = nm.upper(); s = 20
            lab = nm.replace(' ', '\n') if len(nm) > 16 and s >= 10 else nm
            cv.place(mx, my, lab, SERIF_I, s, lsp=0.95, color=WATER_TXT, z=8, alpha=0.95)

    # ---- callouts
    for nm, lon, lat, s in spec.get('callouts', []):
        cxp, cyp = T.transform(lon, lat)
        col, a = ink_for(colour_at(cxp, cyp))
        cv.place(cxp, cyp, nm, COND_I, s, color=col, alpha=a, z=24)

    # ---- communities
    if communities is not None:
        cl, k, fsf = communities
        draw_communities(cv, cl, xy, k, lab_min=0, tiny=3.2, fs=fsf, force_min=2000)
    if metros is not None:
        cl, k, fsf = metros
        draw_communities(cv, cl, xy, k, lab_min=4000, tiny=3.0, fs=fsf, force_min=50000)

    # ---- unit labels
    nlab = unit_labels(cv, sub, minsize=min_label or 2.2, maxsize=max_label or 12.0)
    # ---- province names (orientation only) in large countries without subnational data
    if country_labels and len(bn):
        pv = src('prov') if 'prov' in _SRC else None
        if pv is None:
            pv = gpd.read_file(f'{RAW}/ne_10m_admin_1_states_provinces.geojson')
            pv = pv[pv.geometry.notna()]
            _SRC['prov'] = pv
        pv = pv[pv.adm0_a3.isin(bn) & pv.intersects(clipbox)].copy()
        if len(pv):
            pv['geometry'] = [make_valid(g).intersection(clipbox) for g in pv.geometry]
            pv = pv.set_crs(4326, allow_override=True).to_crs(crs)
            from shapely.ops import polylabel
            for _, r in pv.iterrows():
                g = r.geometry.intersection(box(x0, y0, x1, y1))
                if g.is_empty:
                    continue
                parts = [p for p in getattr(g, 'geoms', [g]) if p.geom_type == 'Polygon']
                if not parts:
                    continue
                main = max(parts, key=lambda p: p.area)
                a_pt = main.area * ppm * ppm
                if a_pt < 2500:
                    continue
                p = polylabel(main, tolerance=math.sqrt(main.area) / 50)
                nm = str(r['name'])
                s_ = float(np.clip(0.035 * math.sqrt(a_pt), 6.0, 11.0))
                lab = nm.upper()
                if len(lab) > 14 and ' ' in lab:
                    w_ = lab.split(' '); h_ = len(w_) // 2 + len(w_) % 2
                    lab = ' '.join(w_[:h_]) + '\n' + ' '.join(w_[h_:])
                dark_bg = lum(colour_at(p.x, p.y)) < 0.18
                cv.place(p.x, p.y, lab, COND_I, s_, lsp=1.0, color='#FFFFFF' if dark_bg else '#8C8C82',
                         alpha=0.55 if dark_bg else 0.9, z=9)
    if title_inset:
        cv.place(x0 + 6 / ppm, y1 - 6 / ppm, title_inset, SANS_B, 11, ha='left', va='top', color=INK, z=45,
                 halo=(PAPER, 2.5, 0.95), force=True)
    # frame
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor='none', edgecolor=INK, lw=frame_lw, zorder=50,
                           clip_on=False))
    print(f'  panel {title_inset or spec["key"]}: 1pt = {1/ppm/1000:.2f} km, unit labels {nlab}')
    return dict(ax=ax, cv=cv, T=T, ppm=ppm, ext=(x0, y0, x1, y1), sub=sub)


# ------------------------------------------------------------------ page specs
def lat_crs(bbox):
    lon0 = (bbox[0] + bbox[2]) / 2; lat0 = (bbox[1] + bbox[3]) / 2
    return f'+proj=laea +lat_0={lat0:.2f} +lon_0={lon0:.2f} +datum=WGS84 +units=m +no_defs'


SPECS = [
    dict(key='samerica', n=2, title='SOUTHERN SOUTH AMERICA',
         sub='Muslim communities of southern Brazil, the Triple Frontier, Paraguay, Uruguay and Argentina',
         bbox=(-66.8, -36.4, -39.0, -14.6), communities=True,
         label_pos={'Brazil': (-49.5, -17.2), 'Argentina': (-62.5, -33.2)},
         note=('Circles: number of Muslims, one scale for the whole page (area proportional to count). Brazil: IBGE census 2010, '
               '175 municipalities with 20+ Muslims, grouped into metropolitan areas where they touch (e.g. Greater '
               'São Paulo = 16 municipalities). Paraguay & Uruguay: Pew 2020 national totals shared among documented '
               'communities (dashed). Paraguay’s census recorded only 872 Muslims (486 in Alto Paraná); community leaders '
               'put Ciudad del Este’s Arab-Muslim community at ≈7,000 (Última Hora, 2026). Argentina: no census '
               'religion data; Pew’s ≈420,000 is heritage-based, so cities are shown without size.')),
    dict(key='weurope', n=3, title='WESTERN EUROPE',
         sub='Regions, provinces and — in the United Kingdom — all 374 local authorities',
         bbox=(-10.6, 35.4, 17.6, 59.4),
         inset=dict(bbox=(-0.54, 51.27, 0.36, 51.71), title='GREATER LONDON', where=(-10.55, 43.95, -5.05, 48.15)),
         label_pos={'United Kingdom': (-4.3, 57.2), 'France': (2.3, 46.6), 'Spain': (-3.6, 40.1)},
         skip_seas={'Bay of Biscay'},
         note=('UK: ONS Census 2021 (England & Wales) and Scotland’s Census 2022; Scottish and Northern Irish councils '
               'without a published figure are merged into one unlabelled remainder. Germany, France and Belgium have '
               'no religion census: shares are estimates consistent with national survey totals; counts marked ≈ are '
               'share × population. Spain: UCIDE community totals (2019, scaled to 2024) shared out by province. Netherlands: CBS. Austria: Statistik Austria '
               '2021. Switzerland: FSO structural survey (persons 15+).')),
    dict(key='balkans', n=4, title='THE BALKANS',
         sub='Former Yugoslavia, Albania, Bulgaria and Greek Thrace — municipalities, cantons, counties and provinces',
         bbox=(13.4, 39.25, 29.9, 46.75),
         callouts=[('Sandžak', 20.25, 43.0, 9), ('Preševo Valley', 21.75, 42.42, 7.5), ('Western Thrace', 25.2, 41.03, 8)],
         note=('Bosnia & Herzegovina: 2013 census by canton / entity region. Serbia: 2022 census (municipalities '
               'with ≥1% Muslims shown; the rest merged). Kosovo: 2011 census (northern Serb-majority municipalities '
               'estimated). North Macedonia 2021, Albania 2023 (by county), Montenegro 2023, Bulgaria 2021 '
               '(share of all residents, incl. ≈12% who did not answer), Greece: Thrace municipalities estimated '
               'from minority-language data. Croatia: 2021 census by county. Romania: Constanța (2021 census) and Tulcea only.')),
    dict(key='caucasus', n=5, title='THE CAUCASUS',
         sub='Georgia’s regions, Russia’s North Caucasus republics, Azerbaijan and Armenia',
         bbox=(36.6, 38.25, 51.2, 45.75),
         callouts=[('Pankisi', 45.42, 42.22, 7)],
         note=('Georgia: 2014 census by region (Adjara’s Muslim Georgians, Kvemo Kartli’s Azerbaijanis, Pankisi Kists). '
               'Russia: 2010/2021 census, combined share of traditionally Muslim nationalities. Azerbaijan, Armenia, '
               'Turkey and Iran: Pew 2020 national estimates (no subnational religion data); Azerbaijan’s figure '
               'includes nominal and secular Muslims.')),
    dict(key='usa', n=6, title='UNITED STATES',
         sub='Muslims by state (share and number) and by metropolitan area — U.S. Religion Census 2020',
         bbox=(-124.6, 24.6, -67.0, 49.3), crs='+proj=aea +lat_1=29.5 +lat_2=45.5 +lat_0=37.5 +lon_0=-96 +datum=WGS84 +units=m +no_defs',
         metros=True, admin1_isos=set(), label_pos={'United States of America': (-100.5, 39.3)},
         note=('2020 U.S. Religion Census (ASARB): Muslim adherents estimated from mosque attendance surveys — a '
               'congregation-based count (4.45 million), higher than survey-based estimates (Pew: ≈3.5–4 million). '
               'Circles: the 383 metropolitan statistical areas, one scale (area proportional to count); circles for metros under '
               '1,000 adherents are omitted. Alaska & Hawaii: see page 1.')),
]


def regional_page(spec, total_pages=7):
    bbox = spec['bbox']
    crs = spec.get('crs') or lat_crs(bbox)
    T = Transformer.from_crs(4326, crs, always_xy=True)
    lons = np.r_[np.linspace(bbox[0], bbox[2], 50), np.full(50, bbox[2]), np.linspace(bbox[2], bbox[0], 50), np.full(50, bbox[0])]
    lats = np.r_[np.full(50, bbox[1]), np.linspace(bbox[1], bbox[3], 50), np.full(50, bbox[3]), np.linspace(bbox[3], bbox[1], 50)]
    px, py = T.transform(lons, lats)
    mw = PW - 2 * PM
    mh = mw * (py.max() - py.min()) / (px.max() - px.min())
    H = PM + PBAND + 0.35 + mh + PHEAD + PM * 0.7
    fig = plt.figure(figsize=(PW, H), facecolor=PAPER)
    my0 = PM + PBAND + 0.35
    comm = metros = None
    if spec.get('communities'):
        cl = cluster_communities(load_communities(), 12)
        comm = (cl, COMK_REG, lambda r: 8.5 if r.basis == 'unsized' and r.muslims > 1e5 else (
            7.0 if r.basis == 'unsized' else float(np.clip(6.0 + 2.4 * math.log10(max(r.muslims, 20) / 100), 5.0, 15))))
    if spec.get('metros'):
        mt = pd.read_csv(f'{DATA}/usa_metros_arda2020.csv')
        mt = mt[mt.adherents >= 1000].copy()
        mt['name'] = mt.city; mt['muslims'] = mt.adherents; mt['basis'] = 'census'; mt['pos'] = 'right'
        mt['label'] = 1; mt['country'] = 'USA'
        mt = mt.sort_values('muslims', ascending=False).reset_index(drop=True)
        metros = (mt, COMK_USA, lambda r: float(np.clip(5.0 + 2.2 * math.log10(r.muslims / 5000), 4.5, 12)))
    P = draw_panel(fig, (PM, my0, mw, mh), H, spec, bbox, crs, communities=comm, metros=metros,
                   inset_marks=[(spec['inset']['bbox'], spec['inset']['title'].title())] if spec.get('inset') else (),
                   min_label=2.0 if spec['key'] == 'weurope' else 2.4)
    if spec.get('inset'):
        ins = spec['inset']
        wb = ins['where']
        wx, wy = P['T'].transform([wb[0], wb[2]], [wb[1], wb[3]])
        x0, y0, x1, y1 = P['ext']
        ix = PM + (min(wx) - x0) / (x1 - x0) * mw
        iy = my0 + (min(wy) - y0) / (y1 - y0) * mh
        iw = abs(wx[1] - wx[0]) / (x1 - x0) * mw
        ih = abs(wy[1] - wy[0]) / (y1 - y0) * mh
        fig.add_artist(Rectangle(((ix - 0.06) / PW, (iy - 0.06) / H), (iw + 0.12) / PW, (ih + 0.12) / H,
                                 facecolor=PAPER, edgecolor='none', transform=fig.transFigure, zorder=60))
        sp2 = dict(spec); sp2['key'] = 'inset'; sp2['callouts'] = []
        Q = draw_panel(fig, (ix, iy, iw, ih), H, sp2, ins['bbox'], lat_crs(ins['bbox']), title_inset=ins['title'],
                       frame_lw=1.0, min_label=3.2, max_label=9, country_labels=False, sea_labels=False)
        Q['ax'].set_zorder(70)
    header_band(fig, spec, H, total_pages, P, comm, metros)
    return fig


COMK_REG = 0.25          # South America page: radius (pt) = k * sqrt(Muslims)
COMK_USA = 0.036         # US page


def header_band(fig, spec, H, total, P, comm, metros):
    def t(x, y, s, fp, size, color=INK, ha='left', va='baseline', **kw):
        return fig.text(x / PW, y / H, s, fontproperties=fp, fontsize=size, color=color, ha=ha, va=va, **kw)
    top = H - PM * 0.7
    t(PM, top - 0.95, spec['title'], SANS_BL, 52)
    t(PM + 0.02, top - 1.6, spec['sub'], SANS_L, 21, color=INK2)
    t(PW - PM, top - 0.8, f'WORLD MUSLIM POPULATION  ·  REGIONAL CLOSE-UP', SANS_B, 15, color=ACCENT, ha='right')
    t(PW - PM, top - 1.25, f'2026 edition  ·  page {spec["n"]} of {total}', SANS, 14, color=INK2, ha='right')
    proj = 'Albers equal-area conic' if spec.get('crs') else 'Lambert azimuthal equal-area'
    t(PW - PM, top - 1.62, f'{proj} projection', SANS, 13, color=INK2, ha='right')
    fig.add_artist(plt.Line2D([PM / PW, (PW - PM) / PW], [(top - 1.92) / H] * 2, color=INK, lw=1.1))
    # ---- bottom band
    by1 = PM + PBAND
    fig.add_artist(plt.Line2D([PM / PW, (PW - PM) / PW], [(by1 + 0.15) / H] * 2, color=INK, lw=1.1))
    A = fig.add_axes([PM / PW, PM / H, 11.2 / PW, PBAND / H]); A.set_xlim(0, 11.2); A.set_ylim(0, PBAND); A.axis('off')
    A.text(0, PBAND - 0.3, 'SHARE OF THE POPULATION THAT IS MUSLIM (%)', fontproperties=SANS_B, fontsize=12.5,
           color=INK, va='top')
    sw, sh, gx = 0.82, 0.38, 0.04
    ly = PBAND - 1.15
    for i in range(12):
        x0 = i * (sw + gx) + (0.25 if i >= 7 else 0)
        A.add_patch(Rectangle((x0, ly), sw, sh, facecolor=COLORS[i], edgecolor='#00000022' if i == 0 else 'none',
                              lw=0.5))
        A.text(x0 + sw / 2, ly - 0.1, LABELS[i], fontproperties=COND_SB, fontsize=10.5, color=INK, ha='center',
               va='top')
    mx = 7 * (sw + gx) + 0.125
    A.plot([mx, mx], [ly - 0.08, ly + sh + 0.18], color=INK, lw=1.1)
    A.text(mx - 0.12, ly + sh + 0.1, 'minority', fontproperties=COND_I, fontsize=10, color=BROWN, ha='right',
           va='bottom')
    A.text(mx + 0.12, ly + sh + 0.1, 'majority', fontproperties=COND_I, fontsize=10, color=ACCENT, ha='left',
           va='bottom')
    A.text(0, ly - 0.62, 'Each unit: name, share and — where known — number of Muslims (e.g. “2.1% · 85k”;\n'
           '≈ = share × population). Unlabelled pale areas: values below 1% or merged fallback units.',
           fontproperties=SANS, fontsize=10.5, color=INK2, va='top', linespacing=1.3)
    # ---- middle: circles or line symbols, scale bar
    Bx = PM + 11.8
    B = fig.add_axes([Bx / PW, PM / H, 8.4 / PW, PBAND / H]); B.set_xlim(0, 8.4); B.set_ylim(0, PBAND); B.axis('off')
    if comm is not None or metros is not None:
        k = COMK_REG if comm is not None else COMK_USA
        vals = (100, 1000, 5000, 10000) if comm is not None else (5000, 50000, 200000, 900000)
        B.text(0, PBAND - 0.3, 'MUSLIMS PER CITY / METRO AREA' if comm is not None else 'MUSLIM ADHERENTS PER METRO AREA',
               fontproperties=SANS_B, fontsize=12.5, color=INK, va='top')
        base = 1.05; cx = 0.1
        for v in vals:
            rr = k * math.sqrt(v) / 72
            cx += max(rr, 0.34)
            B.add_patch(Circle((cx, base + rr), rr, facecolor=COLORS[4], alpha=0.5, edgecolor='none'))
            B.add_patch(Circle((cx, base + rr), rr, facecolor='none', edgecolor=COLORS[6], lw=0.8))
            B.text(cx, base - 0.08, f'{v:,}', fontproperties=COND_M, fontsize=10, color=INK, va='top', ha='center')
            cx += max(rr, 0.34) + 0.08
        lx = max(cx + 0.2, 4.3)
        if comm is not None:
            items = [('solid', 'Census count (IBGE 2010, INE Chile 2024)'), ('dash', 'Estimate (Pew 2020 total shared by city)'),
                     ('sq', 'Community without reliable count (Argentina)')]
        else:
            items = [('solid', 'Adherents, U.S. Religion Census 2020'), ('none', 'Metros with ≥1,000 adherents'),
                     ('none', 'State fill: share of residents')]
        for i, (kind, lab) in enumerate(items):
            yy = PBAND - 0.9 - i * 0.42
            if kind in ('solid', 'dash'):
                B.add_patch(Circle((lx, yy), 0.1, facecolor=COLORS[4], alpha=0.5, edgecolor=COLORS[6], lw=0.8,
                                   ls='solid' if kind == 'solid' else (0, (2.2, 1.3))))
            elif kind == 'sq':
                B.add_patch(Rectangle((lx - 0.09, yy - 0.09), 0.18, 0.18, facecolor=PAPER, edgecolor=COLORS[6], lw=0.8))
                B.add_patch(Circle((lx, yy), 0.04, facecolor=COLORS[6]))
            B.text(lx + 0.2, yy, lab, fontproperties=SANS, fontsize=10.2, color=INK, va='center')
    else:
        B.text(0, PBAND - 0.3, 'SYMBOLS', fontproperties=SANS_B, fontsize=12.5, color=INK, va='top')
        items = [('b', 'International boundary'), ('d', 'Disputed / de facto boundary'), ('u', 'Statistical unit'),
                 ('a', 'Province (countries without subnational data)')]
        for i, (kind, lab) in enumerate(items):
            yy = PBAND - 0.85 - i * 0.4
            if kind == 'b':
                B.plot([0, 0.6], [yy, yy], color=BORDER, lw=1.4)
            elif kind == 'd':
                B.plot([0, 0.6], [yy, yy], color=BORDER, lw=1.2, ls=(0, (3, 2)))
            elif kind == 'u':
                B.add_patch(Rectangle((0, yy - 0.15), 0.6, 0.3, facecolor=COLORS[3], edgecolor='none'))
                B.plot([0.3, 0.3], [yy - 0.15, yy + 0.15], color='#FFFFFF', lw=1)
            else:
                B.plot([0, 0.6], [yy, yy], color='#7E7E76', lw=0.8, ls=(0, (3, 2)))
            B.text(0.8, yy, lab, fontproperties=SANS, fontsize=10.2, color=INK, va='center')
    # scale bar
    ppm = P['ppm']
    km_per_in = 72 / ppm / 1000
    nice = [50, 100, 200, 250, 500, 1000]
    L_km = min(nice, key=lambda v: abs(v / km_per_in - 2.2))
    sbw = L_km / km_per_in
    sy = 0.25
    B.add_patch(Rectangle((0.1, sy), sbw / 2, 0.08, facecolor=INK, edgecolor=INK, lw=0.6))
    B.add_patch(Rectangle((0.1 + sbw / 2, sy), sbw / 2, 0.08, facecolor=PAPER, edgecolor=INK, lw=0.6))
    for xx, lab in ((0.1, '0'), (0.1 + sbw / 2, f'{L_km // 2}'), (0.1 + sbw, f'{L_km} km')):
        B.text(xx, sy + 0.14, lab, fontproperties=COND, fontsize=9.5, color=INK, ha='center', va='bottom')
    B.text(0.1 + sbw + 0.5, sy + 0.04, 'scale at map centre', fontproperties=COND_I, fontsize=9.5, color=INK2,
           va='center')
    # ---- right: notes + locator
    Cx = Bx + 8.9
    cw = PW - PM - Cx - 3.3
    C = fig.add_axes([Cx / PW, PM / H, cw / PW, PBAND / H]); C.set_xlim(0, cw); C.set_ylim(0, PBAND); C.axis('off')
    C.text(0, PBAND - 0.3, 'DATA FOR THIS PAGE', fontproperties=SANS_B, fontsize=12.5, color=INK, va='top')
    C.text(0, PBAND - 0.68, textwrap.fill(spec['note'], int(cw * 13.6)), fontproperties=SANS, fontsize=10.2,
           color=INK, va='top', linespacing=1.3)
    # locator globe
    Lx = PW - PM - 3.0
    D = fig.add_axes([Lx / PW, (PM + 0.15) / H, 3.0 / PW, (PBAND - 0.3) / H])
    import world
    Lw = world.L
    D.set_xlim(world.XL, world.XR); D.set_ylim(world.YB, world.YT); D.set_aspect('equal'); D.axis('off')
    D.add_patch(PathPatch(poly_path([world.SPH]), facecolor='#E3EDF2', edgecolor='#B8CAD4', lw=0.5))
    D.add_patch(PathPatch(poly_path(Lw['national'].geometry), facecolor='#CFCFC8', edgecolor='none'))
    b = spec['bbox']
    pts = [geo.pt(lo, la) for lo, la in [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]), (b[0], b[1])]]
    D.plot([p[0] for p in pts], [p[1] for p in pts], color='#C0392B', lw=1.4)
    fig.text((Lx + 1.5) / PW, (PM + PBAND - 0.05) / H, 'LOCATION', fontproperties=SANS_B, fontsize=10, color=INK,
             ha='center', va='top')
    fig.text(PM / PW, (PM * 0.4) / H, 'Concept after Edin Radončić (2015). Boundaries do not imply endorsement of any '
             'territorial claim. Full sources: last page.', fontproperties=SANS_L, fontsize=10, color=INK2)


if __name__ == '__main__':
    keys = sys.argv[1:] or [s['key'] for s in SPECS]
    for s in SPECS:
        if s['key'] in keys:
            f = regional_page(s)
            f.savefig(ROOT + f'/out/reg_{s["key"]}.pdf', facecolor=PAPER)
            f.savefig(ROOT + f'/out/reg_{s["key"]}.png', dpi=50, facecolor=PAPER)
            plt.close(f)

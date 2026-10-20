"""Last page: data sources & methods."""
import sys, textwrap
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from style import *
from common import DATA, ROOT

METH = [
    ('What is mapped', 'The share of the total resident population that is Muslim, for the smallest statistical unit '
     'for which a reasonably current figure exists. Classes follow the original map: seven minority classes '
     '(<1% to 40–50%) in browns and five majority classes (50–60% to 90–100%) in greens.'),
    ('National baseline', 'All countries and territories start from Pew Research Center, “Religious Composition by '
     'Country, 2010–2020” (published June 2025; 2020 reference year). Territories that Pew does not list separately '
     'use the latest national census or are marked as estimates.'),
    ('Subnational detail', 'Where a census, population register or official survey tabulates religion below the '
     'national level, those shares replace the national value for each province, district or municipality. Values '
     'are not rescaled to the Pew totals, so a country’s units reflect the year of their own source (2000–2024). '
     'Units without a published figure that fall back to a common default value (e.g. Serbian municipalities with '
     'under 1% Muslims, smaller Scottish councils) are merged into one unlabelled remainder.'),
    ('Numbers of Muslims', 'Labels show the share and, where the source gives it, the number of Muslims (e.g. '
     '“0.5% · 24k”) for every minority unit: India, the UK, the US, Canada (76 economic regions), Australia (547 local '
     'government areas), Indonesia (regencies), Bangladesh, the Philippines, Sri Lanka, Nepal, Myanmar, Kenya, '
     'Croatia and Guyana from census counts; countries with national data only from Pew. '
     'Counts marked ≈ (Germany, France, Spain’s provinces, Benelux, Austria, Switzerland, Scottish councils) are share × latest '
     'official population and inherit the uncertainty of the share.'),
    ('Ethnicity-based figures', 'Russia, China, Kyrgyzstan, Mongolia and Kosovo’s Serb-majority areas have no '
     'religion question (or an unreliable one). There, the combined share of traditionally Muslim nationalities '
     '(e.g. Tatars, Bashkirs, Chechens, Hui, Uyghurs, Kazakhs) is shown — the same convention used by Pew and by '
     'the original 2015 map.'),
    ('Estimates', 'Nigeria, Tanzania, Côte d’Ivoire, five of Burkina Faso’s 13 regions, Cameroon, Chad, Togo, Sierra '
     'Leone, Liberia, Eritrea, the Central African Republic, Mozambique, Upper Egypt, Casamance, '
     'Madagascar, Suriname, France, Germany, Belgium, Greek Thrace, Kosovo’s Serb-majority areas and '
     'the post-2017 Rakhine figure are modelled: regional shares follow documented geographic patterns and are '
     'constrained to the national survey or census total. Treat them as ±10 percentage points.'),
    ('Community circles', 'In Latin America and the Caribbean Muslims are under 1% almost everywhere, so communities '
     'are drawn as proportional circles (area proportional to the number of Muslims, one scale per page). Brazil: 175 municipalities '
     'with 20+ Muslims in the 2010 census (IBGE table 137; the 2022 census groups Islam under “other religions”), '
     'merged into metropolitan areas where they adjoin (Greater São Paulo, Baixada Santista, Greater Curitiba, Greater '
     'Porto Alegre, Greater Rio…) and, on page 1, with any town within 45 km. Twin border cities are joined: Foz do '
     'Iguaçu – Ciudad del Este, Chuí – Chuy. Chile: 2024 census (persons 15+). Elsewhere Pew’s national total is '
     'shared among cities with documented communities (dashed). Argentina (no census data; Pew’s ≈420,000 is '
     'heritage-based) and Coquimbo appear as points without size. Paraguay’s 2002 census counted 872 Muslims (486 in '
     'Alto Paraná) — far below community estimates of ≈7,000 in Ciudad del Este, many of them foreign nationals.'),
    ('United States metros', 'Page 6 adds the 2020 U.S. Religion Census (ASARB) “Muslim estimate” for all 383 '
     'metropolitan statistical areas, retrieved from the ARDA metro reports; it is a congregation-based count '
     '(4.45 million nationally), higher than survey-based estimates.'),
    ('Regional pages & projection', 'Page 1: Equal Earth (equal-area), centred on 11°E. Pages 2–5: Lambert azimuthal '
     'equal-area centred on each region; page 6: Albers equal-area conic. Boundaries: Natural Earth 1:10m (coastlines, '
     'countries, provinces; de facto control, disputed lines dashed), geoBoundaries, ONS 2021 local authorities, DataMeet '
     'India 2011 districts, county outlines for Xinjiang and Linxia. Province lines are drawn only for large countries '
     'without subnational data (and Paraguay).'),
    ('Known limitations', 'India’s figures date from the 2011 census (the 2027 census is under way); Indonesia’s '
     'regencies from 2010 (regencies created since take their parent’s value); Burkina Faso’s provinces from 2006; '
     'Ethiopia’s from 2007; Thailand’s provincial table from 2000. Spain’s provinces share out UCIDE community totals. Bulgarian shares are of all residents including the ~12% '
     'who did not answer. Migrant populations (Gulf states, Western Europe, Moscow) may be under-counted by censuses.'),
]


def methods_page(total_pages=7):
    W2, H2 = 33.1, 31.8
    f2 = plt.figure(figsize=(W2, H2), facecolor=PAPER)

    def t2(x, y, s, fp, size, color=INK, ha='left', va='top', **kw):
        return f2.text(x / W2, y / H2, s, fontproperties=fp, fontsize=size, color=color, ha=ha, va=va, **kw)
    m = 1.0
    t2(m, H2 - m, 'WORLD MUSLIM POPULATION — DATA SOURCES & METHODS', SANS_BL, 40)
    t2(m, H2 - m - 0.75, 'Companion sheet to the 2026 edition. Every value on the maps can be traced to a row below.  '
       f'Page {total_pages} of {total_pages}.', SANS_L, 18, color=INK2)
    f2.add_artist(plt.Line2D([m / W2, (W2 - m) / W2], [(H2 - m - 1.3) / H2] * 2, color=INK, lw=1.2))
    y = H2 - m - 1.7
    t2(m, y, 'METHODS', SANS_B, 19, color=ACCENT); y -= 0.55
    for head, body in METH:
        t2(m, y, head, SANS_SB, 14.5); y -= 0.36
        body_w = textwrap.fill(body, 66)
        t2(m, y, body_w, SANS, 12.4, color=INK, linespacing=1.3)
        y -= 0.248 * (body_w.count('\n') + 1) + 0.33
    print('methods column bottom at', round(y, 2), 'in')
    reg = pd.read_csv(f'{DATA}/sources_registry.csv')
    import geopandas as gpd
    ctry = gpd.read_file(ROOT + '/raw/ne_10m_admin_0_countries.geojson', ignore_geometry=True)
    names = dict(zip(ctry.ADM0_A3, ctry.ADMIN))
    names.update({'LAT': 'Latin America & Caribbean (circles)', 'PSE': 'Palestine', 'KOS': 'Kosovo',
                  'GBR': 'United Kingdom', 'USA': 'United States', 'TZA': 'Tanzania', 'SRB': 'Serbia',
                  'CIV': 'Côte d’Ivoire'})
    reg['country'] = reg.iso3.map(names).fillna(reg.iso3)
    reg = reg.sort_values('country')
    x0 = m + 11.0
    t2(x0, H2 - m - 1.7, 'SUBNATIONAL SOURCES BY COUNTRY', SANS_B, 19, color=ACCENT)
    cols = [(x0, 'Country'), (x0 + 3.0, 'Units mapped'), (x0 + 6.6, 'Source'), (x0 + 16.8, 'Year'), (x0 + 18.3, 'Basis')]
    yt = H2 - m - 2.35
    for x, h in cols:
        t2(x, yt, h.upper(), SANS_SB, 11, color=INK2)
    f2.add_artist(plt.Line2D([x0 / W2, (W2 - m) / W2], [(yt - 0.3) / H2] * 2, color=INK, lw=0.8))
    yy = yt - 0.42
    for i, r in enumerate(reg.itertuples()):
        src_s, notes_s = str(r.source), str(r.notes)
        if 'ESTIMATE' in src_s or notes_s.startswith('Estimate'):
            basis = 'Estimate'
        elif 'Partly' in notes_s:
            basis = 'Census + estimate'
        elif 'ethnic' in src_s.lower():
            basis = 'Census (ethnicity)'
        else:
            basis = 'Census / register'
        src = textwrap.fill(src_s.replace('ESTIMATE — ', 'Modelled: ').replace('ESTIMATE ', 'Modelled: '), 104)
        lvl = textwrap.fill(str(r.level), 26)
        nl = max(src.count('\n'), lvl.count('\n')) + 1
        if i % 2 == 0:
            f2.add_artist(Rectangle((x0 / W2, (yy - 0.205 * nl - 0.02) / H2), (W2 - m - x0) / W2,
                                    (0.205 * nl + 0.1) / H2, facecolor='#F0EEE6', edgecolor='none',
                                    transform=f2.transFigure))
        t2(cols[0][0], yy, r.country, COND_SB, 10.6)
        t2(cols[1][0], yy, lvl, COND, 10.2, color=INK2, linespacing=1.15)
        t2(cols[2][0], yy, src, COND, 10.2, linespacing=1.15)
        t2(cols[3][0], yy, str(r.year), COND, 10.2, color=INK2)
        bcol = BROWN if basis == 'Estimate' else (COLORS[3] if 'estimate' in basis else ACCENT)
        t2(cols[4][0], yy, basis, COND_SB, 10.2, color=bcol)
        yy -= 0.205 * nl + 0.085
    t2(x0, yy - 0.15, 'All other countries and territories: Pew Research Center 2020 national estimate (one value '
       'per country). Boundaries: Natural Earth, geoBoundaries (William & Mary geoLab), ONS, DataMeet.', COND_I, 10.5,
       color=INK2)
    t2(m, 0.75, 'Concept after Edin Radončić, “World Muslim Population” (2015). Compiled October 2026. A machine-readable '
       'table of every unit (name, share, count, source) accompanies this PDF.', SANS_L, 11, color=INK2)
    print('sources table bottom at', round(yy, 2), 'in')
    return f2

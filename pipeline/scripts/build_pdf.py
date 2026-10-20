"""Assemble the full 7-page PDF, previews and data tables."""
import sys, time
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import pandas as pd, geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from style import PAPER
from common import DATA, ROOT
import world, regional, methods
from mapkit import cluster_communities, load_communities, clean_unit

OUT = ROOT + '/out'
PDF = f'{OUT}/World_Muslim_Population_2026.pdf'
t0 = time.time()
with PdfPages(PDF) as pdf:
    f = world.world_page()
    pdf.savefig(f, facecolor=PAPER)
    f.savefig(f'{OUT}/preview_p1.png', dpi=60, facecolor=PAPER)
    plt.close(f)
    print('page 1', round(time.time() - t0), 's')
    for s in regional.SPECS:
        f = regional.regional_page(s)
        pdf.savefig(f, facecolor=PAPER)
        f.savefig(f'{OUT}/preview_p{s["n"]}_{s["key"]}.png', dpi=60, facecolor=PAPER)
        plt.close(f)
        print('page', s['n'], round(time.time() - t0), 's')
    f = methods.methods_page()
    pdf.savefig(f, facecolor=PAPER)
    f.savefig(f'{OUT}/preview_p7_sources.png', dpi=60, facecolor=PAPER)
    plt.close(f)
    d = pdf.infodict()
    d['Title'] = 'World Muslim Population — 2026 edition'
    d['Subject'] = 'Share and number of Muslims by country, province, district and city; world map and regional close-ups'
    d['Keywords'] = 'Islam, Muslim population, census, choropleth, Equal Earth, Latin America, Europe, Balkans, Caucasus, United States'
print('pdf written', round(time.time() - t0), 's')

# ---------------------------------------------------------------- data tables
nat = gpd.read_file(f'{DATA}/units_national.gpkg', ignore_geometry=True)
sub = gpd.read_file(f'{DATA}/units_sub.gpkg', ignore_geometry=True)
names = dict(zip(nat.ADM0_A3, nat.ADMIN))
names.update({'PSX': 'Palestine', 'KOS': 'Kosovo'})
subiso = set(sub.iso)
rows = []
for r in sub.itertuples():
    rows.append({'iso3': r.iso, 'country': names.get(r.iso, r.iso), 'unit': clean_unit(r.unit) if r.unit else '(remainder, no separate figure)',
                 'level': 'subnational', 'share_pct': round(r.pct, 3),
                 'muslims': None if r.muslims != r.muslims else int(round(r.muslims)),
                 'muslims_approx': bool(r.cnt_est) if r.muslims == r.muslims else None,
                 'source': r.src})
for r in nat.drop_duplicates('ADMIN').itertuples():
    if r.ADM0_A3 in subiso and r.ADM0_A3 != 'ROU':
        continue
    if r.pct != r.pct:
        continue
    rows.append({'iso3': r.ADM0_A3, 'country': r.ADMIN, 'unit': r.ADMIN, 'level': 'national', 'share_pct': round(r.pct, 3),
                 'muslims': None if r.muslims != r.muslims else int(r.muslims), 'muslims_approx': False, 'source': r.src})
tab = pd.DataFrame(rows).sort_values(['country', 'level', 'unit'])
tab.to_csv(f'{OUT}/World_Muslim_Population_2026_units.csv', index=False)
com = load_communities()
cl = cluster_communities(com, 12)
grp = {}
for c in cl.itertuples():
    for m in c.members.split(', '):
        grp[m] = c.name
com['group_on_maps'] = com.name.map(grp)
com = com.drop(columns=['label', 'pos']).sort_values('muslims', ascending=False)
com.to_csv(f'{OUT}/LatAm_Caribbean_communities_2026.csv', index=False)
us = pd.read_csv(f'{DATA}/usa_metros_arda2020.csv')
us.to_csv(f'{OUT}/USA_metro_areas_Muslim_adherents_2020.csv', index=False)
print('tables:', len(tab), len(com), len(us))

"""Project and simplify all layers once; cache to pickle."""
import sys, pickle, warnings
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, geopandas as gpd
from shapely.ops import unary_union
from shapely import make_valid
from common import RAW, DATA
from geo import project, pt

TOL = 250  # metres; ~1/40 pt at full poster scale

def proj_gdf(g, kind='poly', tol=TOL, seg=0.5):
    geoms = [project(x, seg=seg, simplify=tol, kind=kind) for x in g.geometry]
    g = g.copy(); g['geometry'] = geoms
    return g[g.geometry.notna()]

L = {}
nat = gpd.read_file(f'{DATA}/units_national.gpkg')
sub = gpd.read_file(f'{DATA}/units_sub.gpkg')
print('projecting units...')
L['national'] = proj_gdf(nat)
L['sub'] = proj_gdf(sub)

print('lines...')
L['coast'] = proj_gdf(gpd.read_file(f'{RAW}/ne_10m_coastline.geojson'), 'line', tol=150)
bl = gpd.read_file(f'{RAW}/ne_10m_admin_0_boundary_lines_land.geojson')
L['borders'] = proj_gdf(bl, 'line', tol=150)
dl = gpd.read_file(f'{RAW}/ne_10m_admin_0_boundary_lines_disputed_areas.geojson')
L['disputed'] = proj_gdf(dl, 'line', tol=150)
a1 = gpd.read_file(f'{RAW}/ne_10m_admin_1_states_provinces_lines.geojson')
L['admin1'] = proj_gdf(a1, 'line', tol=250)
lk = gpd.read_file(f'{RAW}/ne_10m_lakes.geojson')
lk = lk[lk.scalerank <= 7]
L['lakes'] = proj_gdf(lk, tol=200)
rv = gpd.read_file(f'{RAW}/ne_10m_rivers_lake_centerlines.geojson')
rv = rv[(rv.scalerank <= 7) & (rv.featurecla != 'Lake Centerline')]
L['rivers'] = proj_gdf(rv, 'line', tol=250)
ice = gpd.read_file(f'{RAW}/ne_10m_antarctic_ice_shelves_polys.geojson')
L['iceshelf'] = proj_gdf(ice, tol=500)
mar = gpd.read_file(f'{RAW}/ne_10m_geography_marine_polys.geojson')
L['marine'] = mar.drop(columns='geometry').assign(rp=[g.representative_point() for g in mar.geometry])
c0 = gpd.read_file(f'{RAW}/ne_10m_admin_0_countries.geojson')
L['countries'] = c0[['ADMIN', 'NAME', 'NAME_LONG', 'ADM0_A3', 'LABELRANK', 'MIN_LABEL', 'LABEL_X', 'LABEL_Y', 'POP_EST']].copy()
pickle.dump(L, open(f'{DATA}/layers.pkl', 'wb'))
for k, v in L.items():
    print(k, len(v))

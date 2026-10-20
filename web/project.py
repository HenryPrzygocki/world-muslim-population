"""Step 1 of 2 of build-time projection: split every layer at the projection's seam (169°W, opposite the 11°E centre)
with a small gap, so that no TopoJSON arc crosses it. topo.sh then builds topology in lon/lat (where mapshaper's clean
works) and topo_project.py projects the finished arcs to Equal Earth metres."""
import os, warnings
warnings.filterwarnings('ignore')
import numpy as np, geopandas as gpd, shapely
from shapely.geometry import box
from pyproj import Transformer

B = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build')
os.makedirs(f'{B}/p', exist_ok=True)
SEAM = -169.0
EPS = 0.05     # degrees either side of the seam; survives quantization, invisible at the map edge
W = box(-180, -90, SEAM - EPS, 90)
E_ = box(SEAM + EPS, -90, 180, 90)
tr = Transformer.from_crs('EPSG:4326', '+proj=eqearth +lon_0=11 +R=6371000 +x_0=0 +y_0=0 +units=m +no_defs', always_xy=True)

def proj_geom(g):
    if g is None or g.is_empty:
        return g
    x0, _, x1, _ = g.bounds
    if x0 < SEAM < x1:                     # crosses the seam: project each side separately
        parts = [g.intersection(W), g.intersection(E_)]
        parts = [p for p in parts if not p.is_empty]
        if g.geom_type in ('Polygon', 'MultiPolygon'):
            return shapely.multipolygons([q for p in parts for q in getattr(p, 'geoms', [p]) if q.geom_type == 'Polygon'])
        return shapely.multilinestrings([l for p in parts for l in getattr(p, 'geoms', [p]) if l.geom_type == 'LineString'])
    return g

for name in ['countries', 'units', 'lakes', 'provlines', 'disputed', 'occupied', 'kri']:
    g = gpd.read_file(f'{B}/{name}.geojson')
    g['geometry'] = [proj_geom(x) for x in g.geometry]
    g.to_file(f'{B}/p/{name}.geojson', driver='GeoJSON')
    print(name, len(g))

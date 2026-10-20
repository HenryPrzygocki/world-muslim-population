"""Projection helpers: Equal Earth centred on 11°E, cut at 169°W."""
import numpy as np
import shapely
from shapely.geometry import box, Polygon, MultiPolygon, LineString, MultiLineString, GeometryCollection
from shapely.geometry.polygon import orient
from pyproj import Transformer

LON0 = 11.0
CUT = LON0 - 180.0          # -169
EPS = 1e-7
PROJ = f'+proj=eqearth +lon_0={LON0} +datum=WGS84 +units=m +no_defs'
T = Transformer.from_crs(4326, PROJ, always_xy=True)
LEFT = box(-180, -90, CUT - EPS, 90)     # goes to the right-hand edge (shift +360)
RIGHT = box(CUT + EPS, -90, 180, 90)


def _fwd(xy):
    x, y = T.transform(xy[:, 0], xy[:, 1])
    return np.column_stack([x, y])


def _fwd_shift(xy):
    x, y = T.transform(xy[:, 0] + 360.0, xy[:, 1])
    return np.column_stack([x, y])


def _parts(g):
    if g is None or g.is_empty:
        return []
    if hasattr(g, 'geoms'):
        out = []
        for p in g.geoms:
            out += _parts(p)
        return out
    return [g]


def project(g, seg=0.5, simplify=0.0, kind='poly'):
    """Project lon/lat geometry; split at the cut meridian; optional simplification (metres)."""
    if g is None or g.is_empty:
        return None
    try:
        g = shapely.segmentize(g, seg)
    except Exception:
        try:
            g = shapely.segmentize(shapely.make_valid(g), seg)
        except Exception:
            return None
    out = []
    for clip, fn in ((RIGHT, _fwd), (LEFT, _fwd_shift)):
        b = g.bounds
        if fn is _fwd_shift and b[0] >= CUT:
            continue
        if fn is _fwd and b[2] <= CUT:
            continue
        p = g if (fn is _fwd and b[0] > CUT) else g.intersection(clip)
        if p.is_empty:
            continue
        p = shapely.transform(p, fn)
        if simplify:
            p = p.simplify(simplify, preserve_topology=True)
        out += _parts(p)
    if kind == 'poly':
        polys = [orient(p, 1.0) for p in out if p.geom_type == 'Polygon' and p.area > 0]
        if not polys:
            return None
        return MultiPolygon(polys) if len(polys) > 1 else polys[0]
    else:
        lines = [p for p in out if p.geom_type in ('LineString', 'LinearRing')]
        if not lines:
            return None
        return MultiLineString(lines) if len(lines) > 1 else lines[0]


def sphere(n=721):
    lats = np.linspace(-90, 90, n)
    left = [(CUT + EPS, la) for la in lats]
    right = [(CUT - EPS + 360, la) for la in lats[::-1]]
    xy = np.array(left + right)
    x, y = T.transform(xy[:, 0], xy[:, 1])
    return Polygon(np.column_stack([x, y]))


def graticule(step=30, n=361):
    lines = []
    for lat in range(-90 + step, 90, step):
        lons = np.linspace(CUT + EPS, CUT + 360 - EPS, n)
        x, y = T.transform(lons, np.full_like(lons, lat))
        lines.append(LineString(np.column_stack([x, y])))
    for lon in np.arange(-180, 180, step):
        if abs(((lon - CUT + 180) % 360) - 180) < 1e-9:
            continue
        lats = np.linspace(-90, 90, n)
        ll = lon if lon > CUT else lon + 360
        x, y = T.transform(np.full_like(lats, ll), lats)
        lines.append(LineString(np.column_stack([x, y])))
    return lines


def pt(lon, lat):
    if lon < CUT:
        lon += 360
    x, y = T.transform(lon, lat)
    return x, y

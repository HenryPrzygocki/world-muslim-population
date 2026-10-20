"""Step 2 of 2: project TopoJSON arcs (lon/lat) to Equal Earth metres (lon_0 = 11°E, sphere R = 6 371 km), re-quantize.
The browser turns metres into its base pixels with d3's Equal Earth scale/translate, so no projection runs client-side."""
import json, sys, os
import numpy as np
from pyproj import Transformer
tr = Transformer.from_crs('EPSG:4326', '+proj=eqearth +lon_0=11 +R=6371000 +x_0=0 +y_0=0 +units=m +no_defs', always_xy=True)
B = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build')
for fn in sys.argv[1:]:
    t = json.load(open(f'{B}/{fn}'))
    (sx, sy), (tx, ty) = t['transform']['scale'], t['transform']['translate']
    lens = [len(a) for a in t['arcs']]
    q = np.concatenate([np.array(a, dtype=np.int64) for a in t['arcs']])
    starts = np.cumsum([0] + lens[:-1])
    xs, ys = q[:, 0].copy(), q[:, 1].copy()
    # undo delta encoding per arc
    idx = np.zeros(len(q), dtype=np.int64); idx[starts] = 1; seg = np.cumsum(idx) - 1
    xs = np.cumsum(xs); ys = np.cumsum(ys)
    off_x = np.concatenate([[0], xs[starts[1:] - 1]]); off_y = np.concatenate([[0], ys[starts[1:] - 1]])
    xs = xs - off_x[seg]; ys = ys - off_y[seg]
    lon, lat = xs * sx + tx, ys * sy + ty
    X, Y = tr.transform(lon, np.clip(lat, -90, 90))
    n = int(max(xs.max(), ys.max())) + 1          # keep the original quantization (e.g. 200 000 steps)
    x0, x1, y0, y1 = X.min(), X.max(), Y.min(), Y.max()
    ksx, ksy = (x1 - x0) / (n - 1), (y1 - y0) / (n - 1)
    QX = np.round((X - x0) / ksx).astype(np.int64); QY = np.round((Y - y0) / ksy).astype(np.int64)
    arcs = []
    for s0, L in zip(starts, lens):
        ax, ay = QX[s0:s0 + L], QY[s0:s0 + L]
        d = np.column_stack([np.diff(ax, prepend=0), np.diff(ay, prepend=0)])
        d[0] = [ax[0], ay[0]]
        arcs.append(d.tolist())
    t['arcs'] = arcs
    t['transform'] = {'scale': [ksx, ksy], 'translate': [x0, y0]}
    t['proj'] = 'eqearth lon_0=11 R=6371000 (metres)'
    t.pop('bbox', None)
    json.dump(t, open(f'{B}/{fn}', 'w'), separators=(',', ':'))
    print(fn, 'projected', len(arcs), 'arcs', os.path.getsize(f'{B}/{fn}') // 1024, 'KB')

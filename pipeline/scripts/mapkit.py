"""Shared drawing, labelling and community-symbol machinery for the world page and the regional pages."""
import math
import numpy as np
import pandas as pd
from matplotlib.path import Path
from matplotlib.patches import PathPatch, Circle, Rectangle
from matplotlib.collections import LineCollection
import matplotlib.patheffects as pe
from matplotlib.ft2font import FT2Font, LOAD_NO_HINTING
from shapely.ops import polylabel
from shapely.geometry import Point
from style import *
from common import DATA


# ------------------------------------------------------------------ text metrics
_FT = {}


def text_w(s, fp, size):
    """Advance width of (possibly multi-line) text in points."""
    fn = fp.get_file()
    f = _FT.get(fn)
    if f is None:
        f = _FT[fn] = FT2Font(fn)
    f.set_size(max(size, 0.5), 72)
    w = 0.0
    for line in s.split('\n'):
        f.set_text(line, 0.0, flags=LOAD_NO_HINTING)
        w = max(w, f.get_width_height()[0] / 64.0)
    return w


def spaced(s):
    """letter-spaced caps (normal spaces; thin spaces are missing from the fonts)"""
    return '\n'.join('   '.join(' '.join(list(w)) for w in line.split(' ')) for line in s.split('\n'))


# ------------------------------------------------------------------ number formatting
def fmt(p):
    if p <= 0:
        return '0%'
    if p < 0.1:
        return '<0.1%'
    if p < 1:
        return f'{p:.1f}%'
    if p >= 99.5:
        return '>99%'
    if p < 10:
        return f'{p:.1f}%'.replace('.0%', '%')
    return f'{p:.0f}%'


def fmtn(n, est=False):
    """compact count: 87 · 540 · 9.6k · 25k · 342k · 3.6M · 36M"""
    if n is None or n != n:
        return ''
    n = float(n)
    if n < 100:
        s = f'{n:.0f}'
    elif n < 1000:
        s = f'{round(n, -1):.0f}'
    elif n < 9950:
        s = f'{n / 1000:.1f}k'
    elif n < 999500:
        s = f'{n / 1000:.0f}k'
    elif n < 9.95e6:
        s = f'{n / 1e6:.1f}M'
    else:
        s = f'{n / 1e6:.0f}M'
    return ('≈' if est else '') + s


def value_line(pct, cnt=None, est=False):
    if cnt is not None and cnt == cnt and pct < 50:
        return f'{fmt(pct)} · {fmtn(cnt, est)}'
    return fmt(pct)


# ------------------------------------------------------------------ collision registry
class Boxes:
    """axis-aligned boxes in data units, bucketed on a grid"""

    def __init__(self, cell):
        self.cell = cell
        self.grid = {}
        self.items = []

    def _cells(self, b):
        c = self.cell
        for i in range(int(math.floor(b[0] / c)), int(math.floor(b[2] / c)) + 1):
            for j in range(int(math.floor(b[1] / c)), int(math.floor(b[3] / c)) + 1):
                yield (i, j)

    def hit(self, b, ignore=None):
        seen = set()
        for k in self._cells(b):
            for idx in self.grid.get(k, ()):
                if idx in seen:
                    continue
                seen.add(idx)
                bb, tag = self.items[idx]
                if ignore is not None and tag == ignore:
                    continue
                if b[0] < bb[2] and b[2] > bb[0] and b[1] < bb[3] and b[3] > bb[1]:
                    return True
        return False

    def add(self, b, tag=None):
        idx = len(self.items)
        self.items.append((b, tag))
        for k in self._cells(b):
            self.grid.setdefault(k, []).append(idx)


# ------------------------------------------------------------------ canvas
def ring_codes(n):
    c = np.full(n, Path.LINETO, dtype=np.uint8)
    c[0] = Path.MOVETO
    c[-1] = Path.CLOSEPOLY
    return c


def poly_path(geoms):
    verts, codes = [], []
    for g in geoms:
        if g is None:
            continue
        for p in getattr(g, 'geoms', [g]):
            if p.geom_type != 'Polygon':
                continue
            for ring in [p.exterior] + list(p.interiors):
                a = np.asarray(ring.coords)
                if len(a) < 4:
                    continue
                verts.append(a)
                codes.append(ring_codes(len(a)))
    if not verts:
        return None
    return Path(np.concatenate(verts), np.concatenate(codes))


def segs_of(geoms, rings=False):
    out = []
    for g in geoms:
        if g is None:
            continue
        for p in getattr(g, 'geoms', [g]):
            if p.geom_type == 'Polygon':
                if rings:
                    out.append(np.asarray(p.exterior.coords))
                    out += [np.asarray(r.coords) for r in p.interiors]
            elif p.geom_type in ('LineString', 'LinearRing'):
                out.append(np.asarray(p.coords))
            elif hasattr(p, 'geoms'):
                out += segs_of([p], rings)
    return out


class Canvas:
    def __init__(self, ax, ppm, cell_pt=24, extent=None, clip=False):
        self.ax = ax
        self.ppm = ppm                      # points per data unit (metre)
        self.boxes = Boxes(cell_pt / ppm)
        self.extent = extent                # (x0, y0, x1, y1): labels must stay inside
        self.clip = clip

    def free(self, b, ignore=None):
        e = self.extent
        if e is not None and (b[0] < e[0] or b[1] < e[1] or b[2] > e[2] or b[3] > e[3]):
            return False
        return not self.boxes.hit(b, ignore=ignore)

    # geometry --------------------------------------------------------
    def fill(self, geoms, color, z, ec=None, lw=0.0, alpha=1.0, hatch=None):
        p = poly_path(geoms)
        if p is None:
            return
        self.ax.add_patch(PathPatch(p, facecolor=color, edgecolor=ec if ec else color, lw=lw, zorder=z, alpha=alpha,
                                    joinstyle='round', capstyle='round', hatch=hatch))

    def lines(self, geoms, color, lw, z, rings=False, ls='solid', alpha=1.0, cap='round'):
        segs = segs_of(geoms, rings)
        if not segs:
            return
        self.ax.add_collection(LineCollection(segs, colors=color, linewidths=lw, zorder=z, linestyles=ls, alpha=alpha,
                                              capstyle=cap, joinstyle='round'))

    # text ----------------------------------------------------------------
    def text(self, x, y, s, fp, size, color=INK, z=20, ha='center', va='center', alpha=1.0, rot=0, ls=None,
             halo=None, lsp=1.2):
        if ls:
            s = spaced(s)
        if halo:   # separate outline copy keeps the real text searchable in the PDF
            h = self.ax.text(x, y, s, fontproperties=fp, fontsize=size, color=halo[0], ha=ha, va=va, zorder=z - 0.01,
                             alpha=halo[2] if len(halo) > 2 else 1, rotation=rot, rotation_mode='anchor')
            h.set_path_effects([pe.withStroke(linewidth=halo[1], foreground=halo[0])])
            h.set_linespacing(lsp)
            h.set_clip_on(self.clip)
        t = self.ax.text(x, y, s, fontproperties=fp, fontsize=size, color=color, ha=ha, va=va, zorder=z, alpha=alpha,
                         rotation=rot, rotation_mode='anchor')
        t.set_linespacing(lsp)
        t.set_clip_on(self.clip)
        return t

    def tbox(self, x, y, s, fp, size, ha='center', va='center', lsp=1.2, pad=0.12, ls=None):
        if ls:
            s = spaced(s)
        w = text_w(s, fp, size) / self.ppm
        n = s.count('\n') + 1
        h = size * (0.86 + (n - 1) * lsp) / self.ppm
        x0 = {'left': x, 'center': x - w / 2, 'right': x - w}[ha]
        y0 = {'bottom': y, 'baseline': y - 0.22 * size / self.ppm, 'center': y - h / 2, 'top': y - h}[va]
        p = pad * size / self.ppm
        return (x0 - p, y0 - p, x0 + w + p, y0 + h + p)

    def place(self, x, y, s, fp, size, ha='center', va='center', lsp=1.2, ls=None, force=False, ignore=None,
              tag=None, **kw):
        """draw text only if its box is free (or force); register it. Returns True if drawn."""
        b = self.tbox(x, y, s, fp, size, ha, va, lsp, ls=ls)
        if not force and not self.free(b, ignore=ignore):
            return False
        self.boxes.add(b, tag)
        self.text(x, y, s, fp, size, ha=ha, va=va, lsp=lsp, ls=ls, **kw)
        return True

    def block(self, b, tag=None):
        self.boxes.add(b, tag)


# ------------------------------------------------------------------ choropleth unit labels
_NAME_FIX = {'Chechen Republic': 'Chechnya', 'Karachay-Cherkess Republic': 'Karachay-Cherkessia',
             'Kabardino-Balkar Republic': 'Kabardino-Balkaria', 'Chuvash Republic': 'Chuvashia',
             'Udmurt Republic': 'Udmurtia', 'Republic of North Ossetia-Alania': 'North Ossetia–Alania',
             'Republic of North Ossetia–Alania': 'North Ossetia–Alania', 'Republic of North Ossetia - Alania': 'North Ossetia–Alania'}


def clean_unit(name):
    name = str(name)
    if name in _NAME_FIX:
        return _NAME_FIX[name]
    if name.startswith('Republic of '):
        name = name[len('Republic of '):]
    return name


def interior_spots(poly, rmin, n=9, k=8):
    """alternative label anchors: interior grid points with the largest clearance (>= rmin)"""
    x0, y0, x1, y1 = poly.bounds
    out = []
    for i in range(n):
        for j in range(n):
            p = Point(x0 + (i + 0.5) * (x1 - x0) / n, y0 + (j + 0.5) * (y1 - y0) / n)
            if not poly.contains(p):
                continue
            d = poly.exterior.distance(p)
            for h in poly.interiors:
                d = min(d, h.distance(p))
            if d >= rmin:
                out.append((d, p))
    out.sort(key=lambda t: -t[0])
    return out[:k]


def country_label(cv, lines_, x, y, size, poly, colour_at, value=None, minsize=2.6, spacing=True, z=25,
                  vfont=None, vfrac=0.66):
    """Fit a country name to its main polygon, then find a free spot among nearby candidates."""
    ppm = cv.ppm
    vfont = vfont or COND_M
    name = '\n'.join(lines_)
    b = poly.bounds if poly is not None else (x, y, x, y)
    wpt, hpt = (b[2] - b[0]) * ppm, (b[3] - b[1]) * ppm
    def fit(sp):
        w0 = text_w(spaced(name) if sp else name, COND_SB, size)
        f = size
        if wpt > 0:
            f = min(size, size * 0.95 * wpt / max(w0, 1e-6), 1.3 * hpt / (1.05 * len(lines_)))
        return max(f, minsize)
    s_un = fit(False)
    s_sp = fit(True) if spacing else 0
    ls = spacing and s_sp >= 9 and s_sp >= 0.8 * s_un
    size = s_sp if ls else s_un
    w = text_w(spaced(name) if ls else name, COND_SB, size)
    inside = poly is not None and w < wpt * 1.02 and size * 1.05 * len(lines_) < hpt * 1.3
    cands = [(x, y)]
    if poly is not None:
        hh = size * 1.1 * len(lines_) / ppm
        cands += [(x, y + 0.7 * hh), (x, y - 0.7 * hh), (x - 0.25 * w / ppm, y), (x + 0.25 * w / ppm, y)]
        cands += [(p.x, p.y) for _, p in interior_spots(poly, 0, n=7, k=6)]
    def vsz(s):
        return min(max(s * vfrac, 2.2), 9.5)
    tried = []
    for s in (size, size * 0.85, size * 0.72, size * 0.6, size * 0.5):
        if s < minsize * 0.9:
            break
        tried.append(s)
        for (cx, cy) in cands:
            bx = cv.tbox(cx, cy, name, COND_SB, s, lsp=0.95, ls=ls and s >= 9)
            vb = None
            if value:
                nl = len(lines_)
                dy = (s * (0.6 * nl) + s * 0.5) / ppm
                vb = cv.tbox(cx, cy - dy, value, vfont, vsz(s))
            if not cv.free(bx) or (vb is not None and not cv.free(vb)):
                continue
            if inside and poly is not None:
                if not poly.contains(Point(cx, cy)):
                    continue
                if vb is not None and not poly.contains(Point((vb[0] + vb[2]) / 2, (vb[1] + vb[3]) / 2)):
                    continue
            return _draw_country(cv, cx, cy, lines_, s, ls and s >= 9, value, colour_at, inside, z, vfont, vfrac)
    s = tried[-1] if tried else size          # nothing free: smallest tried size, at the anchor
    return _draw_country(cv, x, y, lines_, s, ls and s >= 9, value, colour_at, inside, z, vfont, vfrac)


def _draw_country(cv, x, y, lines_, size, ls, value, colour_at, inside, z, vfont, vfrac):
    ppm = cv.ppm
    if inside:
        col, a = ink_for(colour_at(x, y)); halo = None
    else:
        col, a, halo = INK, 1.0, (PAPER, max(1.0, size * 0.22), 0.85)
    cv.place(x, y, '\n'.join(lines_), COND_SB, size, ls=ls, lsp=0.95, force=True, color=col, alpha=a, z=z, halo=halo)
    if value:
        nl = len(lines_)
        dy = (size * (0.6 * nl) + size * 0.5) / ppm
        cv.place(x, y - dy, value, vfont, min(max(size * vfrac, 2.2), 9.5), force=True, color=col, alpha=a * 0.9, z=z,
                 halo=halo)
    return size

def unit_labels(cv, units, minsize=0.7, maxsize=5.5, namecol='unit', avoid=True, colour=None, z=15,
                min_pct_unlabelled=1.0, maxchars=24):
    """Name + value inside each unit (polylabel of its largest part), skipping fallback units and
    uninformative <1% units without a count; never overlaps already-registered labels."""
    ppm = cv.ppm
    cand = []
    for r in units.itertuples():
        g = r.geometry
        if g is None or r.pct != r.pct or getattr(r, 'dflt', False):
            continue
        cnt = getattr(r, 'muslims', np.nan)
        has_cnt = cnt is not None and cnt == cnt and cnt > 0
        if r.pct < min_pct_unlabelled and not has_cnt:
            continue
        if cnt is not None and cnt == cnt and cnt < 10:      # essentially no Muslims (e.g. outback LGAs)
            continue
        parts = sorted(getattr(g, 'geoms', [g]), key=lambda p: p.area, reverse=True)
        poly = parts[0]
        if poly.area * ppm * ppm < 12:
            continue
        try:
            c = polylabel(poly, tolerance=max(0.4 / ppm, math.sqrt(poly.area) / 60))
        except Exception:
            c = poly.representative_point()
        rad = poly.exterior.distance(c)
        for hole in poly.interiors:
            rad = min(rad, hole.distance(c))
        imp = min(1, math.log10(cnt + 1) / 5) if has_cnt else min(1, 0.4 + r.pct / 50)
        cand.append((rad * ppm, r, c, cnt if has_cnt else None, poly, rad * ppm * (0.3 + 0.7 * imp)))
    cand.sort(key=lambda t: -t[5])    # room weighted by importance: populous units win collisions
    n = 0
    for rad_pt, r, c, cnt, poly, _ in cand:
        name = clean_unit(getattr(r, namecol))
        if len(name) > maxchars:
            name = name[:maxchars - 1] + '…'
        val = value_line(r.pct, cnt, bool(getattr(r, 'cnt_est', False)))
        w1 = max(text_w(name, COND, 1.0), text_w(val, COND_SB, 0.92))
        # box (w1*s) x (2.1*s) must fit in the inscribed circle (some overflow allowed)
        size = min(maxsize, 1.22 * rad_pt / math.sqrt((w1 / 2) ** 2 + 1.05 ** 2))
        if size < minsize:
            continue
        k = r.k if hasattr(r, 'k') else klass(r.pct)
        bg = colour(r) if colour else (COLORS[k] if k >= 0 else NODATA)
        col, a = ink_for(bg)
        placed = False
        spots = [(c, size)]
        tried_alt = False
        while spots and not placed:
            cpt, s0 = spots.pop(0)
            s = s0
            while s >= minsize:
                y1 = cpt.y + s * 0.36 / ppm
                y2 = cpt.y - s * 0.62 / ppm
                b1 = cv.tbox(cpt.x, y1, name, COND, s)
                b2 = cv.tbox(cpt.x, y2, val, COND_SB, s * 0.92)
                b = (min(b1[0], b2[0]), b2[1], max(b1[2], b2[2]), b1[3])
                if not avoid or cv.free(b):
                    cv.block(b)
                    cv.text(cpt.x, y1, name, COND, s, color=col, alpha=a * 0.8, z=z)
                    cv.text(cpt.x, y2, val, COND_SB, s * 0.92, color=col, alpha=a * 0.92, z=z)
                    placed = True
                    break
                s *= 0.8
            if not placed and not tried_alt and avoid:
                tried_alt = True
                for rr, p in interior_spots(poly, rad_pt / ppm * 0.45):
                    sz = min(maxsize, 1.22 * rr * ppm / math.sqrt((w1 / 2) ** 2 + 1.05 ** 2))
                    if sz >= minsize:
                        spots.append((p, sz))
        n += placed
    return n


# ------------------------------------------------------------------ communities (proportional circles)
METROS = {
    'Greater São Paulo': ['São Paulo', 'Guarulhos', 'São Bernardo do Campo', 'Santo André', 'Osasco', 'Diadema', 'Mauá',
                          'Mogi das Cruzes', 'Suzano', 'Carapicuíba', 'Barueri', 'Taboão da Serra', 'Itaquaquecetuba',
                          'Cotia', 'Embu das Artes', 'Embu', 'Itapevi', 'São Caetano do Sul', 'Ferraz de Vasconcelos',
                          'Francisco Morato', 'Franco da Rocha', 'Itapecerica da Serra', 'Ribeirão Pires', 'Poá',
                          'Santana de Parnaíba', 'Caieiras', 'Mairiporã', 'Arujá', 'Embu-Guaçu', 'Jandira', 'Cajamar',
                          'Vargem Grande Paulista', 'Rio Grande da Serra', 'Santa Isabel', 'Biritiba-Mirim', 'Guararema',
                          'Salesópolis', 'Pirapora do Bom Jesus', 'Juquitiba', 'São Lourenço da Serra'],
    'Baixada Santista': ['Santos', 'Guarujá', 'São Vicente', 'Praia Grande', 'Cubatão', 'Bertioga', 'Mongaguá',
                         'Itanhaém', 'Peruíbe'],
    'Greater Rio de Janeiro': ['Rio de Janeiro', 'Niterói', 'Nova Iguaçu', 'Duque de Caxias', 'São Gonçalo',
                               'Belford Roxo', 'São João de Meriti', 'Nilópolis', 'Mesquita', 'Queimados', 'Magé',
                               'Itaboraí', 'Maricá', 'Seropédica', 'Japeri', 'Itaguaí', 'Paracambi', 'Guapimirim',
                               'Tanguá', 'Rio Bonito', 'Cachoeiras de Macacu', 'Petrópolis'],
    'Greater Porto Alegre': ['Porto Alegre', 'Canoas', 'Gravataí', 'Viamão', 'Novo Hamburgo', 'São Leopoldo', 'Alvorada',
                             'Sapucaia do Sul', 'Cachoeirinha', 'Esteio', 'Guaíba', 'Eldorado do Sul', 'Montenegro',
                             'Campo Bom', 'Sapiranga', 'Estância Velha', 'Portão', 'Nova Santa Rita', 'Triunfo',
                             'Charqueadas', 'São Jerônimo', 'Parobé', 'Taquara', 'Dois Irmãos', 'Ivoti', 'Glorinha',
                             'Santo Antônio da Patrulha', 'Arroio dos Ratos', 'Capela de Santana', 'Igrejinha'],
    'Greater Curitiba': ['Curitiba', 'São José dos Pinhais', 'Colombo', 'Araucária', 'Pinhais', 'Campo Largo',
                         'Almirante Tamandaré', 'Piraquara', 'Fazenda Rio Grande', 'Campina Grande do Sul',
                         'Quatro Barras', 'Rio Branco do Sul', 'Mandirituba', 'Contenda', 'Balsa Nova', 'Itaperuçu'],
    'Greater Belo Horizonte': ['Belo Horizonte', 'Contagem', 'Betim', 'Ribeirão das Neves', 'Santa Luzia', 'Ibirité',
                               'Sabará', 'Vespasiano', 'Nova Lima', 'Lagoa Santa'],
    'Brasília (Federal District)': ['Brasília', 'Valparaíso de Goiás', 'Águas Lindas de Goiás', 'Luziânia',
                                    'Novo Gama', 'Cidade Ocidental', 'Formosa', 'Planaltina', 'Santo Antônio do Descoberto'],
    'Campinas region': ['Campinas', 'Sumaré', 'Hortolândia', 'Americana', 'Indaiatuba', 'Valinhos', 'Vinhedo',
                        'Paulínia', 'Santa Bárbara d\'Oeste', 'Nova Odessa', 'Jaguariúna'],
    'Foz do Iguaçu – Ciudad del Este': ['Foz do Iguaçu', 'Ciudad del Este', 'Santa Terezinha de Itaipu', 'Hernandarias',
                                       'Presidente Franco', 'Minga Guazú'],
    'Chuí – Chuy': ['Chuí', 'Chuy'],
    'Florianópolis': ['Florianópolis', 'São José', 'Palhoça', 'Biguaçu'],
    'Goiânia': ['Goiânia', 'Aparecida de Goiânia', 'Trindade', 'Senador Canedo'],
}
METRO_ANCHOR = {'Greater São Paulo': 'São Paulo', 'Baixada Santista': 'Santos', 'Greater Rio de Janeiro': 'Rio de Janeiro',
                'Greater Porto Alegre': 'Porto Alegre', 'Greater Curitiba': 'Curitiba',
                'Greater Belo Horizonte': 'Belo Horizonte', 'Brasília (Federal District)': 'Brasília',
                'Campinas region': 'Campinas', 'Foz do Iguaçu – Ciudad del Este': 'Foz do Iguaçu',
                'Chuí – Chuy': 'Chuí', 'Florianópolis': 'Florianópolis', 'Goiânia': 'Goiânia'}


def hav_km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def load_communities():
    return pd.read_csv(f'{DATA}/communities.csv')


def cluster_communities(com, R_km, metros=True):
    """Named metropolitan groupings first, then greedy distance clustering (largest community anchors)."""
    com = com.copy().reset_index(drop=True)
    com['cid'] = -1
    out = []

    def emit(name, rows, anchor=None):
        rows = rows.sort_values('muslims', ascending=False)
        a = rows[rows.name == anchor].iloc[0] if anchor is not None and (rows.name == anchor).any() else rows.iloc[0]
        tot = rows.muslims.sum()
        cen = rows[rows.basis == 'census'].muslims.sum()
        basis = 'unsized' if (rows.basis == 'unsized').all() else ('census' if cen >= 0.5 * tot else 'estimate')
        out.append({'name': name, 'lat': a.lat, 'lon': a.lon, 'muslims': int(tot), 'basis': basis,
                    'n': len(rows), 'members': ', '.join(rows.name), 'country': a.country,
                    'pos': a.pos, 'label': int(rows.label.max()),
                    'mixed': rows.basis.nunique() > 1})

    if metros:
        for mname, members in METROS.items():
            sel = com[(com.cid < 0) & com.name.isin(members)]
            if len(sel) >= 1:
                if len(sel) == 1 and sel.iloc[0]['name'] == METRO_ANCHOR[mname] and ' – ' not in mname:
                    continue      # a lone core city keeps its own name
                com.loc[sel.index, 'cid'] = 1
                emit(mname if len(sel) > 1 else sel.iloc[0]['name'], sel, METRO_ANCHOR[mname])
    rest = com[com.cid < 0].sort_values('muslims', ascending=False)
    used = set()
    idx = list(rest.index)
    for i in idx:
        if i in used:
            continue
        a = com.loc[i]
        grp = [i]
        used.add(i)
        if R_km > 0:
            for j in idx:
                if j in used:
                    continue
                b = com.loc[j]
                if (a.basis == 'unsized') != (b.basis == 'unsized'):
                    continue
                if hav_km(a.lat, a.lon, b.lat, b.lon) <= R_km:
                    grp.append(j)
                    used.add(j)
        rows = com.loc[grp]
        name = a['name'] if len(grp) == 1 else f"{a['name']} area"
        emit(name, rows, a['name'])
    return pd.DataFrame(out).sort_values('muslims', ascending=False).reset_index(drop=True)


def draw_communities(cv, cl, xy, k, lab_min=300, tiny=1.5, fs=None, z0=30, force_min=3000, legend_basis=True,
                     label_counts=True):
    """cl: clustered communities; xy(lon, lat) -> data coords; k: radius pt per sqrt(n)."""
    ppm = cv.ppm
    geo = []
    for zi, r in enumerate(cl.itertuples()):
        x, y = xy(r.lon, r.lat)
        z = z0 + zi * 0.001
        if r.basis == 'unsized':
            R = 2.1 * max(1.0, k / 0.06) ** 0.5 / ppm
            cv.ax.add_patch(Rectangle((x - R, y - R), 2 * R, 2 * R, facecolor=PAPER, edgecolor=COLORS[6], lw=0.7,
                                      zorder=z))
            cv.ax.add_patch(Circle((x, y), R * 0.42, facecolor=COLORS[6], edgecolor='none', zorder=z + 0.0005))
        else:
            rp = max(0.45, k * math.sqrt(r.muslims))
            R = rp / ppm
            cv.ax.add_patch(Circle((x, y), R, facecolor=COLORS[4], edgecolor='none', alpha=0.5, zorder=z))
            cv.ax.add_patch(Circle((x, y), R, facecolor='none', edgecolor=COLORS[6], lw=0.55 if rp > 2 else 0.35,
                                   zorder=z + 0.0005, ls='solid' if r.basis == 'census' else (0, (2.2, 1.3))))
            if rp < 1.4:
                cv.ax.add_patch(Circle((x, y), R * 0.35, facecolor=COLORS[6], edgecolor='none', zorder=z + 0.0006))
        geo.append((r, x, y, R))
        s = R * 0.80
        cv.block((x - s, y - s, x + s, y + s), tag=('com', zi))
    # labels, biggest first
    n = 0
    for zi, (r, x, y, R) in enumerate(geo):
        big = r.basis == 'unsized' or r.muslims >= lab_min
        if fs is not None and big:
            size = fs(r)
            font = COND_SB if (r.basis != 'unsized' and r.muslims >= 3000) else COND_M
        else:
            size, font = tiny, COND
        lab = r.name if (r.basis == 'unsized' or not label_counts) else f'{r.name}  {r.muslims:,}'
        off = R + 0.25 * size / ppm + 0.6 / ppm
        d = off * 0.72
        cand = {'right': (x + off, y, 'left', 'center'), 'left': (x - off, y, 'right', 'center'),
                'above': (x, y + off, 'center', 'bottom'), 'below': (x, y - off, 'center', 'top'),
                'ur': (x + d, y + d, 'left', 'bottom'), 'lr': (x + d, y - d, 'left', 'top'),
                'ul': (x - d, y + d, 'right', 'bottom'), 'll': (x - d, y - d, 'right', 'top')}
        order = [r.pos if r.pos in cand else 'right'] + [p for p in ('right', 'left', 'ur', 'lr', 'above', 'below',
                                                                     'ul', 'll') if p != r.pos]
        halo = (PAPER, max(0.6, size * 0.25), 0.9)
        done = False
        for p in order:
            tx, ty, ha, va = cand[p]
            if cv.place(tx, ty, lab, font, size, ha=ha, va=va, ignore=('com', zi), color=INK, z=34, halo=halo):
                done = True
                break
        if not done and big and (r.basis == 'unsized' or r.muslims >= force_min):
            tx, ty, ha, va = cand[order[0]]
            cv.place(tx, ty, lab, font, size, ha=ha, va=va, force=True, color=INK, z=34, halo=halo)
            done = True
        n += done
    return n

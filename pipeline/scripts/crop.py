"""Render a lon/lat window of the poster PDF to PNG for inspection.
usage: crop.py name lon0 lat0 lon1 lat1 [zoom]"""
import sys, fitz
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from common import ROOT
from geo import pt, sphere
import numpy as np

W = 60.0; M = 1.25; HEAD = 4.1; BAND = 9.4
SPH = sphere(); xmin, ymin, xmax, ymax = SPH.bounds
padx = (xmax - xmin) * 0.004; pady = (ymax - ymin) * 0.006
XL, XR, YB, YT = xmin - padx, xmax + padx, ymin - pady, ymax + pady
MW = W - 2 * M; MH = MW * (YT - YB) / (XR - XL)
H = M + BAND + 0.5 + MH + HEAD + M * 0.6
MAP_Y0 = M + BAND + 0.5

def page_xy(x, y):
    px = (M + (x - XL) / (XR - XL) * MW) * 72
    py = (H - (MAP_Y0 + (y - YB) / (YT - YB) * MH)) * 72
    return px, py

name, lo0, la0, lo1, la1 = sys.argv[1], *map(float, sys.argv[2:6])
zoom = float(sys.argv[6]) if len(sys.argv) > 6 else 4
pdf = sys.argv[7] if len(sys.argv) > 7 else ROOT + '/out/poster_p1.pdf'
xs, ys = [], []
for lo in np.linspace(lo0, lo1, 9):
    for la in np.linspace(la0, la1, 9):
        x, y = pt(lo, la); px, py = page_xy(x, y); xs.append(px); ys.append(py)
clip = fitz.Rect(min(xs), min(ys), max(xs), max(ys))
doc = fitz.open(pdf)
pix = doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip)
pix.save(ROOT + f'/out/crop_{name}.png')
print(pix.width, pix.height)

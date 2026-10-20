import matplotlib as mpl
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
import glob, colorsys

FONT_DIR = __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))), 'fonts')
for f in glob.glob(f'{FONT_DIR}/*.ttf'):
    font_manager.fontManager.addfont(f)

def F(name):
    return FontProperties(fname=f'{FONT_DIR}/{name}.ttf')

SANS = F('FiraSans-Regular'); SANS_L = F('FiraSans-Light'); SANS_LI = F('FiraSans-LightItalic')
SANS_I = F('FiraSans-Italic'); SANS_M = F('FiraSans-Medium'); SANS_SB = F('FiraSans-SemiBold')
SANS_B = F('FiraSans-Bold'); SANS_XB = F('FiraSans-ExtraBold'); SANS_BL = F('FiraSans-Black')
COND = F('FiraSansCondensed-Regular'); COND_M = F('FiraSansCondensed-Medium'); COND_SB = F('FiraSansCondensed-SemiBold')
COND_I = F('FiraSansCondensed-Italic'); COND_L = F('FiraSansCondensed-Light'); COND_LI = F('FiraSansCondensed-LightItalic')
XCOND = F('FiraSansExtraCondensed-Regular'); XCOND_M = F('FiraSansExtraCondensed-Medium')
XCOND_I = F('FiraSansExtraCondensed-Italic')
SERIF = FontProperties(fname=f'{FONT_DIR}/SourceSerif4[opsz,wght].ttf')
SERIF_I = FontProperties(fname=f'{FONT_DIR}/SourceSerif4-Italic[opsz,wght].ttf')

mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.rcParams['svg.fonttype'] = 'none'
mpl.rcParams['path.simplify'] = False

# ------------------------------------------------------------------ classes & palette
BREAKS = [0, 1, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100.0001]
LABELS = ['<1', '1–5', '5–10', '10–20', '20–30', '30–40', '40–50',
          '50–60', '60–70', '70–80', '80–90', '90–100']
COLORS = ['#F6F2EA',  # <1   paper
          '#EEDFBF',  # 1-5
          '#E3C58C',  # 5-10
          '#D3A35C',  # 10-20
          '#BB8038',  # 20-30
          '#96602A',  # 30-40
          '#6B4221',  # 40-50
          '#C2DE8F',  # 50-60
          '#93C66E',  # 60-70
          '#5FA759',  # 70-80
          '#2F8346',  # 80-90
          '#0E5131']  # 90-100
NODATA = '#E6E6E3'
OCEAN = '#D4E4EC'
OCEAN_EDGE = '#9DB9C9'
GRAT = '#BFD3DE'
COAST = '#6F93A6'
LAKE = '#D4E4EC'
RIVER = '#9CC0D2'
BORDER = '#2E3236'
ADMIN = '#FFFFFF'
PAPER = '#FBFAF6'
INK = '#1E2A30'
INK2 = '#4A5A63'
WATER_TXT = '#5A84A0'
ICE = '#F3F6F8'
ACCENT = '#0E5131'
BROWN = '#6B4221'

def klass(p):
    if p is None or p != p:
        return -1
    for i in range(len(BREAKS) - 1):
        if BREAKS[i] <= p < BREAKS[i + 1]:
            return i
    return len(BREAKS) - 2

def lum(hexc):
    h = hexc.lstrip('#')
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)

def ink_for(hexc):
    """dark or light text for a background"""
    return ('#FFFFFF', 0.92) if lum(hexc) < 0.18 else ('#1B1F22', 0.85)

def darker(hexc, f=0.82):
    h = hexc.lstrip('#'); r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    hh, l, s = colorsys.rgb_to_hls(r, g, b); l *= f
    r, g, b = colorsys.hls_to_rgb(hh, l, s)
    return '#%02x%02x%02x' % (int(r * 255), int(g * 255), int(b * 255))

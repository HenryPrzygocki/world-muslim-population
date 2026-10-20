"""Copy the built data next to the page (for the Claude artifact) and write the GitHub Pages site at the repository root
with content-hashed data file names, so a returning visitor's browser never mixes a new page with old data."""
import hashlib, json, os, shutil, glob
WEB = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(WEB)
B, SITE = f'{WEB}/build', f'{WEB}/site'
FILES = {'w': 'map_w.json', 'lo': 'map_lo.json', 'hi': 'map.json', 'extra': 'extra.json', 'csv': 'units.csv'}
for f in FILES.values():
    shutil.copy(f'{B}/{f}', f'{SITE}/{f}')
# GitHub Pages
for old in glob.glob(f'{ROOT}/map*.json') + glob.glob(f'{ROOT}/extra*.json') + glob.glob(f'{ROOT}/units*.csv'):
    os.remove(old)
hashed = {}
for k, f in FILES.items():
    data = open(f'{B}/{f}', 'rb').read()
    h = hashlib.sha256(data).hexdigest()[:10]
    base, ext = os.path.splitext(f)
    name = f'{base}.{h}{ext}'
    open(f'{ROOT}/{name}', 'wb').write(data)
    hashed[k] = name
page = open(f'{SITE}/index.html').read()
k = page.index('<div id="app">')
head = page[:k].replace('<meta name="claude:viewport-fit-sides" content="cover">\n', '').rstrip()
desc = 'Interactive map of the share and number of Muslims by country, province, district and city — 2026 edition.'
html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="{desc}">
<meta property="og:title" content="World Muslim Population — 2026 edition">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
<meta property="og:image" content="https://henryprzygocki.github.io/world-muslim-population/preview.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#FBFAF6">
<style>:root{{color-scheme:light;box-sizing:border-box}}body{{margin:0;font:14px system-ui,sans-serif}}[hidden]{{display:none!important}}</style>
<script>window.WMP_FILES = {json.dumps(hashed)};</script>
{head}
</head>
<body>
{page[k:].rstrip()}
</body>
</html>
'''
open(f'{ROOT}/index.html', 'w').write(html)
print('site written:', hashed)

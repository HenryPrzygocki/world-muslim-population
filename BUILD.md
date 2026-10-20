# Building the map

The site at the repository root (`index.html` + data files) is generated. Everything needed to regenerate it is in this repo.

```
pipeline/            data pipeline (Python 3, geopandas)
  fetch_raw.sh       downloads Natural Earth + geoBoundaries inputs (~330 MB) into pipeline/raw
  raw/               small inputs committed as-is (India districts, UK local authorities, China prefectures, Brazil)
  data/              compiled statistics: sub/ and sub2/ per-country tables, pew2020.csv, sources_registry.csv,
                     communities.csv, usa_metros_arda2020.csv
  scripts/           build_units.py → prep_layers.py → build_pdf.py (print edition, not published)
web/
  site/index.html    the page source (also published as the Claude artifact)
  prep_web.py        exports units/countries/labels from pipeline/data → web/build
  prep_status.py     contested territories (Crimea, occupied Ukraine, Kurdistan Region)
  topo.sh            mapshaper → map.json (detail) and map_lo.json (overview)
  build_site.py      writes the published page and content-hashed data files to the repo root
  smoke.js           Playwright smoke test (desktop + phone)
```

Full rebuild:

```
pip install geopandas shapely pyproj matplotlib
(cd web && npm install)                 # mapshaper, playwright
pipeline/fetch_raw.sh
python pipeline/scripts/build_units.py
python web/prep_web.py && python web/prep_status.py && web/topo.sh
python web/build_site.py                # then: node web/smoke.js
```

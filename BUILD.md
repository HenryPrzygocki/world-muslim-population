# Building the map

The site at the repository root (`index.html` + content-hashed data files) is generated. Everything needed to regenerate it
is in this repo, apart from the public boundary files that `pipeline/fetch_raw.sh` downloads (pinned to fixed commits).

```
pipeline/
  fetch_raw.sh        downloads Natural Earth + geoBoundaries inputs (~180 MB, pinned commits) into pipeline/raw
  raw/                small inputs committed as-is: India districts (DataMeet + Census 2011), UK local authorities (ONS),
                      geoBoundaries licence metadata (gbmeta/, see DATA-LICENSE.md); source material the compiled tables in
                      data/ were made from (Brazil municipalities, Kenya census tables) — not read by the build
  data/               compiled statistics: sub/ and sub2/ per-country tables, pew2020.csv (national baseline),
                      territories.csv (census figures for territories Pew does not cover), sources_registry.csv,
                      communities.csv (Latin America), usa_metros_arda2020.csv
  scripts/
    build_units.py    matches the statistics to boundaries → data/units_national.gpkg, data/units_sub.gpkg
    sub2.py           loaders for Russia, China, Indonesia, Canada and Australia (used by build_units.py)
    speculative.py    survey-based regional estimates (Afrobarometer) → data/speculative/, data/units_spec.gpkg
    common.py         paths and name matching; mapkit.py: label tables, communities, number formats
    prep_layers.py, world.py, regional.py, methods.py, build_pdf.py, style.py, crop.py
                      print edition (PDF; not published and not part of the web build)
web/
  site/index.html     the page source (also published as the Claude artifact)
  prep_web.py         exports countries, units, states/provinces of large countries, lakes, labels, search data and the
                      CSV → web/build
  prep_status.py      contested territories (Crimea, occupied Ukraine, Kurdistan Region); raw_occ/ holds the line of control
  project.py          splits every layer at the projection seam → web/build/p
  topo.sh             mapshaper: four levels of detail (map_w 15 km, map_lo 3 km, map 700 m, map_x 40 m), then
                      topo_project.py projects them to Equal Earth metres
  build_site.py       writes index.html and the content-hashed data files to the repository root (and copies for the artifact)
  mktest.py           mirrors the built site into web/test, with d3 served locally
  smoke.js            Playwright smoke test (desktop + phone); screenshots in web/ux
```

## Full rebuild

Python 3 with the geo stack, and Node for mapshaper and the smoke test:

```
pip install geopandas shapely pyproj matplotlib xlrd pyreadstat
(cd web && npm ci && npx playwright install chromium)
```

Then, from the repository root:

```
pipeline/fetch_raw.sh
python pipeline/scripts/build_units.py
python pipeline/scripts/speculative.py      # speculative layer (survey estimates; shown only in speculative mode)
python web/prep_web.py
python web/prep_status.py
python web/project.py
web/topo.sh
python web/build_site.py
```

`build_units.py` takes about two minutes and prints the names it could not match for each country; the rest takes about
a minute. A rebuild from unchanged inputs reproduces the published data files byte for byte (their names carry a hash of
their content), so `git status` shows exactly what a change did.

## Test

```
python web/mktest.py
(cd web/test && python -m http.server 8765) &
node web/smoke.js
```

The smoke test uses Playwright's own Chromium; set `CHROMIUM=/path/to/chrome` to use another build. When the published
figures or features change, update `UPDATED` in `web/site/index.html` before running `build_site.py`.

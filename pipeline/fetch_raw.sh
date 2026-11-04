#!/bin/bash
# Downloads the large public inputs into pipeline/raw (not committed). Both sources are pinned to a fixed commit, so a
# rebuild always gets the same outlines:
#   Natural Earth 1:10m vectors (public domain)                       nvkelso/natural-earth-vector @ ca96624 (2 Jun 2022)
#   geoBoundaries gbOpen, simplified (licence per file: DATA-LICENSE.md) wmgeolab/geoBoundaries   @ 8ce2700 (1 Nov 2026;
#     none of the files below changed after Dec 2023)
# Only the files a build script reads are downloaded (about 180 MB).
set -e
cd "$(dirname "$0")"
NE_REV=ca96624a56bd078437bca8184e78163e5039ad19
GB_REV=8ce2700661a28ee944350e2b329bbabb58d2ff83
mkdir -p raw/gb
# web map (build_units.py, prep_web.py, prep_status.py)
NE="ne_10m_admin_0_map_units ne_10m_admin_0_countries ne_10m_admin_1_states_provinces ne_10m_admin_1_states_provinces_lines
    ne_10m_admin_0_boundary_lines_disputed_areas ne_10m_lakes ne_10m_populated_places_simple"
# print edition only (prep_layers.py, world.py, regional.py)
NE="$NE ne_10m_admin_0_boundary_lines_land ne_10m_antarctic_ice_shelves_polys ne_10m_coastline
    ne_10m_geography_marine_polys ne_10m_rivers_lake_centerlines"
for f in $NE; do
  [ -s raw/$f.geojson ] || curl -sSfL -o raw/$f.geojson \
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/$NE_REV/geojson/$f.geojson"
done
for c in AUS-ADM2 BEN-ADM1 BFA-ADM2 BGD-ADM2 BIH-ADM2 CAN-ADM2 ESP-ADM2 ETH-ADM2 GIN-ADM1 GNB-ADM1 GUY-ADM1 \
         HRV-ADM1 IDN-ADM1 IDN-ADM2 KEN-ADM1 KHM-ADM1 MNE-ADM1 MWI-ADM2 NPL-ADM1 PHL-ADM2 SRB-ADM2 ZAF-ADM1; do
  iso=${c%-*}; adm=${c#*-}; f=geoBoundaries-$c\_simplified.geojson
  [ -s raw/gb/$f ] || curl -sSfL -o raw/gb/$f \
    "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/$GB_REV/releaseData/gbOpen/$iso/$adm/$f"
done
echo "raw inputs ready"

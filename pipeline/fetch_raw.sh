#!/bin/bash
# Downloads the large public inputs into pipeline/raw (not committed: ~330 MB).
# Natural Earth 1:10m (public domain) and geoBoundaries gbOpen simplified boundaries (CC BY 4.0).
set -e
cd "$(dirname "$0")"
mkdir -p raw/gb
for f in ne_10m_admin_0_boundary_lines_disputed_areas.geojson ne_10m_admin_0_boundary_lines_land.geojson ne_10m_admin_0_countries.geojson ne_10m_admin_0_countries_lakes.geojson ne_10m_admin_0_disputed_areas.geojson ne_10m_admin_0_map_units.geojson ne_10m_admin_0_scale_rank.geojson ne_10m_admin_1_states_provinces.geojson ne_10m_admin_1_states_provinces_lines.geojson ne_10m_antarctic_ice_shelves_polys.geojson ne_10m_coastline.geojson ne_10m_geography_marine_polys.geojson ne_10m_geography_regions_polys.geojson ne_10m_glaciated_areas.geojson ne_10m_lakes.geojson ne_10m_land.geojson ne_10m_minor_islands.geojson ne_10m_ocean.geojson ne_10m_populated_places_simple.geojson ne_10m_rivers_lake_centerlines.geojson ne_50m_admin_0_countries.geojson ; do
  [ -s raw/$f ] || curl -sSfL -o raw/$f "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/$f"
done
for c in ALB-ADM1 AUS-ADM1 AUS-ADM2 AUT-ADM1 BEL-ADM1 BEN-ADM1 BFA-ADM1 BFA-ADM2 BGD-ADM2 BGR-ADM2 BIH-ADM2 BIH-ADM3 BRA-ADM1 CAF-ADM1 CAN-ADM1 CAN-ADM2 CHE-ADM1 CHN-ADM2 CIV-ADM1 CIV-ADM2 CMR-ADM1 COD-ADM1 CYP-ADM1 DEU-ADM1 DNK-ADM1 ERI-ADM1 ESP-ADM1 ESP-ADM2 ETH-ADM1 ETH-ADM2 FRA-ADM1 GBR-ADM2 GBR-ADM3 GEO-ADM1 GHA-ADM1 GIN-ADM1 GNB-ADM1 GRC-ADM3 GUY-ADM1 HRV-ADM1 IDN-ADM1 IDN-ADM2 ISR-ADM1 ITA-ADM1 KAZ-ADM1 KEN-ADM1 KGZ-ADM1 KHM-ADM1 LBN-ADM1 LBR-ADM1 LKA-ADM2 MKD-ADM1 MMR-ADM1 MNE-ADM1 MNG-ADM1 MOZ-ADM1 MWI-ADM2 MYS-ADM1 NGA-ADM1 NLD-ADM1 NOR-ADM1 NPL-ADM1 PAK-ADM2 PAK-ADM3 PHL-ADM2 ROU-ADM1 RUS-ADM1 SLE-ADM2 SRB-ADM2 SSD-ADM1 SUR-ADM1 SWE-ADM1 TCD-ADM1 TGO-ADM1 THA-ADM1 TTO-ADM1 TZA-ADM1 UGA-ADM2 UKR-ADM1 USA-ADM1 XKX-ADM1 ZAF-ADM1 ; do
  iso=${c%-*}; adm=${c#*-}; f=geoBoundaries-$c\_simplified.geojson
  [ -s raw/gb/$f ] || curl -sSfL -o raw/gb/$f "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/$iso/$adm/$f"
done
echo "raw inputs ready"

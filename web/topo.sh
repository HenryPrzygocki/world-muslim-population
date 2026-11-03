#!/bin/bash
# Four levels of detail from the projected layers (metres). Units of CAN/AUS/IDN (geoBoundaries outlines clipped to
# Natural Earth) are topology-cleaned to remove tens of thousands of micro-arcs; other countries pass through unchanged.
cd "$(dirname "$0")/build/p"
M=../../node_modules/.bin/mapshaper
IN="countries.geojson units.geojson lakes.geojson disputed.geojson occupied.geojson kri.geojson combine-files"
KEEP='["CAN","AUS","IDN"].indexOf(c) < 0'
# simplification interval (m) and quantization per level; the client switches level so each stays within ~0.6 device px
for spec in "15000 10000 ../map_w.json" "3000 50000 ../map_lo.json" "700 200000 ../map.json" "40 1000000 ../map_x.json"; do
  set -- $spec
  $M -i $IN snap \
    -filter "$KEEP" target=units + name=ub \
    -filter "!($KEEP)" target=units + name=uc \
    -drop target=units \
    -clean target=uc allow-empty \
    -merge-layers target=uc,ub name=units \
    -simplify dp interval=$1 keep-shapes target='*' \
    -o format=topojson quantization=$2 target='countries,units,lakes,disputed,occupied,kri' $3 2>&1 | grep -E "Error|could not" 
done
cd .. && python3 ../topo_project.py map_w.json map_lo.json map.json map_x.json

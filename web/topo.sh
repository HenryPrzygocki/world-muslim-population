#!/bin/bash
# build both TopoJSON levels of detail; units of CAN/AUS/IDN (geoBoundaries outlines clipped to Natural Earth) are
# topology-cleaned to remove tens of thousands of micro-arcs; other countries pass through unchanged
cd "$(dirname "$0")/build"
M=../node_modules/.bin/mapshaper
IN="countries.geojson units.geojson lakes.geojson provlines.geojson disputed.geojson occupied.geojson kri.geojson combine-files"
BAD='["CAN","AUS","IDN"].indexOf(c) < 0'
for spec in "450 200000 map.json" "4000 50000 map_lo.json"; do
  set -- $spec
  $M -i $IN snap \
    -filter "$BAD" target=units + name=ub \
    -filter "!($BAD)" target=units + name=uc \
    -drop target=units \
    -clean target=uc allow-empty \
    -merge-layers target=uc,ub name=units \
    -simplify dp interval=$1 keep-shapes target='*' \
    -o format=topojson quantization=$2 target='countries,units,lakes,provlines,disputed,occupied,kri' $3 2>&1 | grep -v "^\[o\]"
done
ls -la map.json map_lo.json

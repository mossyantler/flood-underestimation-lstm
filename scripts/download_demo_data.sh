#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${1:-$ROOT_DIR/data/CAMELS_US}"
BASE_URL="https://raw.githubusercontent.com/neuralhydrology/neuralhydrology/master/test/test_data/camels_us"

mkdir -p \
  "$DATA_DIR/basin_mean_forcing/daymet" \
  "$DATA_DIR/usgs_streamflow" \
  "$DATA_DIR/camels_attributes_v2.0"

curl -L "$BASE_URL/basin_mean_forcing/daymet/01022500_lump_cida_forcing_leap.txt" \
  -o "$DATA_DIR/basin_mean_forcing/daymet/01022500_lump_cida_forcing_leap.txt"

curl -L "$BASE_URL/usgs_streamflow/01022500_streamflow_qc.txt" \
  -o "$DATA_DIR/usgs_streamflow/01022500_streamflow_qc.txt"

for name in camels_clim camels_geol camels_hydro camels_name camels_soil camels_topo camels_vege readme; do
  curl -L "$BASE_URL/camels_attributes_v2.0/${name}.txt" \
    -o "$DATA_DIR/camels_attributes_v2.0/${name}.txt"
done

echo "Demo CAMELS-US data is ready at: $DATA_DIR"

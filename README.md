# CAMELS-US Single Basin Demo

This workspace contains a minimal `CAMELS-US + NeuralHydrology` example for the single basin `01022500`.

## Files

- `configs/camels_us_01022500_daymet.yml`: NeuralHydrology run configuration.
- `basins/01022500.txt`: basin list file used for train/validation/test.
- `scripts/download_demo_data.sh`: downloads the official NeuralHydrology CAMELS-US test subset for basin `01022500`.
- `scripts/run_demo.sh`: creates the environment if needed, downloads the demo data, trains, and evaluates.

## Quick start

```bash
./scripts/run_demo.sh
```

The training run is intentionally small so that the full flow is easy to verify on CPU first.

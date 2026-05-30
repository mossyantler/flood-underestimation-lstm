#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "xarray>=2024.1",
#   "netCDF4>=1.6",
# ]
# ///
"""Plot per-basin Q99+ simQ hydrograph gallery (observed + Model1/2 quantile overlay).

For every Q99+ event in the event response table, plots:
  - Top panel: rainfall (from timeseries NC)
  - Bottom panel: observed streamflow + Model1 + Model2 q50/q90/q99 bands
    with Q99 threshold line and observed peak marker.

Outputs one PNG per event, organised as:
  {output_root}/{gauge_id}/{event_id}.png

Also writes a manifest CSV per basin:
  {output_root}/{gauge_id}/q99_simq_manifest.csv
"""
from __future__ import annotations

import argparse
import html
import warnings
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_EVENT_RESPONSE = REPO_ROOT / "output/basin/expanded_drbc/analysis/event_response/tables/event_response_table.csv"
DEFAULT_SERIES_DIR = REPO_ROOT / "output/model_analysis/extreme_rain/expanded_drbc/basin_performance/inference/required_series"
DEFAULT_DATA_DIR = REPO_ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/time_series"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "output/model_analysis/extreme_rain/expanded_drbc/basin_performance/hydrograph"
DEFAULT_SEEDS = [111, 222, 444]
PADDING_HOURS = 72

COLOR_OBS = "#111827"
COLOR_M1 = "#2563eb"
COLOR_M2_Q50 = "#dc2626"
COLOR_M2_BAND = "#f97316"
COLOR_Q99 = "#7c3aed"
COLOR_RAIN = "#2563eb"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--event-response", type=Path, default=DEFAULT_EVENT_RESPONSE)
    p.add_argument("--series-dir", type=Path, default=DEFAULT_SERIES_DIR)
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    p.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    p.add_argument("--padding-hours", type=int, default=PADDING_HOURS)
    p.add_argument("--dpi", type=int, default=180)
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--basin", action="append", dest="basins",
                   help="Restrict to specific gauge_id(s).")
    p.add_argument("--limit-events", type=int, default=None,
                   help="Max events per basin (for smoke testing).")
    return p.parse_args()


def normalize_id(gauge_id: str) -> str:
    return str(gauge_id).strip().zfill(8)


def read_series(series_dir: Path, seed: int) -> pd.DataFrame:
    path = series_dir / f"seed{seed}" / "primary_required_series.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing required series: {path}")
    df = pd.read_csv(path, dtype={"basin": str}, parse_dates=["datetime"])
    df["basin"] = df["basin"].map(normalize_id)
    for col in ["obs", "model1", "q50", "q90", "q95", "q99"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values(["basin", "datetime"]).reset_index(drop=True)


def read_rain(data_dir: Path, gauge_id: str) -> pd.Series:
    path = data_dir / f"{gauge_id}.nc"
    if not path.exists():
        raise FileNotFoundError(f"Missing NC file: {path}")
    with xr.open_dataset(path) as ds:
        time_dim = "DateTime" if "DateTime" in ds.coords else "date"
        rain = pd.Series(
            ds["Rainf"].values.astype(float),
            index=pd.to_datetime(ds[time_dim].values),
            name="Rainf",
        )
    return rain.sort_index()


def build_series_lookup(
    all_series: dict[int, pd.DataFrame],
    basin: str,
) -> dict[str, dict[str, pd.Series]]:
    """Returns {seed: {col_name: Series indexed by datetime}} for a basin."""
    lookup: dict[str, dict[str, pd.Series]] = {}
    for seed, df in all_series.items():
        sub = df[df["basin"] == basin].set_index("datetime")
        if sub.empty:
            continue
        lookup[str(seed)] = {col: sub[col].dropna() for col in sub.columns if col not in {"basin", "block_id", "seed", "basin", "model1_epoch", "model2_epoch"}}
    return lookup


def plot_event(
    event: pd.Series,
    series_by_seed: dict[str, dict[str, pd.Series]],
    rain: pd.Series,
    seeds: list[int],
    output_path: Path,
    padding_hours: int,
    dpi: int,
    skip_existing: bool,
) -> dict[str, Any]:
    event_start = pd.Timestamp(event["event_start"])
    event_peak = pd.Timestamp(event["event_peak"])
    event_end = pd.Timestamp(event["event_end"])
    q99_threshold = float(event["selected_threshold_value"])
    gauge_id = str(event["gauge_id"])
    gauge_name = str(event["gauge_name"])
    event_id = str(event["event_id"])
    peak_discharge = float(event.get("peak_discharge", np.nan))

    t0 = event_start - pd.Timedelta(hours=padding_hours)
    t1 = event_end + pd.Timedelta(hours=padding_hours)

    result: dict[str, Any] = {
        "gauge_id": gauge_id,
        "gauge_name": gauge_name,
        "event_id": event_id,
        "event_start": event_start.isoformat(),
        "event_peak": event_peak.isoformat(),
        "event_end": event_end.isoformat(),
        "q99_threshold": f"{q99_threshold:.3f}",
        "peak_discharge": "NA" if np.isnan(peak_discharge) else f"{peak_discharge:.3f}",
        "plot_path": str(output_path),
        "has_model_data": False,
    }

    if skip_existing and output_path.exists():
        result["has_model_data"] = True
        return result

    n_seeds = len(seeds)
    fig, axes = plt.subplots(
        n_seeds + 1, 1,
        figsize=(14.2, 10.8),
        sharex=True,
        gridspec_kw={"height_ratios": [0.95] + [1.9] * n_seeds},
        constrained_layout=True,
    )
    fig.suptitle(
        f"{gauge_id} · {gauge_name}\nQ99+ event {event_id} · peak {event_peak.strftime('%Y-%m-%d %H:%M')}",
        fontsize=10.3,
    )

    # Rain panel
    ax_rain = axes[0]
    rain_window = rain.loc[t0:t1]
    if not rain_window.empty:
        rain_mmh = rain_window * 3600
        rain_x = mdates.date2num(rain_window.index.to_pydatetime())
        ax_rain.bar(rain_x, rain_mmh.fillna(0.0).to_numpy(dtype=float), width=0.032, color=COLOR_RAIN, alpha=0.82)
        rain_y_max = float(rain_mmh.max(skipna=True)) if rain_mmh.notna().any() else 1.0
        ax_rain.set_ylim(0, rain_y_max * 1.18 if np.isfinite(rain_y_max) and rain_y_max > 0 else 1.0)
    ax_rain.axvline(mdates.date2num(event_start.to_pydatetime()), color="#71717a", lw=0.85, ls=":", alpha=0.7)
    ax_rain.axvline(mdates.date2num(event_peak.to_pydatetime()), color="#71717a", lw=0.85, ls="--", alpha=0.7)
    ax_rain.axvline(mdates.date2num(event_end.to_pydatetime()), color="#71717a", lw=0.85, ls=":", alpha=0.7)
    ax_rain.set_ylabel("Rainf", fontsize=8.5)
    ax_rain.tick_params(labelsize=7.5)
    ax_rain.grid(True, axis="y", color="#d4d4d8", linewidth=0.55, alpha=0.85)

    has_any_model = False
    for i, seed in enumerate(seeds):
        ax = axes[i + 1]
        seed_data = series_by_seed.get(str(seed), {})

        obs_series = seed_data.get("obs")
        if obs_series is not None:
            obs_window = obs_series.loc[t0:t1]
            if not obs_window.empty:
                ax.plot(obs_window.index, obs_window.values, color=COLOR_OBS, lw=1.35, ls="-", label="Observed", zorder=5)

        # Model 2 quantile bands
        q50 = seed_data.get("q50")
        q90 = seed_data.get("q90")
        q99_pred = seed_data.get("q99")
        if q50 is not None:
            q50_w = q50.loc[t0:t1]
            if not q50_w.empty:
                has_any_model = True
                ax.plot(q50_w.index, q50_w.values, color=COLOR_M2_Q50, lw=1.05, ls="-", label="Model 2 q50", zorder=4)
                if q90 is not None and q99_pred is not None:
                    q90_w = q90.loc[t0:t1].reindex(q50_w.index)
                    q99_w = q99_pred.loc[t0:t1].reindex(q50_w.index)
                    ax.fill_between(q50_w.index, q50_w.values, q90_w.values, color=COLOR_M2_BAND, alpha=0.13, label="Model 2 q50–q90")
                    ax.fill_between(q50_w.index, q90_w.values, q99_w.values, color=COLOR_M2_BAND, alpha=0.08, label="Model 2 q90–q99")

        # Model 1
        m1 = seed_data.get("model1")
        if m1 is not None:
            m1_w = m1.loc[t0:t1]
            if not m1_w.empty:
                has_any_model = True
                ax.plot(m1_w.index, m1_w.values, color=COLOR_M1, lw=1.0, ls="-", label="Model 1", zorder=4)

        # Q99 threshold
        ax.axhline(q99_threshold, color=COLOR_Q99, lw=0.85, ls="--", alpha=0.72, label=f"Q99 = {q99_threshold:.1f}")

        # Event markers
        for ts, label, style in [
            (event_start, "event start", ":"),
            (event_peak, "peak", "--"),
            (event_end, "event end", ":"),
        ]:
            ax.axvline(ts, color="#71717a", lw=0.85, ls=style, alpha=0.7)

        if not np.isnan(peak_discharge):
            ax.scatter([event_peak], [peak_discharge], color="#dc2626", s=28, zorder=6, label="Observed peak")

        ax.set_title(f"seed {seed}", fontsize=8.7)
        ax.set_ylabel("Streamflow (m³/s)", fontsize=8.5)
        ax.tick_params(labelsize=7.5)
        ax.grid(True, axis="y", color="#d4d4d8", linewidth=0.55, alpha=0.85)
        if i == len(seeds) - 1:
            ax.legend(fontsize=7.2, loc="upper left", framealpha=0.96,
                      edgecolor="#a1a1aa")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=0, ha="center")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    result["has_model_data"] = has_any_model
    return result


def write_basin_manifest(output_dir: Path, rows: list[dict[str, Any]]) -> Path:
    manifest = pd.DataFrame(rows)
    path = output_dir / "q99_simq_manifest.csv"
    manifest.to_csv(path, index=False)
    return path


def write_basin_index(output_dir: Path, gauge_id: str, gauge_name: str, manifest: pd.DataFrame) -> None:
    rows_html = ""
    for _, row in manifest.iterrows():
        img_rel = Path(row["plot_path"]).name
        rows_html += (
            f'<div class="card">'
            f'<img src="{html.escape(img_rel)}" loading="lazy" alt="{html.escape(str(row["event_id"]))}">'
            f'<p><strong>{html.escape(str(row["event_id"]))}</strong></p>'
            f'<p>Peak {html.escape(str(row["event_peak"]))} · {html.escape(str(row["peak_discharge"]))} m³/s</p>'
            f'</div>\n'
        )
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>{html.escape(gauge_id)} Q99+ simQ</title>
<style>
body{{font-family:sans-serif;margin:16px;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px;}}
.card{{border:1px solid #e2e8f0;border-radius:6px;padding:8px;}}
.card img{{width:100%;height:auto;display:block;}}
.card p{{margin:4px 0;font-size:12px;}}
</style></head><body>
<h1>{html.escape(gauge_id)} · {html.escape(gauge_name)}</h1>
<p>{len(manifest)} Q99+ events (obs + Model 1/2 predictions)</p>
<div class="grid">{rows_html}</div>
</body></html>"""
    (output_dir / "index.html").write_text(page, encoding="utf-8")


def main() -> None:
    args = parse_args()
    seeds = sorted(set(args.seeds))

    events = pd.read_csv(args.event_response, dtype={"gauge_id": str})
    events["gauge_id"] = events["gauge_id"].map(normalize_id)
    if args.basins:
        events = events[events["gauge_id"].isin([normalize_id(b) for b in args.basins])].copy()

    print(f"Events: {len(events)} across {events['gauge_id'].nunique()} basins")

    print("Loading required series...", flush=True)
    all_series: dict[int, pd.DataFrame] = {}
    missing_seeds = []
    for seed in seeds:
        try:
            all_series[seed] = read_series(args.series_dir, seed)
            print(f"  seed {seed}: {len(all_series[seed])} rows", flush=True)
        except FileNotFoundError as e:
            print(f"  WARNING: {e}")
            missing_seeds.append(seed)
    available_seeds = [s for s in seeds if s not in missing_seeds]
    if not available_seeds:
        raise SystemExit("No inference series found. Run inference first.")

    rain_cache: dict[str, pd.Series] = {}
    total_plots = 0
    total_skipped = 0

    for basin, group in events.groupby("gauge_id"):
        gauge_name = str(group.iloc[0]["gauge_name"])
        output_dir = args.output_root / str(basin)
        output_dir.mkdir(parents=True, exist_ok=True)

        series_by_seed = build_series_lookup(all_series, str(basin))

        if str(basin) not in rain_cache:
            try:
                rain_cache[str(basin)] = read_rain(args.data_dir, str(basin))
            except FileNotFoundError:
                print(f"  [{basin}] Missing rain NC, skipping")
                continue

        basin_events = group.sort_values("event_peak").reset_index(drop=True)
        if args.limit_events:
            basin_events = basin_events.head(args.limit_events)

        manifest_rows: list[dict[str, Any]] = []
        for _, event in basin_events.iterrows():
            event_id = str(event["event_id"])
            output_path = output_dir / f"{event_id}.png"
            row = plot_event(
                event=event,
                series_by_seed=series_by_seed,
                rain=rain_cache[str(basin)],
                seeds=available_seeds,
                output_path=output_path,
                padding_hours=args.padding_hours,
                dpi=args.dpi,
                skip_existing=args.skip_existing,
            )
            if output_path.exists():
                manifest_rows.append(row)
                total_plots += 1
            else:
                total_skipped += 1

        if manifest_rows:
            manifest = pd.DataFrame(manifest_rows)
            write_basin_manifest(output_dir, manifest_rows)
            write_basin_index(output_dir, str(basin), gauge_name, manifest)
            print(f"  [{basin}] {len(manifest_rows)} plots written", flush=True)

    print(f"\nDone. Plots: {total_plots} | Skipped: {total_skipped}")


if __name__ == "__main__":
    main()

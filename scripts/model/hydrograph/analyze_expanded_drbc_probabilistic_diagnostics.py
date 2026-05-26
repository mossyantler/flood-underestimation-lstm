#!/usr/bin/env python3
"""Expanded DRBC observed-test probabilistic diagnostics for Model 2 quantiles.

Phase 1 standalone diagnostics on the expanded DRBC observed test split.
Reuses verified helpers from ``analyze_subset300_probabilistic_diagnostics`` and
adds expanded-specific metrics (peak/event capture, train-period skill score,
upper-tail pinball proxy, IQR-distance error-tier grouping).

Imported helpers (frozen list — do NOT add side-effectful imports here):
  _stratum_masks, _summarize_quantile, _summarize_spread,
  _aggregate_pinball, _aggregate_calibration, _aggregate_spread,
  _save_primary_calibration_plot, _save_pinball_stratum_plot, _save_spread_plot,
  _write_report, _quantile_order_flags, _pinball, _safe_pct, _relative
The only import-time side effect of that module is ``matplotlib.use("Agg")``;
its module-level path constants are unused here (this entrypoint sets its own).

NOT reused: the epoch{E:03d}_required_series loader and the same-epoch grid
(no epoch-named inputs exist for the expanded split). The same-epoch
calibration-error figure (AC5) is therefore excluded.

Phase 2 (154-vs-expanded comparison) is intentionally out of scope: the
scaling_300 baseline and its regeneration inputs are absent on disk.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

import analyze_subset300_probabilistic_diagnostics as base

matplotlib.use("Agg")  # redundant safety; base import already set this
import matplotlib.pyplot as plt  # noqa: E402

_stratum_masks = base._stratum_masks
_summarize_quantile = base._summarize_quantile
_summarize_spread = base._summarize_spread
_aggregate_pinball = base._aggregate_pinball
_aggregate_calibration = base._aggregate_calibration
_aggregate_spread = base._aggregate_spread
_save_primary_calibration_plot = base._save_primary_calibration_plot
_save_pinball_stratum_plot = base._save_pinball_stratum_plot
_save_spread_plot = base._save_spread_plot
_write_report = base._write_report
_pinball = base._pinball
_safe_pct = base._safe_pct
QUANTILES = base.QUANTILES
STRATA = base.STRATA
STRATUM_LABELS = base.STRATUM_LABELS

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_DIR = REPO_ROOT / "output/model_analysis/expanded_drbc_test"
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "output/model_analysis/expanded_drbc_test/probabilistic_diagnostics"
)
TIER_PROFILE_REL = "tables/expanded_drbc_tier_profile.csv"
PRIMARY_SEEDS = [111, 222, 444]

# AC8 climatology baseline source: observed Streamflow from the expanded dataset
# NetCDF time series (units m3 s-1; matches required-series `obs` exactly in the
# test period). Train-period rows give a leakage-free per-basin climatology.
DEFAULT_TIMESERIES_DIR = (
    REPO_ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/time_series"
)
STREAMFLOW_VAR = "Streamflow"

# AC7: reuse extreme_rain stress-test event-window definition
# (scripts/model/extreme_rain/analyze_subset300_extreme_rain_stress_test.py
#  peak_quantile_bracket_metrics, default --peak-quantile-window-hours=6):
# +/- N hours around the observed per-basin peak, capture = obs_peak <= max(q_in_window).
EVENT_WINDOW_HOURS = 6

# AC8: skill-score climatology baseline period (TRAIN only — leakage forbidden).
TRAIN_PERIOD_START = "2000-01-01"
TRAIN_PERIOD_END = "2010-12-31T23:59:59"

# AC10: IQR-distance error tier (dominant_distance_label). NOT minor/moderate/major.
# Exact label strings from tables/expanded_drbc_tier_profile.csv.
TIER_ORDER = ["<0.5 IQR", "0.5-1.5 IQR", "1.5-3 IQR", ">=3 IQR"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Expanded DRBC observed-test Model 2 probabilistic diagnostics (Phase 1)."
        )
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seeds", type=int, nargs="+", default=PRIMARY_SEEDS)
    parser.add_argument(
        "--timeseries-dir",
        type=Path,
        default=DEFAULT_TIMESERIES_DIR,
        help=(
            "Dir of per-basin NetCDF files providing observed Streamflow for the "
            "AC8 TRAIN-period (2000-2010) climatology baseline. Leakage-free: only "
            "train-window rows are used."
        ),
    )
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _expanded_series_path(input_dir: Path, seed: int) -> Path:
    return input_dir / "required_series" / f"seed{seed}" / "primary_required_series.csv"


def _preflight(input_dir: Path, seeds: list[int], timeseries_dir: Path) -> tuple[list[Path], Path]:
    """AC0: fail-fast if any required input is missing."""
    missing: list[str] = []
    series_paths: list[Path] = []
    for seed in seeds:
        path = _expanded_series_path(input_dir, seed)
        series_paths.append(path)
        if not path.exists():
            missing.append(str(path))
    tier_path = input_dir / TIER_PROFILE_REL
    if not tier_path.exists():
        missing.append(str(tier_path))
    if not timeseries_dir.is_dir():
        missing.append(f"{timeseries_dir} (AC8 climatology source dir)")
    if missing:
        msg = "AC0 pre-flight FAILED. Missing required input(s):\n  " + "\n  ".join(missing)
        raise SystemExit(msg)
    return series_paths, tier_path


def _read_expanded_series(path: Path, seed: int) -> tuple[pd.DataFrame, dict[str, object]]:
    """Load expanded primary_required_series.csv. Drop NaN-obs rows; record counts."""
    usecols = ["seed", "basin", "model1_epoch", "model2_epoch", "datetime", "obs", *QUANTILES]
    df = pd.read_csv(path, usecols=usecols, dtype={"basin": str})
    df["basin"] = df["basin"].str.zfill(8)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    for col in ["obs", *QUANTILES]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    n_rows_raw = int(len(df))
    nan_obs = int(df["obs"].isna().sum())
    # all-stratum coverage denominator = observed (non-NaN) hours only
    df_obs = df[df["obs"].notna()].copy()
    meta = {
        "seed": int(seed),
        "n_rows_raw": n_rows_raw,
        "n_obs_nan_dropped": nan_obs,
        "n_rows_observed": int(len(df_obs)),
        "obs_nan_fraction": (nan_obs / n_rows_raw) if n_rows_raw else math.nan,
        "n_basins": int(df_obs["basin"].nunique()),
        "datetime_min": str(df_obs["datetime"].min()),
        "datetime_max": str(df_obs["datetime"].max()),
    }
    return df_obs, meta


# ---------------------------------------------------------------------------
# AC7 — peak / event quantile capture rate (reuse extreme_rain +/-6h window)
# ---------------------------------------------------------------------------
def _peak_event_capture(df: pd.DataFrame, seed: int, window_hours: int) -> list[dict[str, object]]:
    """For each basin: observed peak hour + an event window of +/- window_hours
    around it. Capture rate = fraction of basins where obs_peak <= max(q) in window.
    """
    rows: list[dict[str, object]] = []
    peak_idx = df.groupby("basin", observed=True)["obs"].idxmax()
    peaks = df.loc[peak_idx, ["basin", "datetime", "obs"]].rename(
        columns={"datetime": "peak_time", "obs": "obs_peak"}
    )
    df_sorted = df.sort_values(["basin", "datetime"])
    grouped = {b: g for b, g in df_sorted.groupby("basin", observed=True)}

    capture_peak = {q: 0 for q in QUANTILES}  # exact peak-hour capture
    capture_window = {q: 0 for q in QUANTILES}  # any hour within +/-window
    n_basins = 0
    for _, prow in peaks.iterrows():
        basin = prow["basin"]
        obs_peak = prow["obs_peak"]
        peak_time = prow["peak_time"]
        if not np.isfinite(obs_peak) or pd.isna(peak_time):
            continue
        g = grouped[basin]
        n_basins += 1
        peak_hour = g[g["datetime"] == peak_time]
        for q in QUANTILES:
            if not peak_hour.empty and obs_peak <= float(peak_hour[q].max(skipna=True)):
                capture_peak[q] += 1
        lo = peak_time - pd.Timedelta(hours=window_hours)
        hi = peak_time + pd.Timedelta(hours=window_hours)
        win = g[g["datetime"].between(lo, hi, inclusive="both")]
        if win.empty:
            win = g.loc[[g["datetime"].sub(peak_time).abs().idxmin()]]
        for q in QUANTILES:
            win_max = float(win[q].max(skipna=True))
            if np.isfinite(win_max) and obs_peak <= win_max:
                capture_window[q] += 1

    for q, tau in QUANTILES.items():
        rows.append(
            {
                "seed": int(seed),
                "quantile": q,
                "nominal_tau": tau,
                "event_window_hours": int(window_hours),
                "n_basins": int(n_basins),
                "peak_hour_capture_rate": (capture_peak[q] / n_basins) if n_basins else math.nan,
                "event_window_capture_rate": (capture_window[q] / n_basins) if n_basins else math.nan,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# AC8 — quantile skill score vs TRAIN-period per-basin climatology quantiles
# ---------------------------------------------------------------------------
def _load_train_climatology(
    timeseries_dir: Path, basins: list[str]
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Per-basin climatology quantiles from TRAIN-period (2000-2010) observed
    Streamflow in the dataset NetCDF files. Leakage-free: only train-window rows.
    Asserts the observed window stays within [TRAIN_PERIOD_START, TRAIN_PERIOD_END].
    """
    import xarray as xr

    taus = list(QUANTILES.values())
    start = pd.Timestamp(TRAIN_PERIOD_START)
    end = pd.Timestamp(TRAIN_PERIOD_END)
    records: list[dict[str, object]] = []
    total_rows = 0
    used_basins = 0
    for basin in basins:
        nc_path = timeseries_dir / f"{basin}.nc"
        if not nc_path.exists():
            continue
        with xr.open_dataset(nc_path) as ds:
            if STREAMFLOW_VAR not in ds.data_vars:
                raise KeyError(f"{STREAMFLOW_VAR} missing in {nc_path}")
            dates = pd.to_datetime(ds["date"].values)
            sf = pd.to_numeric(pd.Series(ds[STREAMFLOW_VAR].values), errors="coerce")
        mask = (dates >= start) & (dates <= end)
        obs = sf[mask].dropna()
        if obs.empty:
            continue
        # AC8 leakage guard: train window only.
        win_dates = dates[mask]
        assert win_dates.min() >= start and win_dates.max() <= end, (
            f"AC8 leakage guard: basin {basin} train window {win_dates.min()}..{win_dates.max()} "
            f"escapes [{TRAIN_PERIOD_START}, {TRAIN_PERIOD_END}]"
        )
        qs = np.quantile(obs.to_numpy(), taus)
        rec: dict[str, object] = {"basin": basin}
        for name, val in zip(QUANTILES, qs, strict=True):
            rec[f"clim_{name}"] = float(val)
        records.append(rec)
        total_rows += int(len(obs))
        used_basins += 1
    clim = pd.DataFrame(records).set_index("basin")
    meta = {
        "source": "dataset NetCDF Streamflow (m3 s-1), train window only",
        "timeseries_dir": _relative(timeseries_dir),
        "train_period_start": TRAIN_PERIOD_START,
        "train_period_end": TRAIN_PERIOD_END,
        "n_basins_with_climatology": used_basins,
        "total_train_obs_rows": total_rows,
    }
    return clim, meta


def _skill_score(
    df: pd.DataFrame,
    clim: pd.DataFrame,
    seed: int,
) -> list[dict[str, object]]:
    """Pinball skill score = 1 - (model pinball / climatology pinball).

    Baseline climatology comes from TRAIN-period obs ONLY (precomputed, leakage-free).
    Model pinball is evaluated on the observed test rows.
    """
    assert not clim.empty, "AC8: train-period climatology is empty"
    joined = df[["basin", "obs", *QUANTILES]].join(clim, on="basin")
    rows: list[dict[str, object]] = []
    for q, tau in QUANTILES.items():
        sub = joined[joined[f"clim_{q}"].notna() & joined["obs"].notna()]
        if sub.empty:
            continue
        model_loss = _pinball(sub["obs"], sub[q], tau).mean()
        base_loss = _pinball(sub["obs"], sub[f"clim_{q}"], tau).mean()
        skill = 1.0 - (model_loss / base_loss) if base_loss > 0 else math.nan
        rows.append(
            {
                "seed": int(seed),
                "quantile": q,
                "nominal_tau": tau,
                "baseline": "train_climatology_2000_2010",
                "n_rows": int(len(sub)),
                "model_mean_pinball": float(model_loss),
                "baseline_mean_pinball": float(base_loss),
                "pinball_skill_score": float(skill) if np.isfinite(skill) else math.nan,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# AC9 — upper-tail pinball proxy (mean pinball over q50/q90/q95/q99). NOT CRPS.
# ---------------------------------------------------------------------------
def _upper_tail_pinball_proxy(df: pd.DataFrame, seed: int) -> list[dict[str, object]]:
    """Mean of per-quantile pinball losses across the upper quantile set.

    This is an UPPER-TAIL approximation only: the quantile set has no lower tail,
    so this is NOT a full predictive distribution score (deliberately avoids the
    CRPS naming, which would imply a calibrated two-sided distribution).
    """
    masks = _stratum_masks(df)
    rows: list[dict[str, object]] = []
    for stratum, _label in STRATA:
        frame = df.loc[masks[stratum]]
        if frame.empty:
            continue
        per_q = []
        for q, tau in QUANTILES.items():
            valid = frame["obs"].notna() & frame[q].notna()
            if not valid.any():
                continue
            per_q.append(float(_pinball(frame.loc[valid, "obs"], frame.loc[valid, q], tau).mean()))
        if not per_q:
            continue
        rows.append(
            {
                "seed": int(seed),
                "stratum": stratum,
                "stratum_label": STRATUM_LABELS.get(stratum, stratum),
                "n_rows": int(frame["obs"].notna().sum()),
                "upper_tail_pinball_proxy": float(np.mean(per_q)),
                "n_quantiles_averaged": int(len(per_q)),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# AC10 — IQR-distance error-tier calibration / coverage
# ---------------------------------------------------------------------------
def _tier_calibration(df: pd.DataFrame, tier_map: pd.Series, seed: int) -> list[dict[str, object]]:
    """All-hour empirical coverage per IQR-distance error tier.

    tier = dominant_distance_label (basin-level), joined row-wise by basin.
    NOTE: tier is ERROR-DERIVED, so coverage-by-tier is partly circular.
    """
    work = df[["basin", "obs", *QUANTILES]].copy()
    work["tier"] = work["basin"].map(tier_map)
    rows: list[dict[str, object]] = []
    for tier in TIER_ORDER:
        frame = work[work["tier"] == tier]
        if frame.empty:
            continue
        for q, tau in QUANTILES.items():
            valid = frame["obs"].notna() & frame[q].notna()
            if not valid.any():
                continue
            obs = frame.loc[valid, "obs"]
            pred = frame.loc[valid, q]
            coverage = float((obs <= pred).mean())
            rows.append(
                {
                    "seed": int(seed),
                    "tier": tier,
                    "tier_basis": "dominant_distance_label (IQR-distance error tier)",
                    "quantile": q,
                    "nominal_tau": tau,
                    "n_rows": int(len(obs)),
                    "n_basins": int(frame.loc[valid, "basin"].nunique()),
                    "empirical_coverage": coverage,
                    "coverage_error": coverage - tau,
                }
            )
    return rows


def _save_tier_calibration_plot(tier_agg: pd.DataFrame, path: Path) -> None:
    if tier_agg.empty:
        return
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    tiers = [t for t in TIER_ORDER if t in set(tier_agg["tier"])]
    for tier in tiers:
        g = tier_agg[tier_agg["tier"] == tier].sort_values("nominal_tau")
        ax.plot(g["nominal_tau"], g["mean_empirical_coverage"], marker="o", linewidth=1.6, label=tier)
    ax.plot([0, 1], [0, 1], color="#4b5563", linestyle="--", linewidth=1.0, label="nominal")
    ax.set_xlim(0.45, 1.01)
    ax.set_ylim(0.0, 1.01)
    ax.set_xlabel("Nominal quantile level")
    ax.set_ylabel("Empirical coverage: fraction(obs <= q)")
    ax.set_title("Expanded DRBC calibration by IQR-distance error tier")
    ax.grid(True, color="#d1d5db", linewidth=0.7, alpha=0.8)
    ax.legend(frameon=False, loc="lower right", title="error tier")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _agg_mean(df: pd.DataFrame, group_cols: list[str], value_cols: list[str]) -> pd.DataFrame:
    rows = []
    for keys, group in df.groupby(group_cols, dropna=False, sort=True):
        keys = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(group_cols, keys, strict=True))
        row["n_seeds"] = int(len(group))
        for col in value_cols:
            row[f"mean_{col}"] = float(group[col].mean())
            row[f"min_{col}"] = float(group[col].min())
            row[f"max_{col}"] = float(group[col].max())
        rows.append(row)
    return pd.DataFrame(rows)


def _write_expanded_report(
    *,
    output_dir: Path,
    pinball_by_stratum: pd.DataFrame,
    calibration_by_stratum: pd.DataFrame,
    spread_by_stratum: pd.DataFrame,
    capture_agg: pd.DataFrame,
    skill_agg: pd.DataFrame,
    proxy_agg: pd.DataFrame,
    tier_agg: pd.DataFrame,
    manifest: dict[str, object],
) -> Path:
    report_dir = output_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.md"

    def _fmt(df: pd.DataFrame, cols: list[str]) -> str:
        if df.empty:
            return "_No rows._"
        t = df[cols].copy()
        for c in t.select_dtypes(include=["float", "float64"]).columns:
            t[c] = t[c].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
        lines = [
            "| " + " | ".join(cols) + " |",
            "| " + " | ".join("---" for _ in cols) + " |",
        ]
        for _, r in t.iterrows():
            lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
        return "\n".join(lines)

    primary_all_cal = calibration_by_stratum[
        (calibration_by_stratum["comparison"] == "primary")
        & (calibration_by_stratum["stratum"] == "all")
    ]
    primary_top1_cal = calibration_by_stratum[
        (calibration_by_stratum["comparison"] == "primary")
        & (calibration_by_stratum["stratum"] == "basin_top1")
    ]
    primary_all_pinball = pinball_by_stratum[
        (pinball_by_stratum["comparison"] == "primary") & (pinball_by_stratum["stratum"] == "all")
    ]

    total_nan = sum(m["n_obs_nan_dropped"] for m in manifest["per_seed"])
    total_raw = sum(m["n_rows_raw"] for m in manifest["per_seed"])

    lines = [
        "# Expanded DRBC Probabilistic Diagnostics (Phase 1)",
        "",
        "Model 2 `q50/q90/q95/q99` are **one-sided UPPER** quantiles (no lower tail).",
        "Computed on the expanded DRBC observed test split (standalone; 154-vs-expanded comparison is Phase 2, deferred).",
        "",
        "## Inputs",
        "",
        f"- Seeds: {', '.join(str(s) for s in manifest['seeds'])}",
        f"- Raw rows (all seeds): {total_raw:,}; NaN-obs rows dropped: {total_nan:,} "
        f"({total_nan / total_raw * 100:.2f}% of raw).",
        f"- Per-seed observed rows / basins: see `comparability_manifest.json`.",
        "",
        "## Primary All-Hour Calibration (one-sided coverage)",
        "",
        _fmt(
            primary_all_cal,
            ["quantile", "nominal_tau", "median_empirical_coverage", "median_coverage_error",
             "median_abs_coverage_error", "median_underestimation_fraction"],
        ),
        "",
        "## Primary All-Hour Pinball / AQS",
        "",
        _fmt(
            primary_all_pinball,
            ["quantile", "nominal_tau", "median_mean_pinball", "median_mean_aqs",
             "median_mean_pinball_pct_mean_obs"],
        ),
        "",
        "## Q99-Exceedance Tail Hit Rate",
        "",
        _fmt(
            primary_top1_cal,
            ["quantile", "nominal_tau", "median_empirical_coverage", "median_coverage_error",
             "median_underestimation_fraction"],
        ),
        "",
        f"## Peak / Event Quantile Capture Rate (AC7, +/-{EVENT_WINDOW_HOURS}h window)",
        "",
        "Event window definition reused from `scripts/model/extreme_rain/"
        "analyze_subset300_extreme_rain_stress_test.py` (`peak_quantile_bracket_metrics`, "
        f"default `--peak-quantile-window-hours={EVENT_WINDOW_HOURS}`).",
        "",
        _fmt(
            capture_agg,
            ["quantile", "nominal_tau", "mean_peak_hour_capture_rate",
             "mean_event_window_capture_rate"],
        ),
        "",
        "## Quantile Skill Score vs TRAIN-period Climatology (AC8)",
        "",
        "Baseline = per-basin climatology quantiles from the **TRAIN period (2000-2010) only** "
        "(no test-period leakage). Skill = 1 - model_pinball / baseline_pinball; higher is better.",
        "",
        _fmt(
            skill_agg,
            ["quantile", "nominal_tau", "mean_model_mean_pinball",
             "mean_baseline_mean_pinball", "mean_pinball_skill_score"],
        ),
        "",
        "## Upper-Tail Pinball Proxy (AC9)",
        "",
        "Mean pinball loss across the upper quantile set (q50/q90/q95/q99). This is an "
        "**upper-tail approximation only**, not a full two-sided distribution score "
        "(the quantile set has no lower tail).",
        "",
        _fmt(
            proxy_agg,
            ["stratum", "stratum_label", "mean_upper_tail_pinball_proxy"],
        ),
        "",
        "## Calibration by IQR-distance Error Tier (AC10)",
        "",
        "Tier = `dominant_distance_label` from `tables/expanded_drbc_tier_profile.csv` "
        "(basin-level, joined row-wise). **Caveat:** the tier is error-derived, so "
        "coverage-by-tier is partly circular and should not be read as an independent "
        "calibration test.",
        "",
        _fmt(
            tier_agg[tier_agg["nominal_tau"] == 0.99],
            ["tier", "quantile", "nominal_tau", "mean_empirical_coverage", "mean_coverage_error"],
        ),
        "",
        "## Caveats",
        "",
        "- **obs-NaN denominator:** the expanded `primary_required_series.csv` has ~7.7% NaN obs; "
        "these rows are dropped, so the all-stratum coverage denominator is observed hours only.",
        "- **dataset-relative thresholds:** per-basin high-flow strata thresholds are computed from "
        "this split's own obs, so absolute values are NOT comparable across disjoint basin sets.",
        "- **q99 is not a calibrated 99% quantile:** `nominal_tau=0.99` is the training target, not an "
        "empirically calibrated 99% prediction bound (see doc 08).",
        "- **upper-tail proxy:** the pinball proxy and all coverage are one-sided upper quantities; no "
        "lower tail, interval score, or central prediction interval is defined.",
        "- **Phase 2 deferred:** 154-vs-expanded comparison requires the scaling_300 baseline, which is "
        "absent on disk; see `comparability_manifest.json` for the metadata recorded to enable it later.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    args = parse_args()
    input_dir = _resolve(args.input_dir)
    output_dir = _resolve(args.output_dir)
    timeseries_dir = _resolve(args.timeseries_dir)
    seeds = list(args.seeds)

    # AC0 — fail fast before any heavy compute.
    series_paths, tier_path = _preflight(input_dir, seeds, timeseries_dir)

    figures_dir = output_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    tier_df = pd.read_csv(tier_path, dtype={"basin": str})
    tier_df["basin"] = tier_df["basin"].str.zfill(8)
    tier_map = tier_df.set_index("basin")["dominant_distance_label"]

    pinball_rows: list[dict[str, object]] = []
    calibration_rows: list[dict[str, object]] = []
    spread_rows: list[dict[str, object]] = []
    capture_rows: list[dict[str, object]] = []
    skill_rows: list[dict[str, object]] = []
    proxy_rows: list[dict[str, object]] = []
    tier_rows: list[dict[str, object]] = []
    per_seed_meta: list[dict[str, object]] = []

    # AC8 — load TRAIN-period (2000-2010) climatology once (leakage-free).
    clim, clim_meta = _load_train_climatology(timeseries_dir, sorted(tier_map.index.tolist()))

    for seed, path in zip(seeds, series_paths, strict=True):
        df, meta = _read_expanded_series(path, seed)
        meta["path"] = _relative(path)
        per_seed_meta.append(meta)

        rows = base._summarize_series(
            df,
            comparison="primary",
            seed=seed,
            model1_epoch=int(df["model1_epoch"].iloc[0]) if "model1_epoch" in df else -1,
            model2_epoch=int(df["model2_epoch"].iloc[0]) if "model2_epoch" in df else -1,
        )
        pinball_rows.extend(rows[0])
        calibration_rows.extend(rows[1])
        spread_rows.extend(rows[2])

        capture_rows.extend(_peak_event_capture(df, seed, EVENT_WINDOW_HOURS))
        proxy_rows.extend(_upper_tail_pinball_proxy(df, seed))
        tier_rows.extend(_tier_calibration(df, tier_map, seed))

        # AC8 — train-period climatology skill score (baseline precomputed above).
        skill_rows.extend(_skill_score(df, clim, seed))

    pinball = pd.DataFrame(pinball_rows)
    calibration = pd.DataFrame(calibration_rows)
    spread = pd.DataFrame(spread_rows)
    pinball_by_stratum = _aggregate_pinball(pinball)
    calibration_by_stratum = _aggregate_calibration(calibration)
    spread_by_stratum = _aggregate_spread(spread)

    capture = pd.DataFrame(capture_rows)
    skill = pd.DataFrame(skill_rows)
    proxy = pd.DataFrame(proxy_rows)
    tier = pd.DataFrame(tier_rows)

    capture_agg = (
        _agg_mean(capture, ["quantile", "nominal_tau"],
                  ["peak_hour_capture_rate", "event_window_capture_rate"])
        if not capture.empty else capture
    )
    skill_agg = (
        _agg_mean(skill, ["quantile", "nominal_tau"],
                  ["model_mean_pinball", "baseline_mean_pinball", "pinball_skill_score"])
        if not skill.empty else skill
    )
    proxy_agg = (
        _agg_mean(proxy, ["stratum", "stratum_label"], ["upper_tail_pinball_proxy"])
        if not proxy.empty else proxy
    )
    tier_agg = (
        _agg_mean(tier, ["tier", "quantile", "nominal_tau"], ["empirical_coverage", "coverage_error"])
        if not tier.empty else tier
    )

    # AC4 — quantile crossing sanity check (must be 0 rows).
    crossing_total = int(
        sum(int(r["q90_lt_q50_rows"] + r["q95_lt_q90_rows"] + r["q99_lt_q95_rows"]) for r in spread_rows)
    )

    # --- write CSV outputs ---
    pinball.to_csv(output_dir / "quantile_pinball_summary.csv", index=False)
    pinball_by_stratum.to_csv(output_dir / "quantile_pinball_by_stratum.csv", index=False)
    calibration.to_csv(output_dir / "quantile_calibration_summary.csv", index=False)
    calibration_by_stratum.to_csv(output_dir / "quantile_calibration_by_stratum.csv", index=False)
    spread.to_csv(output_dir / "upper_tail_spread_summary.csv", index=False)
    spread_by_stratum.to_csv(output_dir / "upper_tail_spread_by_stratum.csv", index=False)
    capture.to_csv(output_dir / "peak_event_capture_rate.csv", index=False)
    if not capture_agg.empty:
        capture_agg.to_csv(output_dir / "peak_event_capture_rate_agg.csv", index=False)
    skill.to_csv(output_dir / "quantile_skill_score.csv", index=False)
    if not skill_agg.empty:
        skill_agg.to_csv(output_dir / "quantile_skill_score_agg.csv", index=False)
    proxy.to_csv(output_dir / "upper_tail_pinball_proxy.csv", index=False)
    if not proxy_agg.empty:
        proxy_agg.to_csv(output_dir / "upper_tail_pinball_proxy_agg.csv", index=False)
    tier.to_csv(output_dir / "tier_calibration.csv", index=False)
    if not tier_agg.empty:
        tier_agg.to_csv(output_dir / "tier_calibration_agg.csv", index=False)

    crossing_path = output_dir / "quantile_crossing_check.csv"
    pd.DataFrame(
        [{
            "q90_lt_q50_rows": sum(int(r["q90_lt_q50_rows"]) for r in spread_rows),
            "q95_lt_q90_rows": sum(int(r["q95_lt_q90_rows"]) for r in spread_rows),
            "q99_lt_q95_rows": sum(int(r["q99_lt_q95_rows"]) for r in spread_rows),
            "total_crossing_rows": crossing_total,
        }]
    ).to_csv(crossing_path, index=False)

    # --- figures (AC5; same-epoch calibration-error figure intentionally excluded) ---
    _save_primary_calibration_plot(calibration, figures_dir / "primary_all_quantile_calibration.png")
    _save_pinball_stratum_plot(pinball_by_stratum, figures_dir / "primary_pinball_by_stratum.png")
    _save_spread_plot(spread_by_stratum, figures_dir / "primary_q99_q50_spread_by_stratum.png")
    if not tier_agg.empty:
        _save_tier_calibration_plot(tier_agg, figures_dir / "tier_calibration_by_iqr_distance.png")

    # --- AC11 comparability manifest ---
    manifest = {
        "phase": 1,
        "comparison": "primary",
        "input_dir": _relative(input_dir),
        "output_dir": _relative(output_dir),
        "tier_profile": _relative(tier_path),
        "seeds": seeds,
        "quantiles": QUANTILES,
        "strata": {k: v for k, v in STRATA},
        "per_seed": per_seed_meta,
        "skill_score_baseline": {
            "method": "per-basin climatology quantiles from TRAIN period",
            **clim_meta,
        },
        "per_basin_threshold_method": (
            "dataset-relative: per-basin obs quantiles (0.90/0.95/0.99/0.999) computed on this "
            "split's own observed rows via _stratum_masks; NOT comparable across disjoint basin sets"
        ),
        "obs_nan_handling": "rows with NaN obs dropped; all-stratum denominator = observed hours only",
        "event_window": {
            "hours": EVENT_WINDOW_HOURS,
            "source": (
                "scripts/model/extreme_rain/analyze_subset300_extreme_rain_stress_test.py "
                "peak_quantile_bracket_metrics (+/- N hours around observed peak)"
            ),
        },
        "tier_basis": "dominant_distance_label (IQR-distance error tier)",
        "tier_caveat": "error-derived grouping; coverage-by-tier is partly circular",
        "n_basins_per_stratum": _n_basins_per_stratum(calibration),
        "crossing_check": {
            "total_crossing_rows": crossing_total,
            "csv": _relative(crossing_path),
        },
        "phase2_status": (
            "deferred: scaling_300 baseline + regeneration inputs absent on disk"
        ),
    }
    manifest_path = output_dir / "comparability_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    report_path = _write_expanded_report(
        output_dir=output_dir,
        pinball_by_stratum=pinball_by_stratum,
        calibration_by_stratum=calibration_by_stratum,
        spread_by_stratum=spread_by_stratum,
        capture_agg=capture_agg,
        skill_agg=skill_agg,
        proxy_agg=proxy_agg,
        tier_agg=tier_agg,
        manifest=manifest,
    )

    print(f"Wrote expanded DRBC probabilistic diagnostics to {output_dir}")
    print(f"Rows: pinball={len(pinball)}, calibration={len(calibration)}, spread={len(spread)}")
    print(f"AC4 quantile crossing check: total_crossing_rows={crossing_total}")
    print(f"Capture-rate rows={len(capture)}, skill rows={len(skill)}, proxy rows={len(proxy)}, tier rows={len(tier)}")
    print(f"Manifest: {manifest_path}")
    print(f"Report: {report_path}")


def _n_basins_per_stratum(calibration: pd.DataFrame) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    if calibration.empty:
        return out
    sub = calibration[calibration["quantile"] == "q99"]
    for stratum, g in sub.groupby("stratum"):
        out[str(stratum)] = {
            "mean_n_basins": int(round(g["n_basins"].mean())),
            "min_n_basins": int(g["n_basins"].min()),
            "max_n_basins": int(g["n_basins"].max()),
        }
    return out


if __name__ == "__main__":
    main()

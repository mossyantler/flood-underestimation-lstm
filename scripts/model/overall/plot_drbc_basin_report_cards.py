#!/usr/bin/env python3
"""DRBC 유역별 진단 리포트 카드 그림 생성."""
# /// script
# dependencies = [
#   "matplotlib>=3.8",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "scipy>=1.13",
#   "statsmodels>=0.14",
# ]
# ///

import argparse
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

DATA_ROOT    = Path("output/model_analysis/overall_analysis/main_comparison/drbc_basin_report_cards")
SERIES_ROOT  = Path("output/model_analysis/quantile_analysis/required_series")
ATTR_FILE    = Path("output/basin/drbc/analysis/basin_attributes/tables/drbc_selected_basin_analysis_table.csv")
WITHIN_FILE  = Path("output/model_analysis/overall_analysis/main_comparison"
                    "/drbc_attribute_metric_correlations/within_basin/tables/within_basin_rho_table.csv")
METRICS_FILE = Path("output/model_analysis/overall_analysis/epoch_sensitivity/tables/basin_metrics.csv")

Q_BIN_LABELS  = ["Q0-Q50", "Q50-Q90", "Q90-Q99", "Q99+"]
SEASON_ORDER  = ["DJF", "MAM", "JJA", "SON"]
SEASON_COLORS = {"DJF": "#4477AA", "MAM": "#66BB6A", "JJA": "#EF5350", "SON": "#FF9800"}

M1_COLOR  = "#2277BB"
M2_COLOR  = "#EE7722"
OBS_COLOR = "#222222"

FEATURE_LABELS = {
    "drain_sqkm_attr": "Area (km²)", "log10_area": "log10(Area)",
    "frac_snow": "Snow frac.", "p_seasonality": "Seasonality",
    "lat_gage": "Latitude", "elev_mean_m": "Elevation",
    "slope_pct": "Slope (%)", "developed_frac": "Developed",
    "forest_frac": "Forest", "soil_permeability_index": "Permeability",
    "aridity": "Aridity", "baseflow_index_pct": "Baseflow idx",
    "high_prec_freq": "High prec. freq.", "soil_available_water_capacity": "Soil AWC",
    "SANDAVE": "Sand", "CLAYAVE": "Clay",
}
METRIC_LABELS = {
    "m1_mape": "M1 MAPE", "m1_bias": "M1 Bias",
    "m2_q50_mape": "M2 MAPE", "m2_q99_coverage": "M2 q99 cov.",
}


# ── data loaders ─────────────────────────────────────────────────────────────

def load_tables() -> dict:
    tbl = DATA_ROOT / "tables"
    return {
        "regime":    pd.read_csv(tbl / "flow_regime_performance.csv",    dtype={"basin": str}),
        "seasonal":  pd.read_csv(tbl / "seasonal_performance.csv",       dtype={"basin": str}),
        "events":    pd.read_csv(tbl / "event_peak_errors.csv",          dtype={"basin": str}),
        "summary":   pd.read_csv(tbl / "event_summary_per_basin.csv",    dtype={"basin": str}),
        "ante":      pd.read_csv(tbl / "antecedent_condition_perf.csv",  dtype={"basin": str}),
        "rf":        pd.read_csv(tbl / "rising_falling_bias.csv",        dtype={"basin": str}),
        "feat_corr": pd.read_csv(tbl / "feature_regime_correlations.csv"),
    }


def load_basin_metadata() -> pd.DataFrame:
    attrs = pd.read_csv(ATTR_FILE, dtype={"gauge_id": str})
    attrs["gauge_id"] = attrs["gauge_id"].str.zfill(8)
    attrs = attrs.rename(columns={"gauge_id": "basin"}).set_index("basin")

    within = pd.read_csv(WITHIN_FILE, dtype={"basin": str}).set_index("basin")

    metrics = pd.read_csv(METRICS_FILE, dtype={"basin": str})
    basin_ids = sorted(metrics["basin"].str.zfill(8).unique())

    result = []
    for b in basin_ids:
        name = str(attrs.loc[b, "gauge_name"]) if b in attrs.index else b
        area = float(attrs.loc[b, "drain_sqkm_attr"]) if b in attrs.index else np.nan
        rho  = float(within.loc[b, "within_m1_bias_rho"]) if b in within.index else np.nan
        result.append({"basin": b, "name": name, "area": area, "within_bias_rho": rho})
    return pd.DataFrame(result).set_index("basin")


def load_fdc_series(basin: str) -> dict:
    """FDC 계산용 seed111 primary series 로드."""
    path = SERIES_ROOT / "seed111" / "epoch005_required_series.csv"
    df = pd.read_csv(path, dtype={"basin": str})
    df["basin"] = df["basin"].str.zfill(8)
    grp = df[df["basin"] == basin].dropna(subset=["obs"])
    grp = grp[grp["obs"] > 0]
    return {
        "obs":    np.sort(grp["obs"].values)[::-1],
        "model1": np.sort(grp["model1"].values)[::-1],
        "q50":    np.sort(grp["q50"].values)[::-1],
    }


# ── panel plot functions ──────────────────────────────────────────────────────

def plot_p1_fdc(ax: plt.Axes, basin: str) -> None:
    """P1: Flow Duration Curve (log scale)."""
    series = load_fdc_series(basin)
    n = len(series["obs"])
    ep = np.arange(1, n + 1) / n * 100
    ax.semilogy(ep, series["obs"],    color=OBS_COLOR, lw=1.5, label="Obs")
    ax.semilogy(ep, series["model1"], color=M1_COLOR,  lw=1.2, label="M1", alpha=0.8)
    ax.semilogy(ep, series["q50"],    color=M2_COLOR,  lw=1.2, label="M2 q50", alpha=0.8, ls="--")
    ax.set_xlabel("Exceedance prob. (%)", fontsize=7)
    ax.set_ylabel("Flow (m³/s)", fontsize=7)
    ax.set_title("FDC", fontsize=8, fontweight="bold")
    ax.legend(fontsize=6, loc="upper right")
    ax.tick_params(labelsize=6)
    ax.set_xlim(0, 100)


def plot_p2_regime_mape(ax: plt.Axes, basin: str, regime_df: pd.DataFrame) -> None:
    """P2: Q-bin별 MAPE bar (M1 vs M2 q50)."""
    sub = regime_df[regime_df["basin"] == basin].set_index("q_bin")
    bins = [b for b in Q_BIN_LABELS if b in sub.index]
    if not bins:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        return
    x = np.arange(len(bins)); w = 0.35
    ax.bar(x - w/2, [sub.loc[b, "m1_mape"] for b in bins],
           w, color=M1_COLOR, label="M1", alpha=0.85)
    ax.bar(x + w/2, [sub.loc[b, "m2_q50_mape"] for b in bins],
           w, color=M2_COLOR, label="M2 q50", alpha=0.85)
    ax.set_xticks(x); ax.set_xticklabels(bins, fontsize=6, rotation=20)
    ax.set_ylabel("MAPE (%)", fontsize=7)
    ax.set_title("MAPE by flow regime", fontsize=8, fontweight="bold")
    ax.legend(fontsize=6); ax.tick_params(labelsize=6)


def plot_p3_regime_bias(ax: plt.Axes, basin: str, regime_df: pd.DataFrame) -> None:
    """P3: Q-bin별 Bias % (M1 vs M2 q50), 0 기준선 포함."""
    sub = regime_df[regime_df["basin"] == basin].set_index("q_bin")
    bins = [b for b in Q_BIN_LABELS if b in sub.index]
    if not bins:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        return
    x = np.arange(len(bins)); w = 0.35
    ax.bar(x - w/2, [sub.loc[b, "m1_bias"] for b in bins],
           w, color=M1_COLOR, label="M1", alpha=0.85)
    ax.bar(x + w/2, [sub.loc[b, "m2_q50_bias"] for b in bins],
           w, color=M2_COLOR, label="M2 q50", alpha=0.85)
    ax.axhline(0, color="black", lw=0.8, ls="--")
    ax.set_xticks(x); ax.set_xticklabels(bins, fontsize=6, rotation=20)
    ax.set_ylabel("Bias (%)", fontsize=7)
    ax.set_title("Bias by flow regime", fontsize=8, fontweight="bold")
    ax.legend(fontsize=6); ax.tick_params(labelsize=6)


def plot_p4_m2_interval(ax: plt.Axes, basin: str, regime_df: pd.DataFrame) -> None:
    """P4: M2 [q50–q99] 폭/obs 비율 (bar) + q90/q99 coverage (line)."""
    sub = regime_df[regime_df["basin"] == basin].set_index("q_bin")
    bins = [b for b in Q_BIN_LABELS if b in sub.index]
    if not bins:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        return
    x = np.arange(len(bins))
    ax2 = ax.twinx()
    ax.bar(x, [sub.loc[b, "m2_interval_width_ratio"] for b in bins],
           0.6, color="#9C27B0", alpha=0.6, label="Width/obs")
    ax2.plot(x, [sub.loc[b, "m2_q90_coverage"] for b in bins],
             "o--", color="#00BCD4", lw=1.2, ms=4, label="Cov q90")
    ax2.plot(x, [sub.loc[b, "m2_q99_coverage"] for b in bins],
             "s-",  color="#F44336", lw=1.2, ms=4, label="Cov q99")
    ax2.axhline(0.99, color="#F44336", lw=0.6, ls=":", alpha=0.5)
    ax2.axhline(0.90, color="#00BCD4", lw=0.6, ls=":", alpha=0.5)
    ax2.set_ylim(0, 1.15); ax2.set_ylabel("Coverage", fontsize=7)
    ax.set_xticks(x); ax.set_xticklabels(bins, fontsize=6, rotation=20)
    ax.set_ylabel("Interval width / obs", fontsize=7)
    ax.set_title("M2 interval & coverage", fontsize=8, fontweight="bold")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=5, loc="upper left")
    ax.tick_params(labelsize=6); ax2.tick_params(labelsize=6)


def plot_p5_seasonal(ax: plt.Axes, basin: str, seasonal_df: pd.DataFrame) -> None:
    """P5: Q99+ 계절 분포 (막대) + 계절별 M1 MAPE (선, 이중 축)."""
    sub = seasonal_df[seasonal_df["basin"] == basin].set_index("season")
    seasons = [s for s in SEASON_ORDER if s in sub.index]
    if not seasons:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        return
    x = np.arange(len(seasons))
    q99_counts = [sub.loc[s, "q99_hour_count"] for s in seasons]
    total = sum(q99_counts) if sum(q99_counts) > 0 else 1
    q99_fracs = [c / total * 100 for c in q99_counts]
    ax2 = ax.twinx()
    ax.bar(x, q99_fracs, 0.6, color=[SEASON_COLORS[s] for s in seasons], alpha=0.75)
    ax2.plot(x, [sub.loc[s, "m1_mape"] for s in seasons],
             "ko-", lw=1.5, ms=5, label="M1 MAPE")
    ax.set_xticks(x); ax.set_xticklabels(seasons, fontsize=7)
    ax.set_ylabel("Q99+ occurrence (%)", fontsize=7)
    ax2.set_ylabel("M1 MAPE (%)", fontsize=7)
    ax.set_title("Seasonal pattern", fontsize=8, fontweight="bold")
    ax2.legend(fontsize=6); ax.tick_params(labelsize=6); ax2.tick_params(labelsize=6)


def plot_p6_event_peak(ax: plt.Axes, basin: str, event_df: pd.DataFrame) -> None:
    """P6: 홍수 사건 obs_peak vs M1 peak_ratio, 계절 색상 코딩."""
    sub = event_df[event_df["basin"] == basin].dropna(subset=["m1_peak_ratio"])
    if sub.empty:
        ax.text(0.5, 0.5, "No events", ha="center", va="center", transform=ax.transAxes)
        return
    for season in SEASON_ORDER:
        mask = sub["season"] == season
        if mask.sum() == 0:
            continue
        ax.scatter(sub.loc[mask, "obs_peak"], sub.loc[mask, "m1_peak_ratio"],
                   s=25, color=SEASON_COLORS[season], label=season,
                   alpha=0.8, edgecolors="white", linewidths=0.3)
    ax.axhline(1.0, color="black", lw=0.8, ls="-",  alpha=0.6)
    ax.axhline(0.7, color="red",   lw=0.8, ls="--", alpha=0.5)
    ax.set_xscale("log")
    ax.set_xlabel("Obs peak (m³/s)", fontsize=7)
    ax.set_ylabel("M1 peak / obs peak", fontsize=7)
    ax.set_title("Event peak ratio", fontsize=8, fontweight="bold")
    ax.legend(fontsize=5, ncol=2); ax.tick_params(labelsize=6)


def plot_p7_antecedent(ax: plt.Axes, basin: str, ante_df: pd.DataFrame) -> None:
    """P7: dry/normal/wet 조건별 M1 MAPE bar."""
    sub = ante_df[ante_df["basin"] == basin].set_index("condition")
    conditions = [c for c in ["dry", "normal", "wet"] if c in sub.index]
    colors = {"dry": "#FF9800", "normal": "#4CAF50", "wet": "#2196F3"}
    if not conditions:
        ax.text(0.5, 0.5, "Insufficient\nevents", ha="center", va="center",
                transform=ax.transAxes, fontsize=7)
        return
    x = np.arange(len(conditions))
    vals = [float(sub.loc[c, "m1_mape"]) for c in conditions]
    ax.bar(x, vals, 0.6, color=[colors[c] for c in conditions], alpha=0.85)
    ax.set_xticks(x); ax.set_xticklabels(conditions, fontsize=7)
    ax.set_ylabel("M1 MAPE (%)", fontsize=7)
    ax.set_title("Antecedent condition", fontsize=8, fontweight="bold")
    ax.tick_params(labelsize=6)
    for xi, c in enumerate(conditions):
        n = int(sub.loc[c, "n_events"])
        ax.text(xi, vals[xi] * 1.02, f"n={n}", ha="center", fontsize=5.5)


def plot_p8_rising_falling(ax: plt.Axes, basin: str, rf_df: pd.DataFrame) -> None:
    """P8: Rising vs Falling limb M1 / M2 q50 Bias %."""
    sub = rf_df[rf_df["basin"] == basin].set_index("phase")
    phases = [p for p in ["rising", "falling"] if p in sub.index]
    if not phases:
        ax.text(0.5, 0.5, "Insufficient\nevents", ha="center", va="center",
                transform=ax.transAxes, fontsize=7)
        return
    x = np.arange(len(phases)); w = 0.35
    ax.bar(x - w/2, [float(sub.loc[p, "m1_bias"])     for p in phases],
           w, color=M1_COLOR, label="M1", alpha=0.85)
    ax.bar(x + w/2, [float(sub.loc[p, "m2_q50_bias"]) for p in phases],
           w, color=M2_COLOR, label="M2 q50", alpha=0.85)
    ax.axhline(0, color="black", lw=0.8, ls="--")
    ax.set_xticks(x); ax.set_xticklabels(phases, fontsize=7)
    ax.set_ylabel("Bias (%)", fontsize=7)
    ax.set_title("Rising vs Falling bias", fontsize=8, fontweight="bold")
    ax.legend(fontsize=6); ax.tick_params(labelsize=6)


# ── report card assembly ──────────────────────────────────────────────────────

def assemble_report_card(basin: str, meta: pd.Series, tables: dict,
                         out_dir: Path, panel_dir: Path,
                         dpi_combined: int = 300, dpi_panel: int = 150) -> None:
    """8-패널 통합 그림 + 개별 패널 PNG 생성."""
    name = str(meta.get("name", basin))[:40]
    area = meta.get("area", np.nan)
    rho  = meta.get("within_bias_rho", np.nan)
    rho_str = f"{rho:.3f}" if np.isfinite(float(rho)) else "N/A"
    area_str = f"{area:.0f}" if np.isfinite(float(area)) else "N/A"
    title = f"Basin {basin} — {name}  (Area={area_str} km²  |  within_bias_ρ={rho_str})"

    panel_funcs = [
        ("p1_fdc",            lambda ax: plot_p1_fdc(ax, basin)),
        ("p2_regime_mape",    lambda ax: plot_p2_regime_mape(ax, basin, tables["regime"])),
        ("p3_regime_bias",    lambda ax: plot_p3_regime_bias(ax, basin, tables["regime"])),
        ("p4_m2_interval",    lambda ax: plot_p4_m2_interval(ax, basin, tables["regime"])),
        ("p5_seasonal",       lambda ax: plot_p5_seasonal(ax, basin, tables["seasonal"])),
        ("p6_event_peak",     lambda ax: plot_p6_event_peak(ax, basin, tables["events"])),
        ("p7_antecedent",     lambda ax: plot_p7_antecedent(ax, basin, tables["ante"])),
        ("p8_rising_falling", lambda ax: plot_p8_rising_falling(ax, basin, tables["rf"])),
    ]

    panel_dir.mkdir(parents=True, exist_ok=True)
    for pname, pfunc in panel_funcs:
        fig_p, ax_p = plt.subplots(figsize=(5, 4))
        try:
            pfunc(ax_p)
        except Exception as exc:
            log.warning("panel %s basin %s: %s", pname, basin, exc)
            ax_p.text(0.5, 0.5, f"Error:\n{exc}", ha="center", va="center",
                      transform=ax_p.transAxes, fontsize=6, color="red")
        fig_p.tight_layout()
        fig_p.savefig(panel_dir / f"{basin}_{pname}.png", dpi=dpi_panel, bbox_inches="tight")
        plt.close(fig_p)

    fig = plt.figure(figsize=(14, 9))
    fig.suptitle(title, fontsize=8, y=1.005)
    gs = gridspec.GridSpec(2, 4, figure=fig, hspace=0.50, wspace=0.40)
    axes = [fig.add_subplot(gs[r, c]) for r in range(2) for c in range(4)]
    for ax, (_, pfunc) in zip(axes, panel_funcs):
        try:
            pfunc(ax)
        except Exception as exc:
            log.warning("combined panel basin %s: %s", basin, exc)
            ax.text(0.5, 0.5, "Error", ha="center", va="center",
                    transform=ax.transAxes, fontsize=7, color="red")
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{basin}_report_card.png", dpi=dpi_combined, bbox_inches="tight")
    plt.close(fig)


# ── cross-basin summary figures ───────────────────────────────────────────────

def plot_regime_heatmaps(feat_corr_df: pd.DataFrame, out_dir: Path) -> None:
    """Q-bin별 feature × metric 상관 heatmap 4개."""
    out_dir.mkdir(parents=True, exist_ok=True)
    feats   = list(FEATURE_LABELS.keys())
    metrics = list(METRIC_LABELS.keys())
    fname_map = {
        "Q0-Q50":  "heatmap_regime_Q0Q50.png",
        "Q50-Q90": "heatmap_regime_Q50Q90.png",
        "Q90-Q99": "heatmap_regime_Q90Q99.png",
        "Q99+":    "heatmap_regime_Q99plus.png",
    }
    for q_bin in Q_BIN_LABELS:
        sub = feat_corr_df[feat_corr_df["q_bin"] == q_bin]
        rho_mat = np.full((len(feats), len(metrics)), np.nan)
        sig_mat = np.zeros_like(rho_mat, dtype=bool)
        for row in sub.itertuples():
            fi = feats.index(row.feature) if row.feature in feats else -1
            mi = metrics.index(row.metric) if row.metric in metrics else -1
            if fi >= 0 and mi >= 0:
                rho_mat[fi, mi] = row.rho
                sig_mat[fi, mi] = bool(row.significant)

        fig, ax = plt.subplots(figsize=(8, 9))
        im = ax.imshow(rho_mat, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
        plt.colorbar(im, ax=ax, label="Spearman ρ", shrink=0.6)
        ax.set_xticks(range(len(metrics)))
        ax.set_xticklabels([METRIC_LABELS[m] for m in metrics], fontsize=8,
                           rotation=20, ha="right")
        ax.set_yticks(range(len(feats)))
        ax.set_yticklabels([FEATURE_LABELS.get(f, f) for f in feats], fontsize=8)
        ax.set_title(f"Feature × Performance  [{q_bin}]\n(* = BH FDR p<0.05)", fontsize=9)
        for fi in range(len(feats)):
            for mi in range(len(metrics)):
                if not np.isnan(rho_mat[fi, mi]):
                    marker = "*" if sig_mat[fi, mi] else ""
                    v = rho_mat[fi, mi]
                    c = "white" if abs(v) > 0.5 else "black"
                    ax.text(mi, fi, f"{v:.2f}{marker}", ha="center", va="center",
                            fontsize=6, color=c)
        plt.tight_layout()
        fig.savefig(out_dir / fname_map[q_bin], dpi=150, bbox_inches="tight")
        plt.close(fig)
        log.info("heatmap saved: %s", fname_map[q_bin])


def plot_event_capture_ranking(summary_df: pd.DataFrame, meta: pd.DataFrame,
                                out_dir: Path) -> None:
    """38유역 포착률 수평 bar chart, 면적 색상 코딩."""
    df = summary_df.copy()
    df["area"] = df["basin"].map(meta["area"])
    df = df.sort_values("capture_rate_pct", ascending=True).reset_index(drop=True)

    log_areas = np.log10(df["area"].clip(lower=1).fillna(1).values)
    norm = (log_areas - log_areas.min()) / (log_areas.max() - log_areas.min() + 1e-9)
    colors = plt.cm.viridis(norm)

    fig, ax = plt.subplots(figsize=(8, 10))
    ax.barh(range(len(df)), df["capture_rate_pct"], color=colors, alpha=0.85)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df["basin"].tolist(), fontsize=6)
    ax.axvline(70, color="red", lw=1, ls="--", label="70% threshold")
    ax.set_xlabel("Event capture rate (peak_ratio ≥ 0.7, %)", fontsize=9)
    ax.set_title("Event Capture Rate Ranking — 38 DRBC Basins\n(color = log10 area)", fontsize=9)
    ax.legend(fontsize=8)
    sm = plt.cm.ScalarMappable(cmap="viridis")
    sm.set_array([])
    plt.colorbar(sm, ax=ax, label="log10(Area km²)", shrink=0.4)
    plt.tight_layout()
    fig.savefig(out_dir / "event_capture_rate_ranking.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("event capture ranking saved")


def plot_antecedent_effect_dist(ante_df: pd.DataFrame, out_dir: Path) -> None:
    """dry vs wet MAPE 차이 분포 (38유역)."""
    dry_mape = ante_df[ante_df["condition"] == "dry"].set_index("basin")["m1_mape"]
    wet_mape = ante_df[ante_df["condition"] == "wet"].set_index("basin")["m1_mape"]
    common = dry_mape.index.intersection(wet_mape.index)
    if len(common) < 2:
        log.warning("not enough basins for antecedent effect distribution plot")
        return
    diff = dry_mape[common] - wet_mape[common]

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.hist(diff.values, bins=12, color="#5C6BC0", edgecolor="white", alpha=0.85)
    ax.axvline(0, color="black", lw=1.2, ls="--", label="No difference")
    ax.axvline(float(diff.median()), color="red", lw=1.5,
               label=f"Median={diff.median():.1f}%")
    ax.set_xlabel("MAPE(dry) − MAPE(wet) (%)", fontsize=9)
    ax.set_ylabel("Basin count", fontsize=9)
    ax.set_title("Antecedent Condition Effect\n(positive = dry events harder to predict)",
                 fontsize=9)
    ax.legend(fontsize=8)
    plt.tight_layout()
    fig.savefig(out_dir / "antecedent_effect_distribution.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("antecedent effect distribution saved")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--basins", nargs="*", default=None,
                        help="특정 유역만 처리 (기본: 전체)")
    parser.add_argument("--dpi-combined", type=int, default=300)
    parser.add_argument("--dpi-panel",    type=int, default=150)
    args = parser.parse_args()

    tables    = load_tables()
    meta      = load_basin_metadata()
    all_ids   = meta.index.tolist()
    basin_ids = args.basins if args.basins else all_ids

    card_dir  = DATA_ROOT / "figures" / "report_cards"
    panel_dir = card_dir / "panels"
    cross_dir = DATA_ROOT / "figures" / "cross_basin"

    log.info("=== generating %d report cards ===", len(basin_ids))
    for i, basin in enumerate(basin_ids):
        log.info("  [%d/%d] %s", i + 1, len(basin_ids), basin)
        if basin not in meta.index:
            log.warning("  basin %s not in metadata, skipping", basin)
            continue
        assemble_report_card(basin, meta.loc[basin], tables,
                             card_dir, panel_dir,
                             args.dpi_combined, args.dpi_panel)

    log.info("=== cross-basin figures ===")
    plot_regime_heatmaps(tables["feat_corr"], cross_dir)
    plot_event_capture_ranking(tables["summary"], meta, cross_dir)
    plot_antecedent_effect_dist(tables["ante"], cross_dir)

    log.info("=== done ===")
    log.info("report cards : %s", card_dir)
    log.info("cross basin  : %s", cross_dir)


if __name__ == "__main__":
    main()

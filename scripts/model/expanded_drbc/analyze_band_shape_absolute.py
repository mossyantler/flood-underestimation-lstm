#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "scipy>=1.13",
# ]
# ///
"""B12 절대 간격 버전 분석.

rel_width / g3_ratio (상대 비율) 대신 절대 간격으로 Spearman r 및
조건부 분포를 비교한다.

  abs_width  = q99 − q50   [m³/s]
  abs_tail   = q99 − q95   [m³/s]
  abs_mid    = q95 − q50   [m³/s]

Spearman r 목표: abs 지표 vs obs_class_ordinal (0~4 서수형)
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

OUTPUT = Path(__file__).resolve().parents[3] / "output/model_analysis/band_signal/band_shape"
TABLES  = OUTPUT / "tables"
SERIES = Path(__file__).resolve().parents[3] / "output/model_analysis/primary/metrics/data/required_series"
FIGURES = OUTPUT / "figures"

SEEDS = [111, 222, 444]

CLASS_ORDINAL = {
    "below_q50": 0, "q50_to_q90": 1, "q90_to_q95": 2,
    "q95_to_q99": 3, "above_q99": 4,
}
CLASS_ORDER = list(CLASS_ORDINAL.keys())
CLASS_COLORS = {
    "below_q50": "#4393c3", "q50_to_q90": "#92c5de",
    "q90_to_q95": "#fddbc7", "q95_to_q99": "#f4a582", "above_q99": "#d6604d",
}


def normalize_basin_id(b: str) -> str:
    return str(b).zfill(8)


def load_series_at_peaks(metrics: pd.DataFrame) -> pd.DataFrame:
    """각 seed의 required_series에서 이벤트 첨두 시각의 q 값 추출."""
    parts = []
    for seed in SEEDS:
        csv = SERIES / f"seed{seed}" / "required_series.csv"
        print(f"  loading seed{seed}...", flush=True)
        df = pd.read_csv(
            csv,
            usecols=["seed", "basin", "datetime", "obs", "q50", "q90", "q95", "q99",
                     "q99_minus_q50", "q99_minus_q95"],
            dtype={"basin": str},
            parse_dates=["datetime"],
        )
        df["basin_id"] = df["basin"].map(normalize_basin_id)
        df = df.rename(columns={"datetime": "peak_time"})

        # 해당 seed의 이벤트 첨두 키만 추출
        keys = metrics[metrics["seed"] == seed][["basin_id", "peak_time", "obs_class", "obs_class_ordinal"]]
        merged = keys.merge(df[["basin_id", "peak_time", "obs", "q50", "q90", "q95", "q99",
                                 "q99_minus_q50", "q99_minus_q95"]],
                            on=["basin_id", "peak_time"], how="left")
        merged["seed"] = seed
        parts.append(merged)
        print(f"  seed{seed}: {len(merged)} rows, NaN q99={merged['q99'].isna().sum()}", flush=True)
    return pd.concat(parts, ignore_index=True)


def compute_abs_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["abs_width"] = out["q99_minus_q50"]          # q99 − q50
    out["abs_tail"]  = out["q99_minus_q95"]           # q99 − q95
    out["abs_mid"]   = out["q95"] - out["q50"]        # q95 − q50
    valid = out["abs_width"].notna() & (out["abs_width"] > 0)
    return out[valid].copy()


def spearman_summary(df: pd.DataFrame, metrics: list[str], scope: str) -> pd.DataFrame:
    rows = []
    y = df["obs_class_ordinal"].values.astype(float)
    for m in metrics:
        x = df[m].values.astype(float)
        mask = np.isfinite(x) & np.isfinite(y)
        n = int(mask.sum())
        if n >= 3:
            r, p = spearmanr(x[mask], y[mask])
        else:
            r, p = float("nan"), float("nan")
        rows.append({"scope": scope, "metric": m, "r": round(float(r), 4),
                     "p_value": float(p), "n": n})
    return pd.DataFrame(rows)


def plot_scatter_abs(df: pd.DataFrame, out_path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    metrics_info = [
        ("abs_width", "abs_width = q99−q50 [m³/s]"),
        ("abs_tail",  "abs_tail  = q99−q95 [m³/s]"),
        ("abs_mid",   "abs_mid   = q95−q50 [m³/s]"),
    ]
    rng = np.random.default_rng(42)
    jitter = 0.18
    for ax, (metric, xlabel) in zip(axes, metrics_info):
        for cls in CLASS_ORDER:
            sub = df[df["obs_class"] == cls]
            if sub.empty:
                continue
            y_base = CLASS_ORDINAL[cls]
            yj = rng.uniform(-jitter, jitter, size=len(sub))
            ax.scatter(sub[metric], y_base + yj, alpha=0.25, s=8,
                       color=CLASS_COLORS[cls], label=cls, zorder=2)
        x = df[metric].values.astype(float)
        y = df["obs_class_ordinal"].values.astype(float)
        mask = np.isfinite(x) & np.isfinite(y)
        if mask.sum() >= 3:
            r, p = spearmanr(x[mask], y[mask])
            ax.text(0.97, 0.97, f"Spearman r = {r:.3f}\np = {p:.2e}  n={int(mask.sum())}",
                    transform=ax.transAxes, ha="right", va="top", fontsize=8,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
        ax.set_yticks(list(CLASS_ORDINAL.values()))
        ax.set_yticklabels(list(CLASS_ORDINAL.keys()), fontsize=7)
        ax.set_xlabel(xlabel, fontsize=8)
        ax.grid(alpha=0.25, axis="x")
    axes[0].legend(fontsize=7, loc="lower right", markerscale=1.5)
    fig.suptitle("Absolute-interval metrics vs obs gap class at event peaks (B12 supplement)\nQ99 events, n~2,770 (3 seeds pooled)", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {out_path}", flush=True)


BIN_LABELS = ["Q1 (narrow)", "Q2", "Q3", "Q4 (wide)"]


def plot_lookup_abs(df: pd.DataFrame, out_path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    metrics_info = [
        ("abs_width", "abs_width = q99−q50"),
        ("abs_tail",  "abs_tail  = q99−q95"),
        ("abs_mid",   "abs_mid   = q95−q50"),
    ]
    for ax, (metric, title) in zip(axes, metrics_info):
        work = df.copy()
        work["bin"] = pd.qcut(work[metric], q=4, labels=BIN_LABELS, duplicates="drop")
        bottoms = np.zeros(4)
        n_per_bin = work.groupby("bin", observed=True).size()
        for cls in CLASS_ORDER:
            fracs = []
            for lbl in BIN_LABELS:
                sub = work[work["bin"] == lbl]
                fracs.append((sub["obs_class"] == cls).sum() / len(sub) if len(sub) > 0 else 0.0)
            fracs = np.array(fracs)
            ax.bar(range(4), fracs, bottom=bottoms, color=CLASS_COLORS[cls],
                   label=cls, edgecolor="white", linewidth=0.4)
            bottoms += fracs
        for i, lbl in enumerate(BIN_LABELS):
            n = int(n_per_bin.get(lbl, 0))
            ax.text(i, 1.01, f"n={n}", ha="center", fontsize=7, color="0.4")
        ax.set_xticks(range(4))
        ax.set_xticklabels(BIN_LABELS, fontsize=7, rotation=15, ha="right")
        ax.set_ylim(0, 1.12)
        ax.set_ylabel("Fraction of events" if ax == axes[0] else "", fontsize=8)
        ax.set_title(title, fontsize=9)
        ax.grid(axis="y", alpha=0.25)
    axes[-1].legend(fontsize=7, loc="upper left", bbox_to_anchor=(1.01, 1))
    fig.suptitle("Conditional obs gap class distribution by absolute-interval bins (B12 supplement)\nQ99 event peaks", fontsize=10, y=1.01)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {out_path}", flush=True)


def compare_table(abs_sp: pd.DataFrame, rel_sp: pd.DataFrame) -> None:
    """기존 상대 지표 vs 절대 지표 Spearman r 비교."""
    print("\n=== 상대 vs 절대 지표 Spearman r 비교 (Q99 이벤트 첨두) ===")
    print(f"{'지표':<20} {'r':>8} {'p':>12} {'n':>8}  {'비고'}")
    print("-" * 65)
    # 기존 상대 지표
    for _, row in rel_sp[rel_sp["scope"] == "q99"].iterrows():
        print(f"  {row['metric']:<18} {row['r']:>8.4f} {row['p_value']:>12.2e} {row['n']:>8}  (상대)")
    print()
    # 새 절대 지표
    for _, row in abs_sp.iterrows():
        print(f"  {row['metric']:<18} {row['r']:>8.4f} {row['p_value']:>12.2e} {row['n']:>8}  (절대)")


def main() -> None:
    print("[abs-B12] 기존 metrics 로드...", flush=True)
    metrics = pd.read_csv(TABLES / "band_shape_metrics_q99.csv", comment="#",
                          dtype={"basin_id": str}, parse_dates=["peak_time"])
    print(f"  metrics: {len(metrics)} rows, seeds={sorted(metrics['seed'].unique())}")

    print("[abs-B12] required_series에서 q 값 추출...", flush=True)
    df = load_series_at_peaks(metrics)

    print("[abs-B12] 절대 간격 지표 계산...", flush=True)
    df = compute_abs_metrics(df)
    print(f"  유효 행: {len(df)}")
    print(df[["abs_width", "abs_tail", "abs_mid"]].describe().round(2))

    # Spearman r
    abs_metrics = ["abs_width", "abs_tail", "abs_mid"]
    abs_sp = spearman_summary(df, abs_metrics, "q99_abs")
    print("\n[abs-B12] Spearman r (절대 간격):")
    print(abs_sp.to_string(index=False))

    # 기존 상대 지표 Spearman 파일 로드
    rel_sp_path = TABLES / "band_shape_spearman.csv"
    if rel_sp_path.exists():
        rel_sp = pd.read_csv(rel_sp_path, comment="#")
        compare_table(abs_sp, rel_sp)

    # 그림 저장
    scatter_path = FIGURES / "band_shape_scatter_absolute.png"
    lookup_path  = FIGURES / "band_shape_lookup_absolute.png"
    print("\n[abs-B12] 그림 생성...", flush=True)
    plot_scatter_abs(df, scatter_path)
    plot_lookup_abs(df, lookup_path)

    # CSV 저장
    out_csv = TABLES / "band_shape_metrics_q99_absolute.csv"
    df[["basin_id", "seed", "peak_time", "abs_width", "abs_tail", "abs_mid",
        "obs_class", "obs_class_ordinal"]].to_csv(out_csv, index=False)
    print(f"[abs-B12] saved {out_csv}")

    abs_sp_csv = TABLES / "band_shape_spearman_absolute.csv"
    abs_sp.to_csv(abs_sp_csv, index=False)
    print(f"[abs-B12] saved {abs_sp_csv}")

    print("\n[abs-B12] 완료.", flush=True)


if __name__ == "__main__":
    main()

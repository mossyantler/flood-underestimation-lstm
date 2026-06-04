#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=2.0",
#   "pandas>=2.2",
# ]
# ///
"""Aggregate and plot direct SHAP outputs from the quantile LSTM analysis.

입력은 ``compute_q99_lstm_direct_shap.py``가 만든 seed별 CSV이다.
이 스크립트는 q50/q90/q95/q99를 함께 비교하기 위한 seed 평균 표와
논문·발표용 figure를 만든다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_DIR = REPO_ROOT / "output/model_analysis/shap/test_split"
QUANTILES = ["q50", "q90", "q95", "q99"]


def configure_plot_fonts() -> None:
    preferred = ["AppleGothic", "NanumGothic", "Noto Sans CJK KR", "Noto Sans KR", "Malgun Gothic"]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    for name in preferred:
        if name in installed:
            matplotlib.rcParams["font.family"] = [name]
            matplotlib.rcParams["axes.unicode_minus"] = False
            return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze direct quantile LSTM SHAP outputs.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--top-n", type=int, default=8)
    return parser.parse_args()


def seed_from_name(path: Path) -> int:
    return int(path.stem.rsplit("seed", 1)[1])


def read_seed_tables(input_dir: Path, kind: str) -> pd.DataFrame:
    frames = []
    for path in sorted((input_dir / "tables").glob(f"quantile_lstm_direct_shap_{kind}_seed*.csv")):
        # seed_mean 같은 집계 파일은 제외한다.
        suffix = path.stem.rsplit("seed", 1)[1]
        if not suffix.isdigit():
            continue
        frame = pd.read_csv(path)
        frame["seed"] = seed_from_name(path)
        frames.append(frame)
    if not frames:
        raise FileNotFoundError(f"No seed tables for kind={kind!r} under {input_dir / 'tables'}")
    return pd.concat(frames, ignore_index=True)


def aggregate_global(global_df: pd.DataFrame) -> pd.DataFrame:
    return (
        global_df.groupby(["quantile", "feature_group", "feature", "feature_label_ko"], as_index=False)
        .agg(
            mean_abs_shap_mean=("mean_abs_shap", "mean"),
            mean_abs_shap_std=("mean_abs_shap", "std"),
            mean_signed_shap_mean=("mean_signed_shap", "mean"),
            max_abs_shap_max=("max_abs_shap", "max"),
            n_seeds=("seed", "nunique"),
        )
        .sort_values(["quantile", "mean_abs_shap_mean"], ascending=[True, False])
        .reset_index(drop=True)
    )


def aggregate_temporal(temporal_df: pd.DataFrame) -> pd.DataFrame:
    return (
        temporal_df.groupby(["quantile", "lag_hours_before_anchor", "feature", "feature_label_ko"], as_index=False)
        .agg(
            mean_abs_shap_mean=("mean_abs_shap", "mean"),
            mean_abs_shap_std=("mean_abs_shap", "std"),
            mean_signed_shap_mean=("mean_signed_shap", "mean"),
            n_seeds=("seed", "nunique"),
        )
        .sort_values(["quantile", "lag_hours_before_anchor", "mean_abs_shap_mean"], ascending=[True, True, False])
    )


def build_ladder_shift(global_seed_mean: pd.DataFrame) -> pd.DataFrame:
    pivot = global_seed_mean.pivot_table(
        index=["feature_group", "feature", "feature_label_ko"],
        columns="quantile",
        values="mean_abs_shap_mean",
        aggfunc="mean",
    ).reset_index()
    for q in QUANTILES:
        if q not in pivot:
            pivot[q] = np.nan
    pivot["q99_minus_q50"] = pivot["q99"] - pivot["q50"]
    pivot["q99_div_q50"] = pivot["q99"] / pivot["q50"].replace(0, np.nan)
    return pivot.sort_values("q99_minus_q50", ascending=False).reset_index(drop=True)


def plot_seed_mean_top_features(global_seed_mean: pd.DataFrame, figures_dir: Path, top_n: int) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=False)
    axes = axes.ravel()
    colors = {
        "dynamic_forcing": "#2563eb",
        "static_attribute": "#16a34a",
    }
    for ax, quantile in zip(axes, QUANTILES):
        top = global_seed_mean[global_seed_mean["quantile"].eq(quantile)].head(top_n).iloc[::-1]
        bar_colors = [colors.get(g, "#64748b") for g in top["feature_group"]]
        ax.barh(
            top["feature_label_ko"],
            top["mean_abs_shap_mean"],
            xerr=top["mean_abs_shap_std"].fillna(0),
            color=bar_colors,
            alpha=0.88,
        )
        ax.set_title(f"{quantile}: 평균 영향 크기 상위 {top_n}개")
        ax.set_xlabel("평균 |SHAP|")
        ax.grid(axis="x", alpha=0.25)
    fig.suptitle("Model 2 quantile LSTM 직접 SHAP: quantile별 중요 입력", fontsize=16, y=0.99)
    fig.text(
        0.5,
        0.015,
        "막대는 seed 111/222/444 평균, 가는 선은 seed 사이 표준편차입니다. 파랑은 시간별 기상 입력, 초록은 유역 고정 속성입니다.",
        ha="center",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    out = figures_dir / "quantile_lstm_direct_shap_seed_mean_top_features.png"
    fig.savefig(out, dpi=220)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    return out


def plot_ladder_shift(ladder_shift: pd.DataFrame, figures_dir: Path, top_n: int) -> Path:
    top = ladder_shift.head(max(top_n, 10)).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.barh(top["feature_label_ko"], top["q99_minus_q50"], color="#dc2626", alpha=0.86)
    ax.axvline(0, color="#334155", linewidth=1)
    ax.set_title("q99로 갈수록 더 커지는 입력 영향: q99 - q50")
    ax.set_xlabel("평균 |SHAP| 차이")
    ax.grid(axis="x", alpha=0.25)
    fig.text(
        0.5,
        0.02,
        "값이 클수록 중심 예측(q50)보다 극단 상단 예측(q99)에서 해당 입력을 더 강하게 본다는 뜻입니다.",
        ha="center",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    out = figures_dir / "quantile_lstm_direct_shap_q99_minus_q50_ladder_shift.png"
    fig.savefig(out, dpi=220)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    return out


def plot_temporal_lag(temporal_seed_mean: pd.DataFrame, global_seed_mean: pd.DataFrame, figures_dir: Path) -> Path:
    dynamic_top = (
        global_seed_mean[global_seed_mean["feature_group"].eq("dynamic_forcing")]
        .groupby(["feature", "feature_label_ko"], as_index=False)["mean_abs_shap_mean"]
        .mean()
        .sort_values("mean_abs_shap_mean", ascending=False)
        .head(4)
    )
    selected = dynamic_top["feature"].tolist()
    labels = dict(zip(dynamic_top["feature"], dynamic_top["feature_label_ko"]))
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True, sharey=False)
    axes = axes.ravel()
    palette = ["#2563eb", "#f97316", "#16a34a", "#7c3aed"]
    for ax, quantile in zip(axes, QUANTILES):
        qdf = temporal_seed_mean[temporal_seed_mean["quantile"].eq(quantile)]
        for color, feature in zip(palette, selected):
            fdf = qdf[qdf["feature"].eq(feature)].sort_values("lag_hours_before_anchor")
            ax.plot(
                fdf["lag_hours_before_anchor"],
                fdf["mean_abs_shap_mean"],
                marker="o",
                linewidth=2,
                color=color,
                label=labels.get(feature, feature),
            )
        ax.invert_xaxis()
        ax.set_title(f"{quantile}: 첨두 전 시간별 영향")
        ax.set_xlabel("첨두 전 시간")
        ax.set_ylabel("평균 |SHAP|")
        ax.grid(alpha=0.25)
    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="lower center", ncol=len(selected), frameon=False)
    fig.suptitle("시간별 기상 입력의 영향이 첨두 전 어느 시점에 커지는가", fontsize=16, y=0.99)
    fig.text(
        0.5,
        0.055,
        "오른쪽 0시간은 예측 기준 시점입니다. 왼쪽으로 갈수록 더 과거 입력입니다.",
        ha="center",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.10, 1, 0.95))
    out = figures_dir / "quantile_lstm_direct_shap_temporal_lag_seed_mean_top_dynamic.png"
    fig.savefig(out, dpi=220)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    return out


def plot_event_quantile_heatmap(event_df: pd.DataFrame, figures_dir: Path, top_n: int) -> Path:
    # 사건별 상세값에서 q99 기준 상위 feature를 골라 quantile별 평균 영향 변화를 heatmap으로 보여준다.
    feature_order = (
        event_df[event_df["quantile"].eq("q99")]
        .groupby(["feature", "feature_label_ko"], as_index=False)["mean_abs_shap"]
        .mean()
        .sort_values("mean_abs_shap", ascending=False)
        .head(top_n)
    )
    selected = feature_order["feature"].tolist()
    labels = feature_order["feature_label_ko"].tolist()
    heat = (
        event_df[event_df["feature"].isin(selected)]
        .groupby(["feature", "quantile"], as_index=False)["mean_abs_shap"]
        .mean()
        .pivot(index="feature", columns="quantile", values="mean_abs_shap")
        .reindex(selected)[QUANTILES]
    )
    fig, ax = plt.subplots(figsize=(8, max(5, 0.5 * len(selected))))
    im = ax.imshow(heat.values, aspect="auto", cmap="YlOrRd")
    ax.set_xticks(range(len(QUANTILES)), QUANTILES)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_title("사건별 상세 SHAP에서 본 quantile별 영향 강도")
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            ax.text(j, i, f"{heat.values[i, j]:.3f}", ha="center", va="center", fontsize=8)
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("평균 |SHAP|")
    fig.tight_layout()
    out = figures_dir / "quantile_lstm_direct_shap_event_level_quantile_heatmap.png"
    fig.savefig(out, dpi=220)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    return out


def aggregate_flow_regime(event_df: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["flow_stratum", "flow_stratum_ko", "quantile", "feature_group", "feature", "feature_label_ko"]
    return (
        event_df.groupby(group_cols, as_index=False)
        .agg(
            mean_abs_shap_mean=("mean_abs_shap", "mean"),
            mean_abs_shap_std=("mean_abs_shap", "std"),
            mean_signed_shap_mean=("mean_signed_shap", "mean"),
            max_abs_shap_max=("max_abs_shap", "max"),
            n_seeds=("seed", "nunique"),
            n_anchor_rows=("row_index", "nunique"),
        )
        .sort_values(["flow_stratum", "quantile", "mean_abs_shap_mean"], ascending=[True, True, False])
    )


def plot_flow_regime_q99_top_features(flow_seed_mean: pd.DataFrame, figures_dir: Path, top_n: int) -> Path:
    order = ["low", "mid", "high", "extreme_q99"]
    title = {
        "low": "저유량",
        "mid": "중유량",
        "high": "고유량",
        "extreme_q99": "극유량(Q99 이상)",
    }
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=False)
    axes = axes.ravel()
    for ax, stratum in zip(axes, order):
        top = (
            flow_seed_mean[flow_seed_mean["flow_stratum"].eq(stratum) & flow_seed_mean["quantile"].eq("q99")]
            .sort_values("mean_abs_shap_mean", ascending=False)
            .head(top_n)
            .iloc[::-1]
        )
        ax.barh(top["feature_label_ko"], top["mean_abs_shap_mean"], color="#2563eb", alpha=0.88)
        ax.set_title(f"{title.get(stratum, stratum)}: q99 출력 중요 입력")
        ax.set_xlabel("평균 |SHAP|")
        ax.grid(axis="x", alpha=0.25)
    fig.suptitle("유량 구간별 직접 SHAP: q99 출력이 무엇을 보는가", fontsize=16, y=0.99)
    fig.text(
        0.5,
        0.015,
        "유량 구간은 공식 test split 관측 유량 분위수로만 나눴고, 관측 유량은 LSTM 입력으로 넣지 않았습니다.",
        ha="center",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    out = figures_dir / "flow_regime_direct_shap_q99_top_features.png"
    fig.savefig(out, dpi=220)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    return out


def plot_flow_regime_feature_heatmap(flow_seed_mean: pd.DataFrame, figures_dir: Path, top_n: int) -> Path:
    q99 = flow_seed_mean[flow_seed_mean["quantile"].eq("q99")]
    feature_order = (
        q99.groupby(["feature", "feature_label_ko"], as_index=False)["mean_abs_shap_mean"]
        .mean()
        .sort_values("mean_abs_shap_mean", ascending=False)
        .head(top_n)
    )
    selected = feature_order["feature"].tolist()
    labels = feature_order["feature_label_ko"].tolist()
    stratum_order = ["low", "mid", "high", "extreme_q99"]
    stratum_labels = ["저유량", "중유량", "고유량", "극유량(Q99 이상)"]
    heat = (
        q99[q99["feature"].isin(selected)]
        .pivot_table(index="flow_stratum", columns="feature", values="mean_abs_shap_mean", aggfunc="mean")
        .reindex(stratum_order)[selected]
    )
    fig, ax = plt.subplots(figsize=(max(9, 0.9 * len(selected)), 4.8))
    im = ax.imshow(heat.values, aspect="auto", cmap="YlOrRd")
    ax.set_xticks(range(len(labels)), labels, rotation=35, ha="right")
    ax.set_yticks(range(len(stratum_labels)), stratum_labels)
    ax.set_title("유량 구간별 q99 출력 SHAP 강도")
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            ax.text(j, i, f"{heat.values[i, j]:.3f}", ha="center", va="center", fontsize=8)
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("평균 |SHAP|")
    fig.tight_layout()
    out = figures_dir / "flow_regime_direct_shap_q99_feature_heatmap.png"
    fig.savefig(out, dpi=220)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    return out


def main() -> int:
    args = parse_args()
    configure_plot_fonts()
    input_dir = args.input_dir.resolve()
    tables_dir = input_dir / "tables"
    figures_dir = input_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    global_df = read_seed_tables(input_dir, "global_feature_importance")
    temporal_df = read_seed_tables(input_dir, "temporal_lag")
    event_df = read_seed_tables(input_dir, "event_feature_importance")

    global_seed_mean = aggregate_global(global_df)
    temporal_seed_mean = aggregate_temporal(temporal_df)
    ladder_shift = build_ladder_shift(global_seed_mean)

    global_path = tables_dir / "quantile_lstm_direct_shap_global_feature_importance_seed_mean.csv"
    temporal_path = tables_dir / "quantile_lstm_direct_shap_temporal_lag_seed_mean.csv"
    ladder_path = tables_dir / "quantile_lstm_direct_shap_q99_minus_q50_ladder_shift.csv"
    global_seed_mean.to_csv(global_path, index=False)
    temporal_seed_mean.to_csv(temporal_path, index=False)
    ladder_shift.to_csv(ladder_path, index=False)

    figure_paths = [
        plot_seed_mean_top_features(global_seed_mean, figures_dir, args.top_n),
        plot_ladder_shift(ladder_shift, figures_dir, args.top_n),
        plot_temporal_lag(temporal_seed_mean, global_seed_mean, figures_dir),
        plot_event_quantile_heatmap(event_df, figures_dir, args.top_n),
    ]

    extra_table_paths: list[Path] = []
    if {"flow_stratum", "flow_stratum_ko"}.issubset(event_df.columns):
        flow_seed_mean = aggregate_flow_regime(event_df)
        flow_path = tables_dir / "flow_regime_direct_shap_feature_importance_seed_mean.csv"
        flow_seed_mean.to_csv(flow_path, index=False)
        extra_table_paths.append(flow_path)
        figure_paths.extend(
            [
                plot_flow_regime_q99_top_features(flow_seed_mean, figures_dir, args.top_n),
                plot_flow_regime_feature_heatmap(flow_seed_mean, figures_dir, args.top_n),
            ]
        )

    print("Wrote aggregate tables:")
    for path in [global_path, temporal_path, ladder_path, *extra_table_paths]:
        print(f"  - {path.relative_to(REPO_ROOT)}")
    print("Wrote aggregate figures:")
    for path in figure_paths:
        print(f"  - {path.relative_to(REPO_ROOT)}")
        print(f"  - {path.with_suffix('.pdf').relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

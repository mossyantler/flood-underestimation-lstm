#!/usr/bin/env python3
# /// script
# dependencies = [
#   "matplotlib>=3.9",
# ]
# ///

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patheffects
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


DEFAULT_OUTPUT_DIR = Path("output/model_analysis/overall_analysis/main_comparison/figures/model_architecture")

COLORS = {
    "background": "#fbfbf8",
    "ink": "#232323",
    "muted": "#60615d",
    "line": "#8a8c86",
    "common_fill": "#dbe7ef",
    "common_edge": "#617989",
    "input_fill": "#f2f4f1",
    "input_edge": "#a7aaa1",
    "model1_fill": "#dceee8",
    "model1_edge": "#6f9b8c",
    "model2_fill": "#f1e2bd",
    "model2_edge": "#a98945",
    "output_fill": "#ffffff",
    "loss_fill": "#f7f5ed",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Draw a presentation-ready Model 1 / Model 2 architecture comparison diagram."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["png", "svg", "pdf"],
        choices=["png", "svg", "pdf"],
        help="Figure formats to write.",
    )
    return parser.parse_args()


def add_box(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    *,
    facecolor: str,
    edgecolor: str,
    fontsize: float = 12.0,
    linewidth: float = 1.45,
    radius: float = 0.12,
    align: str = "center",
    zorder: int = 3,
) -> FancyBboxPatch:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.018,rounding_size={radius}",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        zorder=zorder,
    )
    patch.set_path_effects(
        [
            patheffects.SimplePatchShadow(offset=(1.3, -1.3), alpha=0.13, rho=0.96),
            patheffects.Normal(),
        ]
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha=align,
        va="center",
        fontsize=fontsize,
        color=COLORS["ink"],
        linespacing=1.28,
        wrap=False,
        clip_on=True,
        zorder=zorder + 1,
    )
    return patch


def arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = COLORS["line"],
    linewidth: float = 1.35,
    rad: float = 0.0,
    zorder: int = 2,
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=13,
            linewidth=linewidth,
            color=color,
            shrinkA=4,
            shrinkB=4,
            connectionstyle=f"arc3,rad={rad}",
            zorder=zorder,
        )
    )


def add_lane_label(ax: plt.Axes, x: float, y: float, text: str, color: str) -> None:
    ax.text(
        x,
        y,
        text,
        ha="left",
        va="center",
        fontsize=11.5,
        color=color,
        fontweight="bold",
    )


def draw_diagram(output_base: Path, formats: list[str], dpi: int) -> list[Path]:
    fig, ax = plt.subplots(figsize=(15.8, 8.9))
    fig.patch.set_facecolor(COLORS["background"])
    ax.set_facecolor(COLORS["background"])
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")

    ax.text(
        8,
        8.55,
        "Model 1 vs. Model 2 Architecture",
        ha="center",
        va="center",
        fontsize=22,
        color=COLORS["ink"],
        fontweight="bold",
    )
    ax.text(
        8,
        8.12,
        "Same split, same inputs, same multi-basin LSTM backbone. Only the output head and objective change.",
        ha="center",
        va="center",
        fontsize=12.6,
        color=COLORS["muted"],
    )

    dynamic = add_box(
        ax,
        0.55,
        5.35,
        2.75,
        1.28,
        "Hourly dynamic\nforcings\n$X_{b,t}$\nRainf, Tair, PET,\nradiation, ...",
        facecolor=COLORS["input_fill"],
        edgecolor=COLORS["input_edge"],
        fontsize=9.6,
    )
    static = add_box(
        ax,
        0.55,
        3.10,
        2.75,
        1.28,
        "Static basin\nattributes\n$s_b$\narea, slope, aridity,\nsnow, soil, ...",
        facecolor=COLORS["input_fill"],
        edgecolor=COLORS["input_edge"],
        fontsize=9.6,
    )
    merged = add_box(
        ax,
        4.02,
        4.22,
        2.65,
        1.32,
        "Per-basin\nsequence input\n$z_{b,t}=[X_{b,t},\\,s_b]$\n336 h lookback\n→ 24 h forecast",
        facecolor=COLORS["common_fill"],
        edgecolor=COLORS["common_edge"],
        fontsize=9.6,
    )
    backbone = add_box(
        ax,
        7.20,
        4.05,
        2.85,
        1.66,
        "Shared multi-basin\nLSTM backbone\n$h_{b,t}=\\mathrm{LSTM}(z_{b,t},h_{b,t-1})$\nhidden size 128",
        facecolor=COLORS["common_fill"],
        edgecolor=COLORS["common_edge"],
        fontsize=9.8,
        linewidth=1.7,
    )

    model1_head = add_box(
        ax,
        10.92,
        5.77,
        2.10,
        1.04,
        "Model 1 head\nregression",
        facecolor=COLORS["model1_fill"],
        edgecolor=COLORS["model1_edge"],
        fontsize=11.8,
    )
    model1_out = add_box(
        ax,
        13.58,
        5.77,
        1.72,
        1.04,
        "Point\nestimate\n$\\hat{Q}_{b,t}$",
        facecolor=COLORS["output_fill"],
        edgecolor=COLORS["model1_edge"],
        fontsize=10.8,
    )
    model1_loss = add_box(
        ax,
        13.42,
        4.42,
        2.05,
        0.94,
        "Training objective\nNSE loss",
        facecolor=COLORS["loss_fill"],
        edgecolor=COLORS["model1_edge"],
        fontsize=10.4,
        linewidth=1.2,
    )

    model2_head = add_box(
        ax,
        10.92,
        2.38,
        2.10,
        1.04,
        "Model 2 head\nquantile",
        facecolor=COLORS["model2_fill"],
        edgecolor=COLORS["model2_edge"],
        fontsize=11.8,
    )
    model2_out = add_box(
        ax,
        13.17,
        2.18,
        2.55,
        1.44,
        "Tail-aware outputs\n$\\hat{Q}_{0.50,b,t}$\n$\\hat{Q}_{0.90,b,t}$\n$\\hat{Q}_{0.95,b,t}$   $\\hat{Q}_{0.99,b,t}$",
        facecolor=COLORS["output_fill"],
        edgecolor=COLORS["model2_edge"],
        fontsize=9.8,
    )
    model2_loss = add_box(
        ax,
        13.42,
        0.94,
        2.05,
        0.94,
        "Training objective\npinball loss",
        facecolor=COLORS["loss_fill"],
        edgecolor=COLORS["model2_edge"],
        fontsize=10.4,
        linewidth=1.2,
    )

    arrow(ax, (dynamic.get_x() + dynamic.get_width(), dynamic.get_y() + dynamic.get_height() / 2), (merged.get_x(), merged.get_y() + merged.get_height() * 0.68))
    arrow(ax, (static.get_x() + static.get_width(), static.get_y() + static.get_height() / 2), (merged.get_x(), merged.get_y() + merged.get_height() * 0.32))
    arrow(ax, (merged.get_x() + merged.get_width(), merged.get_y() + merged.get_height() / 2), (backbone.get_x(), backbone.get_y() + backbone.get_height() / 2))
    arrow(ax, (backbone.get_x() + backbone.get_width(), backbone.get_y() + backbone.get_height() * 0.68), (model1_head.get_x(), model1_head.get_y() + model1_head.get_height() / 2), rad=0.08)
    arrow(ax, (backbone.get_x() + backbone.get_width(), backbone.get_y() + backbone.get_height() * 0.32), (model2_head.get_x(), model2_head.get_y() + model2_head.get_height() / 2), rad=-0.08)
    arrow(ax, (model1_head.get_x() + model1_head.get_width(), model1_head.get_y() + model1_head.get_height() / 2), (model1_out.get_x(), model1_out.get_y() + model1_out.get_height() / 2), color=COLORS["model1_edge"])
    arrow(ax, (model2_head.get_x() + model2_head.get_width(), model2_head.get_y() + model2_head.get_height() / 2), (model2_out.get_x(), model2_out.get_y() + model2_out.get_height() / 2), color=COLORS["model2_edge"])
    arrow(ax, (model1_out.get_x() + model1_out.get_width() / 2, model1_out.get_y()), (model1_loss.get_x() + model1_loss.get_width() / 2, model1_loss.get_y() + model1_loss.get_height()), color=COLORS["model1_edge"], linewidth=1.15)
    arrow(ax, (model2_out.get_x() + model2_out.get_width() / 2, model2_out.get_y()), (model2_loss.get_x() + model2_loss.get_width() / 2, model2_loss.get_y() + model2_loss.get_height()), color=COLORS["model2_edge"], linewidth=1.15)

    add_lane_label(ax, 10.92, 7.18, "Deterministic baseline", COLORS["model1_edge"])
    add_lane_label(ax, 10.92, 3.80, "Probabilistic extension", COLORS["model2_edge"])

    ax.text(
        8,
        0.45,
        "Interpretation: the experiment isolates output design, so any tail-behavior difference is evaluated against the same learned representation $h_{b,t}$.",
        ha="center",
        va="center",
        fontsize=11.7,
        color=COLORS["muted"],
    )

    output_base.parent.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for fmt in formats:
        path = output_base.with_suffix(f".{fmt}")
        save_kwargs: dict[str, Any] = {
            "bbox_inches": "tight",
            "pad_inches": 0.12,
            "facecolor": COLORS["background"],
            "dpi": dpi,
        }
        fig.savefig(path, **save_kwargs)
        written.append(path)
    plt.close(fig)
    return written


def write_manifest(output_dir: Path, written: list[Path], args: argparse.Namespace) -> None:
    manifest = {
        "description": "Presentation-ready architecture diagram for Model 1 deterministic LSTM vs Model 2 quantile LSTM.",
        "figure_paths": [str(path) for path in written],
        "model_1": {
            "backbone": "cudalstm",
            "head": "regression",
            "loss": "nse",
            "output": "point streamflow estimate",
        },
        "model_2": {
            "backbone": "cudalstm",
            "head": "quantile",
            "loss": "pinball",
            "quantiles": [0.5, 0.9, 0.95, 0.99],
        },
        "math_rendering": "matplotlib mathtext",
        "source_script": "scripts/model/overall/plot_model12_architecture_diagram.py",
    }
    metadata_dir = output_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "model12_architecture_diagram_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    output_base = args.output_dir / "model12_architecture_comparison"
    written = draw_diagram(output_base, args.formats, args.dpi)
    write_manifest(args.output_dir, written, args)
    for path in written:
        print(f"Wrote figure: {path}")
    print(f"Wrote manifest: {args.output_dir / 'metadata' / 'model12_architecture_diagram_manifest.json'}")


if __name__ == "__main__":
    main()

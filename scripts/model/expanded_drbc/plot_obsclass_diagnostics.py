#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
#   "numpy>=2.0",
#   "pyarrow>=15",
#   "matplotlib>=3.9",
# ]
# ///
"""Generate 4 diagnostic figures for obs_class classifier.

Outputs (signal_sweep/figures/):
  obsclass_confusion_binary.png   – binary confusion matrix heatmap
  obsclass_confusion_ordinal.png  – ordinal 5-class confusion matrix
  obsclass_feature_importance.png – RF feature importance bar chart
  obsclass_leakage_gap.png        – basin vs event accuracy per fold
"""

import pathlib

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TABLES = pathlib.Path("output/model_analysis/band_signal/signal_sweep/tables")
FIGURES = pathlib.Path("output/model_analysis/band_signal/signal_sweep/figures")

plt.rcParams.update({"font.size": 11, "axes.titlesize": 12})


def plot_confusion_binary():
    cm = pd.read_csv(TABLES / "obsclass_confusion_binary.csv", index_col=0)
    arr = cm.values
    total = arr.sum()

    fig, ax = plt.subplots(figsize=(4.5, 3.8))
    im = ax.imshow(arr, cmap="Blues")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Other (oc 0–3)", "Above q99 (oc 4)"])
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Other (oc 0–3)", "Above q99 (oc 4)"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Confusion Matrix: Binary Classifier\n(Basin GroupKFold, allrain)")

    for i in range(2):
        for j in range(2):
            val = arr[i, j]
            color = "white" if val > total * 0.25 else "black"
            ax.text(j, i, f"{val:,}", ha="center", va="center", color=color, fontsize=11)

    fig.tight_layout()
    out = FIGURES / "obsclass_confusion_binary.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  → {out}")


def plot_confusion_ordinal():
    cm = pd.read_csv(TABLES / "obsclass_confusion_ordinal.csv", index_col=0)
    arr = cm.values
    vmax = arr.max()
    labels = [f"oc {i}" for i in range(5)]

    fig, ax = plt.subplots(figsize=(5.5, 4.8))
    im = ax.imshow(arr, cmap="Blues")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_xticks(range(5))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticks(range(5))
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Confusion Matrix: Ordinal 5-Class\n(Basin GroupKFold, allrain)")

    for i in range(5):
        for j in range(5):
            val = arr[i, j]
            color = "white" if vmax > 0 and val > vmax * 0.5 else "black"
            ax.text(j, i, f"{val:,}", ha="center", va="center", color=color, fontsize=9)

    fig.tight_layout()
    out = FIGURES / "obsclass_confusion_ordinal.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  → {out}")


def plot_feature_importance():
    df = pd.read_csv(TABLES / "obsclass_feature_importance.csv")
    df = df.sort_values("importance_mean", ascending=True)

    colors = ["#1a5276" if f == "area" else "#2e86c1" for f in df["feature"]]
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    bars = ax.barh(
        df["feature"], df["importance_mean"],
        xerr=df["importance_std"], color=colors, capsize=3,
        ecolor="gray", error_kw={"linewidth": 1},
    )
    ax.set_xlabel("Mean Decrease in Impurity")
    ax.set_title("Feature Importance: RF Binary Classifier\n(Basin GroupKFold, allrain, S1 features)")

    x_max = (df["importance_mean"] + df["importance_std"]).max()
    ax.set_xlim(0, x_max * 1.3)
    for bar, val in zip(bars, df["importance_mean"]):
        ax.text(
            bar.get_width() + df["importance_std"].max() * 0.15,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.3f}", va="center", fontsize=9,
        )

    fig.tight_layout()
    out = FIGURES / "obsclass_feature_importance.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  → {out}")


def plot_leakage_gap():
    df = pd.read_csv(TABLES / "obsclass_cv_metrics.csv")
    basin = df[df["split"] == "basin_groupkfold"]["accuracy"].values
    event = df[df["split"] == "event_level_upper_bound"]["accuracy"].values
    folds = np.arange(1, len(basin) + 1)

    basin_mean = basin.mean()
    event_mean = event.mean()
    gap = event_mean - basin_mean

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(folds, basin, "o-", color="#1a5276", linewidth=2,
            label=f"Basin GroupKFold (mean={basin_mean:.3f})")
    ax.plot(folds, event, "s--", color="#c0392b", linewidth=2,
            label=f"Event StratifiedKFold (mean={event_mean:.3f})")
    ax.fill_between(
        [folds[0], folds[-1]],
        basin_mean, event_mean,
        alpha=0.12, color="#c0392b",
        label=f"Leakage gap: +{gap:.3f}",
    )
    ax.axhline(basin_mean, color="#1a5276", linestyle=":", linewidth=1, alpha=0.6)
    ax.axhline(event_mean, color="#c0392b", linestyle=":", linewidth=1, alpha=0.6)
    ax.set_xlabel("Fold")
    ax.set_ylabel("Accuracy")
    ax.set_title("Static-Attribute Leakage: Basin vs Event Split\n(Binary Classifier, allrain)")
    ax.legend(loc="lower right", fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.set_xticks(folds.tolist())

    fig.tight_layout()
    out = FIGURES / "obsclass_leakage_gap.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  → {out}")


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    print("Generating 4 figures...")
    plot_confusion_binary()
    plot_confusion_ordinal()
    plot_feature_importance()
    plot_leakage_gap()
    print("Done.")


if __name__ == "__main__":
    main()

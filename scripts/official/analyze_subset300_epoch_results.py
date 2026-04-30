#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import MultipleLocator


RUN_RE = re.compile(r"camelsh_hourly_(model[12])_drbc_holdout_subset300_seed(\d+)_")
METRIC_FILE_RE = re.compile(
    r"(?:^|/)(validation|test)/model_epoch(\d{3})/(?:validation|test)_metrics\.csv$"
)
TRAIN_LOSS_RE = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2} [\d:,]+): Epoch (?P<epoch>\d+) average loss: "
    r"avg_loss: (?P<avg_loss>[-+0-9.eE]+|nan), avg_total_loss: (?P<avg_total_loss>[-+0-9.eE]+|nan)"
)
VAL_LOG_RE = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2} [\d:,]+): Epoch (?P<epoch>\d+) average validation loss: "
    r"(?P<validation_loss>[-+0-9.eE]+|nan) -- Median validation metrics: "
    r"avg_loss: (?P<avg_loss>[-+0-9.eE]+|nan), NSE: (?P<NSE>[-+0-9.eE]+|nan), "
    r"KGE: (?P<KGE>[-+0-9.eE]+|nan), FHV: (?P<FHV>[-+0-9.eE]+|nan), "
    r"Peak-Timing: (?P<Peak_Timing>[-+0-9.eE]+|nan), Peak-MAPE: (?P<Peak_MAPE>[-+0-9.eE]+|nan)"
)

METRICS = ["NSE", "KGE", "FHV", "Peak-Timing", "Peak-MAPE"]
SUMMARY_PLOT_METRICS = [
    ("median_NSE", "Median NSE"),
    ("median_KGE", "Median KGE"),
    ("median_FHV", "Median FHV"),
    ("median_abs_FHV", "Median |FHV|"),
    ("median_Peak_Timing", "Median Peak Timing"),
    ("median_Peak_MAPE", "Median Peak MAPE"),
]
PRIMARY_EPOCHS = {
    ("model1", 111): 25,
    ("model1", 222): 10,
    ("model1", 444): 15,
    ("model2", 111): 5,
    ("model2", 222): 10,
    ("model2", 444): 10,
}
OFFICIAL_SEEDS = tuple(sorted({seed for _, seed in PRIMARY_EPOCHS}))
MODEL_LABELS = {"model1": "Model 1", "model2": "Model 2"}
MODEL_COLORS = {"model1": "#1f77b4", "model2": "#d62728"}
SEED_MARKERS = {111: "o", 222: "s", 444: "^"}


def _set_epoch_tick_interval(ax: plt.Axes) -> None:
    """Use the validation checkpoint cadence without changing the x-axis span."""
    ax.xaxis.set_major_locator(MultipleLocator(5))


@dataclass(frozen=True)
class MetricCandidate:
    model: str
    seed: int
    run_name: str
    split: str
    epoch: int
    path: Path
    source: str
    priority: int
    excluded_reason: str


def _as_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return math.nan


def _run_dirs(run_root: Path) -> list[Path]:
    return sorted(
        path for path in run_root.iterdir() if path.is_dir() and RUN_RE.match(path.name)
    )


def _metric_candidate_from_path(run_dir: Path, path: Path) -> MetricCandidate | None:
    match = RUN_RE.match(run_dir.name)
    if not match:
        return None

    rel = path.relative_to(run_dir)
    rel_posix = rel.as_posix()
    metric_match = METRIC_FILE_RE.search(rel_posix)
    if not metric_match:
        return None

    parts = rel.parts
    excluded_reason = ""
    if "_resume_archive" in parts:
        excluded_reason = "resume archive duplicate"
    elif any("failed_nan" in part for part in parts):
        excluded_reason = "failed NaN continuation"
    elif any("interrupted" in part for part in parts):
        excluded_reason = "interrupted continuation"

    split = metric_match.group(1)
    epoch = int(metric_match.group(2))
    source = "top_level" if parts[0] == split else parts[0]
    priority = 0 if source == "top_level" else 1
    if excluded_reason:
        priority = 99

    return MetricCandidate(
        model=match.group(1),
        seed=int(match.group(2)),
        run_name=run_dir.name,
        split=split,
        epoch=epoch,
        path=path,
        source=source,
        priority=priority,
        excluded_reason=excluded_reason,
    )


def _discover_metric_files(run_root: Path) -> tuple[pd.DataFrame, list[MetricCandidate]]:
    candidates: list[MetricCandidate] = []
    for run_dir in _run_dirs(run_root):
        for path in sorted(run_dir.rglob("*_metrics.csv")):
            candidate = _metric_candidate_from_path(run_dir, path)
            if candidate is not None:
                candidates.append(candidate)

    candidates = [candidate for candidate in candidates if candidate.seed in OFFICIAL_SEEDS]

    selected_by_key: dict[tuple[str, int, str, int], MetricCandidate] = {}
    for candidate in candidates:
        if candidate.excluded_reason:
            continue
        key = (candidate.model, candidate.seed, candidate.split, candidate.epoch)
        current = selected_by_key.get(key)
        if current is None or (candidate.priority, len(candidate.path.parts)) < (
            current.priority,
            len(current.path.parts),
        ):
            selected_by_key[key] = candidate

    selected_paths = {candidate.path for candidate in selected_by_key.values()}
    manifest_rows = []
    for candidate in candidates:
        key = (candidate.model, candidate.seed, candidate.split, candidate.epoch)
        duplicate_reason = ""
        if not candidate.excluded_reason and candidate.path not in selected_paths:
            duplicate_reason = f"duplicate; selected {selected_by_key[key].path}"
        manifest_rows.append(
            {
                "model": candidate.model,
                "seed": candidate.seed,
                "run_name": candidate.run_name,
                "split": candidate.split,
                "epoch": candidate.epoch,
                "source": candidate.source,
                "selected": candidate.path in selected_paths,
                "excluded_reason": candidate.excluded_reason or duplicate_reason,
                "path": str(candidate.path),
            }
        )

    manifest = pd.DataFrame(manifest_rows).sort_values(
        ["model", "seed", "split", "epoch", "selected", "path"],
        ascending=[True, True, True, True, False, True],
    )
    selected = sorted(
        selected_by_key.values(), key=lambda item: (item.model, item.seed, item.split, item.epoch)
    )
    return manifest, selected


def _read_metric_rows(candidates: list[MetricCandidate]) -> pd.DataFrame:
    frames = []
    for candidate in candidates:
        df = pd.read_csv(candidate.path, dtype={"basin": str})
        df["basin"] = df["basin"].astype(str).str.zfill(8)
        for metric in METRICS:
            df[metric] = pd.to_numeric(df[metric], errors="coerce")
        df.insert(0, "model", candidate.model)
        df.insert(1, "seed", candidate.seed)
        df.insert(2, "split", candidate.split)
        df.insert(3, "epoch", candidate.epoch)
        df.insert(4, "run_name", candidate.run_name)
        df.insert(5, "source", candidate.source)
        df.insert(6, "metric_path", str(candidate.path))
        frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _q25(values: pd.Series) -> float:
    return float(values.quantile(0.25))


def _q75(values: pd.Series) -> float:
    return float(values.quantile(0.75))


def _summarize_metrics(metric_rows: pd.DataFrame) -> pd.DataFrame:
    if metric_rows.empty:
        return pd.DataFrame()

    group_cols = ["model", "seed", "split", "epoch", "run_name", "source"]
    rows = []
    for keys, group in metric_rows.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, keys, strict=True))
        row["model_label"] = MODEL_LABELS.get(row["model"], row["model"])
        row["n_basins"] = int(group["basin"].nunique())
        row["negative_nse_basins"] = int((group["NSE"] < 0).sum())
        for metric in METRICS:
            out_name = metric.replace("-", "_")
            values = group[metric].dropna()
            row[f"mean_{out_name}"] = float(values.mean()) if not values.empty else math.nan
            row[f"median_{out_name}"] = float(values.median()) if not values.empty else math.nan
            row[f"std_{out_name}"] = float(values.std(ddof=1)) if len(values) > 1 else math.nan
            row[f"q25_{out_name}"] = _q25(values) if not values.empty else math.nan
            row[f"q75_{out_name}"] = _q75(values) if not values.empty else math.nan
        fhv_abs = group["FHV"].abs().dropna()
        row["mean_abs_FHV"] = float(fhv_abs.mean()) if not fhv_abs.empty else math.nan
        row["median_abs_FHV"] = float(fhv_abs.median()) if not fhv_abs.empty else math.nan
        rows.append(row)

    return pd.DataFrame(rows).sort_values(["split", "model", "seed", "epoch"])


def _log_paths_for_run(run_dir: Path) -> list[Path]:
    paths = []
    top_level = run_dir / "output.log"
    if top_level.exists():
        paths.append(top_level)
    for path in sorted(run_dir.glob("continue_training_from_epoch*/output.log")):
        rel = path.relative_to(run_dir).as_posix()
        if "failed_nan" in rel or "interrupted" in rel:
            continue
        paths.append(path)
    return paths


def _parse_logs(run_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_rows = []
    val_rows = []
    for run_dir in _run_dirs(run_root):
        match = RUN_RE.match(run_dir.name)
        if not match:
            continue
        model = match.group(1)
        seed = int(match.group(2))
        if seed not in OFFICIAL_SEEDS:
            continue
        for log_path in _log_paths_for_run(run_dir):
            source = "top_level" if log_path.parent == run_dir else log_path.parent.name
            text = log_path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                train_match = TRAIN_LOSS_RE.search(line)
                if train_match:
                    train_rows.append(
                        {
                            "model": model,
                            "seed": seed,
                            "run_name": run_dir.name,
                            "source": source,
                            "epoch": int(train_match.group("epoch")),
                            "timestamp": train_match.group("timestamp"),
                            "avg_loss": _as_float(train_match.group("avg_loss")),
                            "avg_total_loss": _as_float(train_match.group("avg_total_loss")),
                            "log_path": str(log_path),
                        }
                    )
                val_match = VAL_LOG_RE.search(line)
                if val_match:
                    val_rows.append(
                        {
                            "model": model,
                            "seed": seed,
                            "run_name": run_dir.name,
                            "source": source,
                            "epoch": int(val_match.group("epoch")),
                            "timestamp": val_match.group("timestamp"),
                            "validation_loss": _as_float(val_match.group("validation_loss")),
                            "avg_loss": _as_float(val_match.group("avg_loss")),
                            "NSE": _as_float(val_match.group("NSE")),
                            "KGE": _as_float(val_match.group("KGE")),
                            "FHV": _as_float(val_match.group("FHV")),
                            "Peak_Timing": _as_float(val_match.group("Peak_Timing")),
                            "Peak_MAPE": _as_float(val_match.group("Peak_MAPE")),
                            "log_path": str(log_path),
                        }
                    )

    train_df = pd.DataFrame(train_rows)
    if not train_df.empty:
        train_df = (
            train_df.sort_values(["model", "seed", "epoch", "timestamp", "log_path"])
            .drop_duplicates(["model", "seed", "epoch"], keep="last")
            .sort_values(["model", "seed", "epoch"])
        )

    val_df = pd.DataFrame(val_rows)
    if not val_df.empty:
        val_df = (
            val_df.sort_values(["model", "seed", "epoch", "timestamp", "log_path"])
            .drop_duplicates(["model", "seed", "epoch"], keep="last")
            .sort_values(["model", "seed", "epoch"])
        )

    return train_df, val_df


def _line_style(seed: int) -> dict[str, object]:
    return {
        "marker": SEED_MARKERS.get(seed, "o"),
        "markersize": 4,
        "linewidth": 1.5,
        "alpha": 0.88,
        "linestyle": "-",
    }


def _save_epoch_summary_plot(summary: pd.DataFrame, split: str, output_path: Path) -> None:
    data = summary[summary["split"] == split].copy()
    if data.empty:
        return

    fig, axes = plt.subplots(2, 3, figsize=(14, 8), sharex=True)
    axes = axes.ravel()
    for ax, (column, title) in zip(axes, SUMMARY_PLOT_METRICS, strict=True):
        for (model, seed), group in data.groupby(["model", "seed"]):
            group = group.sort_values("epoch")
            label = f"{MODEL_LABELS.get(model, model)} seed {seed}"
            ax.plot(
                group["epoch"],
                group[column],
                color=MODEL_COLORS.get(model, "#333333"),
                label=label,
                **_line_style(int(seed)),
            )
        if column in {"median_FHV"}:
            ax.axhline(0, color="#777777", linewidth=0.8)
        ax.set_title(title)
        ax.set_xlabel("Epoch")
        ax.grid(True, color="#dddddd", linewidth=0.7, alpha=0.8)
        _set_epoch_tick_interval(ax)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False)
    fig.suptitle(f"{split.title()} median metrics by epoch")
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _save_training_loss_plot(train_logs: pd.DataFrame, output_path: Path) -> None:
    if train_logs.empty:
        return

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), sharex=True)
    for ax, model in zip(axes, ["model1", "model2"], strict=True):
        data = train_logs[train_logs["model"] == model]
        for seed, group in data.groupby("seed"):
            group = group.sort_values("epoch")
            ax.plot(
                group["epoch"],
                group["avg_loss"],
                color=MODEL_COLORS[model],
                label=f"seed {seed}",
                **_line_style(int(seed)),
            )
        ax.set_title(f"{MODEL_LABELS[model]} training loss")
        ax.set_xlabel("Epoch")
        ax.set_ylabel("avg_loss")
        ax.set_yscale("log")
        ax.grid(True, color="#dddddd", linewidth=0.7, alpha=0.8)
        _set_epoch_tick_interval(ax)
        ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _pair_same_epoch(metric_rows: pd.DataFrame, split: str = "test") -> pd.DataFrame:
    data = metric_rows[metric_rows["split"] == split]
    if data.empty:
        return pd.DataFrame()

    left = data[data["model"] == "model1"].copy()
    right = data[data["model"] == "model2"].copy()
    paired = left.merge(
        right,
        on=["seed", "split", "epoch", "basin"],
        suffixes=("_model1", "_model2"),
        how="inner",
    )
    if paired.empty:
        return paired

    paired["delta_NSE"] = paired["NSE_model2"] - paired["NSE_model1"]
    paired["delta_KGE"] = paired["KGE_model2"] - paired["KGE_model1"]
    paired["delta_FHV"] = paired["FHV_model2"] - paired["FHV_model1"]
    paired["abs_FHV_reduction"] = paired["FHV_model1"].abs() - paired["FHV_model2"].abs()
    paired["Peak_Timing_reduction"] = paired["Peak-Timing_model1"] - paired["Peak-Timing_model2"]
    paired["Peak_MAPE_reduction"] = paired["Peak-MAPE_model1"] - paired["Peak-MAPE_model2"]
    return paired


def _summarize_deltas(delta_rows: pd.DataFrame) -> pd.DataFrame:
    if delta_rows.empty:
        return pd.DataFrame()

    delta_cols = [
        "delta_NSE",
        "delta_KGE",
        "delta_FHV",
        "abs_FHV_reduction",
        "Peak_Timing_reduction",
        "Peak_MAPE_reduction",
    ]
    rows = []
    for (seed, split, epoch), group in delta_rows.groupby(["seed", "split", "epoch"]):
        row = {"seed": seed, "split": split, "epoch": epoch, "n_basins": group["basin"].nunique()}
        for col in delta_cols:
            values = group[col].dropna()
            row[f"mean_{col}"] = float(values.mean()) if not values.empty else math.nan
            row[f"median_{col}"] = float(values.median()) if not values.empty else math.nan
            row[f"q25_{col}"] = _q25(values) if not values.empty else math.nan
            row[f"q75_{col}"] = _q75(values) if not values.empty else math.nan
            row[f"improved_fraction_{col}"] = float((values > 0).mean()) if not values.empty else math.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["split", "seed", "epoch"])


def _save_delta_plot(delta_summary: pd.DataFrame, output_path: Path) -> None:
    if delta_summary.empty:
        return

    metrics = [
        ("median_delta_NSE", "Median delta NSE (M2 - M1)"),
        ("median_delta_KGE", "Median delta KGE (M2 - M1)"),
        ("median_delta_FHV", "Median signed FHV delta (M2 - M1)"),
        ("median_abs_FHV_reduction", "Median |FHV| reduction (|M1| - |M2|)"),
        ("median_Peak_Timing_reduction", "Median peak timing reduction (M1 err - M2 err)"),
        ("median_Peak_MAPE_reduction", "Median peak MAPE reduction (M1 err - M2 err)"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), sharex=True)
    axes = axes.ravel()
    for ax, (column, title) in zip(axes, metrics, strict=False):
        for seed, group in delta_summary.groupby("seed"):
            group = group.sort_values("epoch")
            ax.plot(group["epoch"], group[column], label=f"seed {seed}", **_line_style(int(seed)))
        ax.axhline(0, color="#777777", linewidth=0.8)
        ax.set_title(title)
        ax.set_xlabel("Epoch")
        ax.grid(True, color="#dddddd", linewidth=0.7, alpha=0.8)
        _set_epoch_tick_interval(ax)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False)
    fig.suptitle("Test paired same-epoch deltas and error reductions")
    fig.text(
        0.5,
        0.925,
        "NSE/KGE: M2 - M1. Signed FHV: M2 - M1, where above 0 means upward FHV shift. Error reductions: above 0 favors M2.",
        ha="center",
        va="center",
        fontsize=9.5,
        color="#374151",
    )
    fig.tight_layout(rect=[0, 0.08, 1, 0.91])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _primary_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model, seed), epoch in PRIMARY_EPOCHS.items():
        match = summary[
            (summary["split"] == "test")
            & (summary["model"] == model)
            & (summary["seed"] == seed)
            & (summary["epoch"] == epoch)
        ]
        if match.empty:
            rows.append(
                {
                    "model": model,
                    "model_label": MODEL_LABELS[model],
                    "seed": seed,
                    "split": "test",
                    "epoch": epoch,
                    "status": "missing test metrics",
                }
            )
        else:
            row = match.iloc[0].to_dict()
            row["status"] = "available"
            rows.append(row)
    return pd.DataFrame(rows)


def _primary_delta_rows(metric_rows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for seed in sorted({seed for _, seed in PRIMARY_EPOCHS}):
        m1_epoch = PRIMARY_EPOCHS.get(("model1", seed))
        m2_epoch = PRIMARY_EPOCHS.get(("model2", seed))
        if m1_epoch is None or m2_epoch is None:
            continue
        m1 = metric_rows[
            (metric_rows["split"] == "test")
            & (metric_rows["model"] == "model1")
            & (metric_rows["seed"] == seed)
            & (metric_rows["epoch"] == m1_epoch)
        ]
        m2 = metric_rows[
            (metric_rows["split"] == "test")
            & (metric_rows["model"] == "model2")
            & (metric_rows["seed"] == seed)
            & (metric_rows["epoch"] == m2_epoch)
        ]
        paired = m1.merge(m2, on=["seed", "basin"], suffixes=("_model1", "_model2"), how="inner")
        for _, row in paired.iterrows():
            rows.append(
                {
                    "seed": seed,
                    "basin": row["basin"],
                    "model1_epoch": m1_epoch,
                    "model2_epoch": m2_epoch,
                    "delta_NSE": row["NSE_model2"] - row["NSE_model1"],
                    "delta_KGE": row["KGE_model2"] - row["KGE_model1"],
                    "delta_FHV": row["FHV_model2"] - row["FHV_model1"],
                    "abs_FHV_reduction": abs(row["FHV_model1"]) - abs(row["FHV_model2"]),
                    "Peak_Timing_reduction": row["Peak-Timing_model1"] - row["Peak-Timing_model2"],
                    "Peak_MAPE_reduction": row["Peak-MAPE_model1"] - row["Peak-MAPE_model2"],
                }
            )
    return pd.DataFrame(rows)


def _save_primary_delta_boxplot(primary_deltas: pd.DataFrame, output_path: Path) -> None:
    if primary_deltas.empty:
        return

    cols = [
        ("delta_NSE", "Delta NSE"),
        ("delta_KGE", "Delta KGE"),
        ("abs_FHV_reduction", "|FHV| reduction"),
        ("Peak_Timing_reduction", "Peak timing reduction"),
        ("Peak_MAPE_reduction", "Peak MAPE reduction"),
    ]
    fig, axes = plt.subplots(1, len(cols), figsize=(15, 4.5))
    for ax, (col, title) in zip(axes, cols, strict=True):
        values = [
            primary_deltas.loc[primary_deltas["seed"] == seed, col].dropna().to_numpy()
            for seed in sorted(primary_deltas["seed"].unique())
        ]
        labels = [str(seed) for seed in sorted(primary_deltas["seed"].unique())]
        ax.boxplot(values, tick_labels=labels, showfliers=False)
        ax.axhline(0, color="#777777", linewidth=0.8)
        ax.set_title(title)
        ax.set_xlabel("Seed")
        ax.grid(True, axis="y", color="#dddddd", linewidth=0.7, alpha=0.8)
    fig.suptitle("Primary epoch basin-level deltas")
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _write_summary_markdown(
    output_path: Path,
    manifest: pd.DataFrame,
    summary: pd.DataFrame,
    primary: pd.DataFrame,
    delta_summary: pd.DataFrame,
) -> None:
    def table(df: pd.DataFrame, **kwargs: object) -> str:
        try:
            return df.to_markdown(index=False, **kwargs)
        except ImportError:
            return "```text\n" + df.to_string(index=False) + "\n```"

    selected = manifest[manifest["selected"]]
    selected_counts = (
        selected.groupby(["model", "seed", "split"])["epoch"]
        .apply(lambda values: ",".join(f"{int(value):03d}" for value in sorted(values)))
        .reset_index()
    )

    lines = [
        "# Subset300 Epoch Result Analysis",
        "",
        "This report was generated by `scripts/official/analyze_subset300_epoch_results.py`.",
        "",
        "## Selected metric files",
        "",
        table(selected_counts) if not selected_counts.empty else "No selected metric files.",
        "",
        "## Primary test epoch availability",
        "",
    ]

    primary_cols = [
        "model_label",
        "seed",
        "epoch",
        "status",
        "n_basins",
        "median_NSE",
        "median_KGE",
        "median_FHV",
        "median_abs_FHV",
        "median_Peak_Timing",
        "median_Peak_MAPE",
    ]
    for col in primary_cols:
        if col not in primary.columns:
            primary[col] = np.nan
    lines.append(table(primary[primary_cols], floatfmt=".4f"))
    lines.extend(["", "## Same-epoch test delta summary", ""])
    if delta_summary.empty:
        lines.append("No paired same-epoch test deltas were available.")
    else:
        cols = [
            "seed",
            "epoch",
            "n_basins",
            "median_delta_NSE",
            "median_delta_KGE",
            "median_abs_FHV_reduction",
            "median_Peak_Timing_reduction",
            "median_Peak_MAPE_reduction",
        ]
        lines.append(table(delta_summary[cols], floatfmt=".4f"))

    lines.extend(
        [
            "",
            "## Notes",
            "",
            f"- Official analysis outputs include only paired seeds: {', '.join(str(seed) for seed in OFFICIAL_SEEDS)}.",
            "- Validation/test basin metrics are available at validation/test evaluation epochs, not necessarily every trained epoch.",
            "- Training loss is parsed for every epoch that appears in `output.log` files.",
            "- Seed 333 is excluded from aggregate CSVs and charts because Model 2 hit NaN loss and Model 1 seed 333 is not part of the official paired-seed comparison.",
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze(run_root: Path, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    main_tables_dir = output_dir / "main_comparison" / "tables"
    main_figures_dir = output_dir / "main_comparison" / "figures"
    main_report_dir = output_dir / "main_comparison" / "report"
    sensitivity_tables_dir = output_dir / "epoch_sensitivity" / "tables"
    sensitivity_logs_dir = output_dir / "epoch_sensitivity" / "logs"
    sensitivity_figures_dir = output_dir / "epoch_sensitivity" / "figures"
    run_records_dir = output_dir / "run_records"
    for directory in [
        main_tables_dir,
        main_figures_dir,
        main_report_dir,
        sensitivity_tables_dir,
        sensitivity_logs_dir,
        sensitivity_figures_dir,
        run_records_dir,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    manifest, selected_candidates = _discover_metric_files(run_root)
    metric_rows = _read_metric_rows(selected_candidates)
    summary = _summarize_metrics(metric_rows)
    train_logs, val_logs = _parse_logs(run_root)
    same_epoch_deltas = _pair_same_epoch(metric_rows, split="test")
    same_epoch_delta_summary = _summarize_deltas(same_epoch_deltas)
    primary = _primary_summary(summary)
    primary_deltas = _primary_delta_rows(metric_rows)
    primary_delta_summary = _summarize_deltas(
        primary_deltas.assign(split="test", epoch=-1) if not primary_deltas.empty else primary_deltas
    )

    paths = {
        "manifest": run_records_dir / "metric_file_manifest.csv",
        "basin_metrics": sensitivity_tables_dir / "basin_metrics.csv",
        "epoch_metric_summary": sensitivity_tables_dir / "epoch_metric_summary.csv",
        "training_epoch_log": sensitivity_logs_dir / "training_epoch_log.csv",
        "validation_epoch_log": sensitivity_logs_dir / "validation_epoch_log.csv",
        "test_same_epoch_basin_deltas": sensitivity_tables_dir / "test_same_epoch_basin_deltas.csv",
        "test_same_epoch_delta_summary": sensitivity_tables_dir / "test_same_epoch_delta_summary.csv",
        "primary_epoch_summary": main_tables_dir / "primary_epoch_summary.csv",
        "primary_epoch_basin_deltas": main_tables_dir / "primary_epoch_basin_deltas.csv",
        "primary_epoch_delta_summary": main_tables_dir / "primary_epoch_delta_summary.csv",
        "analysis_summary": main_report_dir / "analysis_summary.md",
        "metadata": run_records_dir / "analysis_metadata.json",
    }

    manifest.to_csv(paths["manifest"], index=False)
    metric_rows.to_csv(paths["basin_metrics"], index=False)
    summary.to_csv(paths["epoch_metric_summary"], index=False)
    train_logs.to_csv(paths["training_epoch_log"], index=False)
    val_logs.to_csv(paths["validation_epoch_log"], index=False)
    same_epoch_deltas.to_csv(paths["test_same_epoch_basin_deltas"], index=False)
    same_epoch_delta_summary.to_csv(paths["test_same_epoch_delta_summary"], index=False)
    primary.to_csv(paths["primary_epoch_summary"], index=False)
    primary_deltas.to_csv(paths["primary_epoch_basin_deltas"], index=False)
    primary_delta_summary.to_csv(paths["primary_epoch_delta_summary"], index=False)

    _save_epoch_summary_plot(summary, "validation", sensitivity_figures_dir / "validation_epoch_median_metrics.png")
    _save_epoch_summary_plot(summary, "test", sensitivity_figures_dir / "test_epoch_median_metrics.png")
    _save_training_loss_plot(train_logs, sensitivity_figures_dir / "training_loss_by_epoch.png")
    _save_delta_plot(same_epoch_delta_summary, sensitivity_figures_dir / "test_same_epoch_delta_summary.png")
    _save_primary_delta_boxplot(primary_deltas, main_figures_dir / "primary_epoch_basin_deltas.png")
    _write_summary_markdown(
        paths["analysis_summary"], manifest, summary, primary, same_epoch_delta_summary
    )

    metadata = {
        "run_root": str(run_root),
        "output_dir": str(output_dir),
        "selected_metric_files": int(manifest["selected"].sum()) if not manifest.empty else 0,
        "candidate_metric_files": int(len(manifest)),
        "basin_metric_rows": int(len(metric_rows)),
        "epoch_summary_rows": int(len(summary)),
        "training_log_rows": int(len(train_logs)),
        "validation_log_rows": int(len(val_logs)),
        "same_epoch_delta_rows": int(len(same_epoch_deltas)),
        "primary_delta_rows": int(len(primary_deltas)),
        "figures": sorted(
            str(path)
            for directory in [main_figures_dir, sensitivity_figures_dir]
            for path in directory.glob("*.png")
        ),
        "layout": {
            "main_comparison": str(output_dir / "main_comparison"),
            "epoch_sensitivity": str(output_dir / "epoch_sensitivity"),
            "result_checks": str(output_dir / "result_checks"),
            "run_records": str(run_records_dir),
        },
        "primary_epochs": {f"{model}_seed{seed}": epoch for (model, seed), epoch in PRIMARY_EPOCHS.items()},
        "official_seeds": list(OFFICIAL_SEEDS),
        "excluded_seeds": [333],
    }
    paths["metadata"].write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    return {key: str(path) for key, path in paths.items()}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate subset300 Model 1/2 seed/epoch metrics and create diagnostic charts."
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path("runs/subset_comparison"),
        help="Directory containing subset300 NeuralHydrology run folders.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/model_analysis/overall_analysis"),
        help="Directory for aggregate CSVs, charts, and markdown summary.",
    )
    args = parser.parse_args()

    paths = analyze(args.run_root, args.output_dir)
    print("Wrote subset300 epoch analysis outputs:")
    for key, path in paths.items():
        print(f"- {key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

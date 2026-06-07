from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, to_rgb
from matplotlib.text import Text

from direct_shap_plot_common import (
    FORCE_NEGATIVE,
    FORCE_NEGATIVE_LIGHT,
    FORCE_POSITIVE,
    FORCE_POSITIVE_LIGHT,
    NEGATIVE,
    NEUTRAL,
    POSITIVE,
)


def legacy_signed_cmap() -> LinearSegmentedColormap:
    return LinearSegmentedColormap.from_list("legacy_signed_shap", [NEGATIVE, NEUTRAL, POSITIVE])


def force_color_from_rgb(red: float, green: float, blue: float, *, light: bool = False) -> str | None:
    if red > 0.85 and green < 0.25 and blue > 0.2:
        return FORCE_POSITIVE_LIGHT if light else FORCE_POSITIVE
    if blue > 0.65 and red < 0.35:
        return FORCE_NEGATIVE_LIGHT if light else FORCE_NEGATIVE
    if red > 0.95 and green > 0.65 and blue > 0.75 and red - green > 0.15:
        return FORCE_POSITIVE_LIGHT
    if red > 0.75 and green > 0.85 and blue > 0.9 and blue - red > 0.08:
        return FORCE_NEGATIVE_LIGHT
    return None


def recolor_force_artists(fig: plt.Figure) -> None:
    for ax in fig.axes:
        recolor_force_axis(ax)
    for artist in fig.findobj(Text):
        try:
            red, green, blue = to_rgb(artist.get_color())
        except ValueError:
            continue
        color = force_color_from_rgb(red, green, blue)
        if color is not None:
            artist.set_color(color)


def recolor_force_axis(ax: plt.Axes) -> None:
    for patch in ax.patches:
        face = patch.get_facecolor()
        if len(face) >= 4 and face[3] > 0:
            color = force_color_from_rgb(*face[:3])
            if color is not None:
                patch.set_facecolor(color)
        edge = patch.get_edgecolor()
        if len(edge) >= 4 and edge[3] > 0:
            color = force_color_from_rgb(*edge[:3], light=True)
            if color is not None:
                patch.set_edgecolor(color)
    for line in ax.lines:
        try:
            red, green, blue = to_rgb(line.get_color())
        except ValueError:
            continue
        color = force_color_from_rgb(red, green, blue)
        if color is not None:
            line.set_color(color)
    for image in ax.images:
        left, right, _bottom, _top = image.get_extent()
        base_color = FORCE_POSITIVE if right < left else FORCE_NEGATIVE
        image.set_cmap(LinearSegmentedColormap.from_list("force_shading", [base_color, "#ffffff"]))


def recolor_bar_patches(ax: plt.Axes, *, signed: bool) -> None:
    for patch in ax.patches:
        width = float(patch.get_width())
        if not signed:
            patch.set_facecolor(POSITIVE)
            patch.set_edgecolor(POSITIVE)
            continue
        color = POSITIVE if width > 0 else NEGATIVE if width < 0 else NEUTRAL
        patch.set_facecolor(color)
        patch.set_edgecolor(color)


def legacy_color_from_rgb(red: float, green: float, blue: float) -> str | None:
    if red > 0.85 and green < 0.25 and blue > 0.2:
        return POSITIVE
    if blue > 0.65 and red < 0.35:
        return NEGATIVE
    return None


def recolor_signed_artists(fig: plt.Figure) -> None:
    for ax in fig.axes:
        recolor_axis_patches(ax)
    for artist in fig.findobj(Text):
        try:
            red, green, blue = to_rgb(artist.get_color())
        except ValueError:
            continue
        color = legacy_color_from_rgb(red, green, blue)
        if color is not None:
            artist.set_color(color)


def recolor_axis_patches(ax: plt.Axes) -> None:
    for patch in ax.patches:
        face = patch.get_facecolor()
        if len(face) < 3:
            continue
        red, green, blue = face[:3]
        color = legacy_color_from_rgb(red, green, blue)
        if color is None:
            continue
        patch.set_facecolor(color)
        patch.set_edgecolor(color)


def apply_text_size(fig: plt.Figure, *, base: float = 9.0, emphasis: float = 10.0) -> None:
    for artist in fig.findobj(Text):
        artist.set_clip_on(False)
        label = artist.get_text()
        if label in {"higher", "lower", "High", "Low"}:
            artist.set_fontsize(emphasis)
        else:
            artist.set_fontsize(base)


def save_panel_composite(panel_paths: list[Path], out: Path, title: str, *, horizontal: bool = False) -> None:
    images = [mpimg.imread(path) for path in panel_paths]
    if horizontal:
        total_width = sum(image.shape[1] for image in images)
        max_height = max(image.shape[0] for image in images)
        fig_width = max(6.8, total_width / 180)
        fig_height = max(3.4, max_height / 180 + 0.45)
        fig, axes = plt.subplots(1, len(images), figsize=(fig_width, fig_height), squeeze=False)
    else:
        max_width = max(image.shape[1] for image in images)
        total_height = sum(image.shape[0] for image in images)
        fig_width = max(6.8, max_width / 180)
        fig_height = max(3.4, total_height / 180 + 0.45)
        fig, axes = plt.subplots(len(images), 1, figsize=(fig_width, fig_height), squeeze=False)
    fig.suptitle(title, fontsize=11, y=0.995)
    for ax, image in zip(axes.ravel(), images, strict=True):
        ax.imshow(image)
        ax.axis("off")
    fig.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=0.965, hspace=0.02, wspace=0.02)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)

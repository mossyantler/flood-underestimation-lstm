#!/usr/bin/env python3
# /// script
# dependencies = ["pandas>=2.2"]
# ///
"""Build an HTML gallery index for DRBC confirmed flood event hydrographs.

Reads: output/model_analysis/confirmed_flood/hydrographs/confirmed_flood_hydrograph_manifest.csv
Writes: output/model_analysis/confirmed_flood/hydrographs/event_plot_index.html
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = REPO_ROOT / "output/model_analysis/confirmed_flood/hydrographs/confirmed_flood_hydrograph_manifest.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/confirmed_flood/hydrographs"

TIER_ORDER = ["major", "moderate", "minor"]
TIER_LABELS = {"major": "Major Flood", "moderate": "Moderate Flood", "minor": "Minor Flood"}
TIER_COLORS = {"major": "#dc2626", "moderate": "#f97316", "minor": "#fbbf24"}
PERIOD_LABELS = {"pre_2000": "Pre-2000 (Historical)", "post_2013": "Post-2013 (Recent)"}
PERIOD_ORDER = ["major", "post_2013", "pre_2000"]

CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #18181b; }
h1 { font-size: 22px; margin: 0 0 8px; }
h2 { font-size: 20px; margin: 30px 0 6px; border-top: 1px solid #d4d4d8; padding-top: 18px; }
h2 span, h3 span { color: #71717a; font-weight: 500; }
h3 { font-size: 15px; margin: 18px 0 10px; }
.meta, .section-note { color: #52525b; margin: 0 0 18px; max-width: 980px; line-height: 1.45; }
table { border-collapse: collapse; margin: 14px 0 24px; font-size: 13px; }
th, td { border: 1px solid #d4d4d8; padding: 6px 8px; text-align: left; }
th { background: #f4f4f5; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.95em; }
.tier-badge { display: inline-block; border-radius: 4px; padding: 1px 7px; font-size: 12px; font-weight: 600; color: #fff; }
.tier-major { background: #dc2626; }
.tier-moderate { background: #f97316; }
.tier-minor { background: #ca8a04; color: #fff; }
.condition-details { border: 1px solid #d4d4d8; border-radius: 8px; margin: 14px 0; background: #fff; }
.condition-details summary { align-items: center; cursor: pointer; display: flex; gap: 12px; justify-content: space-between; list-style: none; padding: 10px 12px; }
.condition-details summary::-webkit-details-marker { display: none; }
.condition-details summary::before { color: #71717a; content: "+"; flex: 0 0 auto; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-weight: 700; }
.condition-details[open] > summary::before { content: "-"; }
.condition-details summary:hover { background: #f4f4f5; }
.condition-label { color: #18181b; flex: 1 1 auto; font-size: 14px; font-weight: 650; }
.condition-count { color: #71717a; font-size: 13px; white-space: nowrap; }
.condition-details .grid { padding: 12px; border-top: 1px solid #e4e4e7; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 18px; }
.card { border: 1px solid #d4d4d8; border-radius: 8px; padding: 10px; background: #fff; }
.card .image-link { cursor: zoom-in; display: block; }
.card img { width: 100%; height: auto; display: block; border: 1px solid #e4e4e7; }
.card h3 { font-size: 13px; margin: 10px 0 4px; }
.card p { font-size: 12px; margin: 3px 0; color: #52525b; }
.card .classline { color: #18181b; font-weight: 600; }
body.lightbox-open { overflow: hidden; }
.lightbox[hidden] { display: none; }
.lightbox { align-items: center; display: flex; inset: 0; justify-content: center; padding: 24px; position: fixed; z-index: 20; }
.lightbox-backdrop { background: rgba(24,24,27,0.74); inset: 0; position: absolute; }
.lightbox-panel { background: #fff; border-radius: 8px; box-shadow: 0 20px 60px rgba(0,0,0,0.35); max-height: calc(100vh - 48px); max-width: min(1200px, calc(100vw - 48px)); overflow: auto; padding: 14px; position: relative; width: 100%; }
.lightbox-close { background: #fff; border: 1px solid #d4d4d8; border-radius: 6px; color: #3f3f46; cursor: pointer; font-size: 12px; padding: 6px 9px; position: absolute; right: 14px; top: 14px; z-index: 1; }
.lightbox-close:hover, .lightbox-nav-button:hover { background: #f4f4f5; }
.lightbox-image-frame { align-items: center; background: #f4f4f5; border: 1px solid #e4e4e7; border-radius: 6px; display: flex; justify-content: center; min-height: 240px; padding: 10px; }
.lightbox-image-frame img { display: block; height: auto; max-height: min(70vh, 860px); max-width: 100%; object-fit: contain; }
.lightbox-copy { color: #52525b; display: grid; gap: 4px; font-size: 12px; line-height: 1.45; margin: 10px 0 12px; }
.lightbox-copy p { margin: 0; }
.lightbox-copy p:first-child { color: #18181b; font-weight: 650; }
.lightbox-nav { align-items: center; display: grid; gap: 12px; grid-template-columns: 48px minmax(0, 1fr) 48px; }
.lightbox-nav h3 { color: #3f3f46; font-size: 12px; font-weight: 600; line-height: 1.35; margin: 0; overflow-wrap: anywhere; text-align: center; }
.lightbox-nav-button { background: #fff; border: 1px solid #d4d4d8; border-radius: 6px; color: #18181b; cursor: pointer; font-size: 18px; height: 40px; line-height: 1; }
"""

JS = """
const allCards = [];
document.querySelectorAll('.card').forEach((card, idx) => {
  card.dataset.lbIdx = idx;
  allCards.push(card);
  card.querySelector('.image-link').addEventListener('click', (e) => {
    e.preventDefault();
    openLightbox(idx);
  });
});
const lb = document.getElementById('lightbox');
const lbImg = lb.querySelector('.lightbox-image-frame img');
const lbTitle = lb.querySelector('.lightbox-title');
const lbMeta = lb.querySelector('.lightbox-meta');
const lbNavTitle = lb.querySelector('.lightbox-nav h3');
let curIdx = 0;
function openLightbox(idx) {
  curIdx = idx;
  renderLightbox();
  lb.removeAttribute('hidden');
  document.body.classList.add('lightbox-open');
}
function closeLightbox() {
  lb.setAttribute('hidden', '');
  document.body.classList.remove('lightbox-open');
}
function renderLightbox() {
  const card = allCards[curIdx];
  const img = card.querySelector('img');
  lbImg.src = img.src;
  lbTitle.textContent = card.querySelector('h3')?.textContent ?? '';
  lbMeta.textContent = card.querySelector('p.classline')?.textContent ?? '';
  lbNavTitle.textContent = (curIdx + 1) + ' / ' + allCards.length;
}
lb.querySelector('.lightbox-backdrop').addEventListener('click', closeLightbox);
lb.querySelector('.lightbox-close').addEventListener('click', closeLightbox);
lb.querySelector('[data-action=prev]').addEventListener('click', () => { curIdx = (curIdx - 1 + allCards.length) % allCards.length; renderLightbox(); });
lb.querySelector('[data-action=next]').addEventListener('click', () => { curIdx = (curIdx + 1) % allCards.length; renderLightbox(); });
document.addEventListener('keydown', (e) => {
  if (lb.hasAttribute('hidden')) return;
  if (e.key === 'Escape') closeLightbox();
  if (e.key === 'ArrowLeft') { curIdx = (curIdx - 1 + allCards.length) % allCards.length; renderLightbox(); }
  if (e.key === 'ArrowRight') { curIdx = (curIdx + 1) % allCards.length; renderLightbox(); }
});
"""


def fix_path(plot_path: str) -> str:
    """Fix legacy paths to current expanded paths."""
    return plot_path.replace(
        "output/model_analysis/confirmed_flood/",
        "output/model_analysis/confirmed_flood/",
    )


def relative_img_path(plot_path: str, gallery_dir: Path) -> str:
    """Return path relative to gallery_dir for use in HTML <img src>."""
    abs_path = REPO_ROOT / plot_path
    try:
        return str(abs_path.relative_to(gallery_dir))
    except ValueError:
        return str(abs_path)


def card_html(row: pd.Series, gallery_dir: Path) -> str:
    plot_path = fix_path(str(row["plot_path"]))
    rel = relative_img_path(plot_path, gallery_dir)
    event_id = html_lib.escape(str(row["event_id"]))
    basin = html_lib.escape(str(row["basin"]))
    peak_time = html_lib.escape(str(row["peak_time"])[:16].replace("T", " "))
    tier = str(row["flood_tier"])
    period = PERIOD_LABELS.get(str(row.get("period", "")), str(row.get("period", "")))
    noaa = int(row.get("noaa_record_count", 0))
    noaa_note = f"{noaa} NOAA records" if noaa > 0 else "no NOAA records"

    tier_label = tier.capitalize()
    tier_cls = f"tier-{tier}"

    return f"""
    <div class="card">
      <a class="image-link" href="{rel}" target="_blank">
        <img src="{rel}" alt="{event_id}" loading="lazy">
      </a>
      <h3>{basin} — {peak_time}</h3>
      <p class="classline"><span class="tier-badge {tier_cls}">{tier_label}</span> &nbsp; {period}</p>
      <p>{noaa_note}</p>
    </div>"""


def build_summary_table(df: pd.DataFrame) -> str:
    rows = []
    for tier in TIER_ORDER:
        for period in ["pre_2000", "post_2013"]:
            n = len(df[(df["flood_tier"] == tier) & (df["period"] == period)])
            if n:
                rows.append(f"<tr><td>{TIER_LABELS.get(tier, tier)}</td><td>{PERIOD_LABELS.get(period, period)}</td><td>{n}</td></tr>")
    return "<table><thead><tr><th>Flood Tier</th><th>Period</th><th>Events</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def build_html(df: pd.DataFrame, gallery_dir: Path) -> str:
    total = len(df)
    n_basins = df["basin"].nunique()
    summary_table = build_summary_table(df)

    section_html = []
    for tier in TIER_ORDER:
        tier_df = df[df["flood_tier"] == tier]
        if tier_df.empty:
            continue
        tier_label = TIER_LABELS.get(tier, tier)
        tier_n = len(tier_df)
        section_html.append(f'<h2>{tier_label} <span>({tier_n} events)</span></h2>')
        for period in ["post_2013", "pre_2000"]:
            period_df = tier_df[tier_df["period"] == period].sort_values(["basin", "peak_time"])
            if period_df.empty:
                continue
            period_label = PERIOD_LABELS.get(period, period)
            period_n = len(period_df)
            cards = "".join(card_html(row, gallery_dir) for _, row in period_df.iterrows())
            section_html.append(f"""
    <details class="condition-details" open>
      <summary>
        <span class="condition-label">{period_label}</span>
        <span class="condition-count">{period_n} events</span>
      </summary>
      <div class="grid">{cards}</div>
    </details>""")

    sections = "\n".join(section_html)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>DRBC Confirmed Flood Event Hydrographs</title>
  <style>{CSS}</style>
</head>
<body>
  <h1>DRBC Confirmed Flood Event Hydrographs</h1>
  <p class="meta">{total} events across {n_basins} DRBC basins. NWS flood stage thresholds: minor / moderate / major. Each panel shows observed streamflow, Model 1 prediction, and Model 2 quantile bands (q50/q90/q95/q99). NOAA event records are marked where available.</p>
  {summary_table}
  {sections}
  <div class="lightbox" id="lightbox" hidden>
    <div class="lightbox-backdrop"></div>
    <div class="lightbox-panel">
      <button class="lightbox-close">✕ close</button>
      <div class="lightbox-image-frame"><img src="" alt=""></div>
      <div class="lightbox-copy">
        <p class="lightbox-title"></p>
        <p class="lightbox-meta"></p>
      </div>
      <div class="lightbox-nav">
        <button class="lightbox-nav-button" data-action="prev">‹</button>
        <h3></h3>
        <button class="lightbox-nav-button" data-action="next">›</button>
      </div>
    </div>
  </div>
  <script>{JS}</script>
</body>
</html>"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    df = pd.read_csv(args.manifest, dtype={"basin": str})
    df["basin"] = df["basin"].astype(str).str.zfill(8)
    df["flood_tier"] = pd.Categorical(df["flood_tier"], categories=TIER_ORDER, ordered=True)

    # Fix manifest paths
    df["plot_path"] = df["plot_path"].apply(fix_path)

    # Verify files exist
    missing = [p for p in df["plot_path"] if not (REPO_ROOT / p).exists()]
    if missing:
        print(f"Warning: {len(missing)} plot files not found, e.g.: {missing[0]}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    gallery_html = build_html(df, args.output_dir)
    out_path = args.output_dir / "event_plot_index.html"
    out_path.write_text(gallery_html, encoding="utf-8")
    print(f"Wrote: {out_path.relative_to(REPO_ROOT)} ({len(df)} events, {df['basin'].nunique()} basins)")

    # Also fix and rewrite manifest with corrected paths
    manifest_out = args.output_dir / "confirmed_flood_hydrograph_manifest.csv"
    df.to_csv(manifest_out, index=False)
    print(f"Updated manifest: {manifest_out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

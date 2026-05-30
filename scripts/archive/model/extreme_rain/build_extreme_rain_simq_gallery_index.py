#!/usr/bin/env python3
# /// script
# dependencies = ["pandas>=2.2"]
# ///
"""Build an HTML gallery index for extreme rain simQ event hydrographs (model prediction overlays).

Reads: output/model_analysis/extreme_rain/expanded_drbc/event_simq_plots/event_simq_plot_manifest.csv
Writes: output/model_analysis/extreme_rain/expanded_drbc/event_simq_plots/event_plot_index.html
"""
from __future__ import annotations

import argparse
import html as html_lib
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = REPO_ROOT / "output/model_analysis/extreme_rain/expanded_drbc/event_simq_plots/event_simq_plot_manifest.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output/model_analysis/extreme_rain/expanded_drbc/event_simq_plots"

STRESS_GROUP_ORDER = ["positive_response", "negative_control"]
RESPONSE_CLASS_ORDER = [
    "flood_response_ge25",
    "flood_response_ge2_to_lt25",
    "high_flow_non_flood_q99_only",
    "low_response_below_q99",
]
STRESS_GROUP_LABELS = {
    "positive_response": "Positive Response (Flood)",
    "negative_control": "Negative Control",
}
RESPONSE_CLASS_LABELS = {
    "flood_response_ge25": "Flood ≥ ARI25 — Strongest flood response",
    "flood_response_ge2_to_lt25": "Flood ARI2–25 — Moderate flood response",
    "high_flow_non_flood_q99_only": "High flow, non-flood (q99 only)",
    "low_response_below_q99": "Low/no response (below q99)",
}
RAIN_COHORT_ORDER = ["prec_ge100", "prec_ge50", "prec_ge25", "near_prec100"]
RAIN_COHORT_LABELS = {
    "prec_ge100": "prec ≥ ARI100",
    "prec_ge50": "prec ≥ ARI50",
    "prec_ge25": "prec ≥ ARI25",
    "near_prec100": "near ARI100 (≥0.8×)",
}

CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #18181b; }
h1 { font-size: 22px; margin: 0 0 8px; }
h2 { font-size: 20px; margin: 30px 0 6px; border-top: 1px solid #d4d4d8; padding-top: 18px; }
h2 span, h3 span { color: #71717a; font-weight: 500; }
h3 { font-size: 15px; margin: 18px 0 10px; }
.meta { color: #52525b; margin: 0 0 18px; max-width: 980px; line-height: 1.45; }
table { border-collapse: collapse; margin: 14px 0 24px; font-size: 13px; }
th, td { border: 1px solid #d4d4d8; padding: 6px 8px; text-align: left; }
th { background: #f4f4f5; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.95em; }
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


def relative_img_path(plot_path: str, gallery_dir: Path) -> str:
    abs_path = REPO_ROOT / plot_path if not Path(plot_path).is_absolute() else Path(plot_path)
    try:
        return str(abs_path.relative_to(gallery_dir))
    except ValueError:
        return str(abs_path)


def card_html(row: pd.Series, gallery_dir: Path) -> str:
    plot_path = str(row["plot_path"])
    rel = relative_img_path(plot_path, gallery_dir)
    event_id = html_lib.escape(str(row["event_id"]))
    gauge_id = html_lib.escape(str(row.get("gauge_id", "")))
    response_class = str(row.get("response_class", ""))
    rain_cohort = str(row.get("rain_cohort", ""))
    rain_cohort_label = RAIN_COHORT_LABELS.get(rain_cohort, rain_cohort)
    response_label = RESPONSE_CLASS_LABELS.get(response_class, response_class)

    # Format observed peak
    obs_peak = row.get("observed_response_peak", "")
    obs_str = f"{float(obs_peak):.1f} cms" if obs_peak != "" and str(obs_peak) not in ("", "nan") else ""

    return f"""
    <div class="card">
      <a class="image-link" href="{rel}" target="_blank">
        <img src="{rel}" alt="{event_id}" loading="lazy">
      </a>
      <h3>{gauge_id} — {event_id.split("_rain_")[0] if "_rain_" in event_id else event_id}</h3>
      <p class="classline">{response_label}</p>
      <p>{rain_cohort_label}{(" · " + obs_str) if obs_str else ""}</p>
    </div>"""


def build_summary_table(df: pd.DataFrame) -> str:
    rows = []
    for sg in STRESS_GROUP_ORDER:
        for rc in RESPONSE_CLASS_ORDER:
            n = len(df[(df["stress_group"] == sg) & (df["response_class"] == rc)])
            if n:
                rows.append(f"<tr><td>{STRESS_GROUP_LABELS.get(sg, sg)}</td><td><code>{rc}</code></td><td>{n}</td></tr>")
    return "<table><thead><tr><th>Stress Group</th><th>Response Class</th><th>Events</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def build_html(df: pd.DataFrame, gallery_dir: Path) -> str:
    total = len(df)
    n_basins = df["gauge_id"].nunique() if "gauge_id" in df.columns else "?"
    summary_table = build_summary_table(df)

    section_html = []
    for sg in STRESS_GROUP_ORDER:
        sg_df = df[df["stress_group"] == sg]
        if sg_df.empty:
            continue
        sg_label = STRESS_GROUP_LABELS.get(sg, sg)
        section_html.append(f'<h2>{sg_label} <span>({len(sg_df)} events)</span></h2>')
        for rc in RESPONSE_CLASS_ORDER:
            rc_df = sg_df[sg_df["response_class"] == rc].sort_values(["gauge_id", "event_id"] if "gauge_id" in sg_df.columns else ["event_id"])
            if rc_df.empty:
                continue
            rc_label = RESPONSE_CLASS_LABELS.get(rc, rc)
            cards = "".join(card_html(row, gallery_dir) for _, row in rc_df.iterrows())
            section_html.append(f"""
    <details class="condition-details" open>
      <summary>
        <span class="condition-label"><code>{rc}</code> — {rc_label}</span>
        <span class="condition-count">{len(rc_df)} events</span>
      </summary>
      <div class="grid">{cards}</div>
    </details>""")

    sections = "\n".join(section_html)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>Expanded DRBC Extreme Rain — Sim-Q Event Hydrographs</title>
  <style>{CSS}</style>
</head>
<body>
  <h1>Expanded DRBC Extreme Rain — Simulated Q Event Hydrographs</h1>
  <p class="meta">{total} events across {n_basins} basins. Each panel shows observed streamflow + Model 1 deterministic + Model 2 quantile bands (q50/q90/q95/q99) for extreme-rain stress events. Events are grouped by response class (flood response strength).</p>
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
    if not args.manifest.exists():
        raise FileNotFoundError(f"Missing manifest: {args.manifest}")
    df = pd.read_csv(args.manifest, dtype={"gauge_id": str})
    if "gauge_id" in df.columns:
        df["gauge_id"] = df["gauge_id"].astype(str).str.zfill(8)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    gallery_html = build_html(df, args.output_dir)
    out_path = args.output_dir / "event_plot_index.html"
    out_path.write_text(gallery_html, encoding="utf-8")
    n_basins = df["gauge_id"].nunique() if "gauge_id" in df.columns else "?"
    print(f"Wrote: {out_path.relative_to(REPO_ROOT)} ({len(df)} events, {n_basins} basins)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

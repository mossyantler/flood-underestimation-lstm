#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pandas>=2.2",
#   "numpy>=2.0",
#   "scipy>=1.13",
#   "matplotlib>=3.9",
#   "seaborn>=0.13",
# ]
# ///
from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ANALYSIS_DIR = REPO_ROOT / "output/model_analysis/shap/test_split"
DEFAULT_Q99_SHAP_DIR = REPO_ROOT / "output/model_analysis/shap/q99"
DEFAULT_STATIC_CSV = REPO_ROOT / "data/CAMELSH_generic/drbc_expanded_observed_test/attributes/static_attributes.csv"
DEFAULT_OUTPUT_HTML = DEFAULT_ANALYSIS_DIR / "report/area_signed_shap_rq0_report.html"
DEFAULT_NOTES_JSON = DEFAULT_ANALYSIS_DIR / "report/area_signed_shap_rq0_source_notes.json"

TOKENS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
    "grid": "#E6E8F0",
    "axis": "#D7DBE7",
}
BLUE = {"xlight": "#EAF1FE", "light": "#CEDFFE", "base": "#A3BEFA", "mid": "#5477C4", "dark": "#2E4780"}
ORANGE = {"xlight": "#FFEDDE", "light": "#FFBDA1", "base": "#F0986E", "mid": "#CC6F47", "dark": "#804126"}
GOLD = {"xlight": "#FFF4C2", "light": "#FFEA8F", "base": "#FFE15B", "mid": "#B8A037", "dark": "#736422"}
NEUTRAL = {"xlight": "#F4F5F7", "light": "#E2E5EA", "base": "#C5CAD3", "mid": "#7A828F", "dark": "#464C55"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Korean technical report linking area, signed SHAP, and RQ-0 Spearman evidence.")
    parser.add_argument("--analysis-dir", type=Path, default=DEFAULT_ANALYSIS_DIR)
    parser.add_argument("--q99-shap-dir", type=Path, default=DEFAULT_Q99_SHAP_DIR)
    parser.add_argument("--static-csv", type=Path, default=DEFAULT_STATIC_CSV)
    parser.add_argument("--output-html", type=Path, default=DEFAULT_OUTPUT_HTML)
    parser.add_argument("--notes-json", type=Path, default=DEFAULT_NOTES_JSON)
    return parser.parse_args()


def configure_style() -> None:
    sns.set_theme(style="whitegrid")
    plt.rcParams.update(
        {
            "figure.facecolor": TOKENS["surface"],
            "axes.facecolor": TOKENS["panel"],
            "axes.edgecolor": TOKENS["axis"],
            "axes.labelcolor": TOKENS["ink"],
            "xtick.color": TOKENS["muted"],
            "ytick.color": TOKENS["ink"],
            "text.color": TOKENS["ink"],
            "font.family": ["DejaVu Sans", "sans-serif"],
            "axes.unicode_minus": False,
        }
    )


def add_header(fig: plt.Figure, title: str, subtitle: str) -> None:
    fig.text(0.08, 0.965, title, ha="left", va="top", fontsize=17, fontweight="bold", color=TOKENS["ink"])
    fig.text(0.08, 0.925, subtitle, ha="left", va="top", fontsize=11.5, color=TOKENS["muted"])


def read_global_shap(analysis_dir: Path) -> pd.DataFrame:
    path = analysis_dir / "tables/quantile_lstm_direct_shap_global_feature_importance_seed_mean.csv"
    return pd.read_csv(path, comment="#")


def read_event_area_rows(analysis_dir: Path, static_csv: Path) -> pd.DataFrame:
    attrs = pd.read_csv(static_csv, comment="#")
    attrs["basin"] = attrs["gauge_id"].astype(str).str.zfill(8)
    rows = []
    for path in sorted((analysis_dir / "tables").glob("quantile_lstm_direct_shap_event_feature_importance_seed*.csv")):
        frame = pd.read_csv(path, comment="#")
        sub = frame[(frame["feature"] == "area") & (frame["quantile"] == "q99")].copy()
        sub["basin"] = sub["basin"].astype(str).str.zfill(8)
        rows.append(sub)
    if not rows:
        raise FileNotFoundError(f"No event SHAP tables found in {analysis_dir / 'tables'}")
    merged = pd.concat(rows, ignore_index=True).merge(attrs[["basin", "area"]], on="basin", how="left")
    return merged


def corr_row(frame: pd.DataFrame, x: str, y: str, label: str, interpretation: str) -> dict[str, object]:
    clean = frame.dropna(subset=[x, y])
    stat = spearmanr(clean[x], clean[y])
    return {
        "relationship": label,
        "spearman_r": float(stat.statistic),
        "p_value": float(stat.pvalue),
        "n": int(len(clean)),
        "interpretation": interpretation,
    }


def build_relationship_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows = [
        corr_row(events, "area", "quantile_prediction_normalized", "area vs normalized q99 output", "큰 유역일수록 normalized q99 출력이 커지는 경향"),
        corr_row(events, "area", "q99_peak", "area vs q99 peak", "큰 유역일수록 q99 peak도 커지는 경향"),
        corr_row(events, "area", "obs_peak", "area vs observed peak", "관측 첨두는 area와 훨씬 강하게 증가"),
        corr_row(events, "area", "mean_signed_shap", "area vs area signed SHAP", "큰 유역일수록 area signed SHAP가 덜 음수 또는 양수 쪽으로 이동"),
        corr_row(events, "area", "q99_peak_rel_error", "area vs q99 relative error", "큰 유역일수록 q99가 관측에 비해 부족해지는 방향"),
    ]
    return pd.DataFrame(rows)


def plot_relationships(summary: pd.DataFrame, output: Path) -> None:
    labels = [
        "Normalized q99 output",
        "q99 peak",
        "Observed peak",
        "Area signed SHAP",
        "q99 relative error",
    ]
    frame = summary.copy()
    frame["label"] = labels
    frame = frame.iloc[::-1]
    colors = [ORANGE["base"] if v < 0 else BLUE["base"] for v in frame["spearman_r"]]
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    fig.subplots_adjust(left=0.28, right=0.94, top=0.80, bottom=0.18)
    sns.barplot(data=frame, y="label", x="spearman_r", ax=ax, palette=colors, hue="label", legend=False, edgecolor=NEUTRAL["dark"], linewidth=0.8)
    ax.axvline(0, color=TOKENS["ink"], linewidth=1.1)
    limit = max(1.0, float(np.abs(frame["spearman_r"]).max()) * 1.08)
    ax.set_xlim(-limit, limit)
    ax.set_xlabel("Spearman r with basin area")
    ax.set_ylabel("")
    ax.grid(axis="x", color=TOKENS["grid"], linewidth=0.9)
    ax.grid(axis="y", visible=False)
    for i, value in enumerate(frame["spearman_r"]):
        ha = "left" if value >= 0 else "right"
        dx = 0.025 if value >= 0 else -0.025
        ax.text(value + dx, i, f"{value:+.3f}", va="center", ha=ha, fontsize=10.5, color=TOKENS["ink"])
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    add_header(fig, "Area relationship checks", "Event-level q99 direct SHAP sample, three Model 2 seeds pooled; positive r means larger area aligns with larger metric values")
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_signed_shap(global_shap: pd.DataFrame, output: Path) -> pd.DataFrame:
    q99 = global_shap[global_shap["quantile"] == "q99"].copy()
    q99 = q99.sort_values("mean_abs_shap_mean", ascending=False).head(10)
    plot_frame = q99.sort_values("mean_signed_shap_mean")
    colors = [ORANGE["base"] if value < 0 else BLUE["base"] for value in plot_frame["mean_signed_shap_mean"]]
    fig, ax = plt.subplots(figsize=(9.2, 5.8))
    fig.subplots_adjust(left=0.30, right=0.94, top=0.80, bottom=0.18)
    sns.barplot(
        data=plot_frame,
        y="feature",
        x="mean_signed_shap_mean",
        ax=ax,
        palette=colors,
        hue="feature",
        legend=False,
        edgecolor=NEUTRAL["dark"],
        linewidth=0.8,
    )
    ax.axvline(0, color=TOKENS["ink"], linewidth=1.1)
    limit = max(0.03, float(np.abs(plot_frame["mean_signed_shap_mean"]).max()) * 1.18)
    ax.set_xlim(-limit, limit)
    ax.set_xlabel("Mean signed SHAP contribution to q99 output")
    ax.set_ylabel("")
    ax.grid(axis="x", color=TOKENS["grid"], linewidth=0.9)
    ax.grid(axis="y", visible=False)
    for i, value in enumerate(plot_frame["mean_signed_shap_mean"]):
        ha = "left" if value >= 0 else "right"
        dx = limit * 0.025 if value >= 0 else -limit * 0.025
        ax.text(value + dx, i, f"{value:+.3f}", va="center", ha=ha, fontsize=10.5, color=TOKENS["ink"])
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    add_header(fig, "Signed SHAP contributions for q99", "Top features ranked by mean absolute SHAP; signed bars show direction relative to the background baseline")
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return q99


def format_p(value: float) -> str:
    if value < 0.001:
        return f"{value:.1e}"
    return f"{value:.3f}"


def table_html(frame: pd.DataFrame) -> str:
    rows = []
    for _, row in frame.iterrows():
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(row['relationship']))}</td>"
            f"<td>{row['spearman_r']:+.3f}</td>"
            f"<td>{format_p(float(row['p_value']))}</td>"
            f"<td>{int(row['n'])}</td>"
            f"<td>{html.escape(str(row['interpretation']))}</td>"
            "</tr>"
        )
    return """
<table>
  <thead><tr><th>검정 관계</th><th>Spearman r</th><th>p-value</th><th>n</th><th>해석</th></tr></thead>
  <tbody>
""" + "\n".join(rows) + "\n  </tbody>\n</table>"


def render_report(output_html: Path, relationship_png: Path, signed_png: Path, summary: pd.DataFrame, q99_top: pd.DataFrame, events: pd.DataFrame) -> str:
    area_row = q99_top[q99_top["feature"] == "area"].iloc[0]
    rel = {row["relationship"]: row for _, row in summary.iterrows()}
    sample_n = int(len(events.dropna(subset=["area", "quantile_prediction_normalized"])))
    basin_n = int(events["basin"].nunique())
    title = "Area, signed SHAP, and RQ-0 interpretation"
    rel_img = html.escape(os.path.relpath(relationship_png, output_html.parent))
    signed_img = html.escape(os.path.relpath(signed_png, output_html.parent))
    css = """
    body { font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Segoe UI", sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }
    main { max-width: 980px; margin: 0 auto; padding: 44px 22px 70px; }
    header, section { margin-bottom: 34px; }
    section { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 18px; padding: 24px; box-shadow: 0 10px 28px rgba(15,23,42,.045); }
    header { padding: 8px 2px 0; }
    h1 { font-size: 34px; line-height: 1.16; margin: 0 0 10px; letter-spacing: -0.025em; }
    h2 { font-size: 22px; line-height: 1.25; margin: 0 0 12px; letter-spacing: -0.015em; }
    h3 { font-size: 17px; margin: 18px 0 8px; }
    p, li { line-height: 1.72; font-size: 15.5px; }
    .dek { color: #475569; margin: 0; font-size: 16px; }
    .summary { background: #eff6ff; border-color: #bfdbfe; }
    .metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 16px 0 8px; }
    .metric { border: 1px solid #e2e8f0; border-radius: 14px; padding: 14px; background: #fbfdff; }
    .metric strong { display: block; font-size: 22px; margin-bottom: 2px; }
    .metric span { color: #64748b; font-size: 13px; line-height: 1.45; }
    figure { margin: 20px 0 8px; }
    figure img { display: block; width: 100%; height: auto; border: 1px solid #e2e8f0; border-radius: 14px; background: #fff; }
    figcaption { color: #64748b; font-size: 13.5px; line-height: 1.55; margin-top: 8px; }
    table { width: 100%; border-collapse: collapse; margin: 14px 0 4px; font-size: 14px; }
    th, td { border-bottom: 1px solid #e2e8f0; padding: 10px 9px; text-align: left; vertical-align: top; }
    th { background: #f1f5f9; font-weight: 700; }
    code { background: #eef2ff; padding: 1px 5px; border-radius: 5px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    .note { border-left: 4px solid #f59e0b; padding-left: 12px; color: #334155; }
    @media (max-width: 760px) { .metric-grid { grid-template-columns: 1fr; } main { padding: 28px 14px 48px; } }
    """
    body = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{css}</style>
</head>
<body>
  <main data-report-audience="technical">
    <header data-contract-section="title">
      <h1>{html.escape(title)}</h1>
      <p class="dek">Model 2 q99 출력에서 area의 signed SHAP와 RQ-0 Spearman 신호를 함께 해석하기 위한 한국어 기술 보고서.</p>
    </header>

    <section class="summary" data-contract-section="technical-summary">
      <h2>기술 요약: area는 출력과 반비례하지 않고, 관측 증가를 충분히 따라가지 못하는 위험 신호다</h2>
      <p><strong>현재 산출값 기준 결론은 명확하다.</strong> area가 클수록 q99 출력 자체가 작아진다는 반비례 관계는 아니다. sampled direct SHAP 사건에서 area와 normalized q99 출력의 Spearman r은 <strong>{rel['area vs normalized q99 output']['spearman_r']:+.3f}</strong>, area와 q99 peak의 r은 <strong>{rel['area vs q99 peak']['spearman_r']:+.3f}</strong>로 모두 양수다. 그러나 area와 관측 첨두의 r은 <strong>{rel['area vs observed peak']['spearman_r']:+.3f}</strong>로 훨씬 크다.</p>
      <p><strong>따라서 논문 문장은 “큰 유역에서 모델 출력이 감소한다”가 아니라 “모델도 큰 유역에서 출력을 올리지만 관측 첨두 증가를 충분히 따라가지 못해 과소추정 위험이 커진다”로 써야 한다.</strong> RQ-0의 area Spearman 양수 신호는 이 해석과 정합적이다.</p>
      <div class="metric-grid">
        <div class="metric"><strong>{rel['area vs normalized q99 output']['spearman_r']:+.3f}</strong><span>area vs normalized q99 output</span></div>
        <div class="metric"><strong>{rel['area vs observed peak']['spearman_r']:+.3f}</strong><span>area vs observed peak</span></div>
        <div class="metric"><strong>{area_row['mean_signed_shap_mean']:+.3f}</strong><span>q99 area mean signed SHAP</span></div>
      </div>
    </section>

    <section data-contract-section="key-findings">
      <h2>출력 관계 검정은 반비례가 아니라 “부족한 스케일링”을 가리킨다</h2>
      <p>아래 그림은 같은 event-level SHAP 표본에서 raw area와 주요 값들의 Spearman 순위상관을 비교한다. q99 출력과 관측 첨두 모두 area와 양의 관계지만, 관측 첨두 쪽 관계가 훨씬 강하다. 또한 area와 q99 relative error의 음의 관계는 큰 유역에서 q99가 관측 대비 더 부족해지는 방향임을 보여준다.</p>
      <figure>
        <img src="{rel_img}" alt="Area relationship checks">
        <figcaption>표본은 q99 direct SHAP event rows를 세 seed 기준으로 합친 {sample_n}개 행, {basin_n}개 유역이다. 양수는 area가 클수록 해당 값도 커지는 경향, 음수는 area가 클수록 해당 값이 작아지는 경향을 뜻한다.</figcaption>
      </figure>
      {table_html(summary)}
    </section>

    <section data-contract-section="key-findings">
      <h2>area의 signed SHAP는 평균적으로 약간 음수지만, 이것은 raw area-output 반비례를 뜻하지 않는다</h2>
      <p>q99에서 area는 mean absolute SHAP 기준 가장 큰 feature다. 동시에 mean signed SHAP는 <strong>{area_row['mean_signed_shap_mean']:+.3f}</strong>로 약간 음수다. 이 값은 “현재 background baseline과 비교했을 때 area feature가 q99 출력에 배정받은 평균 기여가 약간 낮추는 방향”이라는 뜻이지, raw area가 커질수록 q99 출력이 감소한다는 뜻은 아니다.</p>
      <figure>
        <img src="{signed_img}" alt="Signed SHAP contributions for q99">
        <figcaption>SHAP 값의 부호는 background baseline 대비 해당 feature의 출력 방향 기여다. 막대 길이는 mean signed SHAP이며, feature 중요도 순위는 mean absolute SHAP 기준 상위 10개에서 가져왔다.</figcaption>
      </figure>
      <p class="note"><strong>해석 주의:</strong> SHAP baseline은 zero-flow나 “feature 없음” 상태가 아니라, background event sample에서 기대되는 모델 출력 기준이다. 따라서 signed SHAP 평균은 baseline 선택, feature 간 상호작용, 표준화된 입력 공간의 위치에 영향을 받는다.</p>
    </section>

    <section data-contract-section="scope-data-and-metric-definitions">
      <h2>분석 범위와 지표 정의</h2>
      <p>이 보고서는 <code>output/model_analysis/shap/test_split</code>과 <code>output/model_analysis/shap/q99</code>의 direct SHAP 산출물, 그리고 RQ-0 문서의 Spearman 결과를 함께 해석한다. direct SHAP는 Model 2의 q50/q90/q95/q99 LSTM 출력 자체를 설명하며, 관측 유량은 입력으로 넣지 않는다. 관측 유량은 사건 선택과 사후 검증에만 사용된다.</p>
      <ul>
        <li><strong>SHAP baseline</strong>: background event sample에서 모델 출력의 기대 기준. 현재 metadata 기준 seed별 background event는 32개, SHAP samples는 64개다.</li>
        <li><strong>signed SHAP</strong>: baseline 대비 해당 feature가 출력을 올리면 양수, 낮추면 음수인 additive contribution.</li>
        <li><strong>mean absolute SHAP</strong>: 부호를 제거한 평균 기여 크기. feature가 얼마나 많이 관여했는지를 보는 중요도 지표다.</li>
        <li><strong>obs_class</strong>: 관측 첨두가 q50/q90/q95/q99 예측 사다리 어디에 놓이는지 나타내는 관측 위치 구간. 값이 클수록 q99 초과, 즉 과소추정 위험이 커진다.</li>
      </ul>
    </section>

    <section data-contract-section="methodology">
      <h2>방법: direct SHAP는 모델 출력 설명, RQ-0 Spearman은 과소추정 위험 신호 검정</h2>
      <p>direct SHAP는 reconstructed quantile LSTM에 expected-gradient 방식으로 적용했다. 각 사건의 dynamic forcing sequence와 static attributes를 background event와 보간하고, 출력 기울기와 입력 차이를 평균해 feature별 contribution을 계산한다.</p>
      <p>RQ-0 Spearman 분석은 feature 값과 obs_class 사이의 순위상관을 본다. RQ-0 문서 기준 area의 Spearman r은 Q99 사건 <strong>+0.50</strong>, NOAA/NWS 홍수 <strong>+0.50</strong>, 전체 강우 사건 <strong>+0.27</strong>이다. 이는 area가 관측 위치 구간을 위쪽으로 밀어 올리는 독립 신호임을 뜻한다.</p>
    </section>

    <section data-contract-section="limitations-uncertainty-and-robustness-checks">
      <h2>제한과 견고성: SHAP 방향성은 보조 해석이고, 결론은 RQ-0와 함께 읽어야 한다</h2>
      <p>direct SHAP 표본은 seed별 98개 사건, 세 seed 합산 294개 event-feature rows이며, 현재 area 관계 검정은 8개 유역에 걸친 sampled SHAP 사건에 기반한다. 따라서 raw area-output 관계의 방향 확인에는 유용하지만, 전체 DRBC 사건의 일반화 근거로 단독 사용하면 안 된다.</p>
      <p>반면 RQ-0 Spearman은 Q99, NOAA/NWS 홍수, 전체 강우 사건으로 범위를 넓혀 area 신호가 반복되는지 확인한다. 그래서 본문 결론의 주된 근거는 RQ-0이고, SHAP는 “모델 내부에서도 area가 q99 출력 설명에 크게 관여한다”는 보조 진단으로 두는 것이 안전하다.</p>
    </section>

    <section data-contract-section="recommended-next-steps">
      <h2>권장 문장: area는 큰 출력의 반대가 아니라 큰 과소추정 위험의 조건이다</h2>
      <p>논문에는 다음처럼 쓰는 편이 가장 안전하다.</p>
      <p><strong>“Basin area was positively associated with both q99 predictions and observed peaks, but the observed peak response scaled much more strongly with area. Thus, area should be interpreted as a robust underestimation-risk signal rather than as a feature that simply suppresses q99 output.”</strong></p>
      <p>한국어 해석 문장으로는 “큰 유역에서 q99 출력이 작아진다”가 아니라 “큰 유역에서 q99 출력도 증가하지만 관측 첨두 증가를 충분히 따라가지 못해 q99 초과 위험이 커진다”가 맞다.</p>
    </section>

    <section data-contract-section="further-questions">
      <h2>추가 확인 질문: area 효과는 정규화·유역 단위 첨두와 분리해서 다시 볼 필요가 있다</h2>
      <p>다음 단계에서는 raw peak 대신 단위면적 첨두, normalized output, basin-level aggregation을 분리해 area 효과를 다시 그리는 것이 좋다. 이렇게 하면 “큰 유역이라 총유량이 큰 효과”와 “유역 반응성이 모델에서 부족하게 표현되는 효과”를 더 명확히 나눌 수 있다.</p>
    </section>
  </main>
</body>
</html>
"""
    output_html.write_text(body, encoding="utf-8")
    return body


def main() -> None:
    args = parse_args()
    configure_style()
    report_dir = args.output_html.parent
    figures_dir = args.analysis_dir / "figures"
    tables_dir = args.analysis_dir / "tables"
    report_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    global_shap = read_global_shap(args.analysis_dir)
    events = read_event_area_rows(args.q99_shap_dir, args.static_csv)
    summary = build_relationship_summary(events)
    summary_path = tables_dir / "area_output_relationship_spearman.csv"
    summary.to_csv(summary_path, index=False)

    relationship_png = figures_dir / "area_output_relationship_spearman.png"
    signed_png = figures_dir / "signed_shap_q99_top_features_report.png"
    plot_relationships(summary, relationship_png)
    q99_top = plot_signed_shap(global_shap, signed_png)

    render_report(args.output_html, relationship_png, signed_png, summary, q99_top, events)

    notes = {
        "report": str(args.output_html.relative_to(REPO_ROOT)),
        "delivery_mode": "html",
        "audience": "technical",
        "sources": {
            "global_shap_seed_mean": str((args.analysis_dir / "tables/quantile_lstm_direct_shap_global_feature_importance_seed_mean.csv").relative_to(REPO_ROOT)),
            "event_shap_tables": [str(p.relative_to(REPO_ROOT)) for p in sorted((args.q99_shap_dir / "tables").glob("quantile_lstm_direct_shap_event_feature_importance_seed*.csv"))],
            "static_attributes": str(args.static_csv.relative_to(REPO_ROOT)),
            "rq0_document": "docs/experiment/analysis/model/00b_rq0_framework_validation.md",
        },
        "generated": {
            "relationship_summary_table": str(summary_path.relative_to(REPO_ROOT)),
            "relationship_chart": str(relationship_png.relative_to(REPO_ROOT)),
            "signed_shap_chart": str(signed_png.relative_to(REPO_ROOT)),
        },
        "chart_map": [
            {
                "section": "출력 관계 검정은 반비례가 아니라 부족한 스케일링을 가리킨다",
                "question": "Does larger basin area correspond to smaller q99 output?",
                "family": "Comparison & Ranking",
                "chart_type": "diverging horizontal bar",
                "supported_claim": "area has positive association with q99 output and stronger positive association with observed peak",
            },
            {
                "section": "area의 signed SHAP는 평균적으로 약간 음수지만 raw area-output 반비례를 뜻하지 않는다",
                "question": "What direction do q99 signed SHAP contributions take for top features?",
                "family": "Comparison & Ranking",
                "chart_type": "diverging horizontal bar",
                "supported_claim": "area is the largest q99 SHAP feature by absolute contribution but has small negative mean signed contribution",
            },
        ],
        "validation_notes": {
            "relationship_rows": int(len(events)),
            "relationship_basins": int(events["basin"].nunique()),
            "rq0_area_spearman": {"q99": 0.50, "noaa": 0.50, "all_rain": 0.27},
        },
    }
    args.notes_json.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(notes["generated"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

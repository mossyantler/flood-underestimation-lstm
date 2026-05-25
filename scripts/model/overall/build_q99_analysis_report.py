#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "Pillow>=10.0",
# ]
# ///
"""Build Q99 analysis report (HTML + MD).

HTML is fully self-contained (base64 figures).
MD uses relative figure paths.

Outputs
-------
output/q99_analysis/q99_analysis_report.html
output/q99_analysis/q99_analysis_report.md
"""
from __future__ import annotations

import base64
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
TABLE_DIR = REPO_ROOT / "output/q99_analysis/tables"
FIG_DIR = REPO_ROOT / "output/q99_analysis/figures"
OUT_DIR = REPO_ROOT / "output/q99_analysis"

# ── data ────────────────────────────────────────────────────────────────────

def load_tables() -> dict:
    d = {}
    d["error_summary"] = pd.read_csv(TABLE_DIR / "basin_q99_error_summary.csv")
    d["stable_drivers"] = pd.read_csv(TABLE_DIR / "q99_stable_drivers.csv")
    d["event_forcing"] = pd.read_csv(TABLE_DIR / "q99_event_forcing_correlation.csv")
    d["attribution"] = pd.read_csv(TABLE_DIR / "q99_lstm_attribution_multiseed_summary.csv")
    d["basin_attr_corr"] = pd.read_csv(TABLE_DIR / "q99_lstm_attribution_basin_correlation.csv")
    return d


# ── helpers ──────────────────────────────────────────────────────────────────

def fig_b64(name: str) -> str:
    p = FIG_DIR / name
    if not p.exists():
        return ""
    return base64.b64encode(p.read_bytes()).decode()


def df_to_html(df: pd.DataFrame, float_fmt: str = ".3f") -> str:
    return df.to_html(
        index=False, border=0, classes="table",
        float_format=lambda x: f"{x:{float_fmt}}",
    )


def df_to_md(df: pd.DataFrame, float_fmt: str = ".3f") -> str:
    cols = df.columns.tolist()
    rows = []
    rows.append("| " + " | ".join(cols) + " |")
    rows.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for _, row in df.iterrows():
        cells = []
        for v in row:
            if isinstance(v, float):
                cells.append(f"{v:{float_fmt}}")
            else:
                cells.append(str(v))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


# ── content builders ─────────────────────────────────────────────────────────

def build_overview(d: dict) -> tuple[str, str]:
    es = d["error_summary"]
    q99_median_bias = es["q99_med_rel_bias"].median()
    m1_median_bias = es["model1_med_rel_bias"].median()
    q99_uf = es["q99_under_frac"].median()
    m1_uf = es["model1_under_frac"].median()
    delta_med = es["med_rel_bias_delta"].median()
    n_basins = len(es)
    n_improved = (es["med_rel_bias_delta"] > 0).sum()

    html = f"""
<h2>1. 개요 및 주요 성능 지표</h2>
<p>분석 대상: DRBC holdout <strong>{n_basins}개 유역</strong>, 테스트 기간 2014–2016, seed 111/222/444.</p>
<p>Q99 quantile 예측(model2)과 결정론적 기준선(model1)의 obs≥basin 99th pct 시점 성능 비교.</p>

<table class="table summary-table">
<thead><tr><th>지표</th><th>Q99 (model2)</th><th>Model1</th></tr></thead>
<tbody>
<tr><td>Median relative bias (중앙값)</td><td class="bad">{q99_median_bias:+.3f}</td><td>{m1_median_bias:+.3f}</td></tr>
<tr><td>Under-fraction (중앙값)</td><td>{q99_uf:.3f}</td><td class="bad">{m1_uf:.3f}</td></tr>
<tr><td>Bias delta (model1−q99) 중앙값</td><td colspan="2">{delta_med:+.3f}  ({n_improved}/{n_basins} 유역 Q99 개선)</td></tr>
</tbody>
</table>

<p><strong>해석:</strong> Q99는 model1 대비 under-fraction이 크게 감소하나({m1_uf:.2f}→{q99_uf:.2f}),
median relative bias는 오히려 증가(overestimation 방향 이동, {m1_median_bias:+.2f}→{q99_median_bias:+.2f}).
{n_basins - n_improved}/{n_basins} 유역에서 Q99 bias가 model1보다 악화.</p>
"""

    md = f"""## 1. 개요 및 주요 성능 지표

분석 대상: DRBC holdout **{n_basins}개 유역**, 테스트 기간 2014–2016, seed 111/222/444.

| 지표 | Q99 (model2) | Model1 |
|------|-------------|--------|
| Median relative bias | {q99_median_bias:+.3f} | {m1_median_bias:+.3f} |
| Under-fraction | {q99_uf:.3f} | {m1_uf:.3f} |
| Bias delta (model1−q99) 중앙값 | {delta_med:+.3f} ({n_improved}/{n_basins} 개선) | — |

**해석:** Q99는 under-fraction 감소({m1_uf:.2f}→{q99_uf:.2f})하나 median relative bias 증가(overestimation 방향). {n_basins - n_improved}/{n_basins} 유역에서 bias 악화.
"""
    return html, md


def build_basin_drivers(d: dict) -> tuple[str, str]:
    sd = d["stable_drivers"]
    bias_top = sd[sd["target"] == "q99_med_rel_bias"].head(10)[
        ["attribute", "rho_median", "pval_median", "direction"]
    ].copy()
    bias_top.columns = ["attribute", "ρ (중앙값)", "p-value", "방향"]

    delta_top = sd[sd["target"] == "med_rel_bias_delta"].head(6)[
        ["attribute", "rho_median", "pval_median", "direction"]
    ].copy()
    delta_top.columns = ["attribute", "ρ (중앙값)", "p-value", "방향"]

    img_bar = fig_b64("q99_driver_correlation_bar.png")
    img_radar = fig_b64("q99_quartile_radar.png")
    img_scatter = fig_b64("q99_driver_scatter_top4.png")

    html = f"""
<h2>2. 유역 특성 × Q99 오차 상관 (Analysis B)</h2>
<p>85개 유역 × 3 seed Spearman 상관. 3-seed 방향 일치 = "stable driver".</p>

<h3>2-1. q99_med_rel_bias 주요 stable drivers (top-10)</h3>
{df_to_html(bias_top)}

<h3>2-2. Spearman ρ 바 차트</h3>
<img src="data:image/png;base64,{img_bar}" style="max-width:700px">

<h3>2-3. Q1(worst) vs Q4(best) 유역 프로파일</h3>
<img src="data:image/png;base64,{img_radar}" style="max-width:550px">

<h3>2-4. Top-4 물리 특성 scatter</h3>
<img src="data:image/png;base64,{img_scatter}" style="max-width:900px">

<h3>2-5. med_rel_bias_delta drivers (Q99 개선 유역 특성)</h3>
{df_to_html(delta_top)}

<p><strong>핵심 발견:</strong></p>
<ul>
<li><strong>Strahler 하천 차수 ↑</strong> → Q99 bias ↓ (ρ=−0.46): 복잡한 하천망 유역에서 Q99가 더 정확</li>
<li><strong>토양 투수성(PERMAVE) ↑</strong> → Q99 bias ↓ (ρ=−0.44): 투수성 높은 유역 = 기저류 지배 = 예측 쉬움</li>
<li><strong>사행도(MAINSTEM_SINUOUSITY) ↑</strong> → Q99 bias ↓ (ρ=−0.44)</li>
<li><strong>단위면적 첨두 P90(unit_area_peak_p90) ↑</strong> → Q99 bias ↑ (ρ=+0.39): 플래시성 유역 취약</li>
<li><strong>인공수로 비율(ARTIFPATH_PCT) ↑</strong> → Q99 bias ↓ (ρ=−0.31): 인공화된 유역에서 예측 용이</li>
</ul>
"""

    md = f"""## 2. 유역 특성 × Q99 오차 상관 (Analysis B)

85개 유역 × 3 seed Spearman 상관. 3-seed 방향 일치 = "stable driver".

### 2-1. q99_med_rel_bias 주요 stable drivers (top-10)

{df_to_md(bias_top)}

### 2-2~4. 시각화

![Spearman ρ 바](figures/q99_driver_correlation_bar.png)
![Q1 vs Q4 Radar](figures/q99_quartile_radar.png)
![Scatter top-4](figures/q99_driver_scatter_top4.png)

### 2-5. med_rel_bias_delta drivers

{df_to_md(delta_top)}

**핵심 발견:**
- **Strahler 하천 차수 ↑** → Q99 bias ↓ (ρ=−0.46): 복잡 하천망 유역 정확도 높음
- **토양 투수성(PERMAVE) ↑** → Q99 bias ↓ (ρ=−0.44): 기저류 지배 유역 예측 용이
- **사행도(MAINSTEM_SINUOUSITY) ↑** → Q99 bias ↓ (ρ=−0.44)
- **단위면적 첨두 P90 ↑** → Q99 bias ↑ (ρ=+0.39): 플래시성 유역 취약
- **인공수로 비율(ARTIFPATH_PCT) ↑** → Q99 bias ↓ (ρ=−0.31)
"""
    return html, md


def build_event_forcing(d: dict) -> tuple[str, str]:
    ef = d["event_forcing"]
    peak_err = ef[(ef["target"] == "q99_peak_rel_error") & ef["stable"]][
        ["feature", "rho_median", "pval_median"]
    ].copy()
    peak_err.columns = ["feature", "ρ (중앙값)", "p-value"]

    uf = ef[(ef["target"] == "q99_under_frac_event") & ef["stable"]][
        ["feature", "rho_median", "pval_median"]
    ].copy()
    uf.columns = ["feature", "ρ (중앙값)", "p-value"]

    img_bar_err = fig_b64("q99_event_forcing_correlation_bar_q99_peak_rel_error.png")
    img_bar_uf = fig_b64("q99_event_forcing_correlation_bar_q99_under_frac_event.png")
    img_scatter = fig_b64("q99_event_forcing_scatter.png")

    html = f"""
<h2>3. 이벤트 강제력 × Q99 오차 상관 (Analysis 3)</h2>
<p>~3,666 이벤트 (85 유역 × ~14 이벤트 × 3 seed). 강제력 창: NC 파일에서 이벤트 기간 및 선행 5일 추출.</p>

<h3>3-1. q99_peak_rel_error (stable drivers)</h3>
{df_to_html(peak_err)}

<h3>3-2. q99_under_frac_event (stable drivers)</h3>
{df_to_html(uf)}

<h3>3-3. 첨두 오차 상관 바 차트</h3>
<img src="data:image/png;base64,{img_bar_err}" style="max-width:650px">

<h3>3-4. Under-fraction 상관 바 차트</h3>
<img src="data:image/png;base64,{img_bar_uf}" style="max-width:650px">

<h3>3-5. Top-4 scatter (seed111)</h3>
<img src="data:image/png;base64,{img_scatter}" style="max-width:900px">

<p><strong>핵심 발견:</strong></p>
<ul>
<li><strong>첨두 강우 강도(event_peak_rainf) ↑</strong> → 첨두 과대추정 증가(ρ=+0.20), 과소추정 감소(ρ=−0.21)</li>
<li><strong>총 강우량(event_total_rainf) ↑</strong> → 동일 방향 (ρ=+0.15 / −0.17)</li>
<li><strong>이벤트 지속시간(event_duration_h) ↑</strong> → 첨두 오차 감소(ρ=−0.14) — 지속성 이벤트 예측 유리</li>
<li><strong>선행 5일 강우(antecedent_rainf_5d) ↑</strong> → 첨두 과대추정 증가(ρ=+0.10)</li>
<li><strong>CAPE는 stable driver 아님</strong> — 대류성 불안정도는 Q99 오차와 무관</li>
</ul>
"""

    md = f"""## 3. 이벤트 강제력 × Q99 오차 상관 (Analysis 3)

~3,666 이벤트 (85 유역 × ~14 이벤트 × 3 seed).

### 3-1. q99_peak_rel_error stable drivers

{df_to_md(peak_err)}

### 3-2. q99_under_frac_event stable drivers

{df_to_md(uf)}

### 3-3~5. 시각화

![첨두 오차 상관](figures/q99_event_forcing_correlation_bar_q99_peak_rel_error.png)
![Under-fraction 상관](figures/q99_event_forcing_correlation_bar_q99_under_frac_event.png)
![Scatter top-4](figures/q99_event_forcing_scatter.png)

**핵심 발견:**
- **첨두 강우 강도 ↑** → 과대추정 증가(ρ=+0.20), 과소추정 감소(ρ=−0.21)
- **이벤트 지속시간 ↑** → 첨두 오차 감소(ρ=−0.14): 지속성 이벤트 예측 유리
- **선행 5일 강우 ↑** → 과대추정 증가(ρ=+0.10)
- **CAPE는 stable driver 아님** (대류성 불안정도 무관)
"""
    return html, md


def build_lstm_attribution(d: dict) -> tuple[str, str]:
    attr = d["attribution"].copy()
    attr_tbl = attr[["feature", "attr_median", "attr_min", "attr_max"]].copy()
    attr_tbl.columns = ["Feature", "Attribution 중앙값", "최솟값", "최댓값"]

    bc = d["basin_attr_corr"]
    sig = bc[(bc["pval"] < 0.05) & (bc["type"] == "fraction")].sort_values("rho", key=abs, ascending=False)
    sig_tbl = sig[["feature", "target", "rho", "pval"]].copy()
    sig_tbl.columns = ["Feature", "Target", "ρ", "p-value"]

    img_feat = fig_b64("q99_lstm_feature_importance_multiseed.png")
    img_lag = fig_b64("q99_lstm_temporal_lag_multiseed.png")
    img_strat = fig_b64("q99_lstm_attribution_stratified_multiseed.png")
    img_basin = fig_b64("q99_lstm_attribution_basin_correlation_q99_med_rel_bias.png")

    html = f"""
<h2>4. LSTM 입력 기여도 분석 — GradientInput Attribution (Analysis A)</h2>
<p>Method: GradientInput (|∂q99/∂x_d| × |x_d|), CudaLSTM model2 epoch005, seq_length=336h.<br>
seed111: 1,200 이벤트, seed222: 1,200 이벤트, seed444: 1,194 이벤트.</p>

<h3>4-1. 3-seed 통합 feature importance</h3>
{df_to_html(attr_tbl)}
<img src="data:image/png;base64,{img_feat}" style="max-width:700px">

<h3>4-2. 시간 lag별 attribution (이벤트 첨두 기준)</h3>
<img src="data:image/png;base64,{img_lag}" style="max-width:700px">

<h3>4-3. 과소추정 vs 과대추정 이벤트 층화</h3>
<img src="data:image/png;base64,{img_strat}" style="max-width:850px">

<h3>4-4. 유역별 attribution fraction × Q99 오차 상관 (p&lt;0.05)</h3>
{df_to_html(sig_tbl)}
<img src="data:image/png;base64,{img_basin}" style="max-width:700px">

<p><strong>핵심 발견:</strong></p>
<ul>
<li><strong>강수(Rainf)가 1위</strong> — 3-seed 중앙값 0.0159, 범위 [0.014, 0.020]. 안정적.</li>
<li><strong>비습도(Qair)가 강수에 근접한 2위</strong> (0.0157): LSTM이 대기 수분 상태를 극한 유량의 핵심 전조로 학습.</li>
<li><strong>CAPE 최하위</strong> (0.0043): event-level 강제력 분석과 일치 — 대류 불안정도는 Q99 예측에 미활용.</li>
<li><strong>PotEvap 의존도 높은 유역</strong>: Q99 bias ↓ (ρ=−0.28, p=0.009), under-frac ↑ (ρ=+0.28, p=0.011) — PotEvap에 의존 = 보수적 Q99 예측.</li>
<li><strong>Wind 의존도 높은 유역</strong>: med_rel_bias_delta ↑ (ρ≈+0.28, p≈0.01) — Q99가 model1 대비 더 개선.</li>
</ul>
"""

    md = f"""## 4. LSTM 입력 기여도 분석 — GradientInput Attribution (Analysis A)

Method: GradientInput (|∂q99/∂x_d| × |x_d|), CudaLSTM model2 epoch005, seq_length=336h.
seed111: 1,200 / seed222: 1,200 / seed444: 1,194 이벤트.

### 4-1. 3-seed 통합 feature importance

{df_to_md(attr_tbl)}

![Feature importance](figures/q99_lstm_feature_importance_multiseed.png)

### 4-2. 시간 lag별 attribution

![Temporal lag](figures/q99_lstm_temporal_lag_multiseed.png)

### 4-3. 과소추정 vs 과대추정 층화

![Stratified](figures/q99_lstm_attribution_stratified_multiseed.png)

### 4-4. 유역별 attribution × 오차 상관 (p<0.05)

{df_to_md(sig_tbl)}

![Basin attribution correlation](figures/q99_lstm_attribution_basin_correlation_q99_med_rel_bias.png)

**핵심 발견:**
- **강수(Rainf) 1위** — 3-seed 중앙값 0.0159, 안정적
- **비습도(Qair) 2위** (0.0157): LSTM이 대기 수분 상태를 극한 유량 전조로 학습
- **CAPE 최하위** (0.0043): 대류 불안정도 Q99 예측에 미활용
- **PotEvap 의존 유역**: Q99 bias ↓ (ρ=−0.28, p=0.009), under-frac ↑ — 보수적 예측
- **Wind 의존 유역**: med_rel_bias_delta ↑ (ρ≈+0.28) — Q99가 model1 대비 더 개선
"""
    return html, md


def build_conclusion() -> tuple[str, str]:
    html = """
<h2>5. 종합 해석 및 시사점</h2>

<h3>5-1. Q99 과대추정 편향의 원인</h3>
<ul>
<li>강한 단기 강우(고첨두 강도) 이벤트에서 Q99가 과대추정 → 모델이 강우 신호를 과민 반응</li>
<li>플래시성(unit_area_peak_p90 높은) 유역에서 bias 악화 — 짧고 강한 이벤트 패턴에 취약</li>
<li>선행 강우 높은 조건 → Q99 추가 과대추정 (antecedent moisture 이중 counting 가능성)</li>
</ul>

<h3>5-2. Q99가 잘 작동하는 조건</h3>
<ul>
<li>높은 Strahler 차수 / 높은 투수성 / 높은 사행도 유역 → bias 낮음</li>
<li>긴 지속시간 이벤트 → 첨두 오차 감소 (LSTM이 장기 누적 패턴을 잘 학습)</li>
<li>LSTM이 PotEvap에 의존하는 유역 → 보수적이지만 더 balanced 예측</li>
</ul>

<h3>5-3. LSTM이 학습한 신호</h3>
<ul>
<li>강수(Rainf)와 비습도(Qair)가 동등한 최우선 신호 — 대기 수분 상태 중요</li>
<li>CAPE는 학습하지 않음 — 대류 불안정도 표현이 부재하거나 신호 약함</li>
<li>시간 lag 분석: 이벤트 첨두 직전(0~24h) attribution 가장 높음 → 단기 강우 반응 지배적</li>
</ul>

<h3>5-4. 개선 방향</h3>
<ul>
<li>플래시성 유역 특화 보정 또는 유역 특성 기반 q99 예측 보정</li>
<li>CAPE 신호 활용 강화 (embedding 또는 auxiliary loss)</li>
<li>선행 기간 표현 개선 — 현재 336h(14일) lookback이 충분한지 검토</li>
</ul>
"""

    md = """## 5. 종합 해석 및 시사점

### 5-1. Q99 과대추정 편향의 원인
- 강한 단기 강우(고첨두 강도) → Q99 과대추정: 강우 신호 과민 반응
- 플래시성(unit_area_peak_p90 높음) 유역 bias 악화
- 선행 강우 높은 조건 → Q99 추가 과대추정

### 5-2. Q99가 잘 작동하는 조건
- 높은 Strahler 차수 / 투수성 / 사행도 유역 → bias 낮음
- 긴 지속시간 이벤트 → 첨두 오차 감소
- LSTM이 PotEvap 의존 유역 → 보수적이지만 balanced 예측

### 5-3. LSTM이 학습한 신호
- 강수(Rainf)와 비습도(Qair)가 동등한 최우선 신호 — 대기 수분 상태 중요
- CAPE 미활용 — 대류 불안정도 신호 약함
- 이벤트 첨두 직전(0–24h) attribution 최고 → 단기 강우 반응 지배적

### 5-4. 개선 방향
- 플래시성 유역 특화 보정 (유역 특성 기반 q99 예측 보정)
- CAPE 신호 활용 강화 (embedding 또는 auxiliary loss)
- 선행 기간 표현 개선 — 336h(14일) lookback 적정성 검토
"""
    return html, md


# ── render ────────────────────────────────────────────────────────────────────

CSS = """
body { font-family: "Noto Sans KR", "Apple SD Gothic Neo", sans-serif; max-width: 1100px; margin: 40px auto; padding: 0 24px; color: #222; line-height: 1.7; }
h1 { border-bottom: 3px solid #1f77b4; padding-bottom: 8px; }
h2 { border-left: 5px solid #1f77b4; padding-left: 12px; margin-top: 48px; }
h3 { color: #444; margin-top: 28px; }
table.table { border-collapse: collapse; margin: 16px 0; font-size: 0.88em; }
table.table th { background: #1f77b4; color: white; padding: 6px 12px; text-align: left; }
table.table td { padding: 5px 12px; border-bottom: 1px solid #ddd; }
table.table tr:nth-child(even) td { background: #f5f8fc; }
table.summary-table td.bad { color: #d62728; font-weight: bold; }
img { display: block; margin: 16px auto; border: 1px solid #ddd; border-radius: 4px; }
p { margin: 10px 0; }
ul { margin: 8px 0 16px; }
li { margin: 4px 0; }
.toc { background: #f5f8fc; border: 1px solid #cce; border-radius: 6px; padding: 16px 24px; margin: 24px 0; }
.toc a { color: #1f77b4; text-decoration: none; }
.toc a:hover { text-decoration: underline; }
"""

def render_html(sections: list[str]) -> str:
    body = "\n".join(sections)
    toc = """<div class="toc">
<strong>목차</strong>
<ol>
<li><a href="#s1">개요 및 주요 성능 지표</a></li>
<li><a href="#s2">유역 특성 × Q99 오차 상관 (Analysis B)</a></li>
<li><a href="#s3">이벤트 강제력 × Q99 오차 상관 (Analysis 3)</a></li>
<li><a href="#s4">LSTM 입력 기여도 분석 — GradientInput (Analysis A)</a></li>
<li><a href="#s5">종합 해석 및 시사점</a></li>
</ol>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Q99 예측 오차 원인 분석 보고서</title>
<style>{CSS}</style>
</head>
<body>
<h1>Q99 예측 오차 원인 분석 보고서</h1>
<p style="color:#888">DRBC holdout 85개 유역 · LSTM Model2 · 2014–2016 테스트 · 작성: 2026-05-25</p>
{toc}
{body}
</body>
</html>"""


def render_md(sections: list[str]) -> str:
    header = """# Q99 예측 오차 원인 분석 보고서

DRBC holdout 85개 유역 · LSTM Model2 · 2014–2016 테스트 · 작성: 2026-05-25

---
"""
    return header + "\n\n---\n\n".join(sections)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("── Loading tables …")
    d = load_tables()

    print("── Building sections …")
    h1, m1 = build_overview(d)
    h2, m2 = build_basin_drivers(d)
    h3, m3 = build_event_forcing(d)
    h4, m4 = build_lstm_attribution(d)
    h5, m5 = build_conclusion()

    print("── Rendering HTML …")
    html_out = OUT_DIR / "q99_analysis_report.html"
    html_out.write_text(render_html([h1, h2, h3, h4, h5]), encoding="utf-8")
    print(f"Saved: {html_out}  ({html_out.stat().st_size // 1024} KB)")

    print("── Rendering MD …")
    md_out = OUT_DIR / "q99_analysis_report.md"
    md_out.write_text(render_md([m1, m2, m3, m4, m5]), encoding="utf-8")
    print(f"Saved: {md_out}  ({md_out.stat().st_size // 1024} KB)")

    print("\nDone.")


if __name__ == "__main__":
    main()

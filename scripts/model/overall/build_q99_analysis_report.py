#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy>=2.0",
#   "pandas>=2.2",
#   "Pillow>=10.0",
# ]
# ///
"""Build Q99 analysis report (HTML + MD) — accessible to undergraduate level.

Outputs
-------
output/q99_analysis/q99_analysis_report.html   (self-contained, base64 figures)
output/q99_analysis/q99_analysis_report.md
"""
from __future__ import annotations

import base64
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
TABLE_DIR  = REPO_ROOT / "output/q99_analysis/tables"
FIG_DIR    = REPO_ROOT / "output/q99_analysis/figures"
OUT_DIR    = REPO_ROOT / "output/q99_analysis"

# ── utilities ────────────────────────────────────────────────────────────────

def fig_b64(name: str) -> str:
    p = FIG_DIR / name
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""

def img_html(name: str, caption: str = "", width: str = "720px") -> str:
    b64 = fig_b64(name)
    if not b64:
        return f'<p class="warn">[그림 없음: {name}]</p>'
    cap = f'<p class="caption">{caption}</p>' if caption else ""
    return f'<figure><img src="data:image/png;base64,{b64}" style="max-width:{width}">{cap}</figure>'

def img_md(name: str, caption: str = "") -> str:
    return f"![{caption}](figures/{name})\n*{caption}*\n" if caption else f"![{name}](figures/{name})\n"

def df_html(df: pd.DataFrame, ff: str = ".4f") -> str:
    return df.to_html(index=False, border=0, classes="table",
                      float_format=lambda x: f"{x:{ff}}")

def df_md(df: pd.DataFrame, ff: str = ".4f") -> str:
    cols = df.columns.tolist()
    lines = ["| " + " | ".join(cols) + " |",
             "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        cells = [f"{v:{ff}}" if isinstance(v, float) else str(v) for v in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)

# ── load tables ───────────────────────────────────────────────────────────────

def load() -> dict:
    return {
        "summary":    pd.read_csv(TABLE_DIR / "basin_q99_error_summary.csv"),
        "stable":     pd.read_csv(TABLE_DIR / "q99_stable_drivers.csv"),
        "event_corr": pd.read_csv(TABLE_DIR / "q99_event_forcing_correlation.csv"),
        "attr_ms":    pd.read_csv(TABLE_DIR / "q99_lstm_attribution_multiseed_summary.csv"),
        "basin_corr": pd.read_csv(TABLE_DIR / "q99_lstm_attribution_basin_correlation.csv"),
        "event_df":   pd.read_csv(TABLE_DIR / "q99_event_forcing_drivers.csv"),
    }

# ═══════════════════════════════════════════════════════════════════════════════
# Section builders
# ═══════════════════════════════════════════════════════════════════════════════

# ── 0. Research background ────────────────────────────────────────────────────

def sec0_background() -> tuple[str, str]:
    html = """
<h2 id="s0">0. 연구 배경 — 이 보고서가 답하려는 질문</h2>

<div class="box-info">
<strong>핵심 질문:</strong> 홍수 첨두 유량을 예측하는 딥러닝 모델(LSTM)이 어떤 상황에서,
왜 틀리는가? 그리고 무엇을 보고 예측하는가?
</div>

<h3>0-1. 왜 홍수 첨두를 예측하기 어려운가?</h3>
<p>
하천 유량은 평소에는 완만하게 변하지만, 폭우가 내리면 수 시간 안에 수십 배로 급증할 수 있습니다.
이 <strong>첨두 유량(peak flow)</strong>은 홍수 피해를 결정하는 핵심 지표입니다.
딥러닝(LSTM) 모델이 이를 예측하려 하지만, 특히 극단적으로 높은 유량(상위 1%에 해당하는 Q99)에서
모델이 틀리는 경우가 많습니다.
</p>

<h3>0-2. Q99 quantile 예측이란?</h3>
<p>
이 연구에서 Model 2(확률적 LSTM)는 단순히 "예측값 하나"를 내는 게 아니라,
<strong>q50(중앙값), q90, q95, q99(99번째 백분위수)</strong>를 동시에 예측합니다.
q99 예측은 "실제 유량이 이 값을 넘을 확률이 1%"라는 상한 경계를 의미합니다.
즉, q99 예측은 보통보다 <em>훨씬 높은 값</em>을 예측해야 합니다.
</p>

<table class="table">
<thead><tr><th>비교 대상</th><th>모델 종류</th><th>예측 방식</th></tr></thead>
<tbody>
<tr><td>Model 1 (baseline)</td><td>결정론적 LSTM</td><td>단일 예측값 (점 추정)</td></tr>
<tr><td>Model 2 (주 분석 대상)</td><td>확률적 quantile LSTM</td><td>q50, q90, q95, q99 동시 예측</td></tr>
</tbody>
</table>

<h3>0-3. 분석 대상 데이터</h3>
<ul>
<li><strong>지역:</strong> DRBC(Delaware River Basin Commission) 유역 내 <strong>85개 유역</strong></li>
<li><strong>기간:</strong> 테스트 기간 2014–2016 (학습 2000–2010, 검증 2011–2013)</li>
<li><strong>시간 해상도:</strong> 시간 단위(hourly)</li>
<li><strong>seed:</strong> 111 / 222 / 444 (동일 모델을 다른 난수로 3번 훈련 → 결과 안정성 확인)</li>
</ul>

<h3>0-4. 세 가지 분석 방법</h3>
<table class="table">
<thead><tr><th>분석</th><th>질문</th><th>방법</th></tr></thead>
<tbody>
<tr><td><strong>Analysis B</strong></td><td>어떤 유역 특성이 Q99 오차를 만드는가?</td><td>유역 정적 속성 × 오차 Spearman 상관</td></tr>
<tr><td><strong>Analysis 3</strong></td><td>어떤 기상 조건의 이벤트에서 Q99가 틀리는가?</td><td>이벤트별 강제력 특성 × 오차 Spearman 상관</td></tr>
<tr><td><strong>Analysis A</strong></td><td>LSTM이 예측할 때 실제로 무엇을 가장 많이 "보는가"?</td><td>GradientInput attribution (기울기 기반 귀인)</td></tr>
</tbody>
</table>
"""

    md = """## 0. 연구 배경 — 이 보고서가 답하려는 질문

> **핵심 질문:** 홍수 첨두 유량을 예측하는 딥러닝 모델(LSTM)이 어떤 상황에서, 왜 틀리는가?

### 0-1. 왜 홍수 첨두를 예측하기 어려운가?

하천 유량은 평소에는 완만하게 변하지만, 폭우 시 수 시간 내 수십 배로 급증할 수 있습니다.
이 **첨두 유량(peak flow)**은 홍수 피해를 결정하는 핵심 지표이며,
딥러닝 모델이 특히 극단적으로 높은 유량(상위 1%, Q99)에서 오차가 큰 경우가 많습니다.

### 0-2. Q99 quantile 예측이란?

Model 2(확률적 LSTM)는 q50·q90·q95·q99를 동시에 예측합니다.
q99 예측은 "실제 유량이 이 값을 넘을 확률이 1%"라는 상한 경계를 의미합니다.

| 비교 대상 | 모델 종류 | 예측 방식 |
|-----------|-----------|-----------|
| Model 1 (baseline) | 결정론적 LSTM | 단일 점 추정 |
| Model 2 (주 분석 대상) | 확률적 quantile LSTM | q50, q90, q95, q99 동시 예측 |

### 0-3. 분석 대상

- **지역:** DRBC 유역 내 85개 유역
- **기간:** 테스트 2014–2016, 학습 2000–2010, 검증 2011–2013
- **seed:** 111 / 222 / 444 (결과 안정성 검증용)

### 0-4. 세 가지 분석 방법

| 분석 | 질문 | 방법 |
|------|------|------|
| Analysis B | 어떤 유역 특성이 Q99 오차를 만드는가? | 유역 속성 × 오차 Spearman 상관 |
| Analysis 3 | 어떤 기상 조건에서 Q99가 틀리는가? | 이벤트 강제력 × 오차 Spearman 상관 |
| Analysis A | LSTM이 실제로 무엇을 "보는가"? | GradientInput attribution |
"""
    return html, md


# ── 1. Performance overview ───────────────────────────────────────────────────

def sec1_overview(d: dict) -> tuple[str, str]:
    s = d["summary"]
    q_bias   = s["q99_med_rel_bias"].median()
    m1_bias  = s["model1_med_rel_bias"].median()
    q_uf     = s["q99_under_frac"].median()
    m1_uf    = s["model1_under_frac"].median()
    delta    = s["med_rel_bias_delta"].median()
    n        = len(s)
    n_imp    = (s["med_rel_bias_delta"] > 0).sum()
    n_worse  = n - n_imp

    # describe table
    desc = s[["q99_med_rel_bias","model1_med_rel_bias",
              "q99_under_frac","model1_under_frac","med_rel_bias_delta"]].describe().round(3)
    desc.index.name = "통계"

    html = f"""
<h2 id="s1">1. Q99 예측 성능 개요</h2>

<h3>1-1. 주요 지표 정의</h3>
<div class="box-def">
<dl>
<dt>Median Relative Bias (중앙 상대 편향)</dt>
<dd>극단 유량 시점에서 예측값이 실제값 대비 얼마나 크거나 작은지를 비율로 나타낸 중앙값.<br>
공식: <code>median((예측 − 실제) / 실제)</code> at obs ≥ Q99 threshold<br>
→ 양수 = 과대추정(overestimation), 음수 = 과소추정(underestimation).</dd>

<dt>Under-Fraction (과소추정 비율)</dt>
<dd>극단 유량 시점 중 예측값이 실제값보다 낮았던 시점의 비율.<br>
→ 1.0에 가까울수록 거의 항상 과소추정, 0에 가까울수록 거의 항상 과대추정.</dd>

<dt>Bias Delta (model1_bias − q99_bias)</dt>
<dd>Model 1 대비 Q99 모델의 bias 개선량.<br>
→ 양수 = Q99가 Model 1보다 덜 편향됨(개선), 음수 = Q99가 더 편향됨(악화).</dd>
</dl>
</div>

<h3>1-2. 85개 유역 중앙값 비교</h3>
<table class="table">
<thead><tr><th>지표</th><th>Q99 (model2)</th><th>Model 1 (baseline)</th><th>해석</th></tr></thead>
<tbody>
<tr>
  <td>Median Relative Bias</td>
  <td class="bad">{q_bias:+.3f} (+{q_bias*100:.1f}%)</td>
  <td>{m1_bias:+.3f} ({m1_bias*100:.1f}%)</td>
  <td>Q99 모델이 오히려 <strong>과대추정 편향</strong> 더 강함</td>
</tr>
<tr>
  <td>Under-Fraction</td>
  <td class="good">{q_uf:.3f} ({q_uf*100:.1f}%)</td>
  <td class="bad">{m1_uf:.3f} ({m1_uf*100:.1f}%)</td>
  <td>Q99 모델이 과소추정 <strong>대폭 감소</strong> ✓</td>
</tr>
<tr>
  <td>Bias Delta (개선량 중앙값)</td>
  <td colspan="2" style="text-align:center">{delta:+.3f}
    ({n_imp}/{n} 유역 개선, {n_worse}/{n} 유역 악화)</td>
  <td>절반 이상의 유역에서 Q99 bias <strong>악화</strong></td>
</tr>
</tbody>
</table>

<div class="box-warn">
<strong>⚠ 핵심 긴장 관계:</strong>
Q99 모델은 "과소추정 빈도"를 줄이는 데 성공했지만(under-fraction 84% → 43%),
그 대가로 "과대추정 편향"이 크게 증가했습니다(bias −0.47 → +0.12).
즉, "너무 낮게 예측하는" 문제는 해결됐지만 "너무 높게 예측하는" 새로운 문제가 생겼습니다.
</div>

<h3>1-3. 전체 분포 통계 (85개 유역 × seed 중앙값)</h3>
{df_html(desc.reset_index(), ".3f")}
<p class="caption">Min/Max 값의 범위가 매우 넓음 → 유역별 편차가 극단적으로 큼. 이것이 분석 동기.</p>
"""

    md = f"""## 1. Q99 예측 성능 개요

### 1-1. 주요 지표 정의

- **Median Relative Bias**: `median((예측−실제)/실제)` at obs≥Q99 threshold. 양수=과대추정, 음수=과소추정.
- **Under-Fraction**: 극단 시점 중 예측 < 실제인 비율.
- **Bias Delta**: model1_bias − q99_bias. 양수=Q99 개선, 음수=Q99 악화.

### 1-2. 85개 유역 중앙값 비교

| 지표 | Q99 (model2) | Model 1 | 해석 |
|------|-------------|---------|------|
| Median Relative Bias | {q_bias:+.3f} | {m1_bias:+.3f} | Q99가 과대추정 편향 더 강함 |
| Under-Fraction | {q_uf:.3f} | {m1_uf:.3f} | Q99가 과소추정 대폭 감소 ✓ |
| Bias Delta 중앙값 | {delta:+.3f} ({n_imp}/{n} 개선) | — | 절반 이상 유역에서 bias 악화 |

> ⚠ **핵심 긴장 관계:** Q99는 과소추정 빈도를 줄였지만(84%→43%) 과대추정 편향이 증가했습니다(−0.47→+0.12).

### 1-3. 전체 분포 통계

{df_md(desc.reset_index(), ".3f")}
"""
    return html, md


# ── 2. Basin characteristics ──────────────────────────────────────────────────

def sec2_basin(d: dict) -> tuple[str, str]:
    sd = d["stable"]

    bias_top = sd[sd["target"] == "q99_med_rel_bias"].head(10)[
        ["attribute", "rho_median", "pval_median", "direction"]].copy()
    bias_top.columns = ["유역 속성", "Spearman ρ", "p-value", "방향"]

    uf_top = sd[sd["target"] == "q99_under_frac"].head(6)[
        ["attribute", "rho_median", "pval_median", "direction"]].copy()
    uf_top.columns = ["유역 속성", "Spearman ρ", "p-value", "방향"]

    delta_top = sd[sd["target"] == "med_rel_bias_delta"].head(6)[
        ["attribute", "rho_median", "pval_median", "direction"]].copy()
    delta_top.columns = ["유역 속성", "Spearman ρ", "p-value", "방향"]

    html = f"""
<h2 id="s2">2. Analysis B — 유역 특성 × Q99 오차 상관 분석</h2>

<h3>2-1. 방법론 설명</h3>
<div class="box-def">
<p><strong>Spearman 순위 상관계수(ρ)</strong>란?</p>
<p>두 변수가 같은 방향으로 움직이는지 측정합니다. ρ = +1이면 완벽히 비례, ρ = −1이면 완벽히 반비례, ρ = 0이면 무관계.
일반적으로 |ρ| &gt; 0.3이면 의미 있는 관계, &gt; 0.5이면 강한 관계로 봅니다.</p>
<p><strong>"3-seed stable"</strong> 조건: 동일한 모델을 seed 111/222/444로 3번 훈련했을 때
<em>모든 seed에서 같은 방향(+/−)으로 유의미한 상관</em>이 나타나야 "안정적(stable)"로 분류합니다.
한 번의 우연한 결과가 아님을 보장합니다.</p>
</div>

<p>85개 유역의 정적 속성(지형, 토양, 토지피복, 하천 형태 등 30여 개 변수)과
Q99 오차 지표 간 Spearman 상관을 계산했습니다.</p>

<h3>2-2. Q99 Median Relative Bias — 주요 stable drivers (top-10)</h3>
{df_html(bias_top)}

<div class="interpretation">
<h4>그림으로 이해하기</h4>
{img_html("q99_driver_correlation_bar.png",
    "그림 2-1. 유역 속성별 Spearman ρ. 파란색 = 해당 속성이 높을수록 Q99 bias 증가(과대추정), 빨간색 = bias 감소. 오차 막대는 3 seed 간 변동 범위.",
    "720px")}
{img_html("q99_quartile_radar.png",
    "그림 2-2. Q1(bias 최악 하위 25%) vs Q4(bias 최우수 상위 25%) 유역 속성 프로파일. 0.5 = 해당 속성의 전체 범위에서 중간값.",
    "520px")}
{img_html("q99_driver_scatter_top4.png",
    "그림 2-3. 주요 물리 속성 vs q99_med_rel_bias scatter. 점 하나 = 유역 한 개.",
    "900px")}
</div>

<h3>2-3. 주요 발견 해석</h3>
<div class="finding-cards">

<div class="card-neg">
<h4>✅ Q99 오차가 <em>낮은</em> 유역 특성 (bias 개선, 음의 ρ)</h4>
<ul>
<li><strong>Strahler 하천 차수(STRAHLER_MAX) ↑, ρ=−0.46</strong><br>
Strahler 차수는 지류가 합류할수록 증가하는 지표입니다. 차수가 높다 = 더 큰 본류, 복잡한 하천망.
큰 하천은 홍수 반응이 느리고(유역 집수 시간 길다), 반응 패턴이 규칙적 → LSTM이 예측하기 쉽습니다.</li>
<li><strong>토양 투수성(PERMAVE) ↑, ρ=−0.44</strong><br>
토양이 투수성이 높으면 빗물이 천천히 스며들어 유출이 완만합니다.
급격한 첨두가 적으니 Q99 모델도 안정적으로 예측합니다.</li>
<li><strong>하천 사행도(MAINSTEM_SINUOUSITY) ↑, ρ=−0.44</strong><br>
꾸불꾸불한 하천 = 홍수파가 천천히 전달 = 예측 패턴 규칙적.</li>
<li><strong>토양 수문 A그룹 비율(HGA) ↑, ρ=−0.36</strong><br>
HGA = 투수성이 가장 높은 모래/자갈 토양. 같은 맥락으로 완만한 유출 반응.</li>
<li><strong>인공수로 비율(ARTIFPATH_PCT) ↑, ρ=−0.31</strong><br>
인공 수로가 많으면 흐름이 규칙화 → 예측 패턴 단순화.</li>
</ul>
</div>

<div class="card-pos">
<h4>⚠️ Q99 오차가 <em>높은</em> 유역 특성 (bias 악화, 양의 ρ)</h4>
<ul>
<li><strong>단위면적 첨두 P90(unit_area_peak_p90) ↑, ρ=+0.39</strong><br>
단위면적당 90번째 백분위 첨두가 크다 = "플래시(flash)" 특성 강한 유역.
짧고 강렬한 홍수가 자주 발생 → LSTM이 극단 사례 일반화에 실패.</li>
<li><strong>단위면적 첨두 중앙값(unit_area_peak_median) ↑, ρ=+0.36</strong><br>
평균적으로도 첨두가 큰 유역 = 전반적으로 반응성이 강한 유역.</li>
<li><strong>Q99 이벤트 빈도(q99_event_frequency) ↑, ρ=+0.32</strong><br>
Q99 초과 이벤트가 자주 일어나는 유역에서 오히려 Q99 예측이 더 나쁨 —
"자주 일어난다" ≠ "예측하기 쉽다".</li>
</ul>
</div>
</div>

<h3>2-4. Under-Fraction 관련 stable drivers (top-6)</h3>
{df_html(uf_top)}

<h3>2-5. Bias Delta (Q99 개선량) 관련 stable drivers (top-6)</h3>
{df_html(delta_top)}
<p>Runoff avg(RUNAVE7100) ↑, SLOPE ↑인 유역에서 Q99가 model1 대비 더 개선됩니다.</p>
"""

    md = f"""## 2. Analysis B — 유역 특성 × Q99 오차 상관 분석

### 2-1. 방법론: Spearman 상관 + 3-seed stable 조건

**Spearman ρ**: |ρ|>0.3 = 의미 있는 관계, >0.5 = 강한 관계.
**3-seed stable**: seed 111/222/444 모두 같은 방향 → 우연 아님.

### 2-2. Q99 Median Relative Bias — top-10 stable drivers

{df_md(bias_top)}

### 2-3. 시각화

{img_md("q99_driver_correlation_bar.png", "그림 2-1. 유역 속성별 Spearman ρ")}
{img_md("q99_quartile_radar.png", "그림 2-2. Q1(worst) vs Q4(best) 유역 프로파일")}
{img_md("q99_driver_scatter_top4.png", "그림 2-3. 물리 속성 vs q99_med_rel_bias scatter")}

### 2-4. 주요 발견 해석

**Q99 오차 낮은 유역 특성 (음의 ρ):**
- **Strahler 차수 ↑** (ρ=−0.46): 큰 본류, 완만한 반응 → 예측 쉬움
- **토양 투수성 ↑** (ρ=−0.44): 빗물이 천천히 스며듦 → 급격한 첨두 적음
- **하천 사행도 ↑** (ρ=−0.44): 꾸불꾸불 = 홍수파 지연 = 예측 패턴 규칙적
- **토양 HGA ↑** (ρ=−0.36): 최고 투수성 토양, 같은 맥락
- **인공수로 비율 ↑** (ρ=−0.31): 흐름 규칙화 → 단순 패턴

**Q99 오차 높은 유역 특성 (양의 ρ):**
- **단위면적 첨두 P90 ↑** (ρ=+0.39): 플래시 특성 강한 유역 → LSTM 취약
- **Q99 이벤트 빈도 ↑** (ρ=+0.32): 자주 일어남 ≠ 예측 쉬움

### 2-5. Under-Fraction top-6

{df_md(uf_top)}

### 2-6. Bias Delta top-6

{df_md(delta_top)}
"""
    return html, md


# ── 3. Event forcing ──────────────────────────────────────────────────────────

def sec3_event(d: dict) -> tuple[str, str]:
    ec = d["event_corr"]
    ev = d["event_df"]
    n_events = len(ev[ev["seed"] == 111])
    n_total = len(ev)

    peak_s = ec[(ec["target"] == "q99_peak_rel_error") & ec["stable"]][
        ["feature", "rho_median", "pval_median"]].copy()
    peak_s.columns = ["강제력 특성", "Spearman ρ (중앙값)", "p-value"]

    uf_s = ec[(ec["target"] == "q99_under_frac_event") & ec["stable"]][
        ["feature", "rho_median", "pval_median"]].copy()
    uf_s.columns = ["강제력 특성", "Spearman ρ (중앙값)", "p-value"]

    html = f"""
<h2 id="s3">3. Analysis 3 — 이벤트 강제력 × Q99 오차 상관</h2>

<h3>3-1. 방법론 설명</h3>
<div class="box-def">
<p><strong>이벤트 정의:</strong> 유역의 obs Q99 임계값(basin-specific 99th percentile)을 초과하는
연속 시점들을 하나의 "극단 유량 이벤트"로 정의합니다. 72시간 이상 gap이 있으면 별도 이벤트.</p>
<p><strong>강제력 특성:</strong> 각 이벤트에 대해 NC 파일에서 추출한 기상 변수들:</p>
<ul>
<li>event_peak_rainf_intensity: 이벤트 기간 중 시간당 최대 강우량</li>
<li>event_total_rainf: 이벤트 기간 총 강우량</li>
<li>event_duration_h: 이벤트 지속 시간(시간)</li>
<li>antecedent_rainf_5d: 이벤트 시작 5일 전까지의 누적 강우(선행 강우)</li>
<li>event_mean_cape / event_max_cape: 대류 가용 위치 에너지(뇌우 강도 지표)</li>
<li>antecedent_tair_mean: 선행 기간 평균 기온</li>
</ul>
<p><strong>분석 규모:</strong> seed 111 기준 {n_events}개, 3 seed 합계 {n_total}개 이벤트.</p>
</div>

<h3>3-2. 첨두 상대 오차(q99_peak_rel_error) — stable drivers</h3>
{df_html(peak_s)}
{img_html("q99_event_forcing_correlation_bar_q99_peak_rel_error.png",
    "그림 3-1. 강제력 특성별 Spearman ρ vs q99_peak_rel_error. 양수 = 해당 조건에서 과대추정 심화.",
    "680px")}

<h3>3-3. 과소추정 비율(q99_under_frac_event) — stable drivers</h3>
{df_html(uf_s)}
{img_html("q99_event_forcing_correlation_bar_q99_under_frac_event.png",
    "그림 3-2. 강제력 특성별 Spearman ρ vs q99_under_frac_event. 음수 = 해당 조건에서 과소추정 감소(즉 과대추정 증가).",
    "680px")}
{img_html("q99_event_forcing_scatter.png",
    "그림 3-3. 상위 stable driver들의 scatter plot (seed111, ~1,200 이벤트). 점 하나 = 극단 유량 이벤트 한 건.",
    "900px")}

<h3>3-4. 주요 발견 해석</h3>
<div class="finding-cards">
<div class="card-pos">
<h4>강한 강우 이벤트 → 과대추정 심화</h4>
<p><strong>첨두 강우 강도(ρ=+0.20)와 총 강우량(ρ=+0.15)</strong>이 높을수록
Q99 첨두 예측이 실제보다 과도하게 높아집니다.</p>
<p><em>왜?</em> LSTM이 강한 강우 신호를 보면 Q99를 매우 높게 예측하는데,
실제 첨두는 그만큼 높지 않은 경우가 많습니다.
강우 → 유출 변환 과정에서 손실(침투, 증발 등)이 있기 때문입니다.</p>
</div>
<div class="card-neg">
<h4>긴 이벤트 → 과대추정 감소</h4>
<p><strong>이벤트 지속시간(ρ=−0.14)</strong>이 길수록 첨두 오차가 줄어듭니다.</p>
<p><em>왜?</em> 강우가 오래 지속되는 층상형 강수 이벤트는 반응이 완만합니다.
LSTM이 장기 패턴을 더 잘 학습했기 때문으로 해석됩니다.</p>
</div>
<div class="card-neutral">
<h4>CAPE(대류 불안정도)는 stable driver 아님</h4>
<p>뇌우의 강도를 나타내는 CAPE가 Q99 오차와 유의미한 관계를 보이지 않았습니다.
이는 이후 LSTM attribution 분석(Section 4)에서 CAPE attribution이
최하위인 결과와 일치합니다.</p>
</div>
<div class="card-neutral">
<h4>선행 강우(ρ=+0.10) — 약한 양의 관계</h4>
<p>이벤트 5일 전 강우가 많을수록 Q99가 과대추정되는 경향이 있습니다.
토양이 이미 포화 상태일 때 LSTM이 Q99를 더 높게 예측하지만,
실제 첨두는 선행 강우와 비례하지 않는 경우가 있습니다.</p>
</div>
</div>
"""

    md = f"""## 3. Analysis 3 — 이벤트 강제력 × Q99 오차 상관

### 3-1. 방법론

- **이벤트**: obs≥basin Q99 임계값인 연속 시점, 72h gap 이상이면 별도 이벤트
- **분석 규모**: seed111 기준 {n_events}개, 3 seed 합계 {n_total}개
- **강제력 특성**: 첨두 강도, 총 강우, 지속시간, 선행 5일 강우, CAPE, 기온

### 3-2. q99_peak_rel_error stable drivers

{df_md(peak_s)}

### 3-3. q99_under_frac_event stable drivers

{df_md(uf_s)}

### 3-4. 시각화

{img_md("q99_event_forcing_correlation_bar_q99_peak_rel_error.png", "그림 3-1. 첨두 오차 상관")}
{img_md("q99_event_forcing_correlation_bar_q99_under_frac_event.png", "그림 3-2. Under-fraction 상관")}
{img_md("q99_event_forcing_scatter.png", "그림 3-3. Top driver scatter")}

### 3-5. 주요 발견 해석

- **강한 강우(ρ=+0.20) → 과대추정 심화**: LSTM이 강우 신호에 과민 반응
- **긴 이벤트(ρ=−0.14) → 오차 감소**: 완만한 층상형 강수 패턴 잘 학습
- **CAPE = stable driver 아님**: 대류 불안정도는 Q99 오차와 무관
- **선행 강우(ρ=+0.10)**: 토양 포화 상태 시 Q99 과대추정 경향
"""
    return html, md


# ── 4. LSTM attribution ───────────────────────────────────────────────────────

def sec4_attribution(d: dict) -> tuple[str, str]:
    attr = d["attr_ms"].copy()
    attr_tbl = attr[["feature", "attr_median", "attr_min", "attr_max"]].copy()
    attr_tbl.columns = ["입력 변수", "Attribution 중앙값", "최솟값(seed min)", "최댓값(seed max)"]

    bc = d["basin_corr"]
    sig = bc[(bc["pval"] < 0.05) & (bc["type"] == "fraction")].sort_values(
        "rho", key=abs, ascending=False)
    sig_tbl = sig[["feature", "target", "rho", "pval"]].copy()
    sig_tbl.columns = ["변수", "오차 지표", "ρ", "p-value"]

    n_events = {"111": 1200, "222": 1200, "444": 1194}

    html = f"""
<h2 id="s4">4. Analysis A — LSTM 입력 기여도 분석 (GradientInput Attribution)</h2>

<h3>4-1. 방법론 설명 — Attribution이란?</h3>
<div class="box-def">
<p>LSTM은 블랙박스처럼 동작합니다. 336시간(14일) 분량의 기상 입력을 받아 Q99 예측을 내놓는데,
어떤 변수를 "얼마나 보고" 예측했는지 알 수 없습니다.</p>
<p><strong>GradientInput Attribution</strong>은 이를 근사적으로 파악하는 방법입니다:</p>
<ol>
<li>입력 텐서 <code>x_d</code> (336 시간 × 11 기상 변수)에 <code>requires_grad=True</code> 설정</li>
<li>Forward pass → Q99 예측값 계산</li>
<li>Backward pass → 각 입력 원소에 대한 기울기(gradient) 계산</li>
<li>Attribution = |기울기 × 입력값| → 값이 클수록 해당 변수의 해당 시점이 예측에 많이 기여</li>
</ol>
<p>이 분석에서는 각 극단 이벤트의 이벤트 종료 시점을 끝으로 하는 336h 창을 사용합니다.</p>
<p><strong>모델 구성:</strong> CudaLSTM, hidden_size=128, epoch005, 11 동적 입력 + 8 정적 입력(매 시각 반복).</p>
<p><strong>분석 규모:</strong> seed111 1,200 / seed222 1,200 / seed444 1,194 이벤트 처리.</p>
</div>

<h3>4-2. 3-seed 통합 Feature Importance 순위</h3>
{df_html(attr_tbl)}
{img_html("q99_lstm_feature_importance_multiseed.png",
    "그림 4-1. 3-seed 통합 feature importance. 막대 = seed 중앙값, 오차막대 = seed min/max 범위. 오른쪽이 중요한 변수.",
    "700px")}

<div class="box-warn">
<strong>놀라운 발견:</strong> 비습도(Qair)가 강수량(Rainf)과 거의 같은 수준의 Attribution을 보입니다.
LSTM은 "얼마나 비가 왔는가"만큼 "대기가 얼마나 수분을 머금고 있는가"를 Q99 예측에 활용하고 있습니다.
이는 대기 수분 상태가 강우 지속성 및 강도에 대한 중요한 맥락을 제공하기 때문입니다.
</div>

<h3>4-3. 시간 Lag 별 Attribution — LSTM이 얼마나 "과거를 보는가"</h3>
{img_html("q99_lstm_temporal_lag_multiseed.png",
    "그림 4-2. 이벤트 첨두로부터 몇 시간 전 입력이 얼마나 기여하는지. x축 왼쪽이 더 먼 과거. 오른쪽(0h = 첨두 시점)에 attribution이 집중됨.",
    "700px")}
<p>
이벤트 첨두 직전(0–48h) attribution이 압도적으로 높고, 과거로 갈수록 빠르게 감소합니다.
LSTM이 Q99 첨두 예측을 위해 주로 <strong>단기(최근 1–2일) 강우 신호</strong>에 의존하며,
선행 조건(수주 전 상태)은 상대적으로 적게 활용함을 의미합니다.
</p>

<h3>4-4. 과소추정 vs 과대추정 이벤트 비교</h3>
{img_html("q99_lstm_attribution_stratified_multiseed.png",
    "그림 4-3. Q99가 과소추정한 이벤트(under-frac≥0.5)와 과대추정한 이벤트의 feature attribution 비교 (3-seed 중앙값).",
    "860px")}
<p>두 그룹 간 attribution 패턴 차이가 크지 않습니다. 즉, 어떤 변수를 많이 보느냐보다는
<strong>해당 값의 크기(이벤트 강도)</strong>가 과소/과대추정을 결정하는 주된 요인입니다.
</p>

<h3>4-5. 유역별 Attribution Fraction × 오차 지표 상관 (p&lt;0.05)</h3>
<p>
각 유역의 11개 변수 attribution을 <em>비율(fraction)</em>로 정규화한 뒤
(= 전체 attribution 중 해당 변수가 차지하는 비중),
유역별 오차 지표와 Spearman 상관을 계산했습니다.
</p>
{df_html(sig_tbl)}
{img_html("q99_lstm_attribution_basin_correlation_q99_med_rel_bias.png",
    "그림 4-4. 변수별 attribution fraction vs q99_med_rel_bias. 각 점 = 유역 한 개.",
    "700px")}

<div class="finding-cards">
<div class="card-neg">
<h4>PotEvap 의존 유역 (ρ=−0.28): Q99 bias 낮음</h4>
<p>증발산(PotEvap)에 attribution이 집중된 유역에서 Q99 median relative bias가 낮습니다.
이런 유역은 여름철 열파 이벤트나 건기-우기 전환 패턴이 강하며,
증발산 정보가 토양 수분 상태를 잘 반영하여 LSTM이 더 안정적으로 Q99를 예측합니다.</p>
</div>
<div class="card-neg">
<h4>PotEvap 의존 유역 (ρ=+0.28): under-fraction 높음</h4>
<p>동시에 under-fraction(과소추정 비율)은 높습니다. 즉,
PotEvap에 의존하는 유역의 Q99는 median bias는 낮지만 첨두에서 과소추정하는 경향이 있습니다.
"평균적으로 좋지만 극단치 첨두에서는 부족"한 패턴입니다.</p>
</div>
<div class="card-pos">
<h4>Wind 의존 유역 (ρ=+0.28~0.29): Bias Delta 높음</h4>
<p>바람(Wind_E, Wind_N)에 attribution이 높은 유역에서 Q99가 model1 대비 더 많이 개선됩니다.
바람 패턴이 풍상/풍하 효과(orographic precipitation)를 반영하는 유역에서
Q99 모델이 model1보다 효과적으로 극단 유량을 포착합니다.</p>
</div>
</div>
"""

    md = f"""## 4. Analysis A — LSTM 입력 기여도 분석 (GradientInput Attribution)

### 4-1. 방법론: GradientInput Attribution

1. 입력 `x_d` (336h × 11변수)에 `requires_grad=True` 설정
2. Forward pass → Q99 예측
3. Backward pass → 기울기 계산
4. Attribution = |기울기 × 입력값| — 클수록 해당 변수/시점이 예측에 더 기여

모델: CudaLSTM, hidden_size=128, epoch005, seed 111/222/444.

### 4-2. 3-seed 통합 Feature Importance

{df_md(attr_tbl)}

{img_md("q99_lstm_feature_importance_multiseed.png", "그림 4-1. 3-seed 통합 feature importance")}

> **놀라운 발견:** 비습도(Qair)가 강수량(Rainf)과 거의 동등한 1위. LSTM은 "대기 수분 상태"를 Q99 예측의 핵심 신호로 활용.

### 4-3. 시간 Lag별 Attribution

{img_md("q99_lstm_temporal_lag_multiseed.png", "그림 4-2. 이벤트 첨두로부터 시간 lag별 attribution")}

이벤트 첨두 직전(0–48h)에 attribution 집중. LSTM이 주로 **단기(1–2일) 강우 신호**에 의존.

### 4-4. 과소/과대추정 이벤트 비교

{img_md("q99_lstm_attribution_stratified_multiseed.png", "그림 4-3. 층화 attribution 비교")}

두 그룹 간 패턴 차이 작음 → 변수 종류보다 **이벤트 강도**가 결정적.

### 4-5. 유역별 Attribution × 오차 상관 (p<0.05)

{df_md(sig_tbl)}

{img_md("q99_lstm_attribution_basin_correlation_q99_med_rel_bias.png", "그림 4-4. Basin attribution fraction vs Q99 bias")}

- **PotEvap 의존 유역**: bias 낮음(ρ=−0.28), but under-fraction 높음(ρ=+0.28) — 보수적이지만 balanced
- **Wind 의존 유역**: Bias Delta ↑ (ρ=+0.28~0.29) — Q99가 model1 대비 더 개선
"""
    return html, md


# ── 5. Conclusion ─────────────────────────────────────────────────────────────

def sec5_conclusion() -> tuple[str, str]:
    html = """
<h2 id="s5">5. 종합 해석 및 시사점</h2>

<h3>5-1. 세 분석을 연결하는 일관된 서사</h3>
<div class="box-info">
<p>
세 가지 분석 결과는 서로 일관된 그림을 그립니다:
</p>
<p>
Q99 모델은 <strong>강한 강우 신호(고강도 Rainf + 대기 수분 Qair)</strong>를 주로 보고
Q99를 높게 예측합니다(Attribution 분석). 실제로 강한 강우 이벤트에서 Q99가 과대추정되며
(Event Forcing 분석), 특히 반응이 빠르고 플래시 특성이 강한 유역에서 이 과대추정이 심합니다
(Basin 특성 분석).
</p>
<p>
반대로, 하천 구조가 복잡하고(Strahler 차수 높음), 토양이 투수적이며, 이벤트가 오래 지속될수록
Q99는 안정적으로 예측합니다. 이런 유역에서는 LSTM이 학습한 완만한 수문 반응 패턴이
실제와 잘 맞기 때문입니다.
</p>
</div>

<h3>5-2. Q99 모델의 강점과 약점 정리</h3>
<table class="table">
<thead><tr><th>구분</th><th>조건</th><th>Q99 성능</th></tr></thead>
<tbody>
<tr><td rowspan="3">✅ 강점</td><td>투수성 높은 토양 유역</td><td>bias 낮음, 안정적</td></tr>
<tr><td>긴 지속 강우 이벤트</td><td>첨두 오차 감소</td></tr>
<tr><td>복잡 하천망(Strahler ↑) 유역</td><td>과소추정 적음</td></tr>
<tr><td rowspan="3">⚠️ 약점</td><td>플래시 특성 유역</td><td>과대추정 심화</td></tr>
<tr><td>고강도 단기 강우 이벤트</td><td>Q99 과도하게 높게 예측</td></tr>
<tr><td>선행 강우 많은 조건</td><td>추가적 과대추정</td></tr>
</tbody>
</table>

<h3>5-3. LSTM이 학습하지 못한 것</h3>
<ul>
<li><strong>CAPE(대류 불안정도) 활용 실패:</strong> 세 분석 모두에서 CAPE가 Q99 오차 및 예측과 무관합니다.
뇌우성 극단 강수의 특성이 모델에 반영되지 않고 있습니다.</li>
<li><strong>장기 선행 조건의 과소활용:</strong> Attribution의 시간 lag 분석에서 1–2일 이내 신호가
지배적이며, 수주 전의 토양 수분·지하수 상태 등은 거의 활용되지 않습니다.
이는 336h(14일) lookback이 충분한지 의문을 제기합니다.</li>
<li><strong>플래시 이벤트 특수성 미학습:</strong> 짧고 강한 이벤트가 특히 어렵습니다.
이는 학습 데이터에서 이런 이벤트의 표본이 적거나, 입력 시간 해상도(1h)가 충분하지 않기 때문일 수 있습니다.</li>
</ul>

<h3>5-4. 개선 방향 제안</h3>
<table class="table">
<thead><tr><th>문제</th><th>제안</th></tr></thead>
<tbody>
<tr>
  <td>플래시 유역 과대추정</td>
  <td>유역 특성(unit_area_peak_p90, Strahler) 기반 사후 보정 레이어 추가 또는 플래시 유역 전용 모델 분기</td>
</tr>
<tr>
  <td>CAPE 미활용</td>
  <td>CAPE를 auxiliary input으로 강화하거나 attention 메커니즘을 통해 convective vs stratiform 이벤트 구분</td>
</tr>
<tr>
  <td>단기 강우 의존도 과다</td>
  <td>lookback 연장(336h → 720h) 또는 antecedent soil moisture 명시적 입력</td>
</tr>
<tr>
  <td>과소추정 ↔ 과대추정 trade-off</td>
  <td>pinball loss 가중치 조정 (현재 대칭) — 과소추정에 더 강한 penalty 부여</td>
</tr>
</tbody>
</table>

<h3>5-5. 결론 한 문장 요약</h3>
<div class="box-info" style="font-size:1.1em">
<strong>Q99 LSTM 모델은 과소추정 빈도를 줄이는 데 성공했지만,
강한 단기 강우에 과민 반응하여 플래시 특성이 강한 유역에서 과대추정 편향이 발생하며,
이는 모델이 대기 수분(Qair)과 강수(Rainf) 신호에 주로 의존하고 CAPE·장기 선행 조건을
충분히 활용하지 못하는 데 기인한다.</strong>
</div>
"""

    md = """## 5. 종합 해석 및 시사점

### 5-1. 세 분석을 연결하는 일관된 서사

Q99 모델은 **강한 강우 신호(Rainf + Qair)**를 주로 보고 Q99를 높게 예측합니다(Attribution).
실제로 강한 강우 이벤트에서 Q99가 과대추정되며(Event Forcing),
특히 플래시 특성 유역에서 심합니다(Basin 특성).

반대로, 복잡한 하천망·투수성 토양·지속 이벤트에서는 안정적으로 예측합니다.

### 5-2. Q99 강점 vs 약점

| 구분 | 조건 | Q99 성능 |
|------|------|---------|
| ✅ 강점 | 투수성 높은 토양 유역 | bias 낮음 |
| ✅ 강점 | 긴 지속 강우 이벤트 | 첨두 오차 감소 |
| ✅ 강점 | 복잡 하천망(Strahler ↑) | 과소추정 적음 |
| ⚠️ 약점 | 플래시 특성 유역 | 과대추정 심화 |
| ⚠️ 약점 | 고강도 단기 강우 | Q99 과도하게 높게 예측 |

### 5-3. LSTM이 학습하지 못한 것

- **CAPE 활용 실패**: 세 분석 모두 CAPE = Q99 오차와 무관
- **장기 선행 조건 과소활용**: 0–48h 신호가 지배적, 수주 전 상태 미활용
- **플래시 이벤트 특수성 미학습**: 표본 부족 또는 시간 해상도 한계 가능성

### 5-4. 개선 방향

| 문제 | 제안 |
|------|------|
| 플래시 유역 과대추정 | 유역 특성 기반 사후 보정 또는 전용 모델 분기 |
| CAPE 미활용 | Convective vs stratiform 이벤트 구분 attention |
| 단기 신호 의존 과다 | Lookback 연장 또는 soil moisture 명시적 입력 |
| 과소/과대추정 trade-off | Pinball loss 비대칭 가중치 (과소추정에 더 강한 penalty) |

### 5-5. 결론 한 문장

**Q99 LSTM 모델은 과소추정 빈도를 줄이는 데 성공했지만, 강한 단기 강우에 과민 반응하여 플래시 특성 유역에서 과대추정 편향이 발생하며, 이는 Qair·Rainf 의존과 CAPE·장기 선행 조건 미활용에 기인한다.**
"""
    return html, md


# ══════════════════════════════════════════════════════════════════════════════
# CSS + HTML render
# ══════════════════════════════════════════════════════════════════════════════

CSS = """
* { box-sizing: border-box; }
body {
  font-family: "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
  max-width: 1080px; margin: 48px auto; padding: 0 28px;
  color: #1a1a2e; line-height: 1.85; font-size: 15px;
}
h1 { border-bottom: 4px solid #1f77b4; padding-bottom: 10px; font-size: 2em; }
h2 { border-left: 6px solid #1f77b4; padding-left: 14px; margin-top: 56px;
     font-size: 1.45em; color: #12375c; }
h3 { color: #2c5282; margin-top: 30px; font-size: 1.15em; }
h4 { color: #444; margin: 14px 0 6px; font-size: 1em; }

/* tables */
table.table { border-collapse: collapse; margin: 18px 0; font-size: 0.87em;
              width: 100%; max-width: 860px; }
table.table th { background: #1f77b4; color: white; padding: 8px 14px; text-align: left; }
table.table td { padding: 6px 14px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
table.table tr:nth-child(even) td { background: #f0f7ff; }
td.bad  { color: #c53030; font-weight: 700; }
td.good { color: #276749; font-weight: 700; }

/* boxes */
.box-info { background: #ebf8ff; border-left: 5px solid #2b6cb0;
             padding: 16px 20px; margin: 18px 0; border-radius: 4px; }
.box-def  { background: #f7fafc; border: 1px solid #cbd5e0;
             padding: 16px 20px; margin: 18px 0; border-radius: 4px; }
.box-warn { background: #fff5f5; border-left: 5px solid #c53030;
             padding: 16px 20px; margin: 18px 0; border-radius: 4px; }
dl { margin: 8px 0; }
dt { font-weight: 700; margin-top: 12px; color: #2c5282; }
dd { margin: 4px 0 0 16px; }

/* cards */
.finding-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 20px 0; }
.card-neg, .card-pos, .card-neutral {
  padding: 16px 18px; border-radius: 6px; }
.card-neg  { background: #f0fff4; border: 1px solid #9ae6b4; }
.card-pos  { background: #fff5f5; border: 1px solid #feb2b2; }
.card-neutral { background: #fafafa; border: 1px solid #e2e8f0; }

/* figures */
figure { margin: 20px 0; text-align: center; }
figure img { max-width: 100%; border: 1px solid #e2e8f0; border-radius: 6px;
             display: inline-block; }
p.caption { font-size: 0.84em; color: #666; margin: 8px 0 0; font-style: italic; }
p.warn { color: #c53030; font-style: italic; }

/* toc */
.toc { background: #f7fafc; border: 1px solid #bee3f8; border-radius: 8px;
       padding: 18px 28px; margin: 28px 0; }
.toc ol { margin: 8px 0; padding-left: 20px; }
.toc li { margin: 4px 0; }
.toc a { color: #2b6cb0; text-decoration: none; }
.toc a:hover { text-decoration: underline; }

/* misc */
code { background: #edf2f7; padding: 1px 5px; border-radius: 3px; font-size: 0.9em; }
p.date { color: #888; font-size: 0.9em; margin: 6px 0 0; }
@media (max-width: 680px) {
  .finding-cards { grid-template-columns: 1fr; }
}
"""

def render_html(sections: list[str]) -> str:
    body = "\n".join(sections)
    toc = """<div class="toc">
<strong>목차</strong>
<ol>
<li><a href="#s0">연구 배경 및 분석 방법</a></li>
<li><a href="#s1">Q99 예측 성능 개요</a></li>
<li><a href="#s2">Analysis B: 유역 특성 × Q99 오차</a></li>
<li><a href="#s3">Analysis 3: 이벤트 강제력 × Q99 오차</a></li>
<li><a href="#s4">Analysis A: LSTM 입력 기여도 (GradientInput)</a></li>
<li><a href="#s5">종합 해석 및 시사점</a></li>
</ol>
</div>"""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Q99 예측 오차 원인 분석 보고서 — DRBC 85개 유역</title>
<style>{CSS}</style>
</head>
<body>
<h1>Q99 극한 유량 예측 오차 원인 분석 보고서</h1>
<p class="date">분석 대상: DRBC holdout 85개 유역 · LSTM Model2 (quantile) · 테스트 기간 2014–2016<br>
작성: 2026-05-25 · seed 111 / 222 / 444</p>
{toc}
{body}
</body>
</html>"""

def render_md(sections: list[str]) -> str:
    header = """# Q99 극한 유량 예측 오차 원인 분석 보고서

**분석 대상:** DRBC holdout 85개 유역 · LSTM Model2 · 테스트 기간 2014–2016 · seed 111/222/444
**작성:** 2026-05-25

---

"""
    return header + "\n\n---\n\n".join(sections)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("── Loading tables …")
    d = load()

    print("── Building sections …")
    h0, m0 = sec0_background()
    h1, m1 = sec1_overview(d)
    h2, m2 = sec2_basin(d)
    h3, m3 = sec3_event(d)
    h4, m4 = sec4_attribution(d)
    h5, m5 = sec5_conclusion()

    print("── Rendering HTML …")
    html_path = OUT_DIR / "q99_analysis_report.html"
    html_path.write_text(render_html([h0,h1,h2,h3,h4,h5]), encoding="utf-8")
    print(f"Saved: {html_path}  ({html_path.stat().st_size//1024} KB)")

    print("── Rendering MD …")
    md_path = OUT_DIR / "q99_analysis_report.md"
    md_path.write_text(render_md([m0,m1,m2,m3,m4,m5]), encoding="utf-8")
    print(f"Saved: {md_path}  ({md_path.stat().st_size//1024} KB)")

    print("\nDone.")


if __name__ == "__main__":
    main()

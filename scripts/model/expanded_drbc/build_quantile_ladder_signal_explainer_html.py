#!/usr/bin/env python3
"""Build a student-friendly HTML explainer for quantile ladder signal validation.

The output is an explanatory artifact, not a canonical data table.  It is
regenerated from this script so the HTML source does not have to be edited by
hand.
"""
from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "output/model_analysis/band_signal/band_shape/report/quantile_ladder_signal_explainer.html"
)


def build_html() -> str:
    return r'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Quantile 사다리 신호 해석 기준</title>
  <style>
    :root {
      --ink: #172033;
      --muted: #5d6b82;
      --line: #d9e2ef;
      --paper: #fbfcff;
      --panel: #ffffff;
      --blue: #2563eb;
      --blue-soft: #dbeafe;
      --sky: #0284c7;
      --green: #0f766e;
      --green-soft: #ccfbf1;
      --orange: #c2410c;
      --orange-soft: #ffedd5;
      --red: #b91c1c;
      --red-soft: #fee2e2;
      --violet: #6d28d9;
      --violet-soft: #ede9fe;
      --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
      --sans: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: var(--sans);
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(37, 99, 235, 0.10), transparent 28rem),
        linear-gradient(180deg, #f6f8fc 0%, #eef3f9 100%);
      line-height: 1.62;
    }
    .wrap { max-width: 1180px; margin: 0 auto; padding: 32px 22px 64px; }
    header {
      display: grid;
      grid-template-columns: 1.25fr 0.75fr;
      gap: 22px;
      align-items: stretch;
      margin-bottom: 22px;
    }
    .hero, .card, .callout, .flow-step {
      background: rgba(255,255,255,0.92);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: 0 18px 42px rgba(25, 42, 70, 0.08);
    }
    .hero { padding: 34px; }
    .hero h1 { margin: 0 0 12px; font-size: clamp(2rem, 4vw, 3.4rem); line-height: 1.08; letter-spacing: -0.045em; }
    .hero p { margin: 0; color: var(--muted); font-size: 1.08rem; }
    .tag { display: inline-flex; gap: 8px; align-items: center; padding: 6px 11px; border-radius: 999px; background: var(--blue-soft); color: #1d4ed8; font-weight: 700; font-size: 0.86rem; margin-bottom: 16px; }
    .summary { padding: 24px; display: flex; flex-direction: column; justify-content: space-between; }
    .summary h2 { margin: 0 0 10px; font-size: 1.15rem; }
    .summary .big { font-size: 1.55rem; font-weight: 800; letter-spacing: -0.025em; line-height: 1.25; }
    .summary .small { color: var(--muted); font-size: 0.95rem; }
    code, .mono { font-family: var(--mono); background: #f1f5f9; padding: 0.12em 0.35em; border-radius: 6px; }
    section { margin-top: 22px; }
    .grid { display: grid; gap: 18px; }
    .grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .card { padding: 24px; }
    .card h2, .card h3 { margin-top: 0; letter-spacing: -0.02em; }
    .card h2 { font-size: 1.55rem; }
    .card h3 { font-size: 1.15rem; }
    .muted { color: var(--muted); }
    .emph { font-weight: 800; color: #0f172a; }
    .callout { padding: 18px 20px; border-left: 6px solid var(--blue); }
    .callout.warn { border-left-color: var(--orange); background: #fffaf5; }
    .callout.good { border-left-color: var(--green); background: #f3fffb; }
    .pill-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 0; }
    .pill { border: 1px solid var(--line); background: #fff; border-radius: 999px; padding: 7px 10px; font-size: 0.88rem; font-weight: 700; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; overflow: hidden; border-radius: 14px; font-size: 0.95rem; }
    th, td { border-bottom: 1px solid var(--line); padding: 11px 12px; text-align: left; vertical-align: top; }
    th { background: #eff6ff; font-weight: 800; color: #1e3a8a; }
    tr:last-child td { border-bottom: none; }
    .ladder { padding: 26px 18px 8px; }
    .ladder-line { position: relative; height: 78px; margin: 10px 8px 2px; }
    .rail { position: absolute; left: 4%; right: 4%; top: 36px; height: 8px; border-radius: 99px; background: linear-gradient(90deg, #93c5fd, #60a5fa, #f59e0b, #ef4444); }
    .tick { position: absolute; top: 14px; transform: translateX(-50%); text-align: center; font-family: var(--mono); font-weight: 800; }
    .tick span { display: block; margin-top: 34px; font-family: var(--sans); font-size: 0.8rem; color: var(--muted); font-weight: 700; }
    .q50 { left: 8%; } .q90 { left: 48%; } .q95 { left: 68%; } .q99 { left: 92%; }
    .class-strip { display: grid; grid-template-columns: 1fr 1.15fr 1.15fr 1.15fr 1fr; gap: 8px; margin-top: 18px; }
    .class-box { border-radius: 14px; padding: 12px; min-height: 96px; border: 1px solid var(--line); background: #fff; }
    .class-box b { display: block; font-family: var(--mono); font-size: 0.86rem; }
    .class-box small { color: var(--muted); }
    .c0 { background: #eff6ff; } .c1 { background: #ecfeff; } .c2 { background: #fefce8; } .c3 { background: #fff7ed; } .c4 { background: #fef2f2; }
    .formula { background: #0f172a; color: #e2e8f0; border-radius: 16px; padding: 16px; font-family: var(--mono); overflow-x: auto; font-size: 0.92rem; }
    .flow { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
    .flow-step { padding: 18px; position: relative; }
    .flow-step .num { width: 32px; height: 32px; display: inline-grid; place-items: center; border-radius: 50%; background: var(--blue); color: white; font-weight: 800; margin-bottom: 10px; }
    .feature-card { border: 1px solid var(--line); border-radius: 18px; padding: 16px; background: #fff; }
    .feature-card h3 { margin-bottom: 6px; }
    .feature-card .why { color: var(--muted); font-size: 0.93rem; }
    .bins { display: grid; gap: 7px; margin-top: 12px; }
    .bin { display: grid; grid-template-columns: 135px 1fr; gap: 8px; border-radius: 10px; padding: 8px 10px; background: #f8fafc; border: 1px solid #e2e8f0; }
    .bin b { font-family: var(--mono); font-size: 0.82rem; }
    .risk { border-left: 5px solid; }
    .risk.r1 { border-color: var(--blue); } .risk.r2 { border-color: var(--sky); } .risk.r3 { border-color: var(--orange); } .risk.r4 { border-color: var(--red); }
    .caption { color: var(--muted); font-size: 0.88rem; margin-top: 8px; }
    footer { margin-top: 28px; color: var(--muted); font-size: 0.9rem; }
    @media (max-width: 900px) {
      header, .grid.two, .grid.three, .flow { grid-template-columns: 1fr; }
      .class-strip { grid-template-columns: 1fr; }
      .hero { padding: 24px; }
    }
    @media print {
      body { background: white; }
      .hero, .card, .callout, .flow-step { box-shadow: none; }
      .wrap { padding: 16px; }
    }
  </style>
</head>
<body>
  <main class="wrap">
    <header>
      <div class="hero">
        <div class="tag">Model 2 quantile 사다리 설명</div>
        <h1>q50–q99 사다리를 어떻게 하나의 해석으로 바꿀까?</h1>
        <p>핵심은 <b>q50을 대표 유량</b>으로 두고, <b>q90/q95/q99는 관측 첨두유량이 사다리의 어느 쪽에 놓일지 추정하는 상단부 신호</b>로 읽는 것입니다.</p>
      </div>
      <aside class="summary card">
        <div>
          <h2>한 줄 요약</h2>
          <div class="big">관측값은 기준을 배우는 교사,<br/>미래 적용 때는 입력 금지.</div>
        </div>
        <p class="small">과거 자료에서는 관측값으로 “어느 구간에 들어갔는지”를 배웁니다. 하지만 새 사건을 해석할 때는 관측값 없이 <code>level</code>(수준), <code>spread</code>(벌어짐), <code>jump</code>(상단 튐), <code>context</code>(유역·강우 조건)만으로 위험 단계를 붙입니다.</p>
      </aside>
    </header>

    <section class="callout warn">
      <b>중요한 주의</b><br />
      <code>q99</code>는 보정된 99% 예측구간도, 100년 빈도 홍수도 아닙니다. 이 연구에서는 <b>한쪽 방향의 상단부 보호 출력</b>, 즉 큰 홍수를 덜 놓치기 위해 위쪽으로 열어 둔 값입니다. 따라서 <code>obs <= q99</code>라고 해서 “q99가 정답”이라고 쓰지 않습니다.
    </section>

    <section class="card">
      <h2>1. 먼저 quantile 사다리가 무엇인지 보기</h2>
      <p>Model 2는 같은 시점에 네 개의 값을 냅니다. 네 값은 네 개의 정답이 아니라, 중심 예측에서 극단 상단부까지 올라가는 <b>사다리</b>입니다.</p>
      <div class="ladder">
        <div class="ladder-line" aria-label="q50 q90 q95 q99 ladder">
          <div class="rail"></div>
          <div class="tick q50">q50<span>대표 유량</span></div>
          <div class="tick q90">q90<span>높은 유량</span></div>
          <div class="tick q95">q95<span>홍수 민감</span></div>
          <div class="tick q99">q99<span>상단 보호</span></div>
        </div>
        <div class="class-strip">
          <div class="class-box c0"><b>below_q50</b><small>obs ≤ q50<br/>중심 예측도 과대 가능</small></div>
          <div class="class-box c1"><b>q50_to_q90</b><small>q50 &lt; obs ≤ q90<br/>낮은 상단부 구간</small></div>
          <div class="class-box c2"><b>q90_to_q95</b><small>q90 &lt; obs ≤ q95<br/>고유량 구간</small></div>
          <div class="class-box c3"><b>q95_to_q99</b><small>q95 &lt; obs ≤ q99<br/>극단 상단부 구간</small></div>
          <div class="class-box c4"><b>above_q99</b><small>obs &gt; q99<br/>q99도 부족</small></div>
        </div>
        <p class="caption">이 다섯 구간은 관측값이 있을 때 붙이는 검증용 정답표입니다. 미래에는 실제 관측값이 없으므로 이 구간을 직접 알 수 없습니다.</p>
      </div>
    </section>

    <section class="grid two">
      <div class="card">
        <h2>2. 관측값을 쓰는 곳과 쓰면 안 되는 곳을 분리</h2>
        <table>
          <thead><tr><th>구분</th><th>무엇인가?</th><th>관측값 사용?</th></tr></thead>
          <tbody>
            <tr><td><b>관측 위치 구간</b><br/><span class="muted">obs class</span></td><td>과거 사건에서 실제 관측 첨두유량이 q50–q99 사다리 어디에 들어갔는지</td><td><b>사용함</b><br/>기준을 배우는 정답표</td></tr>
            <tr><td><b>신호 지표</b><br/><span class="muted">signal feature</span></td><td>수준, 벌어짐, 상단 튐, 유역·강우 조건처럼 새 사건에서도 미리 계산 가능한 값</td><td><b>사용 안 함</b><br/>관측값 없이 계산</td></tr>
            <tr><td><b>위험 단계</b><br/><span class="muted">risk tier</span></td><td>과거에서 배운 패턴을 새 사건의 신호 지표에 적용해 붙이는 사전 해석 태그</td><td><b>사용 안 함</b><br/>미래 적용용 태그</td></tr>
          </tbody>
        </table>
      </div>
      <div class="card">
        <h2>3. 관측값 누수는 “배우는 단계”가 아니라 “적용하는 단계”의 문제</h2>
        <p>맞습니다. 기준을 만들려면 과거 관측값을 반드시 써야 합니다. 관측값으로 “어떤 신호 조합일 때 실제 관측 첨두가 어느 구간에 갔는지”를 배웁니다. 다만 새 사건에 그 기준을 적용할 때, 관측 첨두 시점이나 관측 첨두 크기를 신호 지표 계산에 넣으면 안 됩니다. 이것을 <b>관측값 누수</b>라고 부릅니다.</p>
        <p>그래서 기준은 두 단계로 만듭니다.</p>
        <ol>
          <li><b>학습·검증 단계:</b> 관측값으로 정답 구간을 붙이고, 신호 지표와의 패턴을 배운다.</li>
          <li><b>미래 적용 단계:</b> 관측값 없이 계산 가능한 신호 지표만 넣어 위험 단계를 붙인다.</li>
        </ol>
        <table>
          <thead><tr><th>계산 기준 시점</th><th>역할</th></tr></thead>
          <tbody>
            <tr><td><code>model-predicted peak</code><br/>모델 예측 첨두 시점</td><td>사건 구간 안에서 q99 또는 q50이 최대인 시점</td></tr>
            <tr><td><code>rainfall-event window</code><br/>강우 사건 구간</td><td>강우 자료로 정의한 사건 구간</td></tr>
            <tr><td><code>observed peak</code><br/>관측 첨두 시점</td><td>사후 진단에서만 사용</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <h2>4. 분석 흐름: 기준을 어떻게 만들고 검증하나?</h2>
      <div class="flow">
        <div class="flow-step"><div class="num">1</div><h3>과거 사건에 정답 구간 붙이기</h3><p>관측 첨두를 이용해 실제 위치 구간을 붙입니다. 이 단계는 기준을 배우기 위한 정답표 만들기입니다.</p></div>
        <div class="flow-step"><div class="num">2</div><h3>관측값 없는 신호 지표 계산</h3><p><code>rel_width</code>(상대 벌어짐), <code>tail_jump</code>(상단 튐), 강우, 유역 조건을 계산합니다.</p></div>
        <div class="flow-step"><div class="num">3</div><h3>패턴을 기준으로 바꾸기</h3><p>어떤 신호 조합에서 어떤 관측 위치 구간이 자주 나오는지 표로 정리합니다.</p></div>
        <div class="flow-step"><div class="num">4</div><h3>새 사건에는 위험 단계만 붙이기</h3><p>새 사건은 관측값이 없으므로, 배운 패턴을 이용해 “가능성이 큰 위치”를 위험 단계로 표현합니다.</p></div>
      </div>
    </section>

    <section class="card">
      <h2>5. 신호 지표별 세부 기준</h2>
      <p class="muted">기준선은 DRBC test를 보고 임의로 정하지 않습니다. 검증 자료에서 3등분, p90, p95, p99 같은 절단 기준을 먼저 정하고 test에는 그대로 적용합니다. 여기서 p90은 검증 자료 안에서 상위 10% 경계라는 뜻입니다.</p>
      <div class="grid two">
        <div class="feature-card">
          <h3><code>q50_flow_percentile</code></h3>
          <div class="why">q50 자체가 해당 유역의 과거 유량 분포에서 얼마나 높은지 보는 <b>수준 지표</b>입니다.</div>
          <div class="formula">q50_flow_percentile = F_train_obs_basin(q50)</div>
          <div class="bins">
            <div class="bin"><b>normal_flow</b><span>&lt; 0.90: 보통 유량</span></div>
            <div class="bin"><b>elevated_flow</b><span>0.90–0.95: 고유량 후보</span></div>
            <div class="bin"><b>high_flow</b><span>0.95–0.99: 홍수 관련 고유량</span></div>
            <div class="bin"><b>extreme_flow</b><span>≥ 0.99: q50만으로도 극한 유량</span></div>
          </div>
        </div>
        <div class="feature-card">
          <h3><code>rel_width</code></h3>
          <div class="why">q50 대비 q99가 얼마나 열려 있는지 보는 <b>한쪽 방향의 벌어짐 지표</b>입니다.</div>
          <div class="formula">rel_width = (q99 - q50) / max(q50, eps)</div>
          <div class="bins">
            <div class="bin"><b>narrow</b><span>검증 자료 하위 1/3</span></div>
            <div class="bin"><b>moderate</b><span>검증 자료 중간 1/3</span></div>
            <div class="bin"><b>wide</b><span>검증 자료 상위 1/3</span></div>
            <div class="bin"><b>extreme_wide</b><span>검증 자료 p90 이상</span></div>
          </div>
        </div>
        <div class="feature-card">
          <h3><code>tail_jump</code></h3>
          <div class="why">전체 벌어짐 중 q95→q99 구간이 얼마나 큰지 보는 <b>극단 상단부 모양 지표</b>입니다.</div>
          <div class="formula">tail_jump = (q99 - q95) / max(q99 - q50, eps_width)</div>
          <div class="bins">
            <div class="bin"><b>smooth_ladder</b><span>검증 자료 하위 1/3</span></div>
            <div class="bin"><b>balanced_tail</b><span>검증 자료 중간 1/3</span></div>
            <div class="bin"><b>top_heavy</b><span>검증 자료 상위 1/3</span></div>
            <div class="bin"><b>top_heavy_extreme</b><span>검증 자료 p90 이상</span></div>
          </div>
        </div>
        <div class="feature-card">
          <h3><code>q99_q50_ratio</code></h3>
          <div class="why">q99가 q50의 몇 배인지 보는 직관적 비율입니다. 분석에서는 로그 변환도 함께 저장합니다.</div>
          <div class="formula">q99_q50_ratio = q99 / max(q50, eps)</div>
          <div class="bins">
            <div class="bin"><b>low_ratio</b><span>검증 자료 하위 1/3</span></div>
            <div class="bin"><b>mid_ratio</b><span>검증 자료 중간 1/3</span></div>
            <div class="bin"><b>high_ratio</b><span>검증 자료 상위 1/3</span></div>
          </div>
        </div>
        <div class="feature-card">
          <h3><code>rain_event_intensity</code></h3>
          <div class="why">입력 강우 자체가 얼마나 강한지 보는 <b>외부 강우 압박 지표</b>입니다.</div>
          <div class="formula">rain_sum_24h, rain_sum_72h, antecedent_rain_7d, recent_3d_ratio ...</div>
          <div class="bins">
            <div class="bin"><b>normal_rain</b><span>&lt; p90</span></div>
            <div class="bin"><b>heavy_rain</b><span>p90–p95</span></div>
            <div class="bin"><b>extreme_rain</b><span>p95–p99</span></div>
            <div class="bin"><b>record_like</b><span>≥ p99: 과거 최상위급 강우</span></div>
          </div>
        </div>
        <div class="feature-card">
          <h3><code>basin_area</code> + <code>baseflow_index</code></h3>
          <div class="why">유역이 빠르게 반응하는지, 저장성이 큰지 구분하는 <b>유역 조건</b>입니다. 단독 결론보다 다른 지표와의 조합으로 봅니다.</div>
          <div class="formula">log_area = log10(area_km²); BFI tertile = low / mid / high</div>
          <div class="bins">
            <div class="bin"><b>small + low BFI</b><span>빠른 첨두 가능</span></div>
            <div class="bin"><b>mid / mixed</b><span>기준 그룹</span></div>
            <div class="bin"><b>large + high BFI</b><span>지연·저장·regulation 가능</span></div>
          </div>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>6. 최종 해석은 위험 단계로 한다</h2>
      <p>미래에는 관측 위치 구간을 모릅니다. 그래서 “관측값이 q95~q99에 있다”고 단정하지 않고, 신호 지표 조합으로 <b>어느 위치에 놓일 가능성이 큰지</b>를 위험 단계로 말합니다.</p>
      <table>
        <thead><tr><th>위험 단계</th><th>후보 조건</th><th>예상 관측 위치</th><th>해석 문장</th></tr></thead>
        <tbody>
          <tr class="risk r1"><td>중심부 또는 낮은 단계<br/><code>central_or_lower</code></td><td>q50 percentile 높음 + rel_width 낮음/중간</td><td><code>below_q50</code> 또는 <code>q50_to_q90</code></td><td>중심 예측 근처에서 설명 가능</td></tr>
          <tr class="risk r2"><td>중간 상단부 단계<br/><code>mid_upper_band</code></td><td>q50 high 이상 또는 rel_width 중간/높음</td><td><code>q90_to_q95</code></td><td>상단부 확인 필요</td></tr>
          <tr class="risk r3"><td>극단 상단부 단계<br/><code>extreme_upper_band</code></td><td>rel_width 높음 + 상단 튐 큼 또는 극한 강우</td><td><code>q95_to_q99</code></td><td>극단 상단부 신호</td></tr>
          <tr class="risk r4"><td>q99 초과 위험 단계<br/><code>above_q99_risk</code></td><td>매우 넓은 벌어짐 + 매우 큰 상단 튐 + 극한 조건</td><td><code>above_q99</code> 가능성 증가</td><td>q99도 부족할 수 있는 강한 사건</td></tr>
        </tbody>
      </table>
    </section>

    <section class="grid two">
      <div class="card">
        <h2>7. q99 비교는 어떻게 하나?</h2>
        <p><code>q99</code>는 두 층으로 평가합니다.</p>
        <table>
          <thead><tr><th>층</th><th>지표</th><th>해석</th></tr></thead>
          <tbody>
            <tr><td>포함 여부 확인<br/><span class="muted">inclusion guardrail</span></td><td><code>P(obs ≤ q99)</code>, <code>P(obs &gt; q99)</code></td><td>q99가 상단 경계로 관측값을 포함했는지</td></tr>
            <tr><td>거리·비용 평가<br/><span class="muted">distance/cost</span></td><td><code>max(q99-obs,0)/obs</code></td><td>포함했더라도 얼마나 과대했는지</td></tr>
          </tbody>
        </table>
        <div class="callout warn" style="margin-top:14px;"><b>해석 금지:</b> <code>obs <= q99</code> → “q99가 맞았다”.<br/> <b>권장:</b> q99는 inclusion guardrail은 통과했지만 over-gap 비용을 함께 봐야 한다.</div>
      </div>
      <div class="card">
        <h2>8. 기준이 작동한다는 증거</h2>
        <p>좋은 기준이라면 위험 단계가 올라갈수록 관측 위치 구간도 위쪽으로 이동해야 합니다.</p>
        <table>
          <thead><tr><th>확인</th><th>좋은 패턴</th></tr></thead>
          <tbody>
            <tr><td>구간별 분포</td><td>위험 단계가 높을수록 <code>q95_to_q99</code>, <code>above_q99</code> 증가</td></tr>
            <tr><td>Spearman 순위상관</td><td>신호 지표와 관측 위치 순서가 같은 방향으로 움직이는지 확인</td></tr>
            <tr><td>NOAA sanity</td><td>NOAA confirmed flood에서도 방향이 뒤집히지 않음</td></tr>
            <tr><td>실패 기준</td><td>위험 단계별 관측 위치 분포가 거의 같으면 구간 구분 실패</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="callout good">
      <b>최종 문장 예시</b><br />
      대표 유량은 <code>q50</code>이다. 다만 이 사건은 <code>rel_width</code>(상대 벌어짐)와 <code>tail_jump</code>(상단 튐)가 검증 자료의 상위 구간이고 강우 압박도 높으므로, 관측 첨두유량이 상단부 사다리 또는 <code>above_q99</code> 영역에 놓일 가능성이 큰 <b>상단부 위험 사건</b>으로 해석한다.
    </section>

    <footer>
      생성 스크립트: <code>scripts/model/expanded_drbc/build_quantile_ladder_signal_explainer_html.py</code>. 기준 문서: <code>.omx/specs/quantile-ladder-obs-validation-spec.md</code>.
    </footer>
  </main>
</body>
</html>
'''


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    html = build_html()
    args.output.write_text(html, encoding="utf-8")
    print(f"wrote {args.output} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()

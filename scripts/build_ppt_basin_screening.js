/**
 * Basin Screening Method Presentation
 * Delaware River Basin — CAMELSH Cohort Construction
 *
 * Color Palette (Ocean/Hydrology theme):
 *   Dark navy  : 0D1B2A  (title/closing bg)
 *   Deep blue  : 0A3D62  (header bars)
 *   Teal       : 1C7293  (accent elements)
 *   Bright cyan: 00B4D8  (highlight)
 *   Light bg   : F0F7FA  (content slides)
 *   Card white : FFFFFF
 *   Text dark  : 1A2B3C
 *   Muted      : 64748B
 */

const pptxgen = require("/opt/homebrew/lib/node_modules/pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "CAMELS Research";
pres.title = "Basin Screening Method";

// ─── COLORS ──────────────────────────────────────────────────────────────────
const C = {
  navyBg:   "0D1B2A",
  deepBlue: "0A3D62",
  teal:     "1C7293",
  cyan:     "00B4D8",
  lightBg:  "F0F7FA",
  cardBg:   "FFFFFF",
  textDark: "1A2B3C",
  textMid:  "2D4A6A",
  muted:    "64748B",
  border:   "BDD7E7",
  step1:    "0A3D62",
  step2:    "1C7293",
  step3:    "0096C7",
  step4:    "48CAE4",
};

// ─── HELPERS ─────────────────────────────────────────────────────────────────
function makeShadow() {
  return { type: "outer", color: "000000", blur: 6, offset: 3, angle: 135, opacity: 0.12 };
}

function addHeaderBar(slide, title, subtitle) {
  // Dark header bar
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 1.05,
    fill: { color: C.deepBlue }, line: { color: C.deepBlue, width: 0 }
  });
  // Cyan accent stripe
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 1.05, w: 10, h: 0.06,
    fill: { color: C.cyan }, line: { color: C.cyan, width: 0 }
  });
  // Slide title
  slide.addText(title, {
    x: 0.45, y: 0.08, w: 9.1, h: 0.58,
    fontSize: 22, bold: true, color: C.cardBg,
    fontFace: "Calibri", align: "left", valign: "middle", margin: 0
  });
  if (subtitle) {
    slide.addText(subtitle, {
      x: 0.45, y: 0.62, w: 9.1, h: 0.38,
      fontSize: 11, color: "A8D8EA",
      fontFace: "Calibri", align: "left", valign: "middle", margin: 0
    });
  }
}

function addCard(slide, x, y, w, h, opts = {}) {
  const { color = C.cardBg, accentColor = null, accentW = 0.07 } = opts;
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color }, line: { color: C.border, width: 0.5 },
    shadow: makeShadow()
  });
  if (accentColor) {
    slide.addShape(pres.shapes.RECTANGLE, {
      x, y, w: accentW, h,
      fill: { color: accentColor }, line: { color: accentColor, width: 0 }
    });
  }
}

function addStepBadge(slide, x, y, num, color) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 0.38, h: 0.38,
    fill: { color }, line: { color, width: 0 }
  });
  slide.addText(`${num}`, {
    x, y, w: 0.38, h: 0.38,
    fontSize: 14, bold: true, color: C.cardBg,
    fontFace: "Calibri", align: "center", valign: "middle", margin: 0
  });
}

// ─── SLIDE 1: TITLE ──────────────────────────────────────────────────────────
{
  const slide = pres.addSlide();
  slide.background = { color: C.navyBg };

  // Left accent bar
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.18, h: 5.625,
    fill: { color: C.cyan }, line: { color: C.cyan, width: 0 }
  });

  // Decorative background shapes
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 7.2, y: 0, w: 2.8, h: 5.625,
    fill: { color: C.deepBlue, transparency: 60 }, line: { color: C.deepBlue, width: 0 }
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 8.0, y: 0, w: 2.0, h: 5.625,
    fill: { color: C.teal, transparency: 70 }, line: { color: C.teal, width: 0 }
  });

  // Category label
  slide.addText("HYDROLOGICAL RESEARCH · DRBC CAMELSH", {
    x: 0.4, y: 1.0, w: 6.8, h: 0.38,
    fontSize: 9, color: C.cyan, bold: true,
    fontFace: "Calibri", align: "left", charSpacing: 3, margin: 0
  });

  // Main title
  slide.addText("Basin Screening Method", {
    x: 0.4, y: 1.5, w: 7.0, h: 1.2,
    fontSize: 40, bold: true, color: C.cardBg,
    fontFace: "Calibri", align: "left", valign: "middle", margin: 0
  });

  // Subtitle
  slide.addText("Delaware River Basin — CAMELSH Cohort Construction", {
    x: 0.4, y: 2.8, w: 7.0, h: 0.55,
    fontSize: 16, color: "A8D8EA",
    fontFace: "Calibri", align: "left", margin: 0
  });

  // Description
  slide.addText("4-step pipeline: Spatial Selection → Quality Gate → Observed-flow Screening → Cohort Definition", {
    x: 0.4, y: 3.45, w: 7.0, h: 0.55,
    fontSize: 12, color: "7EB8D4",
    fontFace: "Calibri", align: "left", margin: 0
  });

  // Horizontal divider
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.4, y: 4.15, w: 3.5, h: 0.04,
    fill: { color: C.teal }, line: { color: C.teal, width: 0 }
  });

  // Bottom labels
  const labels = ["CAMELS-H", "DRBC", "Flood Relevance", "Cohort Design"];
  labels.forEach((lbl, i) => {
    slide.addText(lbl, {
      x: 0.4 + i * 1.7, y: 4.3, w: 1.5, h: 0.3,
      fontSize: 9, color: "7EB8D4",
      fontFace: "Calibri", align: "left", margin: 0
    });
  });
}

// ─── SLIDE 2: OVERVIEW (4-step pipeline) ────────────────────────────────────
{
  const slide = pres.addSlide();
  slide.background = { color: C.lightBg };
  addHeaderBar(slide, "스크리닝 파이프라인 개요", "4단계 순차 구조 — 각 단계는 독립적인 역할을 담당");

  // Purpose box
  addCard(slide, 0.3, 1.3, 9.4, 0.7, { color: "E8F4FC", accentColor: C.cyan });
  slide.addText("목적: 모델 비교에 적합한 basin을 선정하는 것 — flood susceptibility를 새로 정의하는 것이 아니라, 모델 실험을 위한 cohort construction 절차", {
    x: 0.5, y: 1.35, w: 9.0, h: 0.6,
    fontSize: 12, color: C.textMid, fontFace: "Calibri", align: "left", valign: "middle", margin: 0
  });

  // Step cards
  const steps = [
    { num: 1, color: C.step1, title: "Spatial Selection", sub: "DRBC + CAMELSH\noutlet & overlap 기준", why: "연구권역 고정" },
    { num: 2, color: C.step2, title: "Quality Gate", sub: "usable years /\nestimated-flow / boundary", why: "데이터 품질 보장" },
    { num: 3, color: C.step3, title: "Flood Relevance", sub: "annual peaks / Q99 /\nRBI observed-flow 기반", why: "실제 flood 반응 확인" },
    { num: 4, color: C.step4, title: "Cohort Separation", sub: "broad cohort /\nnatural cohort 분리", why: "인위적 영향 분리" },
  ];

  const cardW = 2.15;
  const cardX0 = 0.28;
  const arrowX = cardX0 + cardW;

  steps.forEach((s, i) => {
    const cx = cardX0 + i * (cardW + 0.22);
    addCard(slide, cx, 2.2, cardW, 2.9, { color: C.cardBg, accentColor: s.color });

    // Step badge
    addStepBadge(slide, cx + 0.12, 2.3, s.num, s.color);

    // Title
    slide.addText(s.title, {
      x: cx + 0.07, y: 2.77, w: cardW - 0.12, h: 0.45,
      fontSize: 13, bold: true, color: C.textDark,
      fontFace: "Calibri", align: "left", margin: 0
    });

    // Sub
    slide.addText(s.sub, {
      x: cx + 0.12, y: 3.25, w: cardW - 0.22, h: 0.8,
      fontSize: 10.5, color: C.muted, fontFace: "Calibri", align: "left", margin: 0
    });

    // Why badge
    slide.addShape(pres.shapes.RECTANGLE, {
      x: cx + 0.12, y: 4.2, w: cardW - 0.3, h: 0.55,
      fill: { color: s.color, transparency: 85 }, line: { color: s.color, width: 0 }
    });
    slide.addText(s.why, {
      x: cx + 0.12, y: 4.2, w: cardW - 0.3, h: 0.55,
      fontSize: 10, bold: true, color: s.color, fontFace: "Calibri",
      align: "center", valign: "middle", margin: 0
    });

    // Arrow between cards
    if (i < 3) {
      slide.addShape(pres.shapes.RECTANGLE, {
        x: cx + cardW + 0.02, y: 3.5, w: 0.15, h: 0.05,
        fill: { color: C.teal }, line: { color: C.teal, width: 0 }
      });
      slide.addText("▶", {
        x: cx + cardW + 0.05, y: 3.38, w: 0.15, h: 0.3,
        fontSize: 11, color: C.teal, fontFace: "Calibri", align: "center", margin: 0
      });
    }
  });
}

// ─── SLIDE 3: STEP 1 — Spatial Selection ─────────────────────────────────────
{
  const slide = pres.addSlide();
  slide.background = { color: C.lightBg };
  addHeaderBar(slide, "Step 1 — Spatial Selection", "DRBC + CAMELSH 기반 basin 선택");

  // Left: explanation
  addCard(slide, 0.3, 1.3, 4.7, 3.9, { color: C.cardBg, accentColor: C.step1 });

  slide.addText("연구권역 정의", {
    x: 0.5, y: 1.42, w: 4.3, h: 0.35,
    fontSize: 13, bold: true, color: C.step1, fontFace: "Calibri", align: "left", margin: 0
  });
  slide.addText("Delaware River Basin Commission (DRBC) 공식 경계 polygon을 연구권역으로 정의한다.", {
    x: 0.5, y: 1.82, w: 4.3, h: 0.7,
    fontSize: 11, color: C.textMid, fontFace: "Calibri", align: "left", margin: 0
  });

  slide.addText("선택 조건 (두 조건 동시 만족)", {
    x: 0.5, y: 2.6, w: 4.3, h: 0.35,
    fontSize: 13, bold: true, color: C.step1, fontFace: "Calibri", align: "left", margin: 0
  });

  const conds = [
    { label: "① Outlet 조건", desc: "basin gauge outlet point가 DRBC polygon 내부에 위치해야 함 (outlet = primary anchor)" },
    { label: "② Overlap 조건", desc: "basin polygon의 DRBC 내부 면적 비율 r_i ≥ 0.9 (90% 이상이 연구권역 내부)" },
  ];
  conds.forEach((c, i) => {
    const cy = 3.05 + i * 0.95;
    slide.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y: cy, w: 4.3, h: 0.85,
      fill: { color: C.step1, transparency: 90 }, line: { color: C.step1, width: 0.5 }
    });
    slide.addText(c.label, {
      x: 0.58, y: cy + 0.04, w: 4.1, h: 0.28,
      fontSize: 11, bold: true, color: C.step1, fontFace: "Calibri", align: "left", margin: 0
    });
    slide.addText(c.desc, {
      x: 0.58, y: cy + 0.32, w: 4.1, h: 0.48,
      fontSize: 10, color: C.textMid, fontFace: "Calibri", align: "left", margin: 0
    });
  });

  // Right: formula card
  addCard(slide, 5.2, 1.3, 4.5, 3.9, { color: "E8F4FC", accentColor: C.cyan });

  slide.addText("공식 선택 기준", {
    x: 5.38, y: 1.42, w: 4.1, h: 0.35,
    fontSize: 13, bold: true, color: C.deepBlue, fontFace: "Calibri", align: "left", margin: 0
  });

  // Formula boxes
  const formulas = [
    { title: "Outlet Condition", expr: "O_i = 1[ covers(Ω_DRBC, p_i) ]" },
    { title: "Overlap Ratio", expr: "r_i = Area(B_i ∩ Ω_DRBC) / Area(B_i)" },
    { title: "Selection Rule", expr: "O_i = 1   AND   r_i ≥ 0.9" },
  ];
  formulas.forEach((f, i) => {
    const fy = 1.9 + i * 1.05;
    slide.addShape(pres.shapes.RECTANGLE, {
      x: 5.35, y: fy, w: 4.15, h: 0.88,
      fill: { color: C.cardBg }, line: { color: C.border, width: 0.5 },
      shadow: makeShadow()
    });
    slide.addText(f.title, {
      x: 5.45, y: fy + 0.05, w: 3.95, h: 0.28,
      fontSize: 10, bold: true, color: C.muted, fontFace: "Calibri", align: "left", margin: 0
    });
    slide.addText(f.expr, {
      x: 5.45, y: fy + 0.36, w: 3.95, h: 0.42,
      fontSize: 12, bold: true, color: C.deepBlue, fontFace: "Consolas", align: "left", margin: 0
    });
  });

  // Rationale note
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.3, y: 5.05, w: 9.4, h: 0.42,
    fill: { color: C.cyan, transparency: 85 }, line: { color: C.cyan, width: 0 }
  });
  slide.addText("왜 outlet + overlap을 같이 쓰는가 — outlet만: 경계 상당 부분이 권역 밖으로 나갈 수 있음  |  overlap만: outlet가 권역 밖인 basin도 포함될 수 있음", {
    x: 0.45, y: 5.05, w: 9.1, h: 0.42,
    fontSize: 10, color: C.deepBlue, fontFace: "Calibri", align: "left", valign: "middle", margin: 0
  });
}

// ─── SLIDE 4: STEP 2 — Quality Gate ─────────────────────────────────────────
{
  const slide = pres.addSlide();
  slide.background = { color: C.lightBg };
  addHeaderBar(slide, "Step 2 — Quality Gate", "데이터 품질 보장 — usable years · estimated-flow fraction · boundary confidence");

  // Usable year definition box
  addCard(slide, 0.3, 1.3, 9.4, 0.95, { color: "E8F4FC", accentColor: C.step2 });
  slide.addText("Usable Year 정의", {
    x: 0.52, y: 1.35, w: 2.5, h: 0.35,
    fontSize: 12, bold: true, color: C.step2, fontFace: "Calibri", align: "left", margin: 0
  });
  slide.addText("연간 관측 시간 커버리지  C_{i,y} = H^obs_{i,y} / H^tot_y  ≥  τ_c = 0.80  를 만족하는 해를 usable year로 정의", {
    x: 0.52, y: 1.72, w: 8.9, h: 0.42,
    fontSize: 11, color: C.textMid, fontFace: "Calibri", align: "left", margin: 0
  });

  // Three conditions
  const conditions = [
    {
      color: C.step1,
      icon: "①",
      title: "Usable Years",
      cond: "Y_i^usable  ≥  τ_y = 10",
      why: "관측 기간이 너무 짧으면\nflood frequency 분석 불가",
    },
    {
      color: C.step2,
      icon: "②",
      title: "Estimated Flow Fraction",
      cond: "E_i  ≤  τ_e = 15%",
      why: "추정값 비율이 높으면\n유량 신뢰도 저하",
    },
    {
      color: C.step3,
      icon: "③",
      title: "Boundary Confidence",
      cond: "B_i  ≥  τ_b = 7",
      why: "경계 불확실 basin은\n공간 일관성 보장 불가",
    },
  ];

  const cw = 2.95;
  conditions.forEach((c, i) => {
    const cx = 0.3 + i * (cw + 0.2);
    addCard(slide, cx, 2.4, cw, 2.7, { color: C.cardBg, accentColor: c.color });

    // Icon badge
    slide.addShape(pres.shapes.RECTANGLE, {
      x: cx + 0.12, y: 2.52, w: 0.42, h: 0.42,
      fill: { color: c.color }, line: { color: c.color, width: 0 }
    });
    slide.addText(c.icon, {
      x: cx + 0.12, y: 2.52, w: 0.42, h: 0.42,
      fontSize: 14, bold: true, color: C.cardBg,
      fontFace: "Calibri", align: "center", valign: "middle", margin: 0
    });

    slide.addText(c.title, {
      x: cx + 0.12, y: 3.02, w: cw - 0.22, h: 0.42,
      fontSize: 12, bold: true, color: C.textDark,
      fontFace: "Calibri", align: "left", margin: 0
    });

    // Condition formula
    slide.addShape(pres.shapes.RECTANGLE, {
      x: cx + 0.12, y: 3.48, w: cw - 0.28, h: 0.52,
      fill: { color: c.color, transparency: 88 }, line: { color: c.color, width: 0 }
    });
    slide.addText(c.cond, {
      x: cx + 0.12, y: 3.48, w: cw - 0.28, h: 0.52,
      fontSize: 11.5, bold: true, color: c.color, fontFace: "Consolas",
      align: "center", valign: "middle", margin: 0
    });

    slide.addText(c.why, {
      x: cx + 0.12, y: 4.12, w: cw - 0.22, h: 0.72,
      fontSize: 10, color: C.muted, fontFace: "Calibri", align: "left", margin: 0
    });
  });

  // Combined gate formula
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.3, y: 5.08, w: 9.4, h: 0.38,
    fill: { color: C.deepBlue, transparency: 88 }, line: { color: C.deepBlue, width: 0 }
  });
  slide.addText("Quality Pass:   Q_i = 1(Y_i ≥ 10) · 1(E_i ≤ 15%) · 1(B_i ≥ 7)   — 세 조건 모두 만족해야 quality-pass", {
    x: 0.45, y: 5.08, w: 9.1, h: 0.38,
    fontSize: 10.5, bold: true, color: C.deepBlue, fontFace: "Consolas",
    align: "left", valign: "middle", margin: 0
  });
}

// ─── SLIDE 5: STEP 3 — Observed-flow Metrics ────────────────────────────────
{
  const slide = pres.addSlide();
  slide.background = { color: C.lightBg };
  addHeaderBar(slide, "Step 3 — Observed-flow 기반 Flood-Relevant Basin 선정", "정적 heuristic이 아닌 실측 유량 지표를 중심으로");

  // Why note
  addCard(slide, 0.3, 1.28, 9.4, 0.65, { color: "FFF8E1", accentColor: "F59E0B" });
  slide.addText("정적 basin 특성은 '왜 빠르게 반응할 가능성이 있는지' 설명하지만, 실제 큰 flood-like event가 자주 나타나는지는 직접 보여주지 않는다.", {
    x: 0.5, y: 1.33, w: 9.0, h: 0.55,
    fontSize: 11, color: "92400E", fontFace: "Calibri", align: "left", valign: "middle", margin: 0
  });

  // Three metrics
  const metrics = [
    {
      color: C.step1,
      num: "M1",
      title: "Annual Peak Specific Discharge",
      formula: "q_peak = Q_max / A_i",
      detail: "basin 면적이 다르기 때문에 연 최대 유량을 basin area로 나눠 비교. Bulletin 17C의 annual peak series framework와 정합적.",
      ref: "→ Bulletin 17C",
    },
    {
      color: C.step2,
      num: "M2",
      title: "Q99 Event Frequency",
      formula: "F_i^99 = N_i^99 / Y_i^usable",
      detail: "usable year당 Q99 수준 고빈도 사상이 몇 회 발생하는지 측정. 단순히 peak가 한 번 컸는지보다 반복적 extreme response를 판단.",
      ref: "→ 반복적 극한 반응",
    },
    {
      color: C.step3,
      num: "M3",
      title: "Richards–Baker Flashiness Index",
      formula: "RBI = Σ|Q_{t+1}−Q_t| / ΣQ_t",
      detail: "hydrograph의 급격한 변화를 정량화. peak underestimation과 빠른 flood response에 관심이 있는 연구 목적에 직접적으로 부합.",
      ref: "→ HESS 2023",
    },
  ];

  const mw = 2.98;
  metrics.forEach((m, i) => {
    const mx = 0.3 + i * (mw + 0.22);
    addCard(slide, mx, 2.08, mw, 3.12, { color: C.cardBg, accentColor: m.color });

    // Num badge
    slide.addShape(pres.shapes.RECTANGLE, {
      x: mx + 0.12, y: 2.2, w: 0.45, h: 0.42,
      fill: { color: m.color }, line: { color: m.color, width: 0 }
    });
    slide.addText(m.num, {
      x: mx + 0.12, y: 2.2, w: 0.45, h: 0.42,
      fontSize: 11, bold: true, color: C.cardBg,
      fontFace: "Calibri", align: "center", valign: "middle", margin: 0
    });

    slide.addText(m.title, {
      x: mx + 0.12, y: 2.68, w: mw - 0.2, h: 0.52,
      fontSize: 11, bold: true, color: C.textDark, fontFace: "Calibri", align: "left", margin: 0
    });

    // Formula
    slide.addShape(pres.shapes.RECTANGLE, {
      x: mx + 0.12, y: 3.25, w: mw - 0.28, h: 0.48,
      fill: { color: m.color, transparency: 88 }, line: { color: m.color, width: 0 }
    });
    slide.addText(m.formula, {
      x: mx + 0.12, y: 3.25, w: mw - 0.28, h: 0.48,
      fontSize: 10.5, bold: true, color: m.color, fontFace: "Consolas",
      align: "center", valign: "middle", margin: 0
    });

    slide.addText(m.detail, {
      x: mx + 0.12, y: 3.82, w: mw - 0.2, h: 0.98,
      fontSize: 9.5, color: C.muted, fontFace: "Calibri", align: "left", margin: 0
    });

    slide.addText(m.ref, {
      x: mx + 0.12, y: 4.88, w: mw - 0.2, h: 0.24,
      fontSize: 9, bold: true, color: m.color, fontFace: "Calibri", align: "left", margin: 0
    });
  });

  // Combined score note
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.3, y: 5.22, w: 9.4, h: 0.28,
    fill: { color: C.deepBlue, transparency: 88 }, line: { color: C.deepBlue, width: 0 }
  });
  slide.addText("S_i^obs = w1·R(q_peak) + w2·R(F^99) + w3·R(RBI)   |   Event Gate: Y_i^peak ≥ 10, N_i^99 ≥ 5", {
    x: 0.45, y: 5.22, w: 9.1, h: 0.28,
    fontSize: 9.5, bold: true, color: C.deepBlue, fontFace: "Consolas",
    align: "left", valign: "middle", margin: 0
  });
}

// ─── SLIDE 6: STEP 4 — Cohort Separation ─────────────────────────────────────
{
  const slide = pres.addSlide();
  slide.background = { color: C.lightBg };
  addHeaderBar(slide, "Step 4 — Broad / Natural Cohort 분리", "Hydromodification risk에 따른 cohort 구분");

  // Two cohort cards side by side
  const cohorts = [
    {
      name: "Broad Cohort",
      sub: "C^broad",
      color: C.step2,
      badge: "전체 포괄",
      formula: "Q_i = 1,  P_i = 1,\nrank(S_i^obs) ≤ K_b",
      points: [
        "flood-relevant basins 전체 집합",
        "현실적인 환경에서의 모델 성능 평가",
        "hydromodification basin 포함",
        "K_b: broad cohort 크기 파라미터",
      ],
      use: "실제 운영 환경 조건에서의 모델 성능 벤치마킹",
    },
    {
      name: "Natural Cohort",
      sub: "C^natural",
      color: C.step3,
      badge: "자연 basin",
      formula: "Q_i = 1,  P_i = 1,  H_i = 0,\nrank(S_i^obs | H_i=0) ≤ K_n",
      points: [
        "hydromod risk = 0 인 basin만 선택",
        "anthropogenic disturbance 최소화",
        "모델 구조 차이를 더 명확히 비교",
        "K_n: natural cohort 크기 파라미터",
      ],
      use: "순수 hydrologic 거동 차이 분리 및 모델 구조 평가",
    },
  ];

  cohorts.forEach((c, i) => {
    const cx = 0.3 + i * 4.85;
    addCard(slide, cx, 1.3, 4.6, 4.0, { color: C.cardBg, accentColor: c.color });

    // Badge
    slide.addShape(pres.shapes.RECTANGLE, {
      x: cx + 0.12, y: 1.42, w: 1.1, h: 0.32,
      fill: { color: c.color }, line: { color: c.color, width: 0 }
    });
    slide.addText(c.badge, {
      x: cx + 0.12, y: 1.42, w: 1.1, h: 0.32,
      fontSize: 9.5, bold: true, color: C.cardBg, fontFace: "Calibri",
      align: "center", valign: "middle", margin: 0
    });

    slide.addText(c.name, {
      x: cx + 0.12, y: 1.83, w: 4.2, h: 0.38,
      fontSize: 16, bold: true, color: C.textDark, fontFace: "Calibri", align: "left", margin: 0
    });
    slide.addText(c.sub, {
      x: cx + 0.12, y: 2.23, w: 4.2, h: 0.28,
      fontSize: 10, color: c.color, fontFace: "Consolas", align: "left", margin: 0
    });

    // Formula
    slide.addShape(pres.shapes.RECTANGLE, {
      x: cx + 0.12, y: 2.56, w: 4.2, h: 0.7,
      fill: { color: c.color, transparency: 88 }, line: { color: c.color, width: 0 }
    });
    slide.addText(c.formula, {
      x: cx + 0.12, y: 2.56, w: 4.2, h: 0.7,
      fontSize: 10.5, bold: true, color: c.color, fontFace: "Consolas",
      align: "center", valign: "middle", margin: 0
    });

    // Points
    c.points.forEach((pt, j) => {
      slide.addText([
        { text: "  " + pt }
      ], {
        x: cx + 0.12, y: 3.35 + j * 0.3, w: 4.2, h: 0.28,
        fontSize: 10.5, color: C.textMid, fontFace: "Calibri", bullet: false, align: "left", margin: 0
      });
      slide.addShape(pres.shapes.RECTANGLE, {
        x: cx + 0.12, y: 3.49 + j * 0.3, w: 0.05, h: 0.08,
        fill: { color: c.color }, line: { color: c.color, width: 0 }
      });
    });
  });

  // Rationale box
  addCard(slide, 0.3, 5.42, 9.4, 0.06, { color: C.cardBg });
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.3, y: 5.42, w: 9.4, h: 0.04,
    fill: { color: C.cyan }, line: { color: C.cyan, width: 0 }
  });

  slide.addText("Broad — 현실적 모델 성능 평가  |  Natural — anthropogenic 영향 분리 후 순수 hydrologic 구조 비교 가능", {
    x: 0.45, y: 5.32, w: 9.1, h: 0.28,
    fontSize: 10, color: C.muted, fontFace: "Calibri", align: "left", margin: 0
  });
}

// ─── SLIDE 7: CLOSING / REFERENCES ──────────────────────────────────────────
{
  const slide = pres.addSlide();
  slide.background = { color: C.navyBg };

  // Left accent bar
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.18, h: 5.625,
    fill: { color: C.cyan }, line: { color: C.cyan, width: 0 }
  });

  // Title
  slide.addText("구현 현황 & 방법론 근거", {
    x: 0.4, y: 0.4, w: 9.2, h: 0.6,
    fontSize: 26, bold: true, color: C.cardBg, fontFace: "Calibri", align: "left", margin: 0
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.4, y: 1.05, w: 3.0, h: 0.04,
    fill: { color: C.teal }, line: { color: C.teal, width: 0 }
  });

  // Implementation status
  slide.addText("현재 구현 완료", {
    x: 0.4, y: 1.2, w: 4.5, h: 0.35,
    fontSize: 13, bold: true, color: C.cyan, fontFace: "Calibri", align: "left", margin: 0
  });

  const doneItems = [
    "Step 1: DRBC + CAMELSH overlap/outlet 기반 basin 선택",
    "Step 2: usable years, estimated-flow fraction, boundary confidence 품질 필터",
    "Provisional static prioritization (supplementary / exploratory 수준)",
  ];
  doneItems.forEach((item, i) => {
    slide.addText("✓  " + item, {
      x: 0.4, y: 1.62 + i * 0.38, w: 4.5, h: 0.35,
      fontSize: 10.5, color: "A8D8EA", fontFace: "Calibri", align: "left", margin: 0
    });
  });

  // Vertical divider
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 5.1, y: 1.15, w: 0.03, h: 4.0,
    fill: { color: C.teal, transparency: 60 }, line: { color: C.teal, width: 0 }
  });

  // References
  slide.addText("참고 문헌", {
    x: 5.3, y: 1.2, w: 4.3, h: 0.35,
    fontSize: 13, bold: true, color: C.cyan, fontFace: "Calibri", align: "left", margin: 0
  });

  const refs = [
    "Addor et al. (2017) CAMELS dataset — HESS 21, 5293–5313",
    "England et al. (2019) Bulletin 17C — USGS flood frequency",
    "Merz & Blöschl (2009) Event runoff coefficients — WRR 45",
    "Stein et al. (2023) Stream classification RBI — HESS 27",
  ];
  refs.forEach((ref, i) => {
    slide.addText("·  " + ref, {
      x: 5.3, y: 1.65 + i * 0.45, w: 4.3, h: 0.4,
      fontSize: 10, color: "7EB8D4", fontFace: "Calibri", align: "left", margin: 0
    });
  });

  // Bottom tagline
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.3, y: 4.85, w: 9.4, h: 0.6,
    fill: { color: C.deepBlue, transparency: 60 }, line: { color: C.deepBlue, width: 0 }
  });
  slide.addText("논문 본문의 공식 screening은 이 4단계 파이프라인이며, static score는 supplementary / exploratory 수준으로만 사용한다.", {
    x: 0.5, y: 4.88, w: 9.1, h: 0.52,
    fontSize: 10.5, color: "A8D8EA", fontFace: "Calibri", align: "left", valign: "middle", margin: 0
  });
}

// ─── WRITE FILE ──────────────────────────────────────────────────────────────
const outPath = "output/basin_screening_method.pptx";
const fs = require("fs");
if (!fs.existsSync("output")) fs.mkdirSync("output");

pres.writeFile({ fileName: outPath }).then(() => {
  console.log(`✓ Created: ${outPath}`);
}).catch(err => {
  console.error("Error:", err);
  process.exit(1);
});

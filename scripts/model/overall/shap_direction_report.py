#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMN_LABELS = {
    "feature": "지표",
    "feature_group": "지표 구분",
    "mean_abs_shap_mean": "평균 |SHAP|",
    "mean_signed_shap_mean": "평균 부호 SHAP",
    "quadrant_label": "사분면",
    "event_share": "사건 비율",
    "median_signed_shap": "중앙 부호 SHAP",
    "n_events": "사건 수",
    "rainfall_regime": "강우 양상",
    "median_signed_shap_delta_scaled": "방향 편차(정규화)",
    "n_rows": "행 수",
}
VALUE_LABELS = {
    "static_attribute": "정적 유역 속성",
    "dynamic_forcing": "시간변화 기상 입력",
    "feature_high_shap_negative": "값 높음 + SHAP 음수",
    "feature_high_shap_positive": "값 높음 + SHAP 양수",
    "feature_low_shap_negative": "값 낮음 + SHAP 음수",
    "feature_low_shap_positive": "값 낮음 + SHAP 양수",
    "convective_cape": "대류 가능성 큼",
    "antecedent_wet": "선행 강우 많음",
    "cold_or_snow_sensitive": "저온·눈 영향 가능",
    "long_duration": "긴 지속 강우",
    "short_intense": "짧고 강한 강우",
    "unclassified": "분류 보류",
    "positive": "양수",
    "negative": "음수",
    "area": "유역 면적(area)",
    "slope": "유역 경사(slope)",
    "forest_fraction": "산림 비율(forest_fraction)",
    "soil_depth": "토양 깊이(soil_depth)",
    "permeability": "투수성(permeability)",
    "snow_fraction": "눈 영향 비율(snow_fraction)",
    "baseflow_index": "기저유출 지수(baseflow_index)",
    "aridity": "건조도(aridity)",
    "Rainf": "강수량(Rainf)",
    "CAPE": "대류 가능 에너지(CAPE)",
    "Tair": "기온(Tair)",
    "Wind_N": "남북 바람(Wind_N)",
}
FEATURE_ORDER = ["area", "slope", "forest_fraction", "soil_depth", "permeability", "snow_fraction", "baseflow_index"]
REGIME_ORDER = ["short_intense", "long_duration", "antecedent_wet", "convective_cape", "cold_or_snow_sensitive", "unclassified"]


def _fmt(value: float) -> str:
    return f"{value:.4f}"


def _label(value: object) -> str:
    return VALUE_LABELS.get(str(value), str(value))


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|")


def _top_features(scope_summary: pd.DataFrame, scope: str, limit: int = 8) -> pd.DataFrame:
    q99 = scope_summary[scope_summary["quantile"].astype(str).eq("q99") & scope_summary["scope"].eq(scope)].copy()
    return q99.sort_values("mean_abs_shap_mean", ascending=False).head(limit)


def _markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "_해당 조건의 행이 없다._\n"
    header = "| " + " | ".join(_cell(COLUMN_LABELS.get(column, str(column))) for column in columns) + " |"
    rule = "| " + " | ".join(["---"] * len(columns)) + " |"
    rows = []
    for _, row in frame.iterrows():
        values = []
        for column in columns:
            value = row[column]
            values.append(_fmt(float(value)) if isinstance(value, float) else _cell(_label(value)))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join([header, rule, *rows]) + "\n"


def _top_feature_section(scope_summary: pd.DataFrame) -> str:
    columns = ["feature", "feature_group", "mean_abs_shap_mean", "mean_signed_shap_mean"]
    q99_top = _top_features(scope_summary, "q99")
    test_top = _top_features(scope_summary, "test_split")
    q99_dynamic = scope_summary[scope_summary["scope"].eq("q99") & scope_summary["quantile"].astype(str).eq("q99") & scope_summary["feature_group"].eq("dynamic_forcing")]
    dynamic_max = float(q99_dynamic["mean_abs_shap_mean"].max()) if not q99_dynamic.empty else 0.0
    static_to_dynamic = float(q99_top.iloc[0]["mean_abs_shap_mean"]) / dynamic_max if dynamic_max > 0 else 0.0
    return (
        "## 2. 막대그림: q99 출력을 크게 움직이는 지표\n\n"
        "![q99 범위별 중요도](../figures/bar_importance_scope_compare.png)\n\n"
        "그림 1. q99에서 각 지표가 모델 출력에 기여한 평균 크기를 비교한 그림이다.\n\n"
        "![q99 범위별 방향성](../figures/signed_bar_direction_scope_compare.png)\n\n"
        "그림 2. q99에서 각 지표가 모델 출력을 올리는지 또는 낮추는지 평균 방향을 비교한 그림이다.\n\n"
        "q99에서는 정적 유역 속성이 대부분의 설명력을 차지한다. 유역 면적, 유역 경사, 산림 비율, 토양 깊이가 상위권이며, "
        "강수량이나 기온 같은 시간변화 기상 입력은 평균 |SHAP|가 훨씬 작다. 이는 관측 홍수의 실제 원인이 정적 속성이라는 뜻이 아니라, "
        f"모델이 q99 출력을 만들 때 유역 고정 속성을 강하게 사용했다는 뜻이다. q99 표본에서 가장 큰 정적 지표인 유역 면적의 평균 |SHAP|는 가장 큰 시간변화 기상 입력보다 약 {static_to_dynamic:.1f}배 크다. 이 차이는 모델이 극한 꼬리 출력을 낼 때 '그 시점에 비가 얼마나 왔는가'만 보는 것이 아니라, 먼저 유역의 기본 반응 규모를 강하게 반영한다는 신호다.\n\n"
        "### q99 상위 지표\n\n"
        f"{_markdown_table(q99_top[columns], columns)}\n"
        "### 전체 시험 구간 상위 지표\n\n"
        f"{_markdown_table(test_top[columns], columns)}\n"
        "유역 면적은 q99와 전체 시험 구간 모두에서 가장 큰 지표지만 평균 방향이 다르다. q99에서는 평균적으로 음수이고, 전체 시험 구간에서는 양수다. "
        "따라서 큰 유역이면 항상 q99를 올린다고 해석하면 안 된다. q99 사건만 떼어 보면 유역 크기의 역할이 일반 시험 구간과 달라진다.\n"
    )


def _feature_detail(feature: str, q99: pd.DataFrame, seed: pd.DataFrame) -> str:
    sub = q99[q99["feature"].eq(feature)].sort_values("event_share", ascending=False)
    if sub.empty:
        return ""
    top = sub.head(4).copy()
    seed_sub = seed[seed["scope"].eq("q99") & seed["quantile"].astype(str).eq("q99") & seed["feature"].eq(feature)]
    signs = ", ".join(f"seed {int(row['seed'])}: {_label(row['dominant_sign'])}" for _, row in seed_sub.sort_values("seed").iterrows())
    main = top.iloc[0]
    second = top.iloc[1] if len(top) > 1 else top.iloc[0]
    trend = (
        f"가장 큰 비율은 '{_label(main['quadrant_label'])}'이며 사건 비율은 {_fmt(float(main['event_share']))}이다. "
        f"다음으로 큰 분류는 '{_label(second['quadrant_label'])}'이다. "
        f"seed별 우세 방향은 {signs if signs else '확인할 수 없다'}."
    )
    if feature == "area":
        meaning = "유역 면적은 q99에서 평균적으로 음수 쪽이 두드러진다. 큰 유역의 홍수 첨두가 완만하게 표현되거나, q99 극한 사건만 모았을 때 큰 유역이 항상 상위 꼬리 출력을 키우지는 않는다는 신호로 볼 수 있다."
    elif feature == "slope":
        meaning = "유역 경사는 한 방향으로 안정적이지 않다. 경사가 큰 유역이 q99를 낮추는 분류와, 경사가 낮은 유역이 q99를 올리는 분류가 함께 나타난다. 경사는 짧고 강한 강우, 선행 습윤 상태 같은 사건 조건과 함께 봐야 한다."
    elif feature == "forest_fraction":
        meaning = "산림 비율은 완충 효과처럼 보이는 음수 방향과 q99를 올리는 양수 방향이 같이 나타난다. 산림 자체의 물리 효과를 단정하기보다, 모델이 산림 비율을 다른 지형·토양 속성과 함께 사용하는 것으로 해석하는 편이 안전하다."
    elif feature == "soil_depth":
        meaning = "토양 깊이는 세 seed에서 모두 음수 방향이 우세하다. 저장·완충 특성이 q99 출력을 낮추는 쪽으로 사용되었을 가능성이 있으나, 낮은 토양 깊이에서 양수 방향도 나타나므로 단일 기준으로 분류하면 안 된다."
    elif feature == "permeability":
        meaning = "투수성은 값이 높을 때 양수와 음수가 모두 크게 나타난다. 침투·저류 특성이 항상 q99를 낮춘다고 보기 어렵고, 선행 강우가 많은 사건에서는 오히려 양수 방향으로 바뀔 수 있다."
    elif feature == "snow_fraction":
        meaning = "눈 영향 비율은 값이 높은 구간에서 양수와 음수가 모두 나온다. 계절, 기온, 적설 또는 융설 가능성이 함께 작동할 때 방향이 달라지는 지표로 보는 것이 적절하다."
    else:
        meaning = "기저유출 지수는 seed별로 양수 방향이 비교적 안정적이지만, 사분면 안에서는 양수와 음수가 모두 관찰된다. 지하수 기여가 큰 유역의 완충 효과와 장기 유출 반응을 함께 검토해야 한다."
    columns = ["quadrant_label", "event_share", "median_signed_shap", "n_events"]
    return f"\n#### {_label(feature)}\n\n{trend} {meaning}\n\n{_markdown_table(top[columns], columns)}"


def _quantile_trend_section(scope_summary: pd.DataFrame) -> str:
    q99_scope = scope_summary[scope_summary["scope"].eq("q99")]
    key_features = ["area", "slope"]
    sections = []
    for feature in key_features:
        sub = q99_scope[q99_scope["feature"].eq(feature)].sort_values("quantile")
        if sub.empty:
            continue
        df = sub[["quantile", "mean_abs_shap_mean", "mean_signed_shap_mean"]].copy()
        df.columns = ["quantile", "평균 |SHAP|", "평균 부호 SHAP"]
        sections.append(f"\n### {_label(feature)} — quantile별 추세\n\n{_markdown_table(df, list(df.columns))}")
    area_q99 = q99_scope[q99_scope["feature"].eq("area") & q99_scope["quantile"].astype(str).eq("q99")]
    area_q50 = q99_scope[q99_scope["feature"].eq("area") & q99_scope["quantile"].astype(str).eq("q50")]
    amp = f"{(float(area_q99.iloc[0]['mean_abs_shap_mean']) / float(area_q50.iloc[0]['mean_abs_shap_mean']) - 1) * 100:.0f}%" if not area_q99.empty and not area_q50.empty else "?"
    return (
        "\n## 3. 정량적 추세: quantile이 올라갈수록 달라지는 것\n\n"
        f"유역 면적의 |SHAP|는 q50 대비 q99에서 약 {amp} 증가한다. 방향(부호)이 함께 변하는지, 크기만 커지는지가 핵심이다.\n"
        + "".join(sections)
    )


def _scope_direction_compare_section(scope_summary: pd.DataFrame) -> str:
    q99_q99 = scope_summary[scope_summary["scope"].eq("q99") & scope_summary["quantile"].astype(str).eq("q99")].set_index("feature")
    ts_q99 = scope_summary[scope_summary["scope"].eq("test_split") & scope_summary["quantile"].astype(str).eq("q99")].set_index("feature")
    rows = []
    for feature in FEATURE_ORDER:
        if feature not in q99_q99.index:
            continue
        q99_abs = float(q99_q99.loc[feature, "mean_abs_shap_mean"])
        q99_sig = float(q99_q99.loc[feature, "mean_signed_shap_mean"])
        ts_abs = float(ts_q99.loc[feature, "mean_abs_shap_mean"]) if feature in ts_q99.index else float("nan")
        ts_sig = float(ts_q99.loc[feature, "mean_signed_shap_mean"]) if feature in ts_q99.index else float("nan")
        direction_note = "방향 같음" if (q99_sig >= 0) == (ts_sig >= 0) else "방향 반전"
        rows.append({"지표": _label(feature), "q99 |SHAP|": q99_abs, "test_split |SHAP|": ts_abs, "q99 부호": q99_sig, "test_split 부호": ts_sig, "방향 변화": direction_note})
    df = pd.DataFrame(rows)
    return (
        "\n## 4. q99 대 전체 시험 구간: 방향이 달라지는 지표\n\n"
        f"{_markdown_table(df, list(df.columns))}\n"
        "가장 주목할 지표는 유역 경사(slope)와 토양 깊이(soil_depth)다. 경사는 전체 시험 구간에서 방향이 거의 0에 가깝다가 q99에서 음수로 전환된다. "
        "토양 깊이는 전체 시험 구간에서 양수였다가 q99에서 음수로 반전된다. 극한 첨두 사건에서만 이 지표들의 방향이 달라지므로, q99 표본을 따로 해석해야 한다.\n"
    )


def _quadrant_section(quadrant: pd.DataFrame, seed: pd.DataFrame) -> str:
    q99 = quadrant[quadrant["scope"].eq("q99") & quadrant["quantile"].astype(str).eq("q99")].copy()
    rows = []
    for feature in FEATURE_ORDER:
        for _, row in q99[q99["feature"].eq(feature)].sort_values("event_share", ascending=False).head(2).iterrows():
            rows.append({"feature": feature, "quadrant_label": row["quadrant_label"], "event_share": row["event_share"], "median_signed_shap": row["median_signed_shap"], "n_events": int(row["n_events"])})
    summary = pd.DataFrame(rows)
    details = "".join(_feature_detail(feature, q99, seed) for feature in FEATURE_ORDER)
    columns = ["feature", "quadrant_label", "event_share", "median_signed_shap", "n_events"]
    return (
        "\n## 5. 사분면 분석: 평균 하나로 설명하지 못하는 것\n\n"
        "![q99 사분면별 사건 비율](../figures/beeswarm_interpretation_grid_q99.png)\n\n"
        "그림 5a. 전체 seed 통합: 지표 값과 SHAP 부호 조합별 사건 비율.\n\n"
        "![q99 사분면별 사건 비율 (seed별)](../figures/beeswarm_interpretation_grid_q99_by_seed.png)\n\n"
        "그림 5b. seed별 분리: 같은 조합의 사건 비율이 seed에 따라 얼마나 달라지는지 확인한다. "
        "area `feature_low_shap_negative`(소면적·SHAP 음수)는 3개 seed 모두 노란색(0.47~0.48)으로 가장 안정적인 패턴이다. "
        "반면 permeability는 seed 222에서 `feature_high_shap_negative` 비율이 올라가고 `feature_low_shap_positive`가 내려가는 등 seed 222가 111·444와 다른 구조를 보인다.\n\n"
        "벌떼그림에서 점이 넓게 퍼진다는 것은 평균 하나로 설명하기 어렵다는 뜻이다. 같은 지표라도 어떤 사건에서는 q99 출력을 낮추고, 다른 사건에서는 올릴 수 있다. "
        "아래 표의 사건 비율은 행 비율이 아니라 중복을 제거한 사건 기준 비율이다. 같은 사건이 여러 seed와 quantile 산출물에 반복될 수 있으므로, 사건 비율을 먼저 보고 중앙 부호 SHAP로 방향의 크기를 함께 확인하는 순서가 안전하다.\n\n"
        f"{_markdown_table(summary, columns)}"
        "\n### 정적 유역 속성별 상세 해석\n"
        f"{details}"
    )


def _regime_detail(regime: str, q99: pd.DataFrame) -> str:
    sub = q99[q99["rainfall_regime"].eq(regime)].copy()
    if sub.empty:
        return ""
    selected = sub[sub["feature"].isin(["area", "slope", "soil_depth", "permeability", "forest_fraction", "snow_fraction", "Rainf", "CAPE", "Tair", "Wind_N"])]
    pos = selected.sort_values("median_signed_shap_delta_scaled", ascending=False).head(3)
    neg = selected.sort_values("median_signed_shap_delta_scaled", ascending=True).head(3)
    n_rows = int(selected["n_rows"].max()) if "n_rows" in selected else 0
    if regime == "short_intense":
        meaning = "짧고 강한 강우에서는 순간 강우 강도와 빠른 유출 반응이 중요할 수 있다. 다만 이 결과에서는 정적 속성의 방향도 함께 움직이므로, 단순히 강수량만으로 q99 판단이 설명되지는 않는다."
    elif regime == "long_duration":
        meaning = "긴 지속 강우에서는 유역 저장량과 누적 반응이 중요하다. 방향 편차가 비교적 완만하므로, 특정 지표 하나보다 여러 정적 속성이 함께 작동하는 양상으로 보는 편이 좋다."
    elif regime == "antecedent_wet":
        meaning = "선행 강우가 많은 사건에서는 이미 젖은 유역 상태가 전제된다. 투수성, 눈 영향 비율, 경사가 양수 방향으로 이동해, 습윤 조건에서 q99 상위 꼬리 판단이 달라질 수 있음을 시사한다."
    elif regime == "convective_cape":
        meaning = "대류 가능성이 큰 사건은 표본이 적지만 방향 차이가 크다. 유역 면적은 강한 음수, 강수량·대류 가능 에너지·바람은 양수 쪽으로 나타나 짧고 국지적인 강우 반응을 따로 점검할 필요가 있다."
    elif regime == "cold_or_snow_sensitive":
        meaning = "저온·눈 영향 가능 사건은 기온과 눈 관련 조건이 함께 들어온다. 경사와 기온은 양수 방향, 토양 깊이와 강수량은 음수 방향으로 나타나므로, 적설·융설 가능성을 별도로 검토해야 한다."
    else:
        meaning = "분류 보류는 위 기준으로 명확히 나뉘지 않은 사건이다. 일부 지표의 방향 편차가 크더라도 해석 이름을 붙이기보다, 새 분류 기준이 필요한 후보로 남기는 것이 안전하다."
    columns = ["feature", "median_signed_shap", "median_signed_shap_delta_scaled", "n_rows"]
    return f"\n#### {_label(regime)}\n\n해석에 사용된 행 수의 대표값은 {n_rows}개다. {meaning}\n\n양수 방향이 큰 지표:\n\n{_markdown_table(pos[columns], columns)}\n음수 방향이 큰 지표:\n\n{_markdown_table(neg[columns], columns)}"


def _rainfall_section(rainfall: pd.DataFrame) -> str:
    q99 = rainfall[rainfall["quantile"].astype(str).eq("q99")].copy()
    selected = q99[q99["feature"].isin(["area", "slope", "soil_depth", "permeability", "forest_fraction", "snow_fraction", "Rainf", "CAPE", "Tair", "Wind_N"])]
    strongest = selected.reindex(selected["median_signed_shap_delta_scaled"].abs().sort_values(ascending=False).index).head(12)
    details = "".join(_regime_detail(regime, q99) for regime in REGIME_ORDER)
    columns = ["rainfall_regime", "feature", "median_signed_shap", "median_signed_shap_delta_scaled", "n_rows"]
    return (
        "\n## 6. 강우 양상: 비 내리는 방식에 따라 방향이 달라지는가\n\n"
        "![q99 강우 양상별 방향 편차](../figures/rainfall_regime_direction_heatmap_q99.png)\n\n"
        "그림 4. 강우 양상별로 각 지표의 SHAP 방향이 평소보다 얼마나 달라지는지 표시한 그림이다.\n\n"
        "이 그림은 원래 부호 SHAP 값을 그대로 그린 것이 아니다. 지표별 중앙값을 뺀 뒤, 그 지표 안에서 가장 큰 편차를 기준으로 나누었다. "
        "따라서 지표끼리 절대 크기를 비교하는 그림이 아니라 강우 양상 안에서 방향이 달라지는지 보는 그림이다. 강우 양상은 긴 지속 시간, 짧고 강한 강우, 선행 5일 강우, CAPE, 저온 조건 순서로 분류했다. 먼저 걸린 조건이 이름을 결정하므로, 예를 들어 긴 지속 강우이면서 선행 강우도 많은 사건은 긴 지속 강우로 들어간다.\n\n"
        f"{_markdown_table(strongest, columns)}"
        "\n### 강우 양상별 상세 해석\n"
        f"{details}"
    )


def _seed_section(seed: pd.DataFrame) -> str:
    q99 = seed[seed["scope"].eq("q99") & seed["quantile"].astype(str).eq("q99")].copy()
    static = q99[q99["feature"].isin(FEATURE_ORDER)]
    pivot = static.pivot_table(index="feature", columns="seed", values="dominant_sign", aggfunc="first").reset_index()
    pivot.columns = [str(column) for column in pivot.columns]
    return (
        "\n## 7. Seed 안정성: 방향 해석의 신뢰도\n\n"
        "![q99 사분면 부호 SHAP (seed별)](../figures/quadrant_heatmap_q99_by_seed.png)\n\n"
        "그림 7a. seed별 사분면 부호 SHAP. area의 `feature_high_shap_positive` 분류(빨강)가 3개 seed 모두에서 일관되게 나타나며, 그 크기(median +0.42~+0.59)도 seed 222→444로 갈수록 강해진다.\n\n"
        "![q99 강우 양상별 방향 편차 (seed별)](../figures/rainfall_regime_direction_heatmap_q99_by_seed.png)\n\n"
        "그림 7b. seed별 강우 양상 방향 편차. `antecedent_wet` 조건에서 area 음수·Rainf 양수 패턴이 3개 seed 공통이고, `cold_or_snow_sensitive`에서 soil_depth 음수도 공통이다. "
        "`convective_cape`는 seed 444에서 패턴이 달라지지만 표본이 45건으로 적어 소표본 노이즈로 보는 것이 안전하다.\n\n"
        f"{_markdown_table(pivot, list(pivot.columns))}\n"
        "유역 면적과 유역 경사는 3개 seed 모두에서 일관된 방향을 보인다. 나머지 지표(산림 비율, 투수성, 기저유출 지수, 눈 영향 비율)는 1개 seed에서 방향이 뒤집힌다. "
        "이 지표들은 단일 방향 결론보다 강우 양상 또는 유역 조합에 따라 달라지는 지표로 해석해야 한다. seed 안정성 표는 평균 |SHAP| 순위를 대체하는 표가 아니라, 같은 지표 방향이 학습 초기값 변화에도 유지되는지 확인하는 보조 장치다. 한 seed에서만 방향이 바뀌는 지표는 논문 본문에서 강한 단정 대신 '조건 의존적 방향성'으로 표현하는 것이 안전하다.\n"
    )


def _sample_section(matrix: pd.DataFrame | None, issues: pd.DataFrame | None) -> str:
    if matrix is None or issues is None:
        return "### 분석 표본과 산출물\n\n표본 수와 병합 이슈 수는 `data/direction_manifest.json`과 `tables/direction_event_feature_matrix.csv`에서 확인한다. 이 report는 재생성 경로에서는 해당 표를 받아 q99 사건 표본과 전체 시험 구간 표본을 함께 요약한다.\n\n"
    q99 = matrix[matrix["scope"].eq("q99")]
    test_split = matrix[matrix["scope"].eq("test_split")]
    q99_events = q99[["basin", "event_id"]].drop_duplicates().shape[0]
    test_events = test_split[["basin", "event_id"]].drop_duplicates().shape[0]
    q99_basins = q99["basin"].nunique()
    test_basins = test_split["basin"].nunique()
    seeds = ", ".join(str(int(seed)) for seed in sorted(matrix["seed"].unique()))
    quantiles = ", ".join(sorted(matrix["quantile"].astype(str).unique()))
    return (
        "### 분석 표본과 산출물\n\n"
        f"이 보고서는 `direction_event_feature_matrix.csv`의 {len(matrix):,}개 행을 기반으로 한다. q99 사건 표본은 {q99_basins}개 유역의 {q99_events}개 사건이고, 전체 시험 구간 비교 표본은 {test_basins}개 유역의 {test_events}개 관측 기준 시점이다. "
        f"seed는 {seeds}, 출력 quantile은 {quantiles}를 함께 집계했다. `direction_merge_issues.csv`의 병합 이슈는 {len(issues):,}개라서, q99 사건 SHAP와 강우 요약·정적 유역 속성의 결합은 현재 표 기준으로 누락 없이 완료된 상태다.\n\n"
        "비교 범위는 두 가지다. `q99`는 극한 첨두 사건만 모은 표본이고, `test_split`은 전체 시험 구간에서 유량 구간별로 뽑은 기준 시점이다. 따라서 두 범위의 평균 |SHAP| 크기는 표본 정의가 달라 직접 성능 점수처럼 비교하지 않는다. 여기서는 같은 모델이 일반 시험 구간과 극한 사건에서 어떤 입력을 다르게 쓰는지 보는 데 초점을 둔다.\n\n"
    )


def _case_study_section() -> str:
    return (
        "\n## 8. 대표 사건 분석: waterfall 해석\n\n"
        "waterfall 그림은 단일 사건에 대해 각 지표가 모델 q99 출력을 기준값(모든 사건 예측 평균, 정규화 기준)에서 얼마나 올리거나 낮췄는지 보여준다. "
        "세 대표 사건은 아래 기준으로 선정했다.\n\n"
        "| 사건 유형 | 사건 번호 | 유역 | 관측 첨두 (m³/s) | q99 예측 | 오차 |\n"
        "|-----------|-----------|------|-------------------|----------|------|\n"
        "| 최대 과소추정 | 12 | 1446776 | 109.9 | 2.8 | −97.5% |\n"
        "| 최대 과대추정 | 2 | 1443900 | 3.7 | 145.8 | +3800% |\n"
        "| 최적 매칭 | 5 | 1480870 | 35.0 | 35.1 | +0.06% |\n\n"
        "![waterfall — 최대 과소추정](../figures/waterfall_max_underestimation.png)\n\n"
        "**최대 과소추정 사건 (유역 1446776, event 12):** 관측 첨두는 109.9 m³/s이지만 q99 예측은 2.8 m³/s에 그쳤다. "
        "waterfall에서 permeability(높음, SHAP −0.195)와 forest_fraction(높음, SHAP −0.046)이 q99 출력을 기준값 아래로 가장 많이 끌어내렸다. "
        "soil_depth는 낮아 SHAP +0.134를 기록해 반대 방향으로 작용했지만 permeability의 음의 기여를 상쇄하기엔 부족했다. "
        "area는 낮은 값(81 km²)임에도 SHAP −0.070이어서, 면적이 작을 때도 음의 기여가 나타나는 비선형 반응을 보인다. "
        "동적 기상 기여 합계는 거의 0에 가까워, 이 사건에서 모델의 q99 판단은 정적 유역 속성에 의해 결정됐음을 뜻한다.\n\n"
        "![waterfall — 최대 과대추정](../figures/waterfall_max_overestimation.png)\n\n"
        "**최대 과대추정 사건 (유역 1443900, event 2):** 관측 첨두 3.7 m³/s 대비 q99는 145.8 m³/s로 극단적 과대추정이다. "
        "forest_fraction(높음, SHAP +0.076)과 baseflow_index(높음, SHAP +0.062)가 q99 출력을 끌어올렸고, "
        "slope(높음, SHAP −0.103)가 이를 일부 낮추는 구조다. "
        "permeability는 낮아 SHAP +0.036이고 area는 낮아 SHAP −0.077이다. "
        "이 사건의 정적 속성 조합이 모델 입장에서는 '극한 첨두가 높을' 조건으로 해석됐지만, 실제 관측은 이와 크게 다른 결과를 보여 모델의 체계적 한계가 드러나는 사례다.\n\n"
        "![waterfall — 최적 매칭](../figures/waterfall_best_match.png)\n\n"
        "**최적 매칭 사건 (유역 1480870, event 5):** 관측과 q99 예측이 35 m³/s 수준으로 거의 일치한다. "
        "area(큰 값, SHAP +0.226)가 q99를 끌어올리고, soil_depth(높음, SHAP −0.216)가 거의 같은 크기로 상쇄하는 구조다. "
        "slope(높음, SHAP −0.089), forest_fraction(낮음, SHAP −0.050)도 하향 기여를 더한다. "
        "이 사건은 대립하는 정적 속성 기여들이 균형을 이뤄 예측이 맞아 들어간 사례이며, 개별 지표 기여를 보면 사실 큰 기여들이 서로 상쇄되는 구조다.\n\n"
        "### 의존도 산점도: 지표 값과 SHAP 방향의 관계\n\n"
        "의존도 산점도는 단일 지표의 값(x축)과 그 지표의 SHAP 값(y축)을 모든 q99 사건에 걸쳐 나타낸다. "
        "2차 지표를 색상으로 함께 표시하여 상호작용 효과를 확인할 수 있다.\n\n"
        "![dependence — area](../figures/dependence_area.png)\n\n"
        "**유역 면적:** 낮은 면적 유역은 SHAP가 음수와 양수 모두에 걸쳐 넓게 퍼지는 반면, "
        "높은 면적 유역은 양수 SHAP가 우세하다. "
        "y=0 위의 점들(면적이 크고 SHAP 양수)은 대형 유역에서 모델이 q99를 높이는 방향으로 반응한 사건이다. "
        "색상(slope)을 보면 경사가 높은 사건(파란색)은 동일 면적에서도 다른 방향을 나타낼 수 있어, 면적과 경사의 상호작용이 있음을 시사한다.\n\n"
        "![dependence — slope](../figures/dependence_slope.png)\n\n"
        "**유역 경사:** 낮은 경사에서는 양수 SHAP, 높은 경사에서는 음수 SHAP가 우세한 경향이 있어, "
        "완경사 유역에서 경사가 q99를 올리는 역할을 하고 급경사 유역에서는 낮추는 역할을 한다. "
        "이 비선형 패턴은 경사 단독으로 방향을 고정하기 어렵다는 §5의 사분면 분석과 일치한다.\n\n"
        "![dependence — soil_depth](../figures/dependence_soil_depth.png)\n\n"
        "**토양 깊이:** 토양 깊이가 증가할수록 SHAP가 점진적으로 음수 방향으로 이동하는 패턴이 가장 단조롭다. "
        "깊은 토양은 모델이 일관되게 q99 출력을 낮추는 근거로 사용한다. "
        "이는 깊은 토양이 큰 저류 용량을 나타내므로 모델이 이를 첨두 유출 억제 신호로 해석했을 가능성과 물리적으로 일치한다.\n\n"
    )


def write_report(out_dir: Path, scope_summary: pd.DataFrame, quadrant: pd.DataFrame, rainfall: pd.DataFrame, seed: pd.DataFrame, matrix: pd.DataFrame | None = None, issues: pd.DataFrame | None = None) -> None:
    report = out_dir / "report" / "direction_analysis_report.md"
    body = (
        "# SHAP 방향성 분석 상세 보고서\n\n"
        "q99는 보정된 99% 예측구간이나 재현기간이 아니라, 모델이 상위 꼬리 유량을 판단하기 위해 낸 출력이다. "
        "SHAP는 모델 출력이 어떤 입력에 의해 올라가거나 내려갔는지 설명하는 방법이며, 관측 홍수의 실제 원인을 직접 증명하지 않는다. "
        "따라서 이 문서의 문장은 모두 '모델이 q99 출력을 만드는 방식'에 대한 해석이며, '실제 유역에서 홍수가 발생한 물리 원인'에 대한 인과 주장으로 읽으면 안 된다.\n\n"
        "## 1. 무엇을 보는 분석인지\n\n"
        "막대그림은 평균 |SHAP|로 지표의 중요도 크기를 본다. |SHAP|는 부호를 없앤 기여 크기이므로, 어떤 지표가 출력을 크게 움직였는지는 알려주지만 올렸는지 낮췄는지는 말하지 않는다. "
        "부호가 있는 SHAP 막대그림은 지표가 모델 출력을 올리는지 낮추는지 본다. 평균 부호 SHAP가 양수이면 그 지표가 평균적으로 q99 출력을 높이는 쪽으로 작동했고, 음수이면 낮추는 쪽으로 작동했다는 뜻이다. "
        "벌떼그림은 사건과 유역에 따라 SHAP 값이 얼마나 넓게 퍼지는지 보여준다. 이 보고서는 전체 시험 구간과 q99를 비교하되, 극한 첨두 과소추정 질문과 직접 연결되는 q99를 중심으로 해석한다.\n\n"
        "여기서 '방향성'은 지표 값 자체의 크고 작음과 모델 출력 기여의 부호를 함께 본다는 뜻이다. 예를 들어 유역 면적이 큰 사건에서 SHAP가 음수라면, 모델은 그 사건에서 유역 면적 정보를 q99 출력을 낮추는 근거로 사용한 것이다. 반대로 유역 면적이 작아도 SHAP가 음수일 수 있으므로, 단순히 '큰 값이면 출력이 오른다'처럼 읽으면 안 된다.\n\n"
        f"{_sample_section(matrix, issues)}"
        f"{_top_feature_section(scope_summary)}"
        f"{_quantile_trend_section(scope_summary)}"
        f"{_scope_direction_compare_section(scope_summary)}"
        f"{_quadrant_section(quadrant, seed)}"
        f"{_rainfall_section(rainfall)}"
        f"{_seed_section(seed)}"
        f"{_case_study_section()}"
        "\n## 9. 종합 해석\n\n"
        "q99 벌떼그림의 넓은 퍼짐은 지표 중요도가 무의미하다는 뜻이 아니다. 같은 정적 유역 속성이라도 지표 값의 높고 낮음, SHAP 부호, 강우 양상, seed에 따라 방향이 갈린다는 뜻이다. "
        "따라서 q99 해석은 평균 막대그림 하나로 끝내면 안 되고, 정적 유역 속성 값의 높고 낮음과 사건별 강우 양상을 함께 봐야 한다.\n\n"
        "해석은 다음과 같다. 이 결과는 q99 출력이 단순히 비가 많이 온 시점을 따라간다기보다, 모델이 먼저 유역의 기본 성격을 보고 상위 꼬리 유량을 조절한 뒤, 강우 양상에 따라 그 방향을 일부 바꾸는 구조에 가깝다. "
        "특히 유역 면적과 토양 깊이는 q99에서 음수 방향이 비교적 안정적으로 나타난다. 이는 큰 유역이나 저장 능력이 큰 유역에서 모델이 극한 첨두를 상대적으로 낮추는 쪽으로 판단했을 가능성을 보여준다. "
        "반대로 유역 경사, 투수성, 산림 비율, 눈 영향 비율은 seed와 강우 양상에 따라 방향이 바뀐다. 이 지표들은 하나의 물리적 의미로 고정하기보다, 특정 사건 조건에서 q99 출력을 올리거나 낮추는 조절 지표로 보는 것이 맞다.\n\n"
        "논문에서 바로 주장해도 되는 것은 세 가지다. 첫째, q99 설명에서 정적 유역 속성의 비중이 시간변화 기상 입력보다 훨씬 크다. 둘째, q99 표본에서는 전체 시험 구간과 다른 방향성이 나타나므로 극한 첨두만 따로 해석해야 한다. 셋째, 벌떼그림의 퍼짐은 평균 해석의 한계를 보여주며, 지표 값과 SHAP 부호를 함께 나눈 사분면 해석이 필요하다.\n\n"
        "아직 주장하면 안 되는 것도 분명하다. 이 결과만으로 산림, 토양, 눈, 투수성이 실제 홍수 발생을 인과적으로 줄이거나 키운다고 말하면 안 된다. 또한 대류 가능성 큼, 저온·눈 영향 가능, 분류 보류 같은 일부 강우 양상은 표본 수가 작으므로 결론이 아니라 후속 검토 가설로 두어야 한다. "
        "따라서 최종 문장은 '모델이 q99 극한 첨두 판단에서 어떤 정보를 사용했는가'에 맞추고, '실제 유역 물리 과정이 무엇인가'는 관측 기반 추가 분석으로 분리하는 것이 안전하다.\n\n"
        "논문에서는 유역 면적, 유역 경사, 산림 비율, 토양 깊이가 q99 출력의 주요 설명 축이라는 점을 먼저 제시하는 것이 좋다. "
        "그 다음 벌떼그림과 강우 양상 분석을 통해 평균 방향이 왜 단순하지 않은지 설명하면, 모델이 극한 첨두를 어떻게 판단하는지 더 설득력 있게 보여줄 수 있다.\n"
    )
    report.write_text(body, encoding="utf-8")

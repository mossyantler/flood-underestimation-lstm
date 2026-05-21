"use client";

import { useMemo, useState } from "react";
import {
  confirmedFloodSnapshot,
  type ConfirmedFloodEvent,
} from "@/lib/confirmed-flood-data";

type MetricKey = "q99Reduction" | "q99Under" | "m1Under" | "eventCount" | "noaaRate";
type BasinSummary = {
  usgsId: string;
  gaugeName: string;
  state: string;
  basinType: string;
  mapX: number;
  mapY: number;
  events: number;
  noaaRate: number;
  medianM1Under: number;
  medianQ99Under: number;
  medianQ99Reduction: number;
  q99UnderRate: number;
  tiers: Record<string, number>;
  noaaTypes: Record<string, number>;
  performanceTypes: Record<string, number>;
};

const metricLabels: Record<MetricKey, string> = {
  q99Reduction: "q99 under-deficit 감소",
  q99Under: "q99 peak under-deficit",
  m1Under: "Model 1 peak under-deficit",
  eventCount: "event 수",
  noaaRate: "NOAA annotation 비율",
};

const performanceLabels: Record<string, string> = {
  q99_reduced_under: "q99 reduced underestimation",
  q99_over_prediction: "q99 crossed to over-prediction",
  q99_not_improved: "q99 did not reduce",
  m1_not_under: "Model 1 already not under",
  unknown: "unknown",
};

function num(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function median(values: number[]): number {
  const clean = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!clean.length) return 0;
  const mid = Math.floor(clean.length / 2);
  return clean.length % 2 ? clean[mid] : (clean[mid - 1] + clean[mid]) / 2;
}

function pct(value: number | null | undefined, digits = 1): string {
  return `${(num(value) * 100).toFixed(digits)}%`;
}

function rate(value: number | null | undefined, digits = 1): string {
  return `${num(value).toFixed(digits)}%`;
}

function signedPct(value: number | null | undefined, digits = 1): string {
  const out = num(value) * 100;
  return `${out >= 0 ? "+" : ""}${out.toFixed(digits)}%`;
}

function inc(target: Record<string, number>, key: string) {
  target[key] = (target[key] ?? 0) + 1;
}

function aggregateBasins(events: readonly ConfirmedFloodEvent[]): BasinSummary[] {
  const buckets = new Map<string, {
    base: ConfirmedFloodEvent;
    events: ConfirmedFloodEvent[];
    tiers: Record<string, number>;
    noaaTypes: Record<string, number>;
    performanceTypes: Record<string, number>;
  }>();

  for (const event of events) {
    const found = buckets.get(event.usgsId);
    const bucket = found ?? {
      base: event,
      events: [],
      tiers: {},
      noaaTypes: {},
      performanceTypes: {},
    };
    bucket.events.push(event);
    inc(bucket.tiers, event.floodTier);
    inc(bucket.noaaTypes, event.noaaType);
    inc(bucket.performanceTypes, event.performanceType);
    buckets.set(event.usgsId, bucket);
  }

  return [...buckets.entries()].map(([usgsId, bucket]) => {
    const rows = bucket.events;
    return {
      usgsId,
      gaugeName: bucket.base.gaugeName,
      state: bucket.base.state,
      basinType: bucket.base.basinType,
      mapX: num(bucket.base.mapX),
      mapY: num(bucket.base.mapY),
      events: rows.length,
      noaaRate: rows.filter((event) => event.noaaCorroborated).length / rows.length * 100,
      medianM1Under: median(rows.map((event) => num(event.m1Under))),
      medianQ99Under: median(rows.map((event) => num(event.q99Under))),
      medianQ99Reduction: median(rows.map((event) => num(event.q99Reduction))),
      q99UnderRate: rows.filter((event) => num(event.q99Under) > 0).length / rows.length * 100,
      tiers: bucket.tiers,
      noaaTypes: bucket.noaaTypes,
      performanceTypes: bucket.performanceTypes,
    };
  }).sort((a, b) => b.events - a.events || a.usgsId.localeCompare(b.usgsId));
}

function groupEvents(
  events: readonly ConfirmedFloodEvent[],
  getKey: (event: ConfirmedFloodEvent) => string,
  labelForKey: (key: string) => string = (key) => key,
) {
  const buckets = new Map<string, ConfirmedFloodEvent[]>();
  for (const event of events) {
    const key = getKey(event);
    buckets.set(key, [...(buckets.get(key) ?? []), event]);
  }
  return [...buckets.entries()]
    .map(([key, rows]) => ({
      key,
      label: labelForKey(key),
      events: rows.length,
      basins: new Set(rows.map((event) => event.usgsId)).size,
      medianReduction: median(rows.map((event) => num(event.q99Reduction))),
      q99UnderRate: rows.filter((event) => num(event.q99Under) > 0).length / rows.length * 100,
      noaaRate: rows.filter((event) => event.noaaCorroborated).length / rows.length * 100,
    }))
    .sort((a, b) => b.events - a.events || a.label.localeCompare(b.label));
}

function metricValue(basin: BasinSummary, metric: MetricKey): number {
  if (metric === "q99Reduction") return basin.medianQ99Reduction;
  if (metric === "q99Under") return basin.medianQ99Under;
  if (metric === "m1Under") return basin.medianM1Under;
  if (metric === "eventCount") return basin.events;
  return basin.noaaRate;
}

function metricText(basin: BasinSummary, metric: MetricKey): string {
  const value = metricValue(basin, metric);
  if (metric === "eventCount") return `${value}`;
  if (metric === "noaaRate") return rate(value);
  return signedPct(value);
}

function dotColor(basin: BasinSummary, metric: MetricKey): string {
  const value = metricValue(basin, metric);
  if (metric === "q99Reduction") {
    if (value >= 0.5) return "#50e3c2";
    if (value >= 0.2) return "#6bb4ff";
    if (value >= 0) return "#f7b955";
    return "#ff6b8a";
  }
  if (metric === "q99Under" || metric === "m1Under") {
    if (value <= 0) return "#50e3c2";
    if (value <= 0.25) return "#6bb4ff";
    if (value <= 0.6) return "#f7b955";
    return "#ff6b8a";
  }
  if (metric === "eventCount") {
    if (value >= 25) return "#ff6b8a";
    if (value >= 12) return "#f7b955";
    return "#6bb4ff";
  }
  if (value >= 75) return "#50e3c2";
  if (value >= 45) return "#f7b955";
  return "#8f8f8f";
}

function countText(counts: Record<string, number>, labels?: Record<string, string>): string {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 3);
  return entries.map(([key, value]) => `${labels?.[key] ?? key} ${value}`).join(" · ");
}

function SelectControl({
  label,
  value,
  options,
  onChange,
  labelMap,
}: {
  label: string;
  value: string;
  options: readonly string[];
  onChange: (value: string) => void;
  labelMap?: Record<string, string>;
}) {
  return (
    <label className="confirmed-control">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="all">all</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {labelMap?.[option] ?? option}
          </option>
        ))}
      </select>
    </label>
  );
}

function SummaryBars({
  title,
  rows,
  color,
}: {
  title: string;
  rows: ReturnType<typeof groupEvents>;
  color: string;
}) {
  const maxEvents = Math.max(1, ...rows.map((row) => row.events));
  return (
    <section className="panel research-panel">
      <div className="panel-sub">{title}</div>
      <div className="confirmed-bar-stack">
        {rows.slice(0, 6).map((row) => (
          <div className="confirmed-bar-row" key={row.key}>
            <div>
              <strong>{row.label}</strong>
              <span>{row.basins} basins · q99 under {rate(row.q99UnderRate, 0)}</span>
            </div>
            <div className="confirmed-mini-track">
              <span style={{ width: `${(row.events / maxEvents) * 100}%`, background: color }} />
            </div>
            <em>{row.events}</em>
          </div>
        ))}
      </div>
    </section>
  );
}

export function ConfirmedFloodDashboard() {
  const [tier, setTier] = useState("all");
  const [noaaType, setNoaaType] = useState("all");
  const [performanceType, setPerformanceType] = useState("all");
  const [period, setPeriod] = useState("all");
  const [metric, setMetric] = useState<MetricKey>("q99Reduction");
  const [selectedBasin, setSelectedBasin] = useState<string>(
    confirmedFloodSnapshot.basins[0]?.usgsId ?? "",
  );

  const filteredEvents = useMemo(() => (
    confirmedFloodSnapshot.events.filter((event) => (
      (tier === "all" || event.floodTier === tier) &&
      (noaaType === "all" || event.noaaType === noaaType) &&
      (performanceType === "all" || event.performanceType === performanceType) &&
      (period === "all" || event.period === period)
    ))
  ), [tier, noaaType, performanceType, period]);

  const basins = useMemo(() => aggregateBasins(filteredEvents), [filteredEvents]);
  const activeBasin = basins.find((basin) => basin.usgsId === selectedBasin) ?? basins[0];
  const activeEvents = activeBasin
    ? filteredEvents
        .filter((event) => event.usgsId === activeBasin.usgsId)
        .sort((a, b) => num(a.q99Reduction) - num(b.q99Reduction))
        .slice(0, 8)
    : [];
  const basinById = useMemo(
    () => new Map(basins.map((basin) => [basin.usgsId, basin])),
    [basins],
  );

  const tierRows = useMemo(() => groupEvents(filteredEvents, (event) => event.floodTier), [filteredEvents]);
  const noaaRows = useMemo(() => groupEvents(filteredEvents, (event) => event.noaaType), [filteredEvents]);
  const performanceRows = useMemo(
    () => groupEvents(filteredEvents, (event) => event.performanceType, (key) => performanceLabels[key] ?? key),
    [filteredEvents],
  );
  const eventList = useMemo(() => (
    [...filteredEvents]
      .sort((a, b) => num(a.q99Reduction) - num(b.q99Reduction))
      .slice(0, 10)
  ), [filteredEvents]);

  const summary = confirmedFloodSnapshot.summary;
  const selectedMetric = metricLabels[metric];

  return (
    <div className="confirmed-dashboard">
      <div className="confirmed-kpis">
        <div className="confirmed-kpi">
          <span>event universe</span>
          <strong>{summary.events}</strong>
          <em>{summary.basins} basins · {summary.seeds.join("/")}</em>
        </div>
        <div className="confirmed-kpi">
          <span>NOAA annotation</span>
          <strong>{summary.noaaRate}%</strong>
          <em>{summary.noaaEvents} / {summary.events} events</em>
        </div>
        <div className="confirmed-kpi">
          <span>q99 median reduction</span>
          <strong>{signedPct(summary.medianQ99Reduction)}</strong>
          <em>M1 {pct(summary.medianM1Under)} → q99 {pct(summary.medianQ99Under)}</em>
        </div>
        <div className="confirmed-kpi">
          <span>NWS coverage gate</span>
          <strong>{summary.coverageHasFloodStageBasins}</strong>
          <em>/ {summary.coverageTotalDrbcBasins} DRBC basins with flood stage</em>
        </div>
      </div>

      <div className="confirmed-filter-bar">
        <SelectControl label="flood tier" value={tier} options={confirmedFloodSnapshot.filters.tiers} onChange={setTier} />
        <SelectControl label="NOAA type" value={noaaType} options={confirmedFloodSnapshot.filters.noaaTypes} onChange={setNoaaType} />
        <SelectControl
          label="performance type"
          value={performanceType}
          options={confirmedFloodSnapshot.filters.performanceTypes}
          onChange={setPerformanceType}
          labelMap={performanceLabels}
        />
        <SelectControl label="period" value={period} options={confirmedFloodSnapshot.filters.periods} onChange={setPeriod} />
        <label className="confirmed-control">
          <span>map metric</span>
          <select value={metric} onChange={(event) => setMetric(event.target.value as MetricKey)}>
            {(Object.keys(metricLabels) as MetricKey[]).map((key) => (
              <option key={key} value={key}>{metricLabels[key]}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="confirmed-workbench">
        <section className="panel confirmed-map-panel">
          <div className="panel-header">
            <div>
              <div className="panel-sub">DRBC confirmed flood basin map</div>
              <div className="panel-title">{selectedMetric}</div>
            </div>
            <div className="confirmed-count-pill">{filteredEvents.length} events · {basins.length} basins</div>
          </div>
          <svg
            className="confirmed-map"
            viewBox={`0 0 ${confirmedFloodSnapshot.mapGeometry.viewBoxWidth} ${confirmedFloodSnapshot.mapGeometry.viewBoxHeight}`}
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label="DRBC confirmed flood basin polygon map"
          >
            <path className="confirmed-boundary-fill" d={confirmedFloodSnapshot.mapGeometry.boundaryPath} />
            {confirmedFloodSnapshot.mapGeometry.basinPaths.map((shape) => {
              const basin = basinById.get(shape.usgsId);
              const active = activeBasin?.usgsId === shape.usgsId;
              return (
                <path
                  key={shape.usgsId}
                  className="confirmed-basin-shape"
                  d={shape.path}
                  fill={basin ? dotColor(basin, metric) : "#191919"}
                  opacity={basin ? (active ? 0.92 : 0.58) : 0.18}
                  stroke={active ? "#f5f5f5" : "#2e2e2e"}
                  strokeWidth={active ? 1.5 : 0.45}
                  onClick={basin ? () => setSelectedBasin(shape.usgsId) : undefined}
                  aria-label={basin ? `${basin.usgsId} · ${selectedMetric}: ${metricText(basin, metric)}` : shape.usgsId}
                />
              );
            })}
            <path className="confirmed-boundary-line" d={confirmedFloodSnapshot.mapGeometry.boundaryPath} />
            {basins.map((basin) => {
              const active = activeBasin?.usgsId === basin.usgsId;
              return (
                <circle
                  key={basin.usgsId}
                  cx={basin.mapX}
                  cy={basin.mapY}
                  r={2.6}
                  fill="#f5f5f5"
                  stroke={active ? "#f5f5f5" : "#0a0a0a"}
                  strokeWidth={active ? 2.2 : 0.9}
                  opacity={active ? 1 : 0.78}
                  onClick={() => setSelectedBasin(basin.usgsId)}
                  aria-label={`${basin.usgsId} · ${basin.gaugeName} · ${selectedMetric}: ${metricText(basin, metric)}`}
                />
              );
            })}
          </svg>
          <div className="confirmed-map-note">
            실제 DRBC boundary와 CAMELSH basin polygon을 사용합니다. 색은 polygon metric이고, 흰 점은 같은 크기의 gauge 위치 marker입니다.
          </div>
        </section>

        <section className="panel confirmed-detail-panel">
          <div className="panel-sub">selected basin</div>
          {activeBasin ? (
            <>
              <div className="panel-title">{activeBasin.usgsId} · {activeBasin.state}</div>
              <p className="panel-body">{activeBasin.gaugeName}</p>
              <div className="confirmed-detail-grid">
                <div><span>events</span><strong>{activeBasin.events}</strong></div>
                <div><span>NOAA</span><strong>{rate(activeBasin.noaaRate, 0)}</strong></div>
                <div><span>M1 under</span><strong>{pct(activeBasin.medianM1Under)}</strong></div>
                <div><span>q99 reduction</span><strong>{signedPct(activeBasin.medianQ99Reduction)}</strong></div>
              </div>
              <div className="confirmed-chip-line">
                <span>{activeBasin.basinType}</span>
                <span>{countText(activeBasin.tiers)}</span>
                <span>{countText(activeBasin.noaaTypes)}</span>
              </div>
              <div className="data-block confirmed-mini-table">
                <table className="data-table">
                  <thead><tr><th>peak</th><th>tier</th><th>type</th><th style={{ textAlign: "right" }}>q99 Δ</th></tr></thead>
                  <tbody>
                    {activeEvents.map((event) => (
                      <tr key={event.eventId}>
                        <td>{event.peakTime.slice(0, 10)}</td>
                        <td>{event.floodTier}</td>
                        <td>{event.noaaType}</td>
                        <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)", color: num(event.q99Reduction) >= 0 ? "#50e3c2" : "#ff6b8a" }}>
                          {signedPct(event.q99Reduction, 0)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="panel-body">현재 필터에 맞는 basin이 없습니다.</p>
          )}
        </section>
      </div>

      <div className="panel-grid">
        <SummaryBars title="flood tier breakdown" rows={tierRows} color="#50e3c2" />
        <SummaryBars title="NOAA event type breakdown" rows={noaaRows} color="#f7b955" />
        <SummaryBars title="performance type breakdown" rows={performanceRows} color="#6bb4ff" />
        <section className="panel research-panel">
          <div className="panel-sub">model / quantile aggregate</div>
          <div className="data-block">
            <table className="data-table">
              <thead><tr><th>predictor</th><th style={{ textAlign: "right" }}>under-rate</th><th style={{ textAlign: "right" }}>median deficit</th><th style={{ textAlign: "right" }}>NRMSE</th></tr></thead>
              <tbody>
                {confirmedFloodSnapshot.modelQuantileSummary.map((row) => (
                  <tr key={row.key}>
                    <td style={{ color: row.quantile === "q99" ? "#6bb4ff" : "var(--ink-body)", fontWeight: row.quantile === "det" ? 700 : 500 }}>{row.label}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)" }}>{rate(row.underRate)}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)" }}>{pct(row.medianUnder)}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)" }}>{num(row.medianNrmse).toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section className="panel research-panel">
        <div className="panel-header">
          <div>
            <div className="panel-sub">event table · worst q99-reduction first</div>
            <div className="panel-title">필터 결과 event sample</div>
          </div>
          <div className="confirmed-count-pill">source: performance + event_windows + catalog</div>
        </div>
        <div className="data-block">
          <table className="data-table confirmed-event-table">
            <thead>
              <tr>
                <th>event</th><th>basin</th><th>tier</th><th>NOAA type</th><th>performance type</th>
                <th style={{ textAlign: "right" }}>M1 deficit</th>
                <th style={{ textAlign: "right" }}>q99 deficit</th>
                <th style={{ textAlign: "right" }}>q99 Δ</th>
              </tr>
            </thead>
            <tbody>
              {eventList.map((event) => (
                <tr key={event.eventId}>
                  <td data-label="event">{event.peakTime.replace("T", " ")}</td>
                  <td data-label="basin">
                    <button className="confirmed-table-link" onClick={() => setSelectedBasin(event.usgsId)}>
                      {event.usgsId}
                    </button>
                  </td>
                  <td data-label="tier">{event.floodTier}</td>
                  <td data-label="NOAA type">{event.noaaType}</td>
                  <td data-label="performance type">{performanceLabels[event.performanceType] ?? event.performanceType}</td>
                  <td data-label="M1 deficit" style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)" }}>{pct(event.m1Under)}</td>
                  <td data-label="q99 deficit" style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)", color: num(event.q99Under) > 0 ? "#f7b955" : "#50e3c2" }}>{pct(event.q99Under)}</td>
                  <td data-label="q99 Δ" style={{ textAlign: "right", fontFamily: "var(--font-geist-mono)", color: num(event.q99Reduction) >= 0 ? "#50e3c2" : "#ff6b8a" }}>{signedPct(event.q99Reduction)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

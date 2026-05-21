"use client";

import { useMemo, useState } from "react";
import type { AnalysisModuleCopy } from "@/lib/evidence-types";
import type {
  DatasetArtifact,
  DatasetArtifactLayer,
  DatasetExplorerData,
  MarkdownBlock,
} from "@/lib/dataset-explorer-types";

const LAYERS: DatasetArtifactLayer[] = ["Input", "Result", "Analysis", "Database"];

type DatasetEvidenceExplorerProps = {
  copy: AnalysisModuleCopy;
  data: DatasetExplorerData;
};

export function DatasetEvidenceExplorer({ copy, data }: DatasetEvidenceExplorerProps) {
  const [activeLayer, setActiveLayer] = useState<DatasetArtifactLayer>("Input");
  const [selectedId, setSelectedId] = useState(() => data.artifacts.find((artifact) => artifact.layer === "Input")?.id ?? "");

  const visibleArtifacts = useMemo(
    () => data.artifacts.filter((artifact) => artifact.layer === activeLayer),
    [activeLayer, data.artifacts],
  );
  const selected = visibleArtifacts.find((artifact) => artifact.id === selectedId) ?? visibleArtifacts[0];
  const activePanelId = `dataset-layer-panel-${activeLayer.toLowerCase()}`;

  function selectLayer(layer: DatasetArtifactLayer) {
    setActiveLayer(layer);
    const nextArtifact = data.artifacts.find((artifact) => artifact.layer === layer);
    setSelectedId(nextArtifact?.id ?? "");
  }

  return (
    <section className="dataset-explorer" aria-label="Dataset evidence explorer">
      <div className="dataset-context-strip">
        <ContextItem label="분석 목적" value={copy.analysisPurpose} />
        <ContextItem label="해석 방법" value={copy.interpretationMethod} />
        <ContextItem label="Source rule" value="Dashboard는 source-of-truth를 대체하지 않는 read-only viewer다." />
      </div>

      <div className="dataset-explorer-shell">
        <aside className="dataset-artifact-rail" aria-label="Dataset artifact list">
          <div className="dataset-layer-tabs" role="tablist" aria-label="Dataset layers">
            {LAYERS.map((layer) => (
              <button
                aria-controls={`dataset-layer-panel-${layer.toLowerCase()}`}
                aria-selected={layer === activeLayer}
                className={layer === activeLayer ? "active" : ""}
                key={layer}
                onClick={() => selectLayer(layer)}
                role="tab"
                type="button"
              >
                {layer}
              </button>
            ))}
          </div>
          <div className="dataset-artifact-list">
            {visibleArtifacts.length > 0 ? (
              visibleArtifacts.map((artifact) => (
                <button
                  className={selected?.id === artifact.id ? "active" : ""}
                  key={artifact.id}
                  onClick={() => setSelectedId(artifact.id)}
                  type="button"
                >
                  <span>{artifact.viewer}</span>
                  <strong>{artifact.title}</strong>
                  <small>{artifact.subtitle}</small>
                </button>
              ))
            ) : (
              <div className="dataset-empty-state">
                <strong>No artifacts</strong>
                <p>현재 layer에 표시할 dataset artifact가 없다.</p>
              </div>
            )}
          </div>
        </aside>

        <div className="dataset-viewer-canvas" id={activePanelId} role="tabpanel">
          {selected ? (
            <>
              <div className="dataset-viewer-heading">
                <div>
                  <span>
                    {selected.layer} · {selected.viewer}
                  </span>
                  <h3>{selected.title}</h3>
                </div>
                <span className="dataset-status-pill">{selected.status}</span>
              </div>
              <ArtifactViewer artifact={selected} />
            </>
          ) : (
            <div className="dataset-empty-state">
              <strong>No dataset evidence</strong>
              <p>{activeLayer} layer에 표시할 dataset artifact가 없다.</p>
            </div>
          )}
        </div>

        {selected ? (
          <ProvenancePanel artifact={selected} generatedAt={data.generatedAt} />
        ) : (
          <aside className="dataset-provenance-panel" aria-label="Artifact provenance">
            <span className="dataset-provenance-kicker">provenance</span>
            <strong>No artifact selected</strong>
            <p>선택된 source metadata가 없다.</p>
          </aside>
        )}
      </div>
    </section>
  );
}

function ContextItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <p>{value}</p>
    </div>
  );
}

function ArtifactViewer({ artifact }: { artifact: DatasetArtifact }) {
  if (!artifact.metadata.exists) {
    return (
      <div className="dataset-empty-state">
        <strong>Source missing</strong>
        <p>{artifact.metadata.error ?? "현재 checkout에서 source artifact를 찾지 못했다."}</p>
      </div>
    );
  }

  if (artifact.viewer === "markdown") return <MarkdownViewer blocks={artifact.markdown} />;
  if (artifact.viewer === "csv") return <CsvPreview artifact={artifact} />;
  if (artifact.viewer === "image") return <ImageViewer artifact={artifact} />;
  return <DbPresetShell artifact={artifact} />;
}

function MarkdownViewer({ blocks }: { blocks: MarkdownBlock[] }) {
  if (blocks.length === 0) {
    return (
      <div className="dataset-empty-state">
        <strong>No preview</strong>
        <p>Markdown preview block이 비어 있다.</p>
      </div>
    );
  }

  return (
    <div className="dataset-markdown-viewer">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          const Tag = block.level === 1 ? "h2" : block.level === 2 ? "h3" : "h4";
          return <Tag key={`${block.type}-${index}`}>{block.text}</Tag>;
        }
        if (block.type === "list") {
          return (
            <ul key={`${block.type}-${index}`}>
              {block.items.map((item, itemIndex) => (
                <li key={`${item}-${itemIndex}`}>{item}</li>
              ))}
            </ul>
          );
        }
        if (block.type === "code") return <pre key={`${block.type}-${index}`}>{block.text}</pre>;
        return <p key={`${block.type}-${index}`}>{block.text}</p>;
      })}
    </div>
  );
}

function CsvPreview({ artifact }: { artifact: Extract<DatasetArtifact, { viewer: "csv" }> }) {
  if (artifact.csv.columns.length === 0) {
    return (
      <div className="dataset-empty-state">
        <strong>No CSV columns</strong>
        <p>CSV preview metadata가 비어 있다.</p>
      </div>
    );
  }

  return (
    <div className="dataset-csv-viewer">
      <div className="dataset-csv-meta">
        <span>{artifact.csv.totalRows.toLocaleString()} rows</span>
        <span>{artifact.csv.columns.length.toLocaleString()} columns</span>
        <span>{artifact.csv.previewRows.toLocaleString()} preview rows</span>
      </div>
      <div className="dataset-table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              {artifact.csv.columns.map((column, columnIndex) => (
                <th key={`${column}-${columnIndex}`}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {artifact.csv.rows.map((row, rowIndex) => (
              <tr key={`${artifact.id}-${rowIndex}`}>
                {artifact.csv.columns.map((column, columnIndex) => (
                  <td key={`${column}-${columnIndex}`}>{row[columnIndex] ?? ""}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {artifact.csv.truncated && <p className="dataset-viewer-note">Large CSV guard: first {artifact.csv.previewRows} rows only.</p>}
    </div>
  );
}

function ImageViewer({ artifact }: { artifact: Extract<DatasetArtifact, { viewer: "image" }> }) {
  if (!artifact.publicSrc) {
    return (
      <div className="dataset-empty-state">
        <strong>No image source</strong>
        <p>Image preview 경로가 비어 있다.</p>
      </div>
    );
  }

  return (
    <figure className="dataset-image-viewer">
      <img src={artifact.publicSrc} alt={artifact.alt} />
      <figcaption>{artifact.interpretation}</figcaption>
    </figure>
  );
}

function DbPresetShell({ artifact }: { artifact: Extract<DatasetArtifact, { viewer: "db" }> }) {
  return (
    <div className="dataset-db-shell">
      <p>{artifact.interpretation}</p>
      {artifact.presets.length > 0 ? (
        artifact.presets.map((preset) => (
          <article key={`${preset.source}-${preset.label}`}>
            <span>{preset.source}</span>
            <strong>{preset.label}</strong>
            <p>{preset.description}</p>
            <code>{preset.presetQuery}</code>
          </article>
        ))
      ) : (
        <div className="dataset-empty-state">
          <strong>No DB preset</strong>
          <p>Read-only query preset이 아직 없다.</p>
        </div>
      )}
    </div>
  );
}

function ProvenancePanel({ artifact, generatedAt }: { artifact: DatasetArtifact; generatedAt: string }) {
  return (
    <aside className="dataset-provenance-panel" aria-label="Artifact provenance">
      <span className="dataset-provenance-kicker">provenance</span>
      <strong>{artifact.role}</strong>
      <dl>
        <div>
          <dt>source</dt>
          <dd>{artifact.sourcePath || "No source path"}</dd>
        </div>
        {artifact.generatorPath && (
          <div>
            <dt>generator</dt>
            <dd>{artifact.generatorPath}</dd>
          </div>
        )}
        <div>
          <dt>size</dt>
          <dd>{artifact.metadata.sizeLabel || "unknown"}</dd>
        </div>
        <div>
          <dt>modified</dt>
          <dd>{artifact.metadata.modifiedAt || "unknown"}</dd>
        </div>
        <div>
          <dt>generated</dt>
          <dd>{generatedAt || "unknown"}</dd>
        </div>
      </dl>
      <p>{artifact.interpretation}</p>
    </aside>
  );
}

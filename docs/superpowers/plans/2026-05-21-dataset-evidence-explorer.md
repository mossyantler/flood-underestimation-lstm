# Dataset Evidence Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `Foundation / Dataset` detail page with a read-only evidence explorer that renders local Markdown, previews CSV files, shows a chart asset, and presents DB preset metadata.

**Architecture:** Keep source-of-truth outside `dashboard/`; add a small server-side preview layer that reads allowlisted repo-relative artifacts and passes serialized data into a client viewer component. The viewer owns selection state only; filesystem access, row counts, and provenance metadata stay in server helpers.

**Tech Stack:** Next.js App Router 15, React 19, TypeScript, Node `fs/path/readline`, existing CSS in `dashboard/app/globals.css`, existing npm scripts.

---

## File Structure

Create:

- `dashboard/lib/dataset-explorer-types.ts`: shared serializable types for artifact metadata, Markdown blocks, CSV previews, image artifacts, DB presets, and viewer payloads.
- `dashboard/lib/dataset-explorer.ts`: server-only helper that defines Dataset artifacts, reads allowlisted Markdown/CSV files, stats source files, and assembles `DatasetExplorerData`.
- `dashboard/components/dataset-evidence-explorer.tsx`: client component with artifact rail, viewer canvas, provenance panel, Markdown renderer, CSV grid, chart viewer, and DB preset shell.

Modify:

- `dashboard/app/[section]/[detail]/page.tsx`: use `DatasetEvidenceExplorer` only for `foundation/dataset`; keep `EvidenceBlock` for other detail pages.
- `dashboard/app/globals.css`: add `dataset-explorer-*` styles and responsive rules.
- `dashboard/README.md`: document the new Dataset viewer and new preview asset.

Create asset:

- `dashboard/public/figures/input-coverage-overview.png`: small preview copy from `output/basin/timeseries/input_coverage/figures/overview.png`.

Do not modify:

- `output/` source artifacts.
- `database/local/duckdb/camels.duckdb`.
- Existing unrelated dirty files under `scripts/model/...`.

---

### Task 1: Add Dataset Explorer Types

**Files:**

- Create: `dashboard/lib/dataset-explorer-types.ts`

- [ ] **Step 1: Create shared serializable types**

Create `dashboard/lib/dataset-explorer-types.ts` with this content:

```ts
export type DatasetArtifactLayer = "Input" | "Result" | "Analysis" | "Database";

export type DatasetArtifactViewer = "markdown" | "csv" | "image" | "db";

export type DatasetArtifactRole = "canonical" | "supporting" | "cache";

export type DatasetArtifactStatus = "ready" | "needs-rerun" | "cache";

export type DatasetArtifactBase = {
  id: string;
  layer: DatasetArtifactLayer;
  viewer: DatasetArtifactViewer;
  role: DatasetArtifactRole;
  status: DatasetArtifactStatus;
  title: string;
  subtitle: string;
  sourcePath: string;
  generatorPath?: string;
  interpretation: string;
};

export type FileMetadata = {
  exists: boolean;
  sizeLabel: string;
  modifiedAt: string;
  rowCount?: number;
  columnCount?: number;
  error?: string;
};

export type MarkdownBlock =
  | { type: "heading"; level: 1 | 2 | 3; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; items: string[] }
  | { type: "code"; text: string };

export type CsvPreview = {
  columns: string[];
  rows: string[][];
  previewRows: number;
  totalRows: number;
  truncated: boolean;
};

export type DbPreset = {
  label: string;
  source: "DuckDB" | "PostgreSQL";
  description: string;
  presetQuery: string;
};

export type DatasetArtifact =
  | (DatasetArtifactBase & {
      viewer: "markdown";
      markdown: MarkdownBlock[];
      metadata: FileMetadata;
    })
  | (DatasetArtifactBase & {
      viewer: "csv";
      csv: CsvPreview;
      metadata: FileMetadata;
    })
  | (DatasetArtifactBase & {
      viewer: "image";
      publicSrc: string;
      alt: string;
      metadata: FileMetadata;
    })
  | (DatasetArtifactBase & {
      viewer: "db";
      presets: DbPreset[];
      metadata: FileMetadata;
    });

export type DatasetExplorerData = {
  generatedAt: string;
  artifacts: DatasetArtifact[];
};
```

- [ ] **Step 2: Run typecheck red check**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

Expected: PASS. This task only adds exported types and should not affect runtime.

- [ ] **Step 3: Commit**

```bash
git add dashboard/lib/dataset-explorer-types.ts
git commit -m "feat: add dataset explorer types"
```

---

### Task 2: Add Server-Side Artifact Preview Helper

**Files:**

- Create: `dashboard/lib/dataset-explorer.ts`

- [ ] **Step 1: Create server helper skeleton**

Create `dashboard/lib/dataset-explorer.ts` with imports, artifact config, and exported `getDatasetExplorerData()`:

```ts
import { createReadStream } from "node:fs";
import { stat, readFile } from "node:fs/promises";
import path from "node:path";
import readline from "node:readline";
import type {
  CsvPreview,
  DatasetArtifact,
  DatasetArtifactBase,
  DatasetExplorerData,
  DbPreset,
  FileMetadata,
  MarkdownBlock,
} from "./dataset-explorer-types";

const REPO_ROOT = path.resolve(process.cwd(), "..");
const CSV_PREVIEW_ROWS = 50;

type ArtifactConfig = DatasetArtifactBase & {
  publicSrc?: string;
  alt?: string;
  presets?: DbPreset[];
};

const ARTIFACT_CONFIGS: ArtifactConfig[] = [
  {
    id: "dataset-guide-md",
    layer: "Input",
    viewer: "markdown",
    role: "canonical",
    status: "ready",
    title: "Data processing guide",
    subtitle: "CAMELSH source, model input, result, analysis data boundary",
    sourcePath: "docs/experiment/method/data/data_processing_analysis_guide.md",
    interpretation: "먼저 input/result/analysis data 경계를 잡고, 각 파일이 어떤 layer에 속하는지 확인한다.",
  },
  {
    id: "scaling-300-manifest",
    layer: "Input",
    viewer: "csv",
    role: "canonical",
    status: "ready",
    title: "scaling_300 manifest",
    subtitle: "Fixed subset300 basin manifest",
    sourcePath: "configs/pilot/basin_splits/scaling_300/manifest.csv",
    generatorPath: "scripts/pilot/build_scaling_pilot_splits.py",
    interpretation: "Model 1/2 paired-seed 실험에서 쓰는 고정 basin universe와 split metadata를 확인한다.",
  },
  {
    id: "input-coverage-overview",
    layer: "Input",
    viewer: "image",
    role: "supporting",
    status: "ready",
    title: "Input coverage overview",
    subtitle: "CAMELSH input coverage figure",
    sourcePath: "output/basin/timeseries/input_coverage/figures/overview.png",
    publicSrc: "/figures/input-coverage-overview.png",
    alt: "CAMELSH input coverage overview figure",
    interpretation: "모델 입력으로 쓰는 time series coverage가 어디에서 부족하거나 충분한지 빠르게 확인한다.",
  },
  {
    id: "expanded-primary-summary",
    layer: "Result",
    viewer: "csv",
    role: "canonical",
    status: "ready",
    title: "Expanded DRBC primary summary",
    subtitle: "Expanded first-test result summary by seed",
    sourcePath: "output/model_analysis/expanded_drbc_test/tables/primary_summary_by_seed.csv",
    generatorPath: "scripts/model/overall/analyze_expanded_drbc_test_performance.py",
    interpretation: "expanded DRBC 기준 first test 결과 후보를 seed 단위로 확인한다.",
  },
  {
    id: "dashboard-evidence-catalog",
    layer: "Analysis",
    viewer: "csv",
    role: "supporting",
    status: "ready",
    title: "Dashboard evidence catalog",
    subtitle: "Artifacts currently exposed by the dashboard",
    sourcePath: "dashboard/data/evidence_catalog_items.csv",
    generatorPath: "scripts/model/overall/build_dashboard_evidence_catalog.py",
    interpretation: "dashboard가 어떤 docs/output artifact를 노출 대상으로 삼는지 확인한다.",
  },
  {
    id: "duckdb-cache-presets",
    layer: "Database",
    viewer: "db",
    role: "cache",
    status: "cache",
    title: "DuckDB cache presets",
    subtitle: "Read-only query aid, not source-of-truth",
    sourcePath: "database/local/duckdb/camels.duckdb",
    interpretation: "DB cache는 canonical data가 아니라 반복 조회와 sanity check를 위한 read-only surface다.",
    presets: [
      {
        label: "CSV catalog",
        source: "PostgreSQL",
        description: "Imported artifact provenance and hashes",
        presetQuery: "select relative_path, sha256, imported_at from analysis.csv_files order by imported_at desc limit 50;",
      },
      {
        label: "DuckDB catalog",
        source: "DuckDB",
        description: "Local CSV inventory and ad hoc inspection entrypoint",
        presetQuery: "select * from catalog limit 50;",
      },
      {
        label: "Observed timeseries view",
        source: "DuckDB",
        description: "Raw CAMELSH observed flow view registered by the DuckDB helper",
        presetQuery: "select gauge_id, datetime, QObs from obs_timeseries limit 50;",
      },
    ],
  },
];

function safeRepoPath(repoRelativePath: string) {
  const fullPath = path.resolve(REPO_ROOT, repoRelativePath);
  if (!fullPath.startsWith(REPO_ROOT + path.sep)) {
    throw new Error(`Blocked path outside repo: ${repoRelativePath}`);
  }
  return fullPath;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
}

async function getFileMetadata(repoRelativePath: string): Promise<FileMetadata> {
  try {
    const info = await stat(safeRepoPath(repoRelativePath));
    return {
      exists: true,
      sizeLabel: formatBytes(info.size),
      modifiedAt: info.mtime.toISOString(),
    };
  } catch (error) {
    return {
      exists: false,
      sizeLabel: "missing",
      modifiedAt: "missing",
      error: error instanceof Error ? error.message : "unknown file stat error",
    };
  }
}
```

- [ ] **Step 2: Add Markdown parsing functions**

Append these functions to the same file:

```ts
function cleanInlineMarkdown(text: string) {
  return text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .trim();
}

function parseMarkdown(markdown: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  const lines = markdown.split(/\r?\n/);
  let paragraph: string[] = [];
  let list: string[] = [];
  let code: string[] = [];
  let inCode = false;

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocks.push({ type: "paragraph", text: cleanInlineMarkdown(paragraph.join(" ")) });
      paragraph = [];
    }
  };

  const flushList = () => {
    if (list.length > 0) {
      blocks.push({ type: "list", items: list.map(cleanInlineMarkdown).filter(Boolean) });
      list = [];
    }
  };

  for (const line of lines) {
    if (line.startsWith("```")) {
      if (inCode) {
        blocks.push({ type: "code", text: code.join("\n") });
        code = [];
        inCode = false;
      } else {
        flushParagraph();
        flushList();
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      code.push(line);
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push({
        type: "heading",
        level: heading[1].length as 1 | 2 | 3,
        text: cleanInlineMarkdown(heading[2]),
      });
      continue;
    }

    const bullet = /^[-*]\s+(.+)$/.exec(line);
    if (bullet) {
      flushParagraph();
      list.push(bullet[1]);
      continue;
    }

    if (line.trim() === "") {
      flushParagraph();
      flushList();
      continue;
    }

    flushList();
    paragraph.push(line.trim());
  }

  flushParagraph();
  flushList();
  if (code.length > 0) blocks.push({ type: "code", text: code.join("\n") });
  return blocks.slice(0, 80);
}

async function readMarkdownArtifact(config: ArtifactConfig): Promise<DatasetArtifact> {
  const metadata = await getFileMetadata(config.sourcePath);
  if (!metadata.exists) {
    return { ...config, viewer: "markdown", markdown: [], metadata };
  }

  const markdown = await readFile(safeRepoPath(config.sourcePath), "utf-8");
  return {
    ...config,
    viewer: "markdown",
    markdown: parseMarkdown(markdown),
    metadata,
  };
}
```

- [ ] **Step 3: Add CSV preview functions**

Append these functions to the same file:

```ts
function parseCsvLine(line: string) {
  const values: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];
    if (char === '"' && inQuotes && next === '"') {
      current += '"';
      index += 1;
    } else if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === "," && !inQuotes) {
      values.push(current);
      current = "";
    } else {
      current += char;
    }
  }

  values.push(current);
  return values;
}

async function readCsvPreview(config: ArtifactConfig): Promise<DatasetArtifact> {
  const metadata = await getFileMetadata(config.sourcePath);
  if (!metadata.exists) {
    return {
      ...config,
      viewer: "csv",
      csv: { columns: [], rows: [], previewRows: 0, totalRows: 0, truncated: false },
      metadata,
    };
  }

  const stream = createReadStream(safeRepoPath(config.sourcePath), { encoding: "utf-8" });
  const rl = readline.createInterface({ input: stream, crlfDelay: Infinity });
  let columns: string[] = [];
  const rows: string[][] = [];
  let totalRows = 0;

  for await (const line of rl) {
    if (columns.length === 0) {
      columns = parseCsvLine(line);
      continue;
    }
    totalRows += 1;
    if (rows.length < CSV_PREVIEW_ROWS) {
      rows.push(parseCsvLine(line));
    }
  }

  return {
    ...config,
    viewer: "csv",
    csv: {
      columns,
      rows,
      previewRows: rows.length,
      totalRows,
      truncated: totalRows > rows.length,
    },
    metadata: {
      ...metadata,
      rowCount: totalRows,
      columnCount: columns.length,
    },
  };
}
```

- [ ] **Step 4: Add image, DB, and public API functions**

Append these functions to the same file:

```ts
async function readImageArtifact(config: ArtifactConfig): Promise<DatasetArtifact> {
  return {
    ...config,
    viewer: "image",
    publicSrc: config.publicSrc ?? "",
    alt: config.alt ?? config.title,
    metadata: await getFileMetadata(config.sourcePath),
  };
}

async function readDbArtifact(config: ArtifactConfig): Promise<DatasetArtifact> {
  return {
    ...config,
    viewer: "db",
    presets: config.presets ?? [],
    metadata: await getFileMetadata(config.sourcePath),
  };
}

async function readArtifact(config: ArtifactConfig): Promise<DatasetArtifact> {
  if (config.viewer === "markdown") return readMarkdownArtifact(config);
  if (config.viewer === "csv") return readCsvPreview(config);
  if (config.viewer === "image") return readImageArtifact(config);
  return readDbArtifact(config);
}

export async function getDatasetExplorerData(): Promise<DatasetExplorerData> {
  return {
    generatedAt: new Date().toISOString(),
    artifacts: await Promise.all(ARTIFACT_CONFIGS.map(readArtifact)),
  };
}
```

- [ ] **Step 5: Run typecheck**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

Expected: PASS. If TypeScript complains about union narrowing, fix the exact returned object type before continuing.

- [ ] **Step 6: Commit**

```bash
git add dashboard/lib/dataset-explorer.ts
git commit -m "feat: add dataset artifact preview helpers"
```

---

### Task 3: Add Dataset Evidence Explorer Component

**Files:**

- Create: `dashboard/components/dataset-evidence-explorer.tsx`

- [ ] **Step 1: Create client component**

Create `dashboard/components/dataset-evidence-explorer.tsx` with this content:

```tsx
"use client";

import { useMemo, useState } from "react";
import type { AnalysisModuleCopy } from "@/lib/evidence-types";
import type { DatasetArtifact, DatasetArtifactLayer, DatasetExplorerData, MarkdownBlock } from "@/lib/dataset-explorer-types";

const LAYERS: DatasetArtifactLayer[] = ["Input", "Result", "Analysis", "Database"];

type DatasetEvidenceExplorerProps = {
  copy: AnalysisModuleCopy;
  data: DatasetExplorerData;
};

export function DatasetEvidenceExplorer({ copy, data }: DatasetEvidenceExplorerProps) {
  const [activeLayer, setActiveLayer] = useState<DatasetArtifactLayer>("Input");
  const firstArtifact = data.artifacts.find((artifact) => artifact.layer === activeLayer) ?? data.artifacts[0];
  const [selectedId, setSelectedId] = useState(firstArtifact?.id ?? "");

  const visibleArtifacts = useMemo(
    () => data.artifacts.filter((artifact) => artifact.layer === activeLayer),
    [activeLayer, data.artifacts],
  );
  const selected = data.artifacts.find((artifact) => artifact.id === selectedId) ?? visibleArtifacts[0] ?? data.artifacts[0];

  function selectLayer(layer: DatasetArtifactLayer) {
    setActiveLayer(layer);
    const nextArtifact = data.artifacts.find((artifact) => artifact.layer === layer);
    if (nextArtifact) setSelectedId(nextArtifact.id);
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
                className={layer === activeLayer ? "active" : ""}
                key={layer}
                onClick={() => selectLayer(layer)}
                type="button"
              >
                {layer}
              </button>
            ))}
          </div>
          <div className="dataset-artifact-list">
            {visibleArtifacts.map((artifact) => (
              <button
                className={artifact.id === selected.id ? "active" : ""}
                key={artifact.id}
                onClick={() => setSelectedId(artifact.id)}
                type="button"
              >
                <span>{artifact.viewer}</span>
                <strong>{artifact.title}</strong>
                <small>{artifact.subtitle}</small>
              </button>
            ))}
          </div>
        </aside>

        <div className="dataset-viewer-canvas">
          <div className="dataset-viewer-heading">
            <div>
              <span>{selected.layer} · {selected.viewer}</span>
              <h3>{selected.title}</h3>
            </div>
            <span className="dataset-status-pill">{selected.status}</span>
          </div>
          <ArtifactViewer artifact={selected} />
        </div>

        <ProvenancePanel artifact={selected} generatedAt={data.generatedAt} />
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
              {block.items.map((item) => <li key={item}>{item}</li>)}
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
            <tr>{artifact.csv.columns.map((column) => <th key={column}>{column}</th>)}</tr>
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
      {artifact.presets.map((preset) => (
        <article key={preset.label}>
          <span>{preset.source}</span>
          <strong>{preset.label}</strong>
          <p>{preset.description}</p>
          <code>{preset.presetQuery}</code>
        </article>
      ))}
    </div>
  );
}

function ProvenancePanel({ artifact, generatedAt }: { artifact: DatasetArtifact; generatedAt: string }) {
  return (
    <aside className="dataset-provenance-panel" aria-label="Artifact provenance">
      <span className="dataset-provenance-kicker">provenance</span>
      <strong>{artifact.role}</strong>
      <dl>
        <div><dt>source</dt><dd>{artifact.sourcePath}</dd></div>
        {artifact.generatorPath && <div><dt>generator</dt><dd>{artifact.generatorPath}</dd></div>}
        <div><dt>size</dt><dd>{artifact.metadata.sizeLabel}</dd></div>
        <div><dt>modified</dt><dd>{artifact.metadata.modifiedAt}</dd></div>
        <div><dt>generated</dt><dd>{generatedAt}</dd></div>
      </dl>
      <p>{artifact.interpretation}</p>
    </aside>
  );
}
```

- [ ] **Step 2: Run typecheck red check**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

Expected: PASS if the component is not imported yet. If TypeScript reports unused or JSX type issues, fix before route integration.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/dataset-evidence-explorer.tsx
git commit -m "feat: add dataset evidence explorer component"
```

---

### Task 4: Wire Dataset Explorer Into Dataset Detail Route

**Files:**

- Modify: `dashboard/app/[section]/[detail]/page.tsx`

- [ ] **Step 1: Import explorer component and data helper**

Modify the import section near existing `EvidenceBlock` and `getCopyForModule` imports:

```tsx
import { DatasetEvidenceExplorer } from "@/components/dataset-evidence-explorer";
import { getDatasetExplorerData } from "@/lib/dataset-explorer";
```

- [ ] **Step 2: Load Dataset explorer data only for `foundation/dataset`**

Inside `DetailPage`, after `const csvInfo = ...`, add:

```tsx
  const datasetExplorerData = moduleId === "foundation/dataset" ? await getDatasetExplorerData() : undefined;
```

- [ ] **Step 3: Replace Dataset-only evidence rendering**

Replace this block:

```tsx
      {copy && <EvidenceBlock copy={copy} items={evidence} />}

      <div className="panel-grid">
        {content.panels}
      </div>
```

with this block:

```tsx
      {copy && datasetExplorerData && (
        <DatasetEvidenceExplorer copy={copy} data={datasetExplorerData} />
      )}
      {copy && !datasetExplorerData && <EvidenceBlock copy={copy} items={evidence} />}

      {!datasetExplorerData && (
        <div className="panel-grid">
          {content.panels}
        </div>
      )}
```

This keeps all non-Dataset detail pages on the current `EvidenceBlock + panel-grid` layout while Dataset becomes the explorer prototype.

- [ ] **Step 4: Run typecheck**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

Expected: PASS. If Next warns about importing Node `fs` into a client component, confirm `getDatasetExplorerData` is imported only in the server route file and not from `dataset-evidence-explorer.tsx`.

- [ ] **Step 5: Commit**

```bash
git add 'dashboard/app/[section]/[detail]/page.tsx'
git commit -m "feat: route dataset detail to evidence explorer"
```

---

### Task 5: Add Preview Asset and Explorer CSS

**Files:**

- Create asset: `dashboard/public/figures/input-coverage-overview.png`
- Modify: `dashboard/app/globals.css`

- [ ] **Step 1: Copy preview asset**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cp output/basin/timeseries/input_coverage/figures/overview.png dashboard/public/figures/input-coverage-overview.png
```

Expected:

```bash
ls -lh dashboard/public/figures/input-coverage-overview.png
```

shows a PNG around `175K`.

- [ ] **Step 2: Add explorer CSS**

Append this CSS near the existing `.evidence-*` styles in `dashboard/app/globals.css`:

```css
.dataset-explorer {
  display: grid;
  gap: 14px;
}

.dataset-context-strip {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.dataset-context-strip > div,
.dataset-explorer-shell,
.dataset-provenance-panel,
.dataset-empty-state {
  background: var(--panel);
  border: 1px solid var(--hairline);
  border-radius: var(--r-lg);
}

.dataset-context-strip > div {
  display: grid;
  gap: 7px;
  padding: 12px;
}

.dataset-context-strip span,
.dataset-viewer-heading span,
.dataset-csv-meta span,
.dataset-provenance-kicker,
.dataset-provenance-panel dt,
.dataset-db-shell article span {
  color: var(--ink-dim);
  font-family: var(--font-geist-mono), monospace;
  font-size: 9px;
  text-transform: uppercase;
}

.dataset-context-strip p {
  color: var(--ink-body);
  font-size: 12px;
  line-height: 1.55;
  margin: 0;
}

.dataset-explorer-shell {
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(210px, 0.7fr) minmax(0, 1.7fr) minmax(220px, 0.8fr);
  min-width: 0;
  padding: 12px;
}

.dataset-artifact-rail {
  display: grid;
  gap: 10px;
  align-content: start;
  min-width: 0;
}

.dataset-layer-tabs {
  background: var(--panel-inner);
  border: 1px solid var(--hairline);
  border-radius: var(--r-md);
  display: grid;
  gap: 4px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  padding: 4px;
}

.dataset-layer-tabs button,
.dataset-artifact-list button {
  background: transparent;
  border: 0;
  color: var(--ink-muted);
  cursor: pointer;
  text-align: left;
}

.dataset-layer-tabs button {
  border-radius: var(--r-sm);
  font-family: var(--font-geist-mono), monospace;
  font-size: 10px;
  padding: 8px;
  text-align: center;
}

.dataset-layer-tabs button.active,
.dataset-artifact-list button.active {
  background: color-mix(in srgb, #50e3c2 13%, var(--panel-inner));
  color: var(--ink);
}

.dataset-artifact-list {
  display: grid;
  gap: 8px;
}

.dataset-artifact-list button {
  border: 1px solid var(--hairline);
  border-radius: var(--r-md);
  display: grid;
  gap: 5px;
  min-width: 0;
  padding: 10px;
}

.dataset-artifact-list button span {
  color: var(--ink-dim);
  font-family: var(--font-geist-mono), monospace;
  font-size: 8px;
  text-transform: uppercase;
}

.dataset-artifact-list button strong {
  color: var(--ink);
  font-size: 12px;
}

.dataset-artifact-list button small {
  color: var(--ink-muted);
  font-size: 10px;
  line-height: 1.35;
}

.dataset-viewer-canvas {
  background: var(--panel-inner);
  border: 1px solid var(--hairline);
  border-radius: var(--r-lg);
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 14px;
}

.dataset-viewer-heading {
  align-items: start;
  display: flex;
  gap: 10px;
  justify-content: space-between;
}

.dataset-viewer-heading h3 {
  color: var(--ink);
  font-size: 17px;
  line-height: 1.25;
  margin-top: 5px;
}

.dataset-status-pill {
  border: 1px solid color-mix(in srgb, #50e3c2 34%, var(--hairline));
  border-radius: 999px;
  padding: 5px 8px;
}

.dataset-markdown-viewer {
  display: grid;
  gap: 10px;
  max-height: 620px;
  overflow: auto;
  padding-right: 4px;
}

.dataset-markdown-viewer h2,
.dataset-markdown-viewer h3,
.dataset-markdown-viewer h4 {
  color: var(--ink);
  line-height: 1.25;
}

.dataset-markdown-viewer h2 { font-size: 18px; }
.dataset-markdown-viewer h3 { font-size: 15px; }
.dataset-markdown-viewer h4 { font-size: 13px; }

.dataset-markdown-viewer p,
.dataset-markdown-viewer li,
.dataset-db-shell p,
.dataset-image-viewer figcaption,
.dataset-viewer-note,
.dataset-empty-state p,
.dataset-provenance-panel p {
  color: var(--ink-body);
  font-size: 12px;
  line-height: 1.65;
}

.dataset-markdown-viewer ul {
  margin: 0;
  padding-left: 18px;
}

.dataset-markdown-viewer pre,
.dataset-db-shell code {
  background: var(--panel-deep);
  border: 1px solid var(--hairline);
  border-radius: var(--r-md);
  color: var(--ink-body);
  font-family: var(--font-geist-mono), monospace;
  font-size: 10px;
  line-height: 1.5;
  overflow: auto;
  padding: 10px;
  white-space: pre-wrap;
}

.dataset-csv-viewer {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.dataset-csv-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.dataset-csv-meta span {
  border: 1px solid var(--hairline);
  border-radius: 999px;
  padding: 5px 8px;
}

.dataset-table-scroll {
  max-height: 560px;
  min-width: 0;
  overflow: auto;
}

.dataset-image-viewer {
  display: grid;
  gap: 10px;
  margin: 0;
}

.dataset-image-viewer img {
  background: #fff;
  border: 1px solid var(--hairline);
  border-radius: var(--r-md);
  display: block;
  max-height: 560px;
  max-width: 100%;
  object-fit: contain;
}

.dataset-db-shell {
  display: grid;
  gap: 10px;
}

.dataset-db-shell article {
  background: var(--panel);
  border: 1px solid var(--hairline);
  border-radius: var(--r-md);
  display: grid;
  gap: 6px;
  padding: 11px;
}

.dataset-db-shell article strong {
  color: var(--ink);
  font-size: 13px;
}

.dataset-provenance-panel {
  align-content: start;
  display: grid;
  gap: 10px;
  min-width: 0;
  padding: 13px;
}

.dataset-provenance-panel > strong {
  color: var(--ink);
  font-size: 14px;
}

.dataset-provenance-panel dl {
  display: grid;
  gap: 8px;
  margin: 0;
}

.dataset-provenance-panel div {
  display: grid;
  gap: 4px;
}

.dataset-provenance-panel dd {
  color: var(--ink-body);
  font-family: var(--font-geist-mono), monospace;
  font-size: 10px;
  line-height: 1.45;
  margin: 0;
  overflow-wrap: anywhere;
}

.dataset-empty-state {
  display: grid;
  gap: 7px;
  padding: 18px;
}

.dataset-empty-state strong {
  color: var(--ink);
}
```

- [ ] **Step 3: Add responsive rule**

Add this inside the existing mobile media query near current `.evidence-*` responsive rules:

```css
  .dataset-context-strip,
  .dataset-explorer-shell {
    grid-template-columns: 1fr;
  }

  .dataset-table-scroll {
    max-height: 420px;
  }
```

- [ ] **Step 4: Run typecheck and static route smoke**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
```

Expected: PASS.

Run while local server is active on 3000:

```bash
curl -s -o /tmp/camels_dataset_explorer.html -w '%{http_code}\n' http://localhost:3000/foundation/dataset
```

Expected: `200`.

- [ ] **Step 5: Commit**

```bash
git add dashboard/app/globals.css dashboard/public/figures/input-coverage-overview.png
git commit -m "feat: style dataset evidence explorer"
```

---

### Task 6: Document Dataset Viewer in Dashboard README

**Files:**

- Modify: `dashboard/README.md`

- [ ] **Step 1: Add preview asset entry**

Under `## Preview Assets`, add:

```md
- `/figures/input-coverage-overview.png` ← `output/basin/timeseries/input_coverage/figures/overview.png`
```

- [ ] **Step 2: Add Dataset Explorer note**

Before `## 검증`, add:

```md
## Dataset Evidence Explorer

`/foundation/dataset`은 Dataset viewer prototype입니다. 이 화면은 `docs/`, `configs/`, `output/`, `database/local/`의 allowlisted artifact를 읽어 Markdown renderer, CSV preview grid, chart viewer, DB preset shell로 보여줍니다.

CSV는 브라우저에 전체를 싣지 않고 server-side preview로 header, first 50 rows, row count, column count, file size를 표시합니다. DB preset shell은 read-only query aid의 위치를 보여주는 UI이며, 자유 SQL 실행기는 아닙니다.
```

- [ ] **Step 3: Run diff and typecheck**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
git diff --check -- dashboard/README.md
cd dashboard
npm run typecheck
```

Expected: `git diff --check` no output, typecheck PASS.

- [ ] **Step 4: Commit**

```bash
git add dashboard/README.md
git commit -m "docs: document dataset evidence explorer"
```

---

### Task 7: Browser Verification

**Files:**

- No planned file edits unless verification finds a concrete issue.

- [ ] **Step 1: Verify server response**

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
curl -s -o /tmp/camels_dataset_explorer.html -w '%{http_code}\n' http://localhost:3000/foundation/dataset
```

Expected: `200`.

- [ ] **Step 2: Verify rendered HTML contains explorer shell**

Run:

```bash
rg -n "Dataset evidence explorer|Data processing guide|scaling_300 manifest|DuckDB cache presets" /tmp/camels_dataset_explorer.html
```

Expected: matches for all listed labels.

- [ ] **Step 3: Verify in browser**

Use the in-app Browser on `http://localhost:3000/foundation/dataset`.

Required checks:

- First view shows Dataset context strip and explorer shell.
- Markdown viewer renders headings and paragraphs from `data_processing_analysis_guide.md`.
- Clicking `scaling_300 manifest` shows a CSV grid and row/column metadata.
- Clicking `Input coverage overview` shows the PNG without broken image icon.
- Clicking `Database` and `DuckDB cache presets` shows preset query cards, not a SQL editor.
- Desktop viewport has no overlap among rail, viewer, and provenance panel.

- [ ] **Step 4: Mobile sanity check**

Resize browser to a mobile-width viewport or use the in-app browser viewport control.

Required checks:

- Context strip stacks vertically.
- Artifact rail, viewer canvas, provenance panel stack vertically.
- CSV table scrolls horizontally without overflowing the page.

- [ ] **Step 5: Fix concrete issues and rerun checks**

If a check fails, edit only the relevant file, run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm run typecheck
curl -s -o /tmp/camels_dataset_explorer.html -w '%{http_code}\n' http://localhost:3000/foundation/dataset
```

Expected: typecheck PASS and `200`.

- [ ] **Step 6: Commit verification fixes**

Only if files changed:

```bash
git add dashboard/app/globals.css dashboard/components/dataset-evidence-explorer.tsx dashboard/lib/dataset-explorer.ts 'dashboard/app/[section]/[detail]/page.tsx'
git commit -m "fix: polish dataset evidence explorer"
```

---

## Final Verification

Run:

```bash
export PATH="/opt/homebrew/bin:$PATH"
git status --short
cd dashboard
npm run typecheck
curl -s -o /tmp/camels_dataset_explorer.html -w '%{http_code}\n' http://localhost:3000/foundation/dataset
```

Expected:

- `git status --short` shows only pre-existing unrelated files if they were already dirty before implementation.
- `npm run typecheck` passes.
- `curl` returns `200`.
- Browser verification confirms Markdown, CSV, image, DB preset shell, and provenance panel.

Do not run `npm run build` while the persistent local dev server owns `.next`; this project already documents that local build can conflict with the active server cache.

---

## Spec Coverage Review

- Markdown renderer: Task 2 and Task 3.
- CSV preview grid: Task 2 and Task 3.
- Chart/image viewer: Task 3 and Task 5.
- DB preset shell: Task 2 and Task 3.
- Provenance panel: Task 3.
- Dataset route replacement: Task 4.
- Preview asset policy: Task 5 and Task 6.
- Browser and type verification: Task 7 and Final Verification.

import { createReadStream } from "node:fs";
import { readFile, stat } from "node:fs/promises";
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
const MARKDOWN_BLOCK_LIMIT = 80;

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
    interpretation:
      "먼저 input/result/analysis data 경계를 잡고, 각 파일이 어떤 layer에 속하는지 확인한다.",
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
    generatorPath: "scripts/scaling/build_scaling_pilot_splits.py",
    interpretation:
      "Model 1/2 paired-seed 실험에서 쓰는 고정 basin universe와 split metadata를 확인한다.",
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
    interpretation:
      "모델 입력으로 쓰는 time series coverage가 어디에서 부족하거나 충분한지 빠르게 확인한다.",
  },
  {
    id: "expanded-primary-summary",
    layer: "Result",
    viewer: "csv",
    role: "canonical",
    status: "ready",
    title: "Expanded DRBC primary summary",
    subtitle: "Expanded first-test result summary by seed",
    sourcePath:
      "output/model_analysis/expanded/expanded_drbc_test/tables/primary_summary_by_seed.csv",
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
    generatorPath: "scripts/dashboard/build_evidence_catalog.py",
    interpretation:
      "dashboard가 어떤 docs/output artifact를 노출 대상으로 삼는지 확인한다.",
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
    interpretation:
      "DB cache는 canonical data가 아니라 반복 조회와 sanity check를 위한 read-only surface다.",
    presets: [
      {
        label: "CSV catalog",
        source: "PostgreSQL",
        description: "Imported artifact provenance and hashes",
        presetQuery:
          "select relative_path, sha256, imported_at from analysis.csv_files order by imported_at desc limit 50;",
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
  if (!fullPath.startsWith(`${REPO_ROOT}${path.sep}`)) {
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
      modifiedAt: new Date(0).toISOString(),
      error: error instanceof Error ? error.message : "unknown file stat error",
    };
  }
}

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
    if (paragraph.length === 0) return;
    blocks.push({ type: "paragraph", text: cleanInlineMarkdown(paragraph.join(" ")) });
    paragraph = [];
  };

  const flushList = () => {
    if (list.length === 0) return;
    const items = list.map(cleanInlineMarkdown).filter(Boolean);
    if (items.length > 0) blocks.push({ type: "list", items });
    list = [];
  };

  for (const line of lines) {
    if (blocks.length >= MARKDOWN_BLOCK_LIMIT) break;

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

    const bullet = /^\s*[-*]\s+(.+)$/.exec(line);
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

  if (blocks.length < MARKDOWN_BLOCK_LIMIT) {
    flushParagraph();
    flushList();
    if (code.length > 0) blocks.push({ type: "code", text: code.join("\n") });
  }

  return blocks.slice(0, MARKDOWN_BLOCK_LIMIT);
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

  const csv: CsvPreview = {
    columns,
    rows,
    previewRows: rows.length,
    totalRows,
    truncated: totalRows > rows.length,
  };

  return {
    ...config,
    viewer: "csv",
    csv,
    metadata: {
      ...metadata,
      rowCount: totalRows,
      columnCount: columns.length,
    },
  };
}

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

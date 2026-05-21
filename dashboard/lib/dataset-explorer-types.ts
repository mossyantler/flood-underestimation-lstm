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

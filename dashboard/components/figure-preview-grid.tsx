import type { FigureAsset } from "@/lib/figure-assets";

type FigurePreviewGridProps = {
  figures: readonly FigureAsset[];
  compact?: boolean;
};

export function FigurePreviewGrid({ figures, compact = false }: FigurePreviewGridProps) {
  return (
    <div className={compact ? "figure-grid compact" : "figure-grid"}>
      {figures.map((figure) => (
        <figure className="figure-preview" key={figure.id}>
          <img src={figure.src} alt={figure.alt} loading="lazy" />
          <figcaption>
            <span className="figure-kicker">{figure.kicker}</span>
            <strong>{figure.title}</strong>
            <span>{figure.caption}</span>
            <code>{figure.source}</code>
          </figcaption>
        </figure>
      ))}
    </div>
  );
}

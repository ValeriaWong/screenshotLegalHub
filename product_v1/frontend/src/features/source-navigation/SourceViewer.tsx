import { SearchableSelect } from "../../components/collections";
import { useState } from "react";
import type { ViewerContent } from "../../components/shell/DetailRail";
import { useI18n } from "../../i18n";

export function SourceViewer({ content }: { content: ViewerContent }) {
  const { t } = useI18n();
  const [error, setError] = useState(false);
  const [selection, setSelection] = useState(content.bbox ? "citation" : "all");
  const [size, setSize] = useState({ width: content.width || 1, height: content.height || 1 });
  // Different provenance records can point at the same physical rectangle.
  const regions = (content.regions || []).filter((r, i, all) => r.bbox &&
    all.findIndex(other => other.bbox?.join(",") === r.bbox?.join(",")) === i);
  const frame = content.coordinateSpace === "normalized_1000" ? { width: 1000, height: 1000 } : size;
  const selected = regions.find(r => r.id === selection);
  const bbox = selection === "citation" ? content.bbox : selected?.bbox || undefined;
  const boxes = selection === "all" ? (regions.length ? regions.map(r => r.bbox!) : content.bbox ? [content.bbox] : []) : bbox ? [bbox] : [];
  const quote = selected?.quote || (selection === "citation" || !regions.length ? content.highlightText : undefined);
  return (
    <div className="source-viewer">
      <h3>{content.filename}</h3>
      {content.type === "image" && (regions.length > 0 || content.bbox) && (
        <div className="region-controls">
          <SearchableSelect label={<>{t("imageRegions")} ({regions.length || 1})

          </>} aria-label={t("imageRegions")} value={selection} onChange={e => setSelection(e.target.value)}>
              <option value="all">{t("allRegions")}</option>
              <option value="none">{t("wholeImage")}</option>
              {content.bbox && <option value="citation">{t("currentCitation")}</option>}
              {regions.map((r, i) => <option key={r.id} value={r.id}>
                {i + 1}. {r.quote ? r.quote.slice(0, 60) : r.id.startsWith("region.render.") ? t("renderRegion") : t("annotationRegion")}
              </option>)}
            </SearchableSelect>
          <p>{t("regionNotice")}</p>
        </div>
      )}
      {error ? <p role="alert">{t("sourceUnavailable")}</p> : content.type === "image" ? (
        <div className="image-frame">
          <img src={content.url} alt={content.filename} onError={() => setError(true)}
            onLoad={e => setSize({ width: e.currentTarget.naturalWidth, height: e.currentTarget.naturalHeight })} />
          {boxes.map((box, index) => <div key={index} data-testid="source-bbox" className="source-bbox"
            aria-label={t("rawCoordinates")} style={{
              left: (100 * box[0]) / frame.width + "%", top: (100 * box[1]) / frame.height + "%",
              width: (100 * (box[2] - box[0])) / frame.width + "%", height: (100 * (box[3] - box[1])) / frame.height + "%",
            }} />)}
        </div>
      ) : content.type === "pdf" ? <iframe title={content.filename} src={content.url + "#page=" + (content.page || 1)} />
        : content.type === "audio" ? <audio controls src={content.url} />
          : content.type === "video" ? <video controls src={content.url} />
            : <a href={content.url} target="_blank" rel="noreferrer">{content.filename}</a>}
      {content.originalUrl && <a href={content.originalUrl} target="_blank" rel="noreferrer">打开原文件</a>}
      {bbox && <code className="region-coordinates">{t("rawCoordinates")}: [{bbox.map(v => Math.round(v * 100) / 100).join(", ")}]</code>}
      {quote && <blockquote>{quote}</blockquote>}
      {content.type === "image" && !content.bbox && !regions.length && <p>
        {content.regions === undefined ? t("regionsNotLoaded") : t("noBBox")}
      </p>}
    </div>
  );
}

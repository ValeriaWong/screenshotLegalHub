import { Paged } from "../../components/collections";
import { useMemo, useState } from "react";
import type { components } from "../../api/schema";
import { Card, Input } from "../../components/ui";
import { Feedback } from "../../components/feedback";
import { useI18n } from "../../i18n";
type Snapshot = components["schemas"]["WorkbenchSnapshot"];
type Evidence = components["schemas"]["EvidenceItem"];
type ImageEntry = { evidence: Evidence; dates: string[]; label: string | null; order: number };
export function ImageTimeline({ snapshot }: { snapshot: Snapshot }) {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [timeFilter, setTimeFilter] = useState("");
  const images: ImageEntry[] = useMemo(() => {
    const relatedByEvidence = new Map<string, Snapshot["timeline"]>();
    for (const entry of snapshot.timeline) {
      if (entry.kind === "evidence") continue;
      for (const id of entry.evidence_ids) {
        const related = relatedByEvidence.get(id) || []; related.push(entry); relatedByEvidence.set(id, related);
      }
    }
    return snapshot.evidence
    .filter(item => item.kind === "image" || item.mime_type?.startsWith("image/"))
    .map((evidence, order) => {
      const related = relatedByEvidence.get(evidence.id) || [];
      const dates = [...new Set(related.map(entry => entry.timestamp).filter((value): value is string => !!value))].sort();
      const labels = [...new Set(related.map(entry => entry.time_label).filter((value): value is string => !!value))];
      return { evidence, dates, label: labels.length === 1 ? labels[0] : null, order };
    })
    .sort((a, b) => {
      if (a.dates.length && b.dates.length) return a.dates[0].localeCompare(b.dates[0]) || a.order - b.order;
      if (a.dates.length !== b.dates.length && (!a.dates.length || !b.dates.length)) return a.dates.length ? -1 : 1;
      return a.order - b.order;
    });
  }, [snapshot.evidence, snapshot.timeline]);
  const entries = images.filter(entry => {
    const known = !!entry.dates.length;
    return (!timeFilter || (timeFilter === "dated" ? known : !known)) &&
      [entry.evidence.filename, ...entry.dates, entry.label || ""].join(" ").toLowerCase().includes(search.trim().toLowerCase());
  });
  return <>
    <p>{t("imageTimelineNotice")}</p>
    <div className="toolbar">
      <label>{t("imageTimelineSearch")}<Input type="search" value={search} onChange={e => setSearch(e.target.value)} /></label>
      <label>{t("imageTimeFilter")}<select value={timeFilter} onChange={e => setTimeFilter(e.target.value)}>
        <option value="">{t("all")}</option><option value="dated">{t("datedImages")}</option><option value="undated">{t("undatedImages")}</option>
      </select></label>
    </div>
    <p>{t("imageTimelineCount")}: {entries.length} / {images.length}</p>
    {!entries.length ? <p>{t(images.length ? "empty" : "noTimelineImages")}</p> : <ol className="timeline image-timeline">{<Paged items={entries} label="证据图片" layout="list" searchable={false} resetKey={search + timeFilter} pageSize={8}>{(pageItems) => pageItems.map(entry =>
      <li key={snapshot.case.id + ":" + entry.evidence.id}><ImageCard entry={entry} caseId={snapshot.case.id} /></li>)}</Paged>}</ol>}
  </>;
}
function ImageCard({ entry, caseId }: { entry: ImageEntry; caseId: string }) {
  const { t } = useI18n();
  const [failed, setFailed] = useState(false);
  const url = "/v1/cases/" + caseId + "/evidence/" + entry.evidence.id + "/file";
  const first = entry.dates[0];
  const last = entry.dates[entry.dates.length - 1];
  return <Card>
    <time>{first ? first === last ? first : first + " — " + last : entry.label || t("timeUnspecified")}</time>
    <h2>{entry.evidence.filename}</h2>
    <figure className="image-timeline-figure">
      {failed ? <Feedback state="error" error={t("timelineImageFailed")} /> : <a href={url} target="_blank" rel="noreferrer" aria-label={t("openTimelineImage") + ": " + entry.evidence.filename}>
        <img className="image-timeline-preview" src={url} alt={entry.evidence.filename} loading="lazy" decoding="async" onError={() => setFailed(true)} />
      </a>}
      <figcaption><a href={url} target="_blank" rel="noreferrer">{t("openTimelineImage")}</a></figcaption>
    </figure>
  </Card>;
}

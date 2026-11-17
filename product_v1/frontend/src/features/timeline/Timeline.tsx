import { SearchableSelect } from "../../components/collections";
import { Paged } from "../../components/collections";
import { useQuery } from "@tanstack/react-query";
import { api, type Entity } from "../../api/client";
import { Input, Badge, Card } from "../../components/ui";
import { Feedback } from "../../components/feedback";
import { Citations } from "../source-navigation";
import { useI18n } from "../../i18n";
import { useUrlState } from "../../hooks/useUrlState";
export function Timeline({ caseId }: { caseId: string }) {
  const { t } = useI18n();
  const [party, setParty] = useUrlState("party");
  const [type, setType] = useUrlState("event");
  const [status, setStatus] = useUrlState("reviewStatus");
  const [from, setFrom] = useUrlState("from");
  const [to, setTo] = useUrlState("to");
  const q = useQuery({
    queryKey: ["timeline", caseId],
    queryFn: () => api<Entity[]>(`/cases/${caseId}/timeline`),
  });
  if (q.isPending) return <Feedback state="loading" />;
  if (q.error)
    return (
      <Feedback
        state="error"
        error={q.error.message}
        retry={() => q.refetch()}
      />
    );
  const filtered = q.data.filter((e) => {
    const d = e.details || {};
    const date = String(d.timestamp || "");
    return (
      (!party || String(d.party).includes(party)) &&
      (!type || d.event_type === type) &&
      (!status || e.review_status === status) &&
      (!from || date >= from) &&
      (!to || date.slice(0, 10) <= to)
    );
  });
  return (
    <>
      <div className="toolbar">
        <label>
          {t("party")}
          <Input value={party} onChange={(e) => setParty(e.target.value)} />
        </label>
        <SearchableSelect label={<>
          {t("eventType")}

        </>} value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">{t("all")}</option>
            {[...new Set(q.data.map((e) => String(e.details?.event_type)))].map(
              (v) => (
                <option key={v}>{v}</option>
              ),
            )}
          </SearchableSelect>
        <SearchableSelect label={<>
          {t("reviewStatus")}

        </>} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">{t("all")}</option>
            {[
              "unreviewed",
              "verified",
              "edited",
              "rejected",
              "deferred",
              "stale",
            ].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </SearchableSelect>
        <label>
          {t("from")}
          <Input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </label>
        <label>
          {t("to")}
          <Input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </label>
      </div>
      {!filtered.length ? (
        <Feedback state="empty" />
      ) : (
        <ol className="timeline">
          {<Paged items={filtered} label="时间线记录" layout="list" resetKey={caseId}>{(pageItems) => pageItems.map((e) => (
            <li key={e.id}>
              <Card>
                <time>{String(e.details?.timestamp || t("unknown"))}</time>
                <h3>{e.title}</h3>
                <Badge>{String(e.details?.event_type)}</Badge>
                <Badge>{e.review_status}</Badge>
                <Citations caseId={caseId} refs={e.source_refs || []} />
              </Card>
            </li>
          ))}</Paged>}
        </ol>
      )}
    </>
  );
}

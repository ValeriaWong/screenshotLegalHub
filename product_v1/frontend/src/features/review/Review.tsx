import { Paged } from "../../components/collections";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ProofGraph, type ReviewRequest } from "../../api/client";
import { Badge, Button, Card } from "../../components/ui";
import { Feedback } from "../../components/feedback";
import { Citations } from "../source-navigation";
import { useI18n } from "../../i18n";
export function Review({ caseId, readOnly = false }: { caseId: string; readOnly?: boolean }) {
  const { t } = useI18n();
  const client = useQueryClient();
  const [selected, setSelected] = useState("");
  const [text, setText] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const q = useQuery({
    queryKey: ["graph", caseId],
    queryFn: () => api<ProofGraph>(`/cases/${caseId}/proof-graph`),
  });
  const history = useQuery({
    queryKey: ["reviews", caseId],
    queryFn: () => api<Record<string, string>[]>(`/cases/${caseId}/reviews`),
  });
  if (q.isPending) return <Feedback state="loading" />;
  if (q.error) return <Feedback state="error" error={q.error.message} />;
  const queue = (q.data.entities || []).filter((e) =>
    ["fact", "evidence_link", "contradiction", "gap", "strategy"].includes(
      e.kind,
    ),
  );
  if (!queue.length) return <Feedback state="notRun" />;
  const current = queue.find((e) => e.id === selected) || queue[0];
  async function decide(action: ReviewRequest["action"]) {
    setBusy(true);
    setMessage("");
    try {
      await api(`/cases/${caseId}/reviews`, {
        target_id: current.id,
        output_digest: current.output_digest,
        action,
        text,
        reviewer: "local-user",
      } satisfies ReviewRequest);
      await client.invalidateQueries();
      setMessage(t("reviewSaved"));
    } catch (e) {
      setMessage(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="review-workspace">
        <section className="review-queue">
          <h2>{t("reviewQueue")}</h2>
          {<Paged items={queue} label="待审核项目" layout="block" resetKey={caseId + current.id} anchorIndex={queue.findIndex(e => e.id === current.id)}>{(pageItems) => pageItems.map((e) => (
            <Button
              aria-pressed={e.id === current.id}
              key={e.id}
              onClick={() => {
                setSelected(e.id);
                setText("");
              }}
            >
              {e.title}
              <Badge>{e.review_status}</Badge>
            </Button>
          ))}</Paged>}
        </section>
        <Card>
          <h2>{current.title}</h2>
          <Badge>{current.review_status}</Badge>
          {current.review_status === "stale" && (
            <p role="status">{t("reviewStale")}</p>
          )}
          <p>{current.details?.reviewed_text as string}</p>
          <p>
            {String(
              current.details.description ||
                current.details.rationale ||
                current.details.why_needed ||
                current.details.explanation ||
                "",
            )}
          </p>
          <Badge>
            {t("status")}: {current.status}
          </Badge>
          <Citations caseId={caseId} refs={current.source_refs || []} />
          <label>
            {t("reviewText")}
            <textarea value={text} onChange={(e) => setText(e.target.value)} />
          </label>
          <div className="toolbar">
            {(["verified", "edited", "rejected", "deferred"] as const).map(
              (action, i) => (
                <Button
                  key={action}
                  disabled={busy || readOnly || (action === "edited" && !text.trim())}
                  onClick={() => decide(action)}
                >
                  {t((["verify", "edit", "reject", "defer"] as const)[i])}
                </Button>
              ),
            )}
          </div>
          <p role="status">{message}</p>
        </Card>
      </div>
      <Card>
        <h2>{t("reviewHistory")}</h2>
        {<Paged items={history.data} label="案件审核历史" layout="block">{(pageItems) => pageItems.map((r) => (
          <p key={r.id}>
            {r.created_at} ·{" "}
            {queue.find((item) => item.id === r.target_id)?.title ||
              r.target_id}{" "}
            · {r.action} · {r.reviewer}
          </p>
        ))}</Paged>}
      </Card>
    </>
  );
}

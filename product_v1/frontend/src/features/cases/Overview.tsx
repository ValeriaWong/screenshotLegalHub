import { Paged } from "../../components/collections";
import { useQuery } from "@tanstack/react-query";
import { api, type MatrixRow, type EvidenceItem } from "../../api/client";
import { Card, Badge } from "../../components/ui";
import { Feedback } from "../../components/feedback";
import { useI18n } from "../../i18n";
import { CaseMembers } from "./CaseMembers";
export function Overview({ caseId }: { caseId: string }) {
  const { t, locale } = useI18n();
  const matrix = useQuery({
    queryKey: ["matrix", caseId],
    queryFn: () => api<MatrixRow[]>(`/cases/${caseId}/proof-matrix`),
  });
  const evidence = useQuery({
    queryKey: ["evidence", caseId],
    queryFn: () => api<EvidenceItem[]>(`/cases/${caseId}/evidence`),
  });
  const packs = useQuery({
    queryKey: ["packs"],
    queryFn: () => api<Record<string, any>[]>("/matter-packs"),
  });
  if (matrix.isPending) return <Feedback state="loading" />;
  if (matrix.error)
    return <Feedback state="error" error={matrix.error.message} />;
  const rows = matrix.data;
  return (
    <>
      <p className="lede">{t("nextActions")}</p>
      <div className="stats">
        {[
          [t("images"), evidence.data?.length || 0],
          [t("facts"), rows.length],
          [t("gap"), rows.reduce((sum, r) => sum + r.gaps.length, 0)],
          [
            t("pending"),
            rows.filter(
              (r) =>
                r.fact.review_status === "unreviewed" ||
                r.fact.review_status === "stale",
            ).length,
          ],
        ].map(([label, value]) => (
          <Card key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </Card>
        ))}
      </div>
      <div className="stats">
        {["supported", "mixed", "contradicted", "unknown"].map((status) => (
          <Card key={status}>
            <Badge>{status}</Badge>
            <strong>
              {rows.filter((r) => r.fact.status === status).length}
            </strong>
          </Card>
        ))}
      </div>
      {!rows.length && <Feedback state="notRun" />}
      <CaseMembers caseId={caseId} />
      {<Paged items={packs.data} label="案件分析规则" layout="block">{(pageItems) => pageItems.map((pack) => (
        <Card key={pack.digest}>
          <h2>
            {locale === "en" ? pack.manifest.name_en : pack.manifest.name_zh} ·{" "}
            {pack.manifest.version}
          </h2>
          <Badge>
            {pack.manifest.status} / {pack.manifest.expert_review.status}
          </Badge>
          <code className="digest">SHA256 {pack.digest}</code>
          <h3>{t("rules")}</h3>
          {<Paged<Record<string, string>> items={pack.authorities} label="法律依据" layout="block">{(pageItems) => pageItems.map((a: Record<string, string>) => (
            <p key={a.id}>
              <a href={a.source_url} target="_blank" rel="noreferrer">
                {a.title} · {a.article}
              </a>{" "}
              <Badge>{a.verification_status}</Badge>
            </p>
          ))}</Paged>}
          <h3>{t("patterns")}</h3>
          {<Paged<Record<string, string>> items={pack.patterns} label="分析模式" layout="block">{(pageItems) => pageItems.map((p: Record<string, string>) => (
            <p key={p.id}>{p.id}</p>
          ))}</Paged>}
        </Card>
      ))}</Paged>}
    </>
  );
}

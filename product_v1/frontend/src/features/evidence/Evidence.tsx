import { SearchableSelect } from "../../components/collections";
import { Paged } from "../../components/collections";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, uploadBatch, type EvidenceItem, type BatchResult, type ModelConfig, type SourceRef } from "../../api/client";
import { Card, Button, Input } from "../../components/ui";
import { Feedback } from "../../components/feedback";
import { useDetailRail } from "../../components/shell/DetailRail";
import { viewerFor, Citations } from "../source-navigation";
import { useI18n } from "../../i18n";
import { useUrlState } from "../../hooks/useUrlState";
export function Evidence({ caseId, readOnly = false }: { caseId: string; readOnly?: boolean }) {
  const { t } = useI18n();
  const rail = useDetailRail();
  const client = useQueryClient();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [real, setReal] = useState(false);
  const [modelId, setModelId] = useState("");
  const [batch, setBatch] = useState<BatchResult | null>(null);
  const [lastFiles, setLastFiles] = useState<File[]>([]);
  const models = useQuery({ queryKey: ["models"], queryFn: () => api<ModelConfig[]>("/settings/models") });
  const formats = useQuery({ queryKey: ["formats"], queryFn: () => api<{ formats: { mime_type: string }[]; max_files: number; max_file_bytes: number; max_batch_bytes: number }>("/evidence/formats") });
  const visionModels = models.data?.filter(m => m.supports_vision) || [];
  const selectedModel = visionModels.find(m => m.id === modelId) || visionModels.find(m => m.is_default) || visionModels[0];
  const [search, setSearch] = useUrlState("q");
  const [results, setResults] = useState<
    { id: string; text: string; source_refs: string[] }[]
  >([]);
  const query = useQuery({
    queryKey: ["evidence", caseId],
    queryFn: () => api<EvidenceItem[]>(`/cases/${caseId}/evidence`),
  });
  const sourceRefs = useQuery({
    queryKey: ["refs", caseId],
    queryFn: () => api<SourceRef[]>(`/cases/${caseId}/source-refs`),
  });
  async function action(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await client.invalidateQueries();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  function sendFiles(files: File[]) {
    if (!files.length) return;
    setLastFiles(files); setBatch(null);
    void action(async () => setBatch(await uploadBatch(caseId, files)));
  }
  return (
    <>
      <p>{t("noModel")}</p>
      <p>{t("batchNotice")}</p>
      {formats.data && <p>{formats.data.max_files} files · {formats.data.max_file_bytes / 1024 / 1024} MB/file · {formats.data.max_batch_bytes / 1024 / 1024} MB/batch</p>}
      {readOnly && <p role="status">{t("readOnly")}</p>}
      <div className="toolbar">
        <label className="file-button">
          {t("upload")}
          <input
            aria-label={t("upload")}
            type="file"
            multiple
            accept={formats.data?.formats.map(f => f.mime_type).join(",") || "image/png,image/jpeg,image/webp,application/pdf,text/plain"}
            disabled={busy || readOnly}
            onChange={(e) => {
              const files = Array.from(e.target.files || []);
              e.target.value = "";
              sendFiles(files);
            }}
          />
        </label>
        <label className="file-button">
          {t("manual")}
          <input
            type="file"
            aria-label={t("manual")}
            accept="application/json"
            disabled={busy || readOnly}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file)
                void action(async () =>
                  api(`/cases/${caseId}/perception/runs`, {
                    adapter: "manual",
                    fixtures: JSON.parse(await file.text()),
                  }),
                );
            }}
          />
        </label>
        <label>
          <input
            type="checkbox"
            checked={real}
            disabled={busy || readOnly}
            onChange={(e) => setReal(e.target.checked)}
          />
          {t("model")}
        </label>
        {real && <SearchableSelect label={<>{t("selectModel")}</>} value={selectedModel?.id || ""} disabled={busy || readOnly} onChange={e => setModelId(e.target.value)}><option value="" disabled>{t("configureModel")}</option>{visionModels.map(m => <option key={m.id} value={m.id}>{m.name} · {m.model_name}</option>)}</SearchableSelect>}
        <Button
          disabled={busy || readOnly || (real && (!selectedModel || !selectedModel.allow_external_egress)) || !query.data?.some(e => e.kind === "image")}
          onClick={() =>
            action(() =>
              api(`/cases/${caseId}/perception/runs`, {
                adapter: real ? "openai-compatible" : "mock",
                ...(real ? { model_id: selectedModel?.id, evidence_ids: query.data?.filter(e => e.kind === "image").map(e => e.id) } : {}),
              }),
            )
          }
        >
          {t("perceive")}
        </Button>
      </div>
      {real && !selectedModel && <p>{t("configureModel")}</p>}
      {real && selectedModel && !selectedModel.allow_external_egress && <p>{t("requestsDisabled")}</p>}
      {batch && <Card><h2>{t("batchSummary")}</h2><p>{t("uploaded")}: {batch.uploaded} · {t("duplicate")}: {batch.duplicates} · {t("failed")}: {batch.failed}</p><ul>{<Paged items={batch.results} label="批量上传结果" layout="list">{(pageItems) => pageItems.map(result => <li key={result.index}>{result.filename} · {t(result.status === "uploaded" ? "uploaded" : result.status === "duplicate" ? "duplicate" : "failed")}{result.error && ` · ${result.error}`}</li>)}</Paged>}</ul>{batch.failed > 0 && <Button disabled={busy || readOnly} onClick={() => sendFiles(batch.results.filter(r => r.status === "failed").map(r => lastFiles[r.index]))}>{t("retryFailed")}</Button>}</Card>}
      <form
        className="toolbar"
        onSubmit={(e) => {
          e.preventDefault();
          void action(async () =>
            setResults(
              await api(
                `/cases/${caseId}/search?q=${encodeURIComponent(search)}`,
              ),
            ),
          );
        }}
      >
        <Input
          aria-label={t("search")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("search")}
        />
        <Button disabled={busy}>{t("searchAction")}</Button>
      </form>
      {busy && <Feedback state="loading" />}
      {error && <Feedback state="error" error={error} />}
      {<Paged items={results} label="识别结果" layout="block">{(pageItems) => pageItems.map((r) => (
        <Card key={r.id}>
          <p>{r.text}</p>
          <Citations caseId={caseId} refs={r.source_refs} />
        </Card>
      ))}</Paged>}
      {sourceRefs.error && <Feedback state="error" error={sourceRefs.error.message} />}
      {query.isPending ? (
        <Feedback state="loading" />
      ) : query.error ? (
        <Feedback state="error" error={query.error.message} />
      ) : !query.data.length ? (
        <Feedback state="empty" />
      ) : (
        <div className="evidence-grid">
          {<Paged items={query.data} label="证据材料" layout="block" resetKey={caseId} pageSize={12}>{(pageItems) => pageItems.map((e) => (
            <Card key={e.id}>
              <Button
                disabled={e.kind === "image" && sourceRefs.isPending}
                onClick={() =>
                  rail.open({
                    type: "evidence",
                    evidence: e,
                    viewer: viewerFor(caseId, e, undefined, sourceRefs.data),
                  })
                }
              >
                {e.mime_type.startsWith("image/") && (
                  <img
                    className="thumbnail"
                    alt={e.filename}
                    src={viewerFor(caseId, e).url}
                  />
                )}
                <strong>{e.filename}</strong>
              </Button>
              <p>
                {e.mime_type} · {e.size_bytes} bytes
              </p>
              {e.kind === "image" && sourceRefs.data && <p>{t("imageRegions")}: {new Set(sourceRefs.data.filter(r => r.evidence_id === e.id && r.bbox).map(r => r.bbox!.join(","))).size}</p>}
              <code className="digest">SHA256 {e.sha256}</code>
            </Card>
          ))}</Paged>}
        </div>
      )}
    </>
  );
}

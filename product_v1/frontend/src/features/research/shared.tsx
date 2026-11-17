import { SearchableSelect } from "../../components/collections";
import { Paged } from "../../components/collections";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Input, Badge } from "../../components/ui";
import { failureGuide, term } from "./presentation";
import { api, key, stamp, label, type Prompt, type Quality, type Job } from "./client";

export function revealInvalidField(event: { target: EventTarget }) {
 let detail = (event.target as HTMLElement).closest("details");
 while (detail) { detail.open = true; detail = detail.parentElement?.closest("details") || null; }
}
export function JsonView({ value }: { value: unknown }) { return <pre className="research-json">{JSON.stringify(value, null, 2)}</pre>; }
export function ErrorText({ error }: { error: unknown }) { return error ? <p role="alert" className="research-error">{String(error)}</p> : null; }
export function FailureNotice({ error }: { error: { category?: string; message?: string; unknown?: boolean } }) {
 const [title, next] = failureGuide(error.category);
 return <div className="research-orientation" role="alert"><strong>{title}</strong><p>{next}</p>{error.message && <p>{error.message}</p>}<details><summary>排查信息</summary><JsonView value={error} /></details></div>;
}
export function Status({ value }: { value: string }) { const status = value.toLowerCase(); const tone = ["completed", "approved", "published", "passed", "accepted"].includes(status) ? "success" : ["failed", "rejected", "error"].includes(status) ? "danger" : ["unknown", "cancelled", "stale", "needs_review"].includes(status) ? "warning" : ["running", "queued", "rendering", "pending"].includes(status) ? "info" : "neutral"; return <Badge tone={tone}>{label(value)}</Badge>; }
export function PromptEditor({ purpose }: { purpose: "studio" | "review" }) {
  const client = useQueryClient();
  const prompts = useQuery({ queryKey: ["research", purpose, "prompts"], queryFn: () => api<Prompt[]>("/" + purpose + "/prompts") });
  const quality = useQuery({ queryKey: ["research", "quality"], queryFn: () => api<Quality[]>("/review/quality") });
  const initialName = purpose === "studio" ? "候选生成" : "质量评估";
  const blank = (name: string) => ({ name, markdown: "# " + name + "\n\n## 目标与约束\n\n", note: "", feedback: [] as string[], version: 0, basedOn: null as string | null });
  type Editor = ReturnType<typeof blank>;
  const [editor, setEditor] = useState<Editor>(() => blank(initialName));
  const [drafts, setDrafts] = useState<Record<string, Editor>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { name, markdown, note, feedback, version } = editor;
  const history = (prompts.data || []).filter(p => p.name === name).sort((a, b) => b.version - a.version);
  function load(target: string, p?: Prompt) {
    setDrafts(previous => ({ ...previous, [name]: editor }));
    const latest = (prompts.data || []).filter(p => p.name === target).sort((a, b) => b.version - a.version)[0];
    setEditor(p ? { name: target, markdown: p.markdown, note: "", feedback: p.feedback_ids, version: latest?.version || 0, basedOn: p.id } : drafts[target] || (latest ? { name: target, markdown: latest.markdown, note: "", feedback: latest.feedback_ids, version: latest.version, basedOn: latest.id } : blank(target)));
  }
  return <div className="research-two-column">
    <Card><h2>{purpose === "studio" ? "生成规则" : "评估规则"} · Markdown</h2>
      <p>规则用来告诉模型如何生成样本或检查质量。通常选择已有规则即可；需要修改时，请写明原因，旧版本会保留。当前是第 {version} 版。</p>
      <form className="research-form" onSubmit={e => {
        e.preventDefault(); setBusy(true); setError("");
        const submitted = editor;
        void api<Prompt>("/" + purpose + "/prompts", { name, markdown, note, expected_version: version, based_on_id: editor.basedOn, feedback_ids: feedback, idempotency_key: key() })
          .then(async p => { setEditor(current => current.name === submitted.name ? { ...current, version: p.version, basedOn: p.id, note: current.note === submitted.note ? "" : current.note } : current); await client.invalidateQueries({ queryKey: ["research", purpose, "prompts"] }); })
          .catch(e => setError(String(e))).finally(() => setBusy(false));
      }}>
        <label>规则名称<Input required value={name} disabled={busy} onChange={e => load(e.target.value)} /></label>
        {!!history.length && version === 0 && <p role="alert">已有此名称的历史，请加载一个版本再编辑；不会自动覆盖已有内容。</p>}
        <label>规则内容（支持 Markdown）<textarea required rows={14} value={markdown} onChange={e => setEditor({ ...editor, markdown: e.target.value })} /></label>
        <label>本轮修改意见 / 原因<textarea required rows={3} value={note} onChange={e => setEditor({ ...editor, note: e.target.value })} /></label>
        <details><summary>关联质量反馈（已选 {feedback.length} 条）</summary>
          {<Paged items={quality.data || []} label="可关联质量反馈" layout="block">{(pageItems) => pageItems.map(q => <label className="research-check" key={q.id}><Input type="checkbox" checked={feedback.includes(q.id)} onChange={e => setEditor({ ...editor, feedback: e.target.checked ? [...feedback, q.id] : feedback.filter(id => id !== q.id) })} />{q.id.slice(-10)} · r{q.revision} · {label(q.method)} · {q.suggestions || q.findings}</label>)}</Paged>}
        </details>
        <Button disabled={busy || prompts.isPending || !!prompts.error || (!!history.length && version === 0)}>保存为 v{version + 1}</Button>
      </form><ErrorText error={error || prompts.error || quality.error} />
    </Card>
    <Card><h2>迭代记录</h2>
      <a href={"/v1/" + purpose + "/prompts/export?name=" + encodeURIComponent(name)}>下载完整 Markdown 历史</a>
      {!history.length && <p>尚无已保存版本。</p>}
      {<Paged items={history} label="规则迭代历史" layout="block" resetKey={name}>{(pageItems) => pageItems.map(p => <details key={p.id}><summary>v{p.version} · {stamp(p.created_at)} · {p.note}</summary>
        <details><summary>版本编号与校验信息</summary><p>父版本：{p.parent_id || "初版"} · 校验值：{p.sha256}</p></details><a href={"/" + (purpose === "studio" ? "studio" : "review") + ".html?audit=1&object=" + encodeURIComponent(p.id)}>Prompt 操作历史</a><pre className="research-markdown">{p.markdown}</pre>
        <details><summary>引用的质量意见（{p.feedback_ids.length} 条）</summary><p>{p.feedback_ids.join(", ") || "未关联"}</p></details>
        <Button disabled={busy} onClick={() => load(name, p)}>基于此版本继续迭代</Button>
      </details>)}</Paged>}
      <SearchableSelect label={<>查看其他规则</>} value={name} disabled={busy} onChange={e => load(e.target.value)}><option value={name}>{name}</option>{[...new Set((prompts.data || []).map(p => p.name))].filter(n => n !== name).map(n => <option key={n}>{n}</option>)}</SearchableSelect>
    </Card>
  </div>;
}
export function JobsPanel({ jobs, refresh }: { jobs: Job[]; refresh: () => Promise<unknown> }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [full, setFull] = useState<Record<string, Job>>({});
  async function action(id: string, operation: string) {
    setBusy(id); setError("");
    try { await api("/research/jobs/" + id + "/" + operation, operation === "retry" ? { idempotency_key: key() } : {}); await refresh(); }
    catch (e) { setError(String(e)); } finally { setBusy(""); }
  }
  return <Card><h2>过程与恢复任务</h2><ErrorText error={error} />
    <p>这里查看后台正在做什么。若结果待确认，请先核对调用记录，再决定是否重试；重试可能再次计费。</p>
    {!jobs.length && <p>尚无任务。</p>}
    {<Paged items={jobs} label="后台任务" layout="block">{(pageItems) => pageItems.map(j => <details key={j.id} onToggle={e => { if (e.currentTarget.open) void api<Job>("/research/jobs/" + j.id).then(value => setFull(previous => ({ ...previous, [j.id]: value }))).catch(e => setError(String(e))); }}><summary><Status value={j.status} /> {term(j.kind)} · {term(j.phase)}</summary>
      <p>{stamp(j.created_at)} → {stamp(j.updated_at)}</p>{j.error && <FailureNotice error={j.error} />}
      <div className="toolbar">
        {j.kind !== "benchmark_pipeline" && ["queued", "running"].includes(j.status) && <Button disabled={busy === j.id || j.cancel_requested} onClick={() => action(j.id, "cancel")}>{j.cancel_requested ? "正在取消" : "取消任务"}</Button>}
        {!["evaluation", "benchmark", "benchmark_pipeline"].includes(j.kind) && (["failed", "unknown", "cancelled"].includes(j.status) || j.kind === "render" && j.status === "completed") && <Button disabled={busy === j.id} onClick={() => action(j.id, "retry")}>{j.status === "completed" ? "校验并修复产物" : "创建恢复任务"}</Button>}
      </div>
      {j.kind === "benchmark_pipeline" && <a href={"/evaluation.html?benchmark=1&pipeline=" + j.payload.pipeline_id}>从按图流程查看、停止或恢复 →</a>}
      <p>父任务：{j.parent_job_id || "无"} · 检查点：{Object.keys(j.checkpoints).length}</p>
      <details><summary>技术记录与恢复位置</summary><p>检查点是已保存的完成位置，用来避免重复处理。</p><JsonView value={full[j.id] || j} /></details>
    </details>)}</Paged>}
  </Card>;
}

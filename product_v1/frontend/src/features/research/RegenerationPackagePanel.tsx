import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card } from "../../components/ui";
import { api, key, type Prompt, type Batch } from "./client";
import type { ModelConfig } from "../../api/client";
import { ErrorText } from "./shared";
interface RegenPackage { contract: string; batch: string; synthetic: boolean; fact_policy: string; jobs: { item_id: string; instruction: string; judgment_excerpt: string; corrected_dialogue: Record<string, unknown>[]; must_delete_message_ids: string[]; synthetic: boolean }[] }
export function RegenerationPackagePanel() {
  const client = useQueryClient();
  const [text, setText] = useState("");
  const [pack, setPack] = useState<RegenPackage | null>(null);
  const [itemId, setItemId] = useState("");
  const [promptId, setPromptId] = useState("");
  const [modelId, setModelId] = useState("demo");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<Batch | null>(null);
  const prompts = useQuery({ queryKey: ["research", "studio", "prompts"], queryFn: () => api<Prompt[]>("/studio/prompts") });
  const models = useQuery({ queryKey: ["models"], queryFn: () => api<ModelConfig[]>("/settings/models") });
  const job = pack?.jobs.find(j => j.item_id === itemId);
  function inspect() {
    setError(""); setPack(null); setCreated(null);
    try {
      const value: RegenPackage = JSON.parse(text);
      if (value.contract !== "screenshot-review.v1" || value.batch !== "chat-screenshot-review-regen" || value.synthetic !== true || !Array.isArray(value.jobs) || !value.jobs.length || value.jobs.some(j => !j.item_id || !j.instruction || !Array.isArray(j.corrected_dialogue))) throw new Error("请选择包含待重生成任务的 B 导出包。");
      setPack(value); setItemId(value.jobs[0].item_id);
    } catch (e) { setError(String(e)); }
  }
  return <Card><h2>按 B 审核包重生成</h2><p>上传或粘贴审核台导出的 regen_jobs.json。生成输入来自包内的修正对话、判决摘录和明确批注；生成结果仍是待审核的合成数据。</p>
    <label>读取导出文件<input type="file" accept=".json,application/json" onChange={async e => { const f = e.target.files?.[0]; if (!f) return; if (f.size > 20 * 1024 * 1024) { setError("文件超过 20 MiB。"); return; } try { setText(await f.text()); setPack(null); } catch (err) { setError(String(err)); } }} /></label>
    <label>重生成包 JSON<textarea rows={6} value={text} onChange={e => { setText(e.target.value); setPack(null); }} /></label><Button disabled={busy || !text.trim()} onClick={inspect}>验证并预览输入包</Button>
    {pack && <><p className="screenshot-scope-note">合成数据 · {pack.jobs.length} 个重生成任务 · 不作为真实司法证据</p>
      <label>本次任务<select value={itemId} onChange={e => setItemId(e.target.value)}>{pack.jobs.map(j => <option key={j.item_id}>{j.item_id}</option>)}</select></label>
      {job && <details open><summary>核对本次修正目标（{job.corrected_dialogue.length} 条消息）</summary><p>{job.instruction}</p><p>删除消息：{job.must_delete_message_ids?.join("、") || "无"}</p><pre>{JSON.stringify(job.corrected_dialogue, null, 2)}</pre><details><summary>来源摘录</summary><p>{job.judgment_excerpt || "未提供"}</p></details></details>}
      <form onSubmit={e => { e.preventDefault(); setBusy(true); setError(""); void api<Batch>("/studio/screenshot-regenerate", { package: pack, item_id: itemId, name, prompt_id: promptId, model_id: modelId, idempotency_key: key() }).then(async b => { setCreated(b); await client.invalidateQueries({ queryKey: ["research"] }); }).catch(e => setError(String(e))).finally(() => setBusy(false)); }}>
        <label>批次名称<input required value={name} onChange={e => setName(e.target.value)} /></label>
        <label>生成规则<select required value={promptId} onChange={e => setPromptId(e.target.value)}><option value="">请选择已保存规则</option>{prompts.data?.map(p => <option key={p.id} value={p.id}>{p.name} · v{p.version}</option>)}</select></label>
        <label>生成模型<select value={modelId} onChange={e => setModelId(e.target.value)}><option value="demo">离线演练（复制修正目标，不调用模型）</option>{models.data?.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
        <Button variant="primary" disabled={busy || !job || !promptId}>{busy ? "正在创建…" : "按此修正包生成待审样本"}</Button>
      </form>
    </>}<ErrorText error={error || prompts.error || models.error} />{created && <p role="status">已创建待审合成批次。<a href={"/studio.html?batch=" + created.id}>查看批次进度</a></p>}
  </Card>;
}

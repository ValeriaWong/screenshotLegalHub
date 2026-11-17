import { SearchableSelect } from "../../components/collections";
import { Paged } from "../../components/collections";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Input } from "../../components/ui";
import type { ModelConfig } from "../../api/client";
import { api, key, stamp, label, num, type Detail, type Prompt, type Quality } from "./client";
import { term } from "./presentation";
import { revealInvalidField, ErrorText, JsonView, Status } from "./shared";
export function QualityPanel({ detail }: { detail: Detail }) {
  const client = useQueryClient();
  const [verdict, setVerdict] = useState("pending");
  const [score, setScore] = useState("");
  const [findings, setFindings] = useState("");
  const [suggestions, setSuggestions] = useState("");
  const [process, setProcess] = useState("");
  const [dimensions, setDimensions] = useState("{}");
  const [supersedes, setSupersedes] = useState<string | null>(null);
  const [promptId, setPromptId] = useState("");
  const [modelId, setModelId] = useState("demo");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [scope, setScope] = useState("both");
  const [ack, setAck] = useState("");
  const [confirmGold, setConfirmGold] = useState(false);
  const [coverage, setCoverage] = useState("text");
  const [rubric, setRubric] = useState("human.v1");
  const imageReady = !!detail.binding;
  const prompts = useQuery({ queryKey: ["research", "review", "prompts"], queryFn: () => api<Prompt[]>("/review/prompts") });
  const models = useQuery({ queryKey: ["models"], queryFn: () => api<ModelConfig[]>("/settings/models") });
  const rows = detail.quality;
  const superseded = new Set(rows.map(q => q.supersedes));
  function edit(q: Quality) {
    setSupersedes(q.id); setVerdict(q.verdict); setScore(q.score == null ? "" : String(q.score));
    setFindings(q.findings); setSuggestions(q.suggestions); setProcess(q.process); setDimensions(JSON.stringify(q.dimensions, null, 2));
  }
  async function action(fn: () => Promise<unknown>) {
    setError(""); setBusy(true);
    try { await fn(); await client.invalidateQueries({ queryKey: ["research"] }); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  return <Card><h2>审核结论与修改意见 · 第 {detail.sample.revision} 版</h2>
    <p>核对上方截图后，记录发现的问题和处理结论。可以只留下修改意见，不必给分。模型意见只能辅助你判断。</p>
    {rows.some(q => q.input_scope_status === "legacy_scope_ambiguous") && <p role="status">部分历史模型意见的图片范围需要复核。请先核对实际图片清单，再采纳补图或缺页建议。</p>}
    {!imageReady && <p role="status">当前图片尚未准备好，暂时不能确认图片通过。请等待生成完成；若一直未完成，可在下方任务中查看原因并修复。</p>}
    <div className="research-form">
      <form className="research-form" onInvalidCapture={revealInvalidField} onSubmit={e => {
        e.preventDefault();
        void action(async () => {
          const parsed = JSON.parse(dimensions);
          if (!parsed || Array.isArray(parsed) || typeof parsed !== "object" || Object.values(parsed).some(v => typeof v !== "number" || !Number.isFinite(v))) throw new Error("分项分数须为数值对象");
          await api("/review/samples/" + detail.sample.id + "/quality", { revision: detail.sample.revision, review_scope: scope, manifest_id: scope === "text" ? null : ack || null, content_hash: detail.revision.content_hash, confirm_gold: confirmGold, rubric_id: rubric, verdict, score: score === "" ? null : Number(score), dimensions: parsed, findings, suggestions, process, supersedes, idempotency_key: key() });
          setSupersedes(null); setFindings(""); setSuggestions(""); setProcess("");
        });
      }}>
        <h3>{supersedes ? "修订记录 " + supersedes.slice(-10) : "添加人工质量记录"}</h3>
        <p>本次审核的是第 {detail.sample.revision} 版文字和上方对应图片。{!imageReady && "图片尚未就绪。"}</p>
        <label>审核范围<select value={scope} onChange={e => { setScope(e.target.value); setConfirmGold(false); }}><option value="both">文本与图片</option><option value="text">仅文本（不能发布）</option><option value="visual">仅图片（不能单独发布）</option></select></label>

        {scope !== "text" && <label className="research-check"><Input type="checkbox" checked={imageReady && ack === detail.binding?.manifest_id} disabled={!imageReady} onChange={e => setAck(e.target.checked ? detail.binding!.manifest_id : "")} />我已核对上方当前图片</label>}
        {scope === "both" && detail.revision.content.questions.some(q => q.gold) && <label className="research-check"><Input type="checkbox" checked={confirmGold} onChange={e => setConfirmGold(e.target.checked)} />同时确认勾选题目的答案和证据，可作为评测标准答案（金标）</label>}
        <p className="research-hint">“通过”表示你已人工核对；“需修改”会保留问题，供后续修正或生成使用。</p><label>结论<select value={verdict} onChange={e => setVerdict(e.target.value)}><option value="pending">暂不判断</option><option value="pass">通过</option><option value="revise">需修改</option><option value="reject">不采用</option></select></label>
        <details><summary>可选：评分与评估方法</summary><p className="research-hint">日常审核可以不评分。只有需要按统一量表比较时才填写；分项格式供维护人员使用。</p>        <label>评分量表版本<Input value={rubric} onChange={e => setRubric(e.target.value)} /></label>        <label>总分（可留空，0–100）<Input type="number" min={0} max={100} step="any" value={score} onChange={e => setScore(e.target.value)} /></label>
        <label>分项分数 JSON<textarea rows={2} value={dimensions} onChange={e => setDimensions(e.target.value)} /></label>
</details>
        <label>你发现了什么问题<textarea rows={3} value={findings} onChange={e => setFindings(e.target.value)} /></label>
        <label>修改意见<textarea rows={3} value={suggestions} onChange={e => setSuggestions(e.target.value)} /></label>
        <label>你依据什么作出判断<textarea rows={3} value={process} onChange={e => setProcess(e.target.value)} /></label>
        <div className="toolbar"><Button variant="primary" disabled={busy || (verdict === "pass" && scope !== "text" && (!imageReady || ack !== detail.binding?.manifest_id))}>保存质量记录</Button>{supersedes && <Button type="button" onClick={() => setSupersedes(null)}>取消修订</Button>}</div>
      </form>
      <div className="research-form">
        <details><summary>需要模型协助检查？</summary><p>模型会给出参考意见并保存记录，不能替你确认人工审核通过。</p><h3>运行模型质量评估</h3><label>模型评估范围<select value={coverage} onChange={e => setCoverage(e.target.value)}><option value="text">仅文本</option><option value="visual">图片与来源/题目</option><option value="multimodal">文本与图片</option></select></label>
        <SearchableSelect label={<>检查规则</>} value={promptId || prompts.data?.[0]?.id || ""} onChange={e => setPromptId(e.target.value)}><option value="" disabled>先在评估规则页保存一份规则</option>{prompts.data?.map(p => <option key={p.id} value={p.id}>{p.name} · v{p.version}</option>)}</SearchableSelect>
        <SearchableSelect label={<>评估模型</>} value={modelId} onChange={e => setModelId(e.target.value)}><option value="demo">离线 Demo（不评分）</option>{models.data?.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</SearchableSelect>
        <Button disabled={busy || !(promptId || prompts.data?.[0]?.id) || (coverage !== "text" && !imageReady)} onClick={() => action(() => api("/review/samples/" + detail.sample.id + "/quality-runs", { revision: detail.sample.revision, coverage, manifest_id: coverage === "text" ? null : detail.binding?.manifest_id, prompt_id: promptId || prompts.data?.[0]?.id, model_id: modelId, idempotency_key: key() }))}>提交质量评估任务</Button>
        <p>将按所选规则检查当前版本。结果和修改建议会保存在下方，可随时追查。</p>
      </details></div>
    </div><ErrorText error={error || prompts.error || models.error} />
    <h3>之前的审核与模型意见（{rows.length}）</h3>
    {<Paged items={rows} label="历史审核意见" layout="block" resetKey={detail.sample.id} pageSize={10}>{(pageItems) => pageItems.map(q => <details key={q.id}><summary><Status value={q.verdict} /> r{q.revision} · {label(q.method)} · {q.score == null ? "未评分" : "参考分 " + num(q.score)} · {superseded.has(q.id) ? "已被后续记录替代" : q.revision === detail.sample.revision ? "本版意见" : "历史版本意见"} · {q.input_scope_status === "legacy_scope_ambiguous" ? "图片范围需复核 · " : ""}{stamp(q.created_at)}</summary>
      <>{q.input_scope_status === "legacy_scope_ambiguous" && <p role="status">这条历史模型意见没有明确区分来源图片和待审合成图。采纳补图或缺页建议前，请按当前图片清单人工核对。</p>}</><p>检查范围：{term(q.coverage || q.review_scope)} · {term(q.binding_status || "legacy_unbound")}</p><>{q.reviewed_object && <p>实际检查对象：{term(q.reviewed_object.visual_role)} · {q.reviewed_object.expected_pages ? q.reviewed_object.expected_pages + " 页" : "未发送图片"}</p>}</><p>{q.findings}</p><p>修改意见：{q.suggestions || "无"}</p><pre className="research-markdown">{q.process}</pre>
      {q.revision === detail.sample.revision && !superseded.has(q.id) && <Button onClick={() => edit(q)}>参考这条意见，填写人工审核</Button>}
      <details><summary>技术详情：评估版本与完整记录</summary><JsonView value={q} /></details>
    </details>)}</Paged>}
  </Card>;
}

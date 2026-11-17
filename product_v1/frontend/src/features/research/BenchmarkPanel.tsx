import { exportLabelU, importLabelU, downloadLabelU } from "./labelu";
import { SearchableSelect } from "../../components/collections";
import { Paged } from "../../components/collections";
import { useEffect, useRef, useState } from "react";
import { RegionCanvas } from "./RegionCanvas";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Input } from "../../components/ui";
import { useUser } from "../auth/AuthGate";
import { api, key, stamp, label } from "./client";
import { ErrorText, JsonView, Status } from "./shared";
import { PipelinePanel } from "./PipelinePanel";
import { BenchmarkSamples } from "./BenchmarkSamples";
import { readDraft, writeDraft, clearDraft, draftKey } from "./benchmarkDrafts";

interface Dataset { id: string; name: string; counts: Record<string, number> }
interface TaskRow { task_id: string; image_name: string; task_family: string; label: string; asset_status: string; reference_status: string; review_version: number }
interface Annotation { id: string; version: number; target: unknown; question: string; bbox_xyxy: number[] | null; region_type: string; reason: string; split: string; case_group: string; image_identity_confirmed: boolean; verdict: string; created_at: string; question_eligibility?: string }
interface Task { task_id: string; image_name: string; question: string; task_family: string; answer_kind: string; target: unknown; bbox_xyxy: number[] | null; source_label?: string; asset: { width: number; height: number; sha256: string; origin: string } }
interface TaskDetail { task: Task; annotation: Annotation | null; revisions: Annotation[]; comments: { id: string; body: string; method: string; created_at: string }[]; quality: { id: string; method: string; findings: string; suggestions: string; verdict: string; created_at: string }[]; asset_url: string; regions: { id: string; bbox: number[]; task_id: string; label: string }[]; legacy_match: { best_iou: number; no_message: boolean; best_msg: { bbox: number[]; content?: string } | null } | null }
interface DraftForm { questionEligibility?: string; target: string; question: string; bbox: number[] | null; regionType: string; reason: string; split: string; caseGroup: string; confirmed: boolean; comment: string; useForGeneration: boolean; verdict: string }
const modes: Record<string, string> = { legacy_replay: "旧结果离线回放", development_reference: "开发参考评分（旧答案未复核）", official_reviewed: "人工发布版本评分" };
const tracks: Record<string, string> = { kie_image: "KIE：整图消息抽取", vqa_image_full: "VQA：只看整图", vqa_image_region: "VQA：整图＋明确指定区域", vqa_predicted_text: "VQA：只看已保存的 KIE 预测" };
const fieldLabels: Record<string, string> = { attitude: "态度（旧标签待核）", classify: "截图类型", speaker_comment_attitude: "回复态度", nickname: "发言人编号（旧标注）", case: "案情分析", evidence: "截图证据形式", group_chat_or_private_chat: "群聊或私聊", show_real_identity: "身份信息是否可见", legal_relationship: "法律关系分析", legal_intent: "法律意图分析", legal_analysis: "法律分析", action_analysis: "行为分析", amount: "金额", speaker: "说话人", file_name: "文件名", evidence_: "文件证据类型（待核）", evidence_content: "文件证据内容", speaker_avator: "头像关联（待核）" };
const fieldLabel = (value: string) => fieldLabels[value] || value;
function display(value: unknown) { return typeof value === "string" ? value : JSON.stringify(value, null, 2); }

function OpenRubric({ dataset, task }: { dataset: string; task: Task }) {
  const client = useQueryClient(), user = useUser(), rubricEpoch = useRef(0);
  const [rubricReady, setRubricReady] = useState(false);
  const rubricKey = draftKey(user?.id || "", dataset, task.task_id + ":rubric");
  const [attemptId, setAttemptId] = useState(""), [process, setProcess] = useState(""), [findings, setFindings] = useState(""), [suggestions, setSuggestions] = useState(""), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const [dimensions, setDimensions] = useState<Record<string, number>>({ faithfulness: 0, relevance: 0, support: 0, no_unsupported_claims: 0, uncertainty: 0 });
  const attempts = useQuery({ queryKey: ["research", "benchmark-review-attempts", dataset, task.task_id], queryFn: () => api<{ id: string; response: { raw: string; demo?: boolean } }[]>("/review/benchmark-attempts?" + new URLSearchParams({ dataset_id: dataset, task_id: task.task_id })) });
  useEffect(() => {
    let active = true;
    void readDraft(rubricKey).then(d => {
      if (!active || !d || rubricEpoch.current) return;
      const c = d.content; setAttemptId(String(c.attemptId || "")); setProcess(String(c.process || "")); setFindings(String(c.findings || "")); setSuggestions(String(c.suggestions || "")); if (c.dimensions) setDimensions(c.dimensions as Record<string, number>);
    }).catch(e => setError(String(e))).finally(() => { if (active) setRubricReady(true); });
    return () => { active = false; };
  }, [rubricKey]);
  useEffect(() => {
    if (!rubricReady || (!process && !findings && !suggestions)) return;
    void writeDraft(rubricKey, { draft_id: rubricKey, base_version: 0, content: { attemptId, process, findings, suggestions, dimensions }, updated_at: new Date().toISOString() }).catch(e => setError(String(e)));
  }, [rubricReady, rubricKey, attemptId, process, findings, suggestions, dimensions]);
  const chosen = attempts.data?.find(a => a.id === attemptId);
  return <details onInput={() => { rubricEpoch.current++; }}><summary>审核模型开放分析答案</summary><p>五项均为 0 至 4 分，分数越高表示越符合要求。此量表评价输入是否支持回答；法律正确性不自动认证。质量裁判 Prompt 仍在“评估规则与修改历史”管理。</p>
    <SearchableSelect label={<>选择已返回的模型答案</>} value={attemptId} onChange={e => setAttemptId(e.target.value)}><option value="">选择答案</option>{attempts.data?.filter(a => !a.response.demo).map(a => <option key={a.id} value={a.id}>{a.id}</option>)}</SearchableSelect>{chosen && <pre className="research-markdown">{chosen.response.raw}</pre>}
    <div className="research-grid-3">{Object.entries({ faithfulness: "事实忠实", relevance: "回答相关", support: "可见证据支持", no_unsupported_claims: "没有无据假设", uncertainty: "恰当表达不确定性" }).map(([k, label]) => <label key={k}>{label}<Input type="number" min={0} max={4} step={1} value={dimensions[k]} onChange={e => setDimensions(d => ({ ...d, [k]: Number(e.target.value) }))} /></label>)}</div>
    <label>审核过程 / 依据<textarea value={process} onChange={e => setProcess(e.target.value)} /></label><label>评估发现<textarea value={findings} onChange={e => setFindings(e.target.value)} /></label><label>修改建议<textarea value={suggestions} onChange={e => setSuggestions(e.target.value)} /></label>
    <Button disabled={busy || !chosen || !process.trim() || !findings.trim()} onClick={async () => { setBusy(true); setError(""); try { await api("/review/benchmark-quality", { attempt_id: attemptId, dimensions, process, findings, suggestions, idempotency_key: key() }); await clearDraft(rubricKey); await client.invalidateQueries({ queryKey: ["research"] }); } catch (e) { setError(String(e)); } finally { setBusy(false); } }}>保存量表和修改意见</Button><ErrorText error={error || attempts.error} />
  </details>;
}

function BenchmarkEditor({ dataset, detail, dirtyChange }: { dataset: string; detail: TaskDetail; dirtyChange: (dirty: boolean) => void }) {
  const client = useQueryClient(), user = useUser(), t = detail.task, a = detail.annotation;
  const initial: DraftForm = { questionEligibility: a?.question_eligibility || "unverified", target: display(a ? a.target : t.target) ?? "null", question: a?.question || t.question, bbox: a ? a.bbox_xyxy : t.bbox_xyxy, regionType: a?.region_type || "unclassified_legacy_rect", reason: "", split: a?.split || "unassigned", caseGroup: a?.case_group || "", confirmed: a?.image_identity_confirmed || false, comment: "", useForGeneration: true, verdict: "draft" };
  const [form, setForm] = useState(initial), [locked, setLocked] = useState(true), [dirty, setDirty] = useState(false), [ready, setReady] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(""), [status, setStatus] = useState("正在检查草稿"), [base, setBase] = useState(a?.version || 0), [judgment, setJudgment] = useState(false), [textDialog, setTextDialog] = useState(false);
  const savedForm = useRef(initial);
  const draftId = useRef<string>(key()), remoteVersion = useRef(0), editEpoch = useRef(0), saveQueue = useRef<Promise<unknown>>(Promise.resolve()), dirtyRef = useRef(false);
  const cacheKey = draftKey(user?.id || "", dataset, t.task_id), endpoint = "/review/benchmarks/" + dataset + "/tasks/" + t.task_id;
  function change(patch: Partial<DraftForm>) { editEpoch.current++; dirtyRef.current = true; setDirty(true); dirtyChange(true); setForm(f => ({ ...f, ...patch })); }
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const local = await readDraft(cacheKey), remote = await api<{ version: number; draft_id: string; base_version: number; content: DraftForm & { _cleared?: boolean }; updated_at: string } | null>(endpoint + "/draft");
        if (!active) return;
        remoteVersion.current = remote?.version || 0;
        const saved = local && (!remote || local.updated_at > remote.updated_at) ? local : remote;
        if (saved && !saved.content._cleared && saved.base_version >= (a?.version || 0)) { setForm(saved.content as unknown as DraftForm); setBase(saved.base_version); draftId.current = saved.draft_id; setDirty(true); dirtyRef.current = true; dirtyChange(true); setStatus("已恢复未提交草稿，请核对后保存"); }
        else setStatus("草稿缓存就绪");
      } catch (e) { if (active) setStatus("草稿读取失败；当前输入仍可保留：" + String(e)); }
      if (active) setReady(true);
    })();
    return () => { active = false; };
  // The editor is keyed by task; refreshes cannot reset user input.
  }, [cacheKey, endpoint]);
  useEffect(() => {
    if (!ready || !dirty || busy) return;
    const draft = { draft_id: draftId.current, base_version: base, content: form as unknown as Record<string, unknown>, updated_at: new Date().toISOString() };
    void writeDraft(cacheKey, draft).catch(e => setStatus("本地缓存失败：" + String(e)));
    const timer = setTimeout(() => { saveQueue.current = saveQueue.current.catch(() => undefined).then(async () => {
      const saved = await api<{ version: number }>(endpoint + "/draft", { draft_id: draftId.current, base_version: base, content: form, expected_version: remoteVersion.current }, "PUT"); remoteVersion.current = saved.version; setStatus("本地与服务器草稿已保存");
    }).catch(e => { setError(String(e)); setStatus("服务器草稿冲突；请保留当前输入后比对其他页面"); }); }, 1000);
    return () => clearTimeout(timer);
  }, [form, base, ready, dirty, busy, cacheKey, endpoint]);
  useEffect(() => { const protect = (e: BeforeUnloadEvent) => { if (dirtyRef.current) { e.preventDefault(); e.returnValue = ""; } }; window.addEventListener("beforeunload", protect); return () => window.removeEventListener("beforeunload", protect); }, []);
  async function save(commentOnly = false) {
    const epoch = editEpoch.current, snapshot = { ...form }; setBusy(true); setError("");
    try {
      await saveQueue.current.catch(() => undefined);
      if (commentOnly) await api(endpoint + "/comments", { body: snapshot.comment, use_for_generation: snapshot.useForGeneration, idempotency_key: key() });
      else {
        const target = ["kie", "amount", "set"].includes(t.answer_kind) ? JSON.parse(snapshot.target) : snapshot.target === "null" ? null : snapshot.target;
        const saved = await api<Annotation>(endpoint, { expected_version: base, target, question: snapshot.question, question_eligibility: snapshot.questionEligibility || "unverified", bbox_xyxy: snapshot.bbox, region_type: snapshot.regionType, reason: snapshot.reason, split: snapshot.split, case_group: snapshot.caseGroup, image_identity_confirmed: snapshot.confirmed, verdict: snapshot.verdict, idempotency_key: key() }, "PUT"); setBase(saved.version);
      }
      if (epoch === editEpoch.current) {
        const pendingOther = commentOnly ? JSON.stringify({ ...snapshot, comment: "" }) !== JSON.stringify({ ...savedForm.current, comment: "" }) : !!snapshot.comment;
        if (!commentOnly) savedForm.current = snapshot;
        if (commentOnly) setForm(f => ({ ...f, comment: "" }));
        dirtyRef.current = pendingOther; setDirty(pendingOther); dirtyChange(pendingOther);
        if (!pendingOther) {
          await clearDraft(cacheKey);
          const cleared = await api<{ version: number }>(endpoint + "/draft", { draft_id: draftId.current, base_version: base, content: { _cleared: true }, expected_version: remoteVersion.current }, "PUT"); remoteVersion.current = cleared.version;
        }
        setStatus(commentOnly ? "评论已保存；其他修改仍留在草稿" : "已保存新审核版本；原图和旧版本保留");
      } else setStatus("提交已保存；提交期间的新输入仍保留在草稿");
      await client.invalidateQueries({ queryKey: ["research"] });
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  return <Card><h2>核对截图和目标答案</h2><p>{t.image_name} · {t.source_label ? fieldLabel(t.source_label) : "整图抽取"} · {a ? "当前审核版本 " + a.version : "旧标注尚未复核"}</p>
    <p>先核对原图，再修改目标或保存评论。只有明确选择“人工通过”，并核对图片、案件组和用途后，才可发布。</p>
    {t.asset.origin === "candidate_identity_unverified" && <p role="status">这张图来自补图候选，尚未确认与旧标注对应。请核对图片身份。</p>}
    <Button onClick={() => setJudgment(v => !v)}>查看判决书原文</Button>{judgment && <aside role="dialog" aria-label="判决书原文"><h3>判决书原文</h3><p>此旧样本尚未绑定判决书。当前没有可展示的原文，不能将旧模型分析作为原文。</p><Button onClick={() => setJudgment(false)}>关闭原文面板</Button></aside>}
    <details><summary>LabelU 矩形标注交换</summary><p>使用 LabelU-Kit 的像素 x/y/width/height 矩形协议；此交换文件针对当前任务，不是 LabelU 全项目备份。导入后只更新草稿，仍须填写审核原因并保存新版本。</p>
      <Button onClick={() => { try { const target = ["kie","amount","set"].includes(t.answer_kind) ? JSON.parse(form.target) : form.target; downloadLabelU(exportLabelU(t.asset,form.bbox,form.question,target,form.regionType)); } catch (e) { setError(String(e)); } }}>导出当前矩形与答案</Button>
      <label>导入 LabelU 矩形交换文件<Input type="file" accept=".json" disabled={busy || !ready} onChange={async e => { const file=e.target.files?.[0]; e.target.value=""; if (!file) return; setError(""); try { if (file.size>1000000) throw new Error("标注文件超过 1 MB"); const imported=importLabelU(JSON.parse(await file.text()),t.asset); change({bbox:imported.bbox,question:imported.question,target:display(imported.target),confirmed:false,verdict:"draft"}); setStatus("标注已导入草稿，请核对后保存新版本"); } catch (e) { setError(String(e)); } }} /></label>
    </details>
    <div className="benchmark-verify-layout"><aside className="benchmark-source-pane"><h3>原图与区域</h3>
    <label className="research-check"><Input type="checkbox" checked={locked} onChange={e => setLocked(e.target.checked)} />锁定坐标（默认只修改文本；取消后可拖动橙色框和角点）</label>
    <RegionCanvas detail={detail} bbox={form.bbox} locked={locked} change={bbox => change({ bbox })} edit={() => setTextDialog(true)} />
    </aside><section className="benchmark-answer-pane" aria-label="任务与答案"><h3>问题、答案与审核</h3>
    {textDialog && <dialog open className="review-message-dialog" style={{ position: "fixed", top: "10vh", padding: 24, zIndex: 20 }} aria-label="编辑区域目标文本"><h3>编辑当前区域的目标文本</h3><label>目标内容<textarea rows={8} value={form.target} onChange={e => change({ target: e.target.value })} /></label><label>修改原因<textarea value={form.reason} onChange={e => change({ reason: e.target.value })} /></label><div className="toolbar"><Button disabled={busy || !ready || !form.reason.trim()} onClick={async () => { await save(); }}>保存文本修订</Button><Button onClick={() => setTextDialog(false)}>关闭，保留草稿</Button></div><p>{status}</p><ErrorText error={error} /></dialog>}
    {detail.legacy_match && <p>旧匹配 IoU：{detail.legacy_match.best_iou.toFixed(4)} · {detail.legacy_match.no_message ? "没有模型消息框" : "仅为旧区域关联值，不是检测准确率"}</p>}
    {t.answer_kind === "amount" && <p>金额目标须填写 JSON，例如 {'{"answer_status":"known","value":"520.00","currency":"CNY"}'}。金额未知时保留 unknown；不能当作零。</p>}
    <div className="research-form"><label>任务问题<textarea value={form.question} onChange={e => change({ question: e.target.value })} /></label>
      <label>目标答案{["kie", "amount", "set"].includes(t.answer_kind) ? "（JSON，保留结构字段）" : "（原文）"}<textarea rows={t.answer_kind === "kie" ? 12 : 4} value={form.target} onChange={e => change({ target: e.target.value })} /></label>
      <div className="research-grid-3"><label>问题能否脱离参考框理解<select value={form.questionEligibility || "unverified"} onChange={e => change({ questionEligibility: e.target.value })}><option value="unverified">尚未核对</option><option value="reviewed_independent">已核对：无需标注编号或参考框即可唯一理解</option><option value="context_required">需要参考区域才能理解</option></select></label><label>区域是什么<select value={form.regionType} onChange={e => change({ regionType: e.target.value })}><option value="unclassified_legacy_rect">尚未确认</option><option value="message">完整消息</option><option value="avatar">头像</option><option value="amount">金额片段</option><option value="filename">文件名片段</option><option value="other">其他</option></select></label>
        <label>案件组编号<Input value={form.caseGroup} placeholder="同一案件使用同一编号" onChange={e => change({ caseGroup: e.target.value })} /></label>
        <label>数据用途<select value={form.split} onChange={e => change({ split: e.target.value })}><option value="unassigned">尚未划分</option><option value="development">开发集：允许用于迭代</option><option value="holdout">留出集：只做独立验证</option></select></label></div>
      <label className="research-check"><Input type="checkbox" checked={form.confirmed} onChange={e => change({ confirmed: e.target.checked })} />我已核对图片身份与本条标注对应</label>
      <label>审核结论<select value={form.verdict} onChange={e => change({ verdict: e.target.value })}><option value="draft">保存修订，继续审核</option><option value="revise">需要纠正</option><option value="pass">人工通过（可申请发布）</option></select></label>
      <label>修改原因 / 审核过程<textarea value={form.reason} onChange={e => change({ reason: e.target.value })} /></label>
      <Button disabled={!ready || busy || !form.reason.trim()} onClick={() => save()}>保存审核新版本</Button>
      <label>评论 / 给下一轮生成的修改建议<textarea value={form.comment} onChange={e => change({ comment: e.target.value })} /></label>
      <label className="research-check"><Input type="checkbox" checked={form.useForGeneration} onChange={e => change({ useForGeneration: e.target.checked })} />用于后续生成改进（只有开发集意见可供生成台读取）</label>
      <Button disabled={!ready || busy || !form.comment.trim()} onClick={() => save(true)}>只保存评论</Button><p role="status">{status}{dirty ? " · 有未提交输入" : ""}</p><ErrorText error={error} />
    </div>
    </section></div>
    {t.answer_kind === "open_text" && <OpenRubric dataset={dataset} task={t} />}
    <details><summary>评论与质量过程（{detail.comments.length + detail.quality.length}）</summary>{<Paged items={detail.comments} label="任务评论" layout="block">{(pageItems) => pageItems.map(c => <p key={c.id}>{c.body} · {c.method === "legacy_import" ? "旧意见，原操作者未知" : "人工评论"} · {stamp(c.created_at)}</p>)}</Paged>}{<Paged items={detail.quality} label="任务质量记录" layout="block">{(pageItems) => pageItems.map(q => <p key={q.id}>{q.findings} · {q.suggestions} · {q.verdict}</p>)}</Paged>}</details>
    <details><summary>审核版本与修改原因（{detail.revisions.length}）</summary>{<Paged items={detail.revisions} label="审核版本" layout="block">{(pageItems) => pageItems.map(r => <div key={r.id}><p>v{r.version} · {r.reason} · {stamp(r.created_at)}</p><JsonView value={r} /></div>)}</Paged>}</details>
    <a href={"/review.html?audit=1&object=" + encodeURIComponent(a?.id || dataset)}>查看操作审计 →</a>
  </Card>;
}

interface TaskPrompt { id: string; name: string; family: string; version: number; markdown: string; note: string; parent_id: string | null }
interface RunSummary { id: string; name: string; mode: string; status: string; created_at: string; dataset_id: string; method?: { id: string; name: string; calls_per_task: number } }
interface BenchResult { run: RunSummary & { job_id?: string; parent_run_id?: string; tasks?: { task_id: string; image_name: string }[] }; attempts: { id: string; task_id: string; status: string; response?: { raw: string }; error?: unknown }[]; scores: { id: string; task_id: string; attempt_id: string; reference_status: string; reason: string; result: { status: string; score: number | null } }[]; method_steps?: { id: string; attempt_id: string; stage: string; status: string; messages: { role: string; content: unknown }[]; response?: { raw: string } }[]; report: Record<string, number> }
export function BenchmarkExecution({ dataset, selected }: { dataset: string; selected: string[] }) {
  const client = useQueryClient(), user = useUser();
  const [promptReady, setPromptReady] = useState(false);
  const [track, setTrack] = useState("kie_image"), [mode, setMode] = useState("development_reference"), [name, setName] = useState(""), [model, setModel] = useState("demo"), [promptId, setPromptId] = useState(""), [releaseId, setReleaseId] = useState(""), [maxCalls, setMaxCalls] = useState(1), [upstream, setUpstream] = useState(""), [runId, setRunId] = useState(new URLSearchParams(location.search).get("benchmark_run") || ""), [error, setError] = useState(""), [busy, setBusy] = useState(false), [preview, setPreview] = useState<unknown>(null), [promptText, setPromptText] = useState(""), [promptNote, setPromptNote] = useState(""), [promptDirty, setPromptDirty] = useState(false), [replayOffset, setReplayOffset] = useState(0), [historyId, setHistoryId] = useState(""), [historyOffset, setHistoryOffset] = useState(0);
  const [method, setMethod] = useState("E00"), [methodAttempts, setMethodAttempts] = useState(2), [methodOutputTokens, setMethodOutputTokens] = useState(6144);
  const [lmadProtocol, setLmadProtocol] = useState("hybrid");
  const [labVariant, setLabVariant] = useState("react");
  const dynamicMethod = ["E09", "E14", "E15", "E16", "E18", "E23", "E24", "E25"].includes(method);
  const requiredCalls = selected.length * (method === "E25" ? 20 : method === "E24" ? 40 : method === "E18" ? 29 : method === "E23" ? (labVariant === "plan_and_solve" ? 4 : 6) : method === "E05" ? 2 * methodAttempts : method === "E01" ? 14 : method === "E21" ? 3 * methodAttempts - 1 : method === "E09" ? (lmadProtocol === "ranked" ? 24 : 10) : method === "E16" ? 4 : method === "E14" ? 2 : 1);
  const methodTrackSupported = method === "E00" || (dynamicMethod ? track === "vqa_predicted_text" : method === "E21" ? ["kie_image", "vqa_image_full", "vqa_predicted_text"].includes(track) : ["kie_image", "vqa_image_full"].includes(track));
  const models = useQuery({ queryKey: ["models"], queryFn: () => api<{ id: string; name: string }[]>("/settings/models") });
  const prompts = useQuery({ queryKey: ["research", "task-prompts"], queryFn: () => api<TaskPrompt[]>("/evaluation/task-prompts") });
  const releases = useQuery({ queryKey: ["research", "benchmark-releases"], queryFn: () => api<{ id: string; name: string; dataset_id: string }[]>("/evaluation/benchmark-releases") });
  const runs = useQuery({ queryKey: ["research", "benchmark-runs"], queryFn: () => api<RunSummary[]>("/evaluation/benchmark-runs"), refetchInterval: 3000 });
  const result = useQuery({ queryKey: ["research", "benchmark-result", runId], queryFn: () => api<BenchResult>("/evaluation/benchmark-runs/" + runId), enabled: !!runId, refetchInterval: 2000 });
  const replay = useQuery({ queryKey: ["research", "replay-detail", runId, replayOffset], queryFn: () => api<{ items: unknown[]; total: number; next_offset: number | null }>("/evaluation/benchmark-runs/" + runId + "/details?offset=" + replayOffset), enabled: result.data?.run.mode === "legacy_replay" });
  const historical = useQuery({ queryKey: ["research", "benchmark-historical", dataset], queryFn: () => api<{ id: string; name: string; role: string; summary: { rows: number } }[]>("/evaluation/benchmarks/" + dataset + "/history"), enabled: !!dataset });
  const rawHistory = useQuery({ queryKey: ["research", "benchmark-historical-raw", dataset, historyId, historyOffset], queryFn: () => api<{ items: unknown[]; total: number; next_offset: number | null }>("/evaluation/benchmarks/" + dataset + "/history/" + historyId + "?offset=" + historyOffset), enabled: !!dataset && !!historyId });
  const available = prompts.data?.filter(p => p.family === (track === "kie_image" ? "kie" : "vqa")) || [], prompt = available.find(p => p.id === promptId) || available[0];
  const promptCacheKey = draftKey(user?.id || "", dataset, "task-prompt:" + (prompt?.id || "none"));
  useEffect(() => {
    let active = true; setPromptReady(false);
    void readDraft(promptCacheKey).then(d => {
      if (!active) return;
      if (d) { setPromptText(String(d.content.markdown || "")); setPromptNote(String(d.content.note || "")); setPromptDirty(true); }
    }).catch(e => setError(String(e))).finally(() => { if (active) setPromptReady(true); });
    return () => { active = false; };
  }, [promptCacheKey]);
  useEffect(() => {
    if (!promptDirty || !promptReady) return;
    void writeDraft(promptCacheKey, { draft_id: promptCacheKey, base_version: prompt?.version || 0, content: { markdown: promptText, note: promptNote }, updated_at: new Date().toISOString() }).catch(e => setError(String(e)));
  }, [promptCacheKey, promptReady, promptDirty, promptText, promptNote, prompt?.version]);
  async function action(fn: () => Promise<unknown>) { setBusy(true); setError(""); try { await fn(); await client.invalidateQueries({ queryKey: ["research"] }); } catch (e) { setError(String(e)); } finally { setBusy(false); } }
  return <>
    <Card><h2>先回放旧结果，或选择任务试跑</h2><p>离线回放不调用模型。新试跑只使用下方勾选的任务，保存模型、Prompt、图片和评分规则快照。</p>
      <Button disabled={busy || !dataset} onClick={() => action(async () => { const r = await api<RunSummary>("/evaluation/benchmarks/" + dataset + "/replay", { idempotency_key: key() }); setRunId(r.id); setReplayOffset(0); })}>离线回放全部旧 IoU（无模型费用）</Button>
      <form className="research-form" onSubmit={e => { e.preventDefault(); if (!prompt) return; void action(async () => { const r = await api<RunSummary>("/evaluation/benchmark-runs", { dataset_id: dataset, name, task_ids: selected, track, mode, release_id: releaseId || null, model_id: model, prompt_id: prompt.id, method_id: method, method_protocol: lmadProtocol, method_variant: labVariant, method_attempts: methodAttempts, method_max_output_tokens: methodOutputTokens, max_calls: maxCalls, iou_threshold: .6, upstream_attempt_id: upstream || null, idempotency_key: key() }); setRunId(r.id); }); }}>
        <p>已勾选 {selected.length} 项任务。KIE 与 VQA 请分别创建运行；预测文本辅助 VQA 必须指定同图的有效 KIE 结果。</p>
        <label>答题方法<select value={method} onChange={e => setMethod(e.target.value)}><option value="E00">单次回答基线</option><option value="E01">ReAct：作者控制器与图像工具适配</option><option value="E05">Self-Refine：作者控制器适配</option><option value="E09">L-MAD：论文协议＋MALLM组件，二分类文本问答</option><option value="E14">CoA：论文算法重实现，KIE 预测文本问答</option><option value="E25">Legal Reasoning Paths：原提示图构建，检索待完成</option><option value="E24">GraphRAG：作者全局查询，冻结文本建图</option><option value="E18">JurisMA：论文推理算法，训练暂缓，KIE 文本问答</option><option value="E15">RAPTOR：作者摘要树与检索</option><option value="E16">LightRAG：作者实体关系图与双层检索</option><option value="E21">Reflexion：作者反思与记忆</option><option value="E23">LegalAgentBench：作者控制器，冻结文本工具</option></select></label>
        {method === "E01" && <><p>保留作者最多七轮交互与格式补问，最多十四次调用；可读取原图局部。实际调用次数逐步记录。</p><label>每次生成最多输出 token<Input type="number" min={100} max={10000} value={methodOutputTokens} onChange={e => setMethodOutputTokens(Number(e.target.value))} /></label></>}
        {dynamicMethod && <><p>使用已保存的 KIE 预测构建索引后回答全局问题。调用数取决于文本长度和索引结构，达到本次上限就停止并保留已有记录。</p><label>每次生成最多输出 token<Input type="number" min={100} max={10000} value={methodOutputTokens} onChange={e => setMethodOutputTokens(Number(e.target.value))} /></label></>}
        {method === "E21" && <><p>根据输出结构与坐标检查形成反思记忆，再次尝试；这些检查不判断内容或法律结论是否正确。</p><label>最多尝试次数<Input type="number" min={1} max={3} value={methodAttempts} onChange={e => setMethodAttempts(Number(e.target.value))} /></label><label>每次生成最多输出 token<Input type="number" min={100} max={10000} value={methodOutputTokens} onChange={e => setMethodOutputTokens(Number(e.target.value))} /></label></>}
        {method === "E05" && <><p>每轮包括生成或修订、反馈两个步骤；每一步保留相同原图。模型自评只用于方法迭代，不作为评测成绩。</p><label>生成轮数<Input type="number" min={1} max={3} value={methodAttempts} onChange={e => setMethodAttempts(Number(e.target.value))} /></label><label>每次生成最多输出 token<Input type="number" min={100} max={10000} value={methodOutputTokens} onChange={e => setMethodOutputTokens(Number(e.target.value))} /></label></>}
        <label>本次运行名称<Input required value={name} onChange={e => setName(e.target.value)} /></label>
        {method === "E23" && <label>LegalAgentBench 控制器<select value={labVariant} onChange={e => setLabVariant(e.target.value)}><option value="react">ReAct</option><option value="plan_and_solve">Plan-and-Solve</option><option value="plan_and_execute">Plan-and-Execute</option></select></label>}
        {method === "E09" && <label>L-MAD 决策协议<select value={lmadProtocol} onChange={e => setLmadProtocol(e.target.value)}><option value="hybrid">混合共识：初始一致，轮次上限时超多数</option><option value="ranked">排名投票：固定3轮，平局最多再讨论1轮</option></select></label>}
        <div className="research-grid-3"><SearchableSelect label={<>模型看什么</>} value={track} onChange={e => { if (promptDirty) { setError("请先保存当前 Prompt 修改，再切换输入轨道；草稿已保留。"); return; } setTrack(e.target.value); setPromptId(""); }}>{Object.entries(tracks).map(([v, label]) => <option key={v} value={v}>{label}</option>)}</SearchableSelect>
          <label>如何计分<select value={mode} onChange={e => setMode(e.target.value)}><option value="development_reference">开发参考（旧答案尚未复核）</option><option value="official_reviewed">人工发布版本</option></select></label>
          <SearchableSelect label={<>模型</>} value={model} onChange={e => setModel(e.target.value)}><option value="demo">离线演练，不计模型能力分</option>{models.data?.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</SearchableSelect>
          <label>本次最多调用次数<Input type="number" min={1} max={500} value={maxCalls} onChange={e => setMaxCalls(Number(e.target.value))} /></label>
          {mode === "official_reviewed" && <SearchableSelect label={<>人工发布版本</>} required value={releaseId} onChange={e => setReleaseId(e.target.value)}><option value="">选择已发布任务</option>{releases.data?.filter(r => r.dataset_id === dataset).map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</SearchableSelect>}
          {track === "vqa_predicted_text" && <label>上游 KIE 结果编号<Input required value={upstream} onChange={e => setUpstream(e.target.value)} /></label>}
        </div>
        <SearchableSelect label={<>答题 Prompt 版本</>} value={prompt?.id || ""} onChange={e => { if (promptDirty) { setError("请先保存当前 Prompt 修改再切换版本；草稿已保留。"); return; } setPromptId(e.target.value); setPromptDirty(false); }}><option value="" disabled>请先保存模板</option>{available.map(p => <option key={p.id} value={p.id}>{p.name} · v{p.version}</option>)}</SearchableSelect>
        {prompt && <details><summary>阅读和迭代答题 Prompt（Markdown）</summary><p>质量裁判规则在审核台维护；这里保存给答题模型的指令。</p><textarea aria-label="答题 Prompt Markdown" rows={8} value={promptDirty ? promptText : prompt.markdown} onChange={e => { setPromptDirty(true); setPromptText(e.target.value); }} /><label>本次 Prompt 修改原因<Input value={promptNote} onChange={e => setPromptNote(e.target.value)} /></label>
          <Button type="button" disabled={busy || !promptDirty || !promptNote.trim()} onClick={() => action(async () => { const p = await api<TaskPrompt>("/evaluation/task-prompts", { name: prompt.name, family: prompt.family, parent_id: prompt.id, markdown: promptText, note: promptNote, idempotency_key: key() }); await clearDraft(promptCacheKey); setPromptId(p.id); setPromptDirty(false); setPromptNote(""); })}>保存 Prompt 新版本</Button><a href={"/v1/evaluation/task-prompts/export?name=" + encodeURIComponent(prompt.name)}>下载 Markdown 迭代记录</a></details>}
        <div className="toolbar"><Button type="button" disabled={busy || selected.length !== 1} onClick={() => action(async () => setPreview(await api("/evaluation/benchmarks/" + dataset + "/input?" + new URLSearchParams({ task_id: selected[0], track, ...(upstream ? { upstream_attempt_id: upstream } : {}) }))))}>预览这道题实际输入</Button><Button disabled={busy || !selected.length || !prompt || requiredCalls > maxCalls || !methodTrackSupported}>开始所选任务</Button></div>
        <p role="status">当前方法{dynamicMethod ? "至少预留" : "最多需要"} {requiredCalls} 次调用，本次上限 {maxCalls} 次。{requiredCalls > maxCalls ? "请调整上限或减少任务。" : ""}{!methodTrackSupported ? "所选方法不支持当前轨道；L-MAD、CoA、RAPTOR、LightRAG 请使用已保存的 KIE 预测文本；L-MAD只接受二分类题。" : ""}</p>
        <p>单次回答的输出 token 上限和输入/输出单价从模型设置读取。未知金额、开放分析和身份歧义会明确标为待审核，不补成零分或法律正确分。</p>
      </form>{preview != null && <details open><summary>实际输入（不含目标答案和审核评论）</summary><JsonView value={preview} /></details>}<ErrorText error={error || prompts.error || runs.error || result.error || historical.error} />
    </Card>
    <Card><h2>KIE / VQA 运行与旧响应</h2>{<Paged items={runs.data?.filter(r => r.dataset_id === dataset)} label="KIE / VQA 运行记录" layout="block" resetKey={dataset}>{(pageItems) => pageItems.map(r => <div className="toolbar" key={r.id}><Button onClick={() => { setRunId(r.id); setReplayOffset(0); }}>{r.name} · {modes[r.mode]}</Button><Status value={r.status} /></div>)}</Paged>}
      <details><summary>历史导入记录（保留原始轮次与最终视图）</summary><p>这些是旧模型调用，费用和请求编号未记录，不代表本轮新执行。</p>{<Paged items={historical.data} label="历史导入记录" layout="block">{(pageItems) => pageItems.map(h => <div className="toolbar" key={h.id}><Button onClick={() => { setHistoryId(h.id); setHistoryOffset(0); }}>查看旧响应 · {h.summary.rows} 条 · {h.role === "derived_final_view" ? "最终汇总视图" : "原始记录"}</Button><small>{h.name}</small></div>)}</Paged>}{rawHistory.data && <><p>共 {rawHistory.data.total} 条，当前从 {historyOffset + 1} 条开始；原始错误和失败均保留。</p><JsonView value={rawHistory.data.items} /><div className="toolbar"><Button disabled={!historyOffset} onClick={() => setHistoryOffset(v => Math.max(0, v - 20))}>上一页旧响应</Button><Button disabled={rawHistory.data.next_offset == null} onClick={() => setHistoryOffset(rawHistory.data!.next_offset!)}>下一页旧响应</Button></div></>}<ErrorText error={rawHistory.error} /></details>
      {result.data && <><h3>{result.data.run.name} · {modes[result.data.run.mode]}</h3><p>答题方法：{result.data.run.method?.id === "E05" ? "Self-Refine 作者控制器适配" : result.data.run.method?.id === "E01" ? "ReAct 作者控制器适配" : result.data.run.method?.id === "E23" ? "LegalAgentBench 作者控制器＋冻结文本工具" : result.data.run.method?.id === "E09" ? "L-MAD 论文协议＋所引MALLM组件" : result.data.run.method?.id === "E14" ? "CoA 论文算法重实现（非作者代码）" : result.data.run.method?.id === "E25" ? "Legal Reasoning Paths 原提示图构建（嵌入检索未完成）" : result.data.run.method?.id === "E24" ? "GraphRAG 作者无嵌入索引与全局查询" : result.data.run.method?.id === "E18" ? "JurisMA 论文推理算法（训练暂缓）" : result.data.run.method?.id === "E15" ? "RAPTOR 作者摘要树与检索" : result.data.run.method?.id === "E16" ? "LightRAG 作者图检索" : result.data.run.method?.id === "E21" ? "Reflexion 作者反思记忆" : "单次回答 / 历史回放"}。执行状态：<Status value={result.data.run.status} />。开发参考分和人工发布成绩分开保存；重评不会重调模型。</p><div className="research-stat-cards benchmark-stats">{Object.entries(result.data.report).map(([k, n]) => <div key={k}><strong>{n}</strong>{({ call_reservations: "调用步骤已占用", model_calls: "实际模型调用", planned: "计划任务", attempted: "已尝试", returned: "已返回", valid: "结构有效", service_failed: "服务失败", unknown: "结果未知", cancelled: "未调用 / 取消", blocked_upstream: "上游阻塞", invalid_reference: "参考未确认", scorable: "可计分", awaiting_rubric: "等待量表评估", unscored: "未计分", abstained: "明确未知 / 弃答", format_failure: "输出格式错误", legacy_replayed: "旧 IoU 回放", pass_at_fixed_threshold: "旧 IoU ≥ 0.6" } as Record<string, string>)[k] || k}</div>)}</div>
        {result.data.run.parent_run_id && <p>本次显式重试来自运行：{result.data.run.parent_run_id}；原回答、输入和模型快照保留。</p>}
        <div className="toolbar">{["queued", "running"].includes(result.data.run.status) && result.data.run.job_id && <Button disabled={busy} onClick={() => action(() => api("/research/jobs/" + result.data!.run.job_id + "/cancel", {}))}>停止后续任务（已发出的请求仍需确认结果）</Button>}
          {result.data.attempts.some(a => ["failed", "unknown", "cancelled"].includes(a.status)) && <Button disabled={busy || ["queued", "running"].includes(result.data.run.status)} onClick={() => action(async () => { const next = await api<RunSummary>("/evaluation/benchmark-runs/" + runId + "/retry", { task_ids: [], idempotency_key: key() }); setRunId(next.id); })}>按失败范围新建重试（可能再次计费）</Button>}
          <a href={"/v1/evaluation/benchmark-runs/" + runId + "/export"}>导出本次完整结果</a><a href={"/evaluation.html?audit=1&object=" + runId}>查看运行审计</a>{result.data.run.mode !== "legacy_replay" && <Button disabled={busy} onClick={() => action(() => api("/evaluation/benchmark-runs/" + runId + "/rescore", { reason: "离线重新核对当前冻结规则", idempotency_key: key() }))}>离线重评旧回答</Button>}</div>
        {replay.data && <details><summary>逐区域旧 IoU 明细（{replay.data.total}）</summary><JsonView value={replay.data.items} /><div className="toolbar"><Button disabled={!replayOffset} onClick={() => setReplayOffset(v => Math.max(0, v - 30))}>上一页区域</Button><Button disabled={replay.data.next_offset == null} onClick={() => setReplayOffset(replay.data!.next_offset!)}>下一页区域</Button></div></details>}
        {<Paged items={result.data.attempts} label="逐项运行回答" layout="block">{(pageItems) => pageItems.map(a => <details key={a.id}><summary>{result.data!.run.tasks?.find(t => t.task_id === a.task_id)?.image_name || a.task_id} · {label(a.status)}</summary><p>结果编号：{a.id}</p>{a.response && <pre className="research-markdown">{a.response.raw}</pre>}{a.error != null && <JsonView value={a.error} />}{!!result.data!.method_steps?.some(s => s.attempt_id === a.id) && <details><summary>查看此方法逐步输入与返回</summary><p>反馈中的自评分不代表 KIE、VQA 或法律准确率。</p>{result.data!.method_steps!.filter(s => s.attempt_id === a.id).map(s => <details key={s.id}><summary>{s.stage} · {s.status}</summary><pre className="research-markdown">{s.response?.raw || "本步骤没有有效返回"}</pre><JsonView value={s.messages.map(m => ({ role: m.role, content: Array.isArray(m.content) ? m.content.map((p: { type: string; text?: string }) => p.type === "text" ? p : { type: p.type, image: "使用本题已冻结原图；完整数据保留在导出记录" }) : m.content }))} /></details>)}</details>}{<Paged items={result.data!.scores.filter(s => s.attempt_id === a.id)} label="回答评分版本" layout="block">{(pageItems) => pageItems.map(s => <div key={s.id}><p>{s.reference_status === "legacy_unverified" ? "旧参考，尚未复核" : "人工版本参考"} · {({ scored: "已评分", abstained: "模型明确回答未知", format_failure: "输出格式错误", invalid_reference: "参考尚未确认", rubric_review_required: "等待量表评估", identity_dictionary_required: "身份字典待确认", unscored_demo: "离线演练不计分", rubric_reviewed: "已按量表人工评估" } as Record<string, string>)[s.result.status] || s.result.status} · {s.result.score ?? "未计分"} · {s.reason}</p><JsonView value={s} /></div>)}</Paged>}<a href={"/review.html?section=benchmark&benchmark=" + dataset + "&benchmark_task=" + a.task_id}>核对来源图、目标与评论 →</a></details>)}</Paged>}
      </>}
    </Card>
  </>;
}

export function BenchmarkPanel({ review = false }: { review?: boolean }) {
  const client = useQueryClient(), initial = new URLSearchParams(location.search);
  const [datasetId, setDatasetId] = useState(initial.get("benchmark") || ""), [q, setQ] = useState(""), [search, setSearch] = useState(""), [family, setFamily] = useState(""), [imageFilter, setImageFilter] = useState(initial.get("image_name") || ""), [offsets, setOffsets] = useState([0]), [taskId, setTaskId] = useState(initial.get("benchmark_task") || ""), [selected, setSelected] = useState<string[]>([]), [selectedImages, setSelectedImages] = useState<string[]>([]), [dirty, setDirty] = useState(false), [notice, setNotice] = useState(""), [releaseName, setReleaseName] = useState(""), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const datasets = useQuery({ queryKey: ["research", "benchmarks"], queryFn: () => api<Dataset[]>("/evaluation/benchmarks") });
  const dataset = datasets.data?.find(d => d.id === datasetId) || datasets.data?.[0], id = dataset?.id || "";
  const [workspace, setWorkspace] = useState(initial.get("benchmark_workspace") || (initial.has("pipeline") ? "results" : "new")), [step, setStep] = useState(initial.get("benchmark_step") === "setup" ? "setup" : "samples");
  function switchWorkspace(next: string) { setWorkspace(next); const u = new URL(location.href); u.searchParams.set("benchmark_workspace", next); history.replaceState(null, "", u); }
  function switchStep(next: string) { setStep(next); const u = new URL(location.href); u.searchParams.set("benchmark_step", next); history.replaceState(null, "", u); }
  const query = new URLSearchParams({ q: search, family, image_name: review ? imageFilter : "", offset: String(offsets.at(-1)) });
  const tasks = useQuery({ queryKey: ["research", "benchmark-tasks", id, query.toString()], queryFn: () => api<{ items: TaskRow[]; total: number; next_offset: number | null }>("/evaluation/benchmarks/" + id + "/tasks?" + query), enabled: !!id });
  const workspaceRef = useRef<HTMLElement>(null);
  const detail = useQuery({ queryKey: ["research", "benchmark-task", id, taskId], queryFn: () => api<TaskDetail>("/review/benchmarks/" + id + "/tasks/" + taskId), enabled: !!id && !!taskId && review });
  useEffect(() => { if (review && taskId && workspaceRef.current) { workspaceRef.current.scrollIntoView({ block: "start" }); workspaceRef.current.focus({ preventScroll: true }); } }, [review, taskId, detail.data?.task.task_id]);
  function choose(t: TaskRow) { if (dirty) { setNotice("当前有未提交输入。请先保存审核和评论，再切换任务；草稿已在本地保留。"); return; } setTaskId(t.task_id); setNotice(""); const u = new URL(location.href); u.searchParams.set("benchmark", id); u.searchParams.set("benchmark_task", t.task_id); history.replaceState(null, "", u); }
  return <>
    {(review || workspace !== "results") && <Card><h2>{review ? "KIE / VQA 标注审核" : workspace === "results" ? "评测结果" : "样本完整流程评测"}</h2><p>{review ? "这里核对旧图片、区域和答案，保存修改过程与评论，再发布人工确认的任务。" : "先选图片，再选择模型并确认调用范围。运行结果单独查看；区域问答含参考定位辅助。"}</p>
      <details open={review || workspace !== "results" || undefined}><summary>数据来源</summary><SearchableSelect label={<>数据来源</>} value={id} onChange={e => { if (dirty) { setNotice("请先保存当前输入再切换数据集。"); return; } setDatasetId(e.target.value); setImageFilter(""); setTaskId(""); setSelected([]); setSelectedImages([]); setOffsets([0]); if (!review) { setWorkspace("new"); setStep("samples"); } const u = new URL(location.href); u.searchParams.set("benchmark", e.target.value); u.searchParams.delete("pipeline"); u.searchParams.delete("pipeline_node"); u.searchParams.delete("benchmark_task"); u.searchParams.set("benchmark_workspace", "new"); u.searchParams.set("benchmark_step", "samples"); history.replaceState(null, "", u); }}>{!dataset && <option value="">暂无已迁移数据</option>}{datasets.data?.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</SearchableSelect>
      <details open={review || undefined}><summary>数据集概况与参考说明</summary>{dataset && <><div className="research-stat-cards benchmark-stats"><div><strong>{dataset.counts.images}</strong>逻辑图片（{dataset.counts.candidate_images} 张待核对补图）</div><div><strong>{dataset.counts.kie}</strong>KIE 整图任务</div><div><strong>{dataset.counts.vqa}</strong>VQA 属性任务</div><div><strong>{dataset.counts.review_notes}</strong>保留的旧审核意见</div></div><p>旧标注导入时均未认证金标。身份映射、部分标签语义和开放分析量表仍需人工确认。</p><a href={review ? "/evaluation.html?benchmark=1" : "/review.html?section=benchmark"}>{review ? "前往评测与离线回放" : "前往标注审核与发布"} →</a></>}</details>
      </details><ErrorText error={datasets.error || tasks.error || detail.error} /><p role="status">{notice}</p>
    </Card>}
    {dataset && <>
      {review && taskId && <section ref={workspaceRef} tabIndex={-1} className="benchmark-workspace" aria-label="原图与答案核对工作区">
        <div className="toolbar"><strong>当前核对任务：{taskId}</strong><Button onClick={() => { if (dirty) { setNotice("请先保存当前审核和评论；草稿保留。"); return; } setTaskId(""); const u = new URL(location.href); u.searchParams.delete("benchmark_task"); history.replaceState(null,"",u); }}>返回任务列表</Button></div>
        {detail.isPending && <p role="status">正在加载原图与目标答案…</p>}
        {detail.error && <><ErrorText error={detail.error} /><Button onClick={() => detail.refetch()}>重试加载核对任务</Button></>}
        {detail.data && <BenchmarkEditor key={id + taskId} dataset={id} detail={detail.data} dirtyChange={setDirty} />}
      </section>}
      {!review && <>
        <div className="research-tabs" role="navigation" aria-label="样本评测工作区">{[["new", "新建评测"], ["results", "运行结果"], ["advanced", "单阶段调试"]].map(([value,text]) => <Button key={value} aria-current={workspace === value ? "page" : undefined} onClick={() => switchWorkspace(value)}>{text}</Button>)}</div>
        {workspace === "new" && <div className="pipeline-stepbar"><strong>{step === "samples" ? "1. 选择样本" : "2. 设置并确认范围"}</strong><span>选择样本 → 设置并预览 → 查看结果</span></div>}
        {workspace === "new" && step === "samples" && <><BenchmarkSamples key={id + ":samples"} dataset={id} selected={selectedImages} onChange={setSelectedImages} /><div className="pipeline-actionbar"><span>已选 {selectedImages.length} 个样本</span><Button disabled={!selectedImages.length} onClick={() => switchStep("setup")}>下一步：选择模型</Button></div></>}
        {workspace === "new" && step === "setup" && <div className="toolbar"><Button onClick={() => switchStep("samples")}>返回选择样本</Button><p>已选 {selectedImages.length} 个样本，下一步预览全部题目和调用上界。</p></div>}
        <PipelinePanel key={id + ":pipeline"} dataset={id} selected={[]} imageNames={selectedImages} view={workspace === "results" ? "results" : workspace === "new" && step === "setup" ? "new" : "hidden"} onCreated={() => switchWorkspace("results")} />
      </>}
      {(review || workspace === "advanced") && <details open><summary>{review ? "逐题标注与发布" : "高级：独立任务与单阶段调试"}</summary>
      <Card><h2>选择任务（共 {tasks.data?.total ?? "—"} 项）</h2>{review && imageFilter && <p>当前仅查看图片：{imageFilter} <Button onClick={() => { setImageFilter(""); setOffsets([0]); const u = new URL(location.href); u.searchParams.delete("image_name"); history.replaceState(null, "", u); }}>查看所有图片任务</Button></p>}<form className="toolbar" onSubmit={e => { e.preventDefault(); setSearch(q); setOffsets([0]); }}><label>搜索图片、字段或任务编号<Input value={q} onChange={e => setQ(e.target.value)} /></label><label>任务类型<select value={family} onChange={e => { setFamily(e.target.value); setOffsets([0]); }}><option value="">全部</option><option value="kie.extract">KIE 整图抽取</option><option value="vqa.categorical">VQA 分类</option><option value="vqa.identity">VQA 身份</option><option value="vqa.amount">VQA 金额</option><option value="vqa.open_text">VQA 开放分析</option><option value="vqa.filename">VQA 文件名</option></select></label><Button>查找任务</Button></form>
        <div className="research-table-wrap" tabIndex={0}><table aria-label="KIE VQA 任务列表"><thead><tr><th>选入运行 / 发布</th><th>图片与任务</th><th>参考状态</th><th>操作</th></tr></thead><tbody>{tasks.data?.items.map(t => <tr key={t.task_id}><td><Input type="checkbox" aria-label={"选择任务 " + t.task_id} checked={selected.includes(t.task_id)} onChange={e => setSelected(v => e.target.checked ? [...v, t.task_id] : v.filter(x => x !== t.task_id))} /></td><td>{t.image_name}<br />{fieldLabel(t.label)} · {t.task_family === "kie.extract" ? "整图抽取" : "字段问答"}</td><td>{t.review_version ? "审核 v" + t.review_version + " · " + ({ pass: "人工通过", draft: "修订待审", revise: "需修改" } as Record<string, string>)[t.reference_status] : "旧参考未复核"}<br />{t.asset_status === "candidate_identity_unverified" && "补图身份待确认"}</td><td>{review ? <Button onClick={() => choose(t)}>核对原图与答案</Button> : <a href={"/review.html?section=benchmark&benchmark=" + id + "&benchmark_task=" + t.task_id}>查看来源 →</a>}</td></tr>)}</tbody></table></div>
        <div className="toolbar"><Button disabled={offsets.length === 1} onClick={() => setOffsets(v => v.slice(0, -1))}>上一页任务</Button><Button disabled={tasks.data?.next_offset == null} onClick={() => setOffsets(v => [...v, tasks.data!.next_offset!])}>下一页任务</Button><Button onClick={() => setSelected([])}>清空已选（{selected.length}）</Button></div>
      </Card>
      {!review && <BenchmarkExecution key={id} dataset={id} selected={selected} />}</details>}
      {review ? <><Card><h2>发布所选人工审核任务</h2><p>每项都须完成当前版本的人工审核，核对图片身份和案件组。开发集与留出集分开发布。</p><label>发布名称<Input value={releaseName} onChange={e => setReleaseName(e.target.value)} /></label><Button disabled={busy || !selected.length || !releaseName.trim()} onClick={async () => { setBusy(true); setError(""); try { await api("/review/benchmark-releases", { dataset_id: id, name: releaseName, task_ids: selected, idempotency_key: key() }); await client.invalidateQueries({ queryKey: ["research"] }); setNotice("所选任务已发布，可在评测台选择人工发布版本。"); } catch (e) { setError(String(e)); } finally { setBusy(false); } }}>发布 {selected.length} 项任务</Button><ErrorText error={error} /></Card></> : null}
    </>}
  </>;
}

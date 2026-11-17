import { SearchableSelect } from "../../components/collections";
import { Paged } from "../../components/collections";
import { BenchmarkPanel } from "./BenchmarkPanel";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Input } from "../../components/ui";
import { useUser } from "../auth/AuthGate";
import { api, key, stamp, emptyContent, type Content, type Detail, type Sample, type Draft, type Manifest, type Render, type Release, type PageLayout } from "./client";
import { clearDraft, draftKey, readDraft, writeDraft, type LocalDraft } from "./drafts";
import { ErrorText, JsonView, JobsPanel, PromptEditor, Status } from "./shared";
import { ReviewCanvas, JudgmentDrawer, manifestLayout } from "./ReviewCanvas";
import { QualityPanel } from "./QualityPanel";

function ContentFields({ content, change }: { content: Content; change: (c: Content) => void }) {
  return <div className="research-form">
    <div className="research-grid-3">
      <label>标题<Input required value={content.title} onChange={e => change({ ...content, title: e.target.value })} /></label>
      <label>类别<Input required value={content.category} onChange={e => change({ ...content, category: e.target.value })} /></label>
      <label>标签（逗号分隔）<Input value={content.tags.join(", ")} onChange={e => change({ ...content, tags: e.target.value.split(",").map(s => s.trim()).filter(Boolean) })} /></label>
      <label>语言<Input value={content.language} onChange={e => change({ ...content, language: e.target.value })} /></label>
      <label>平台<Input value={content.platform} onChange={e => change({ ...content, platform: e.target.value })} /></label>
    </div>
    <details><summary>来源原文与引用（{content.source_text.length} 字）</summary>
      <label>来源原文<textarea rows={10} readOnly={content.kind === "original"} value={content.source_text} onChange={e => change({ ...content, source_text: e.target.value })} /></label>
      <JsonView value={content.source_refs} />
    </details>
    <h3>聊天 / 转录消息（{content.messages.length}）</h3>
    {<Paged items={content.messages} label="消息编辑列表" layout="block" pageSize={10} searchable={false}>{(pageItems, pageOffset) => pageItems.map((m, pageIndex) => { const index = pageIndex + pageOffset; return (<div className="research-item-editor" key={m.id}>
      <div className="toolbar"><strong>{m.id}</strong><label>说话人<Input value={m.speaker} onChange={e => change({ ...content, messages: content.messages.map((v, i) => i === index ? { ...v, speaker: e.target.value } : v) })} /></label>
        <label>时间（未知留空）<Input value={m.timestamp || ""} onChange={e => change({ ...content, messages: content.messages.map((v, i) => i === index ? { ...v, timestamp: e.target.value || null } : v) })} /></label>
        <Button type="button" onClick={() => change({ ...content, messages: content.messages.filter((_, i) => i !== index), questions: content.questions.map(q => ({ ...q, message_ids: q.message_ids.filter(id => id !== m.id), gold: false })) })}>删除消息</Button>
      </div>
      <label>消息文本<textarea required rows={3} value={m.text} onChange={e => change({ ...content, messages: content.messages.map((v, i) => i === index ? { ...v, text: e.target.value } : v) })} /></label>
      {!!m.source_refs.length && <details><summary>来源引用</summary><JsonView value={m.source_refs} /></details>}
    </div>); })}</Paged>}
    <Button type="button" onClick={() => change({ ...content, messages: [...content.messages, { id: "m." + key(), speaker: "unknown", text: "", timestamp: null, source_refs: [] }] })}>添加消息</Button>
    <h3>问题与候选答案（{content.questions.length}）</h3>
    {<Paged items={content.questions} label="题目编辑列表" layout="block" pageSize={10} searchable={false}>{(pageItems, pageOffset) => pageItems.map((q, pageIndex) => { const index = pageIndex + pageOffset; return (<div className="research-item-editor" key={q.id}>
      <div className="toolbar"><strong>{q.id}</strong><label>任务类型<Input value={q.task_type} onChange={e => change({ ...content, questions: content.questions.map((v, i) => i === index ? { ...v, task_type: e.target.value } : v) })} /></label><Button type="button" onClick={() => change({ ...content, questions: content.questions.filter((_, i) => i !== index) })}>删除题目</Button></div>
      <label>题目<textarea required rows={2} value={q.question} onChange={e => change({ ...content, questions: content.questions.map((v, i) => i === index ? { ...v, question: e.target.value } : v) })} /></label>
      <label>答案<textarea rows={2} value={q.answer || ""} onChange={e => change({ ...content, questions: content.questions.map((v, i) => i === index ? { ...v, answer: e.target.value || null, gold: false } : v) })} /></label>
      <label>引用消息 ID（逗号分隔）<Input value={q.message_ids.join(", ")} onChange={e => change({ ...content, questions: content.questions.map((v, i) => i === index ? { ...v, message_ids: e.target.value.split(",").map(s => s.trim()).filter(Boolean) } : v) })} /></label>
      <label className="research-check"><Input type="checkbox" checked={q.gold} disabled={!q.answer} onChange={e => change({ ...content, questions: content.questions.map((v, i) => i === index ? { ...v, gold: e.target.checked } : v) })} />申请作为评测标准答案（金标）；保存后还需人工核对图片、答案和证据</label>
    </div>); })}</Paged>}
    <Button type="button" onClick={() => change({ ...content, questions: [...content.questions, { id: "q." + key(), question: "", answer: null, gold: false, task_type: "qa", message_ids: [] }] })}>添加题目</Button>
  </div>;
}

function SampleEditor({ detail }: { detail: Detail }) {
  const client = useQueryClient();
  const user = useUser();
  const s = detail.sample;
  const [content, setContent] = useState<Content>(detail.revision.content);
  const [layout, setLayout] = useState<PageLayout[] | null>(null);
  const [layoutManifest, setLayoutManifest] = useState<string | null>(null);
  const [geometryChanged, setGeometryChanged] = useState(false);
  const [locked, setLocked] = useState(true);
  const [commentDrafts, setCommentDrafts] = useState<Record<string, string>>({});
  const hasComments = Object.values(commentDrafts).some(v => v.trim());
  const manifestId = detail.sample.published_manifest;
  const manifest = useQuery({ queryKey: ["research", "manifest", manifestId], queryFn: () => api<Manifest>("/review/manifests/" + manifestId), enabled: !!manifestId });
  const draftSave = useRef<Promise<unknown>>(Promise.resolve());
  const [render, setRender] = useState<Render>(detail.revision.render);
  const [note, setNote] = useState("");
  const [base, setBase] = useState(s.revision);
  const [dirty, setDirty] = useState(false);
  const [ready, setReady] = useState(false);
  const [draftState, setDraftState] = useState("正在检查草稿");
  const [serverState, setServerState] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [remoteConflict, setRemoteConflict] = useState<Draft | null>(null);
  const draftId = useRef<string>(key());
  const version = useRef(0);
  const dirtyRef = useRef(false);
  const editEpoch = useRef(0);
  const live = useRef({ content, note, render, layout, layoutManifest, geometryChanged, commentDrafts });
  live.current = { content, note, render, layout, layoutManifest, geometryChanged, commentDrafts };
  function touch() { editEpoch.current++; dirtyRef.current = true; }
  const localKey = draftKey(user?.id || "", s.dataset, s.id);
  useEffect(() => {
    let active = true;
    void (async () => {
      let local: LocalDraft | undefined;
      let remote: Draft | null = null;
      try { local = await readDraft(localKey); if (active) setDraftState(local ? "发现本地草稿" : "本地草稿缓存可用"); }
      catch (e) { if (active) setDraftState("本地缓存不可用：" + String(e)); }
      try { remote = await api<Draft | null>("/review/samples/" + s.id + "/draft"); }
      catch (e) { if (active) setServerState("服务器草稿读取失败：" + String(e)); }
      if (!active) return;
      version.current = remote?.version || 0;
      const pendingRemote = remote && remote.base_revision >= s.revision ? remote : null;
      const candidate = local && (!pendingRemote || local.updated_at > pendingRemote.updated_at) ? local : pendingRemote;
      if (candidate) {
        setContent(candidate.content.content); setNote(candidate.content.note); setRender(candidate.content.render);
        setBase(candidate.base_revision); draftId.current = candidate.draft_id; setDirty(candidate.content.text_dirty ?? true); dirtyRef.current = true;
        setLayout(candidate.content.layout || null); setLayoutManifest(candidate.content.layout_manifest_id || null); setGeometryChanged(candidate.content.coordinates_unlocked || false); setCommentDrafts(candidate.content.comment_drafts || {});
        setServerState("已恢复草稿；请核对后显式保存");
      }
      if (local && remote && local.draft_id !== remote.draft_id && JSON.stringify(local.content) !== JSON.stringify(remote.content) && remote.base_revision >= s.revision) setRemoteConflict(remote);
      setReady(true);
    })();
    return () => { active = false; };
  // Editor is keyed by sample ID, so a new server revision must not reset typing.
  }, [localKey, s.id]);
  useEffect(() => {
    if (!dirtyRef.current && ready) { setContent(detail.revision.content); setRender(detail.revision.render); setBase(s.revision); }
  }, [detail.revision, s.revision, ready]);
  useEffect(() => {
    if (!ready || (!dirty && !hasComments) || saving) return;
    const local: LocalDraft = { draft_id: draftId.current, base_revision: base, content: { content, note, render, layout: layout || undefined, layout_manifest_id: layoutManifest, coordinates_unlocked: geometryChanged, comment_drafts: commentDrafts, text_dirty: dirty }, updated_at: new Date().toISOString() };
    void writeDraft(localKey, local).then(() => setDraftState("本地草稿已缓存 · " + new Date().toLocaleTimeString()))
        .catch(e => setDraftState("本地缓存失败：" + String(e)));
    const serverTimer = setTimeout(() => {
      draftSave.current = draftSave.current.catch(() => undefined).then(() => api<Draft>("/review/samples/" + s.id + "/draft", { ...local, updated_at: undefined, expected_version: version.current }, "PUT"))
        .then(d => { version.current = d.version; setServerState("服务器草稿已保存 · v" + d.version); })
        .catch(e => setServerState("服务器草稿保存失败，保留本地内容：" + String(e)));
    }, 1000);
    return () => { clearTimeout(serverTimer); };
  }, [content, note, render, base, dirty, ready, localKey, s.id, layout, layoutManifest, geometryChanged, commentDrafts, hasComments, saving]);
  useEffect(() => {
    const protect = (e: BeforeUnloadEvent) => { if (dirtyRef.current) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", protect);
    return () => window.removeEventListener("beforeunload", protect);
  }, []);
  function change(next: Content) {
    // A text change invalidates the previous gold confirmation.
    const changedEvidence = JSON.stringify([next.messages, next.source_text, next.source_refs]) !== JSON.stringify([content.messages, content.source_text, content.source_refs]);
    next = { ...next, questions: next.questions.map(q => {
      const previous = content.questions.find(v => v.id === q.id);
      const changedQuestion = previous && JSON.stringify([q.question, q.answer, q.task_type, q.message_ids]) !== JSON.stringify([previous.question, previous.answer, previous.task_type, previous.message_ids]);
      return changedEvidence || changedQuestion ? { ...q, gold: false } : q;
    }) };
    touch(); setContent(next); setDirty(true);
  }
  useEffect(() => {
    if (manifest.data && !geometryChanged) {
      setLayout(manifest.data.revision !== s.revision && detail.revision.layout?.length ? detail.revision.layout : manifestLayout(manifest.data, content)); setLayoutManifest(manifest.data.id);
    }
    setLocked(true);
  }, [manifest.data?.id, s.revision]);
  useEffect(() => { dirtyRef.current = dirty || hasComments; }, [dirty, hasComments]);
  async function cleanDraft(epoch = editEpoch.current) {
    draftSave.current = draftSave.current.catch(() => undefined).then(async () => {
      if (epoch !== editEpoch.current) return;
      if (version.current) { await api("/review/samples/" + s.id + "/draft", { base_revision: base, expected_version: version.current, draft_id: draftId.current, content: {} }, "DELETE"); version.current = 0; }
    });
    await draftSave.current;
    if (epoch === editEpoch.current) await clearDraft(localKey);
  }
  function changeComment(target: string, value: string) {
    touch(); const next = { ...live.current.commentDrafts, [target]: value }; live.current.commentDrafts = next; setCommentDrafts(next);
    if (!dirty && !Object.values(next).some(v => v.trim())) void cleanDraft().catch(e => setServerState("评论已保存；草稿清理失败：" + String(e)));
  }
  async function save(noteOverride?: string) {
    if (base !== s.revision) { setError("请先对照当前版本并合并草稿后保存"); return false; }
    const submittedEpoch = editEpoch.current;
    setSaving(true); setError("");
    try {
      const result = await api<{ sample: Sample }>("/review/samples/" + s.id, { content, render, note: noteOverride || note || "人工保存审核修订", expected_revision: base, layout: geometryChanged ? layout : null, layout_manifest_id: layoutManifest, coordinates_unlocked: geometryChanged, idempotency_key: key() }, "PUT");
      const newer = editEpoch.current !== submittedEpoch;
      const pendingComments = Object.values(live.current.commentDrafts).some(v => v.trim());
      setBase(result.sample.revision); setDirty(newer); dirtyRef.current = newer || pendingComments; setLocked(true);
      if (!newer) { setNote(""); setGeometryChanged(false); setLayout(null); setLayoutManifest(null); }
      if (newer || pendingComments) {
        const v = live.current;
        await writeDraft(localKey, { draft_id: draftId.current, base_revision: result.sample.revision, content: { content: v.content, note: v.note, render: v.render, layout: v.layout || undefined, layout_manifest_id: v.layoutManifest, coordinates_unlocked: v.geometryChanged, comment_drafts: v.commentDrafts, text_dirty: newer }, updated_at: new Date().toISOString() });
        setDraftState("保存期间的新输入已保留为未提交草稿");
      } else { try { await cleanDraft(submittedEpoch); setDraftState("本地草稿已清除"); } catch (e) { setServerState("已保存服务器；草稿清理失败：" + String(e)); } }
      setServerState("文本已保存 r" + result.sample.revision + "；渲染已排队");
      await client.invalidateQueries({ queryKey: ["research"] });
      return editEpoch.current === submittedEpoch;
    } catch (e) { setError(String(e)); return false; } finally { setSaving(false); }
  }
  async function upgradeRenderer() {
    if (dirtyRef.current || base !== s.revision || remoteConflict || saving) return;
    const epoch = editEpoch.current;
    setSaving(true); setError("");
    try {
      const result = await api<{ sample: Sample }>("/review/samples/" + s.id + "/upgrade-renderer", { expected_revision: base, idempotency_key: key() });
      setBase(result.sample.revision);
      if (editEpoch.current === epoch && !dirtyRef.current) {
        try { await cleanDraft(epoch); } catch (e) { setDraftState("新版本已创建；草稿清理失败：" + String(e)); }
      }
      setServerState("新版排版已排队 r" + result.sample.revision + "；旧图保留，完成后需重新审核");
      await client.invalidateQueries({ queryKey: ["research"] });
    } catch (e) { setError(String(e)); } finally { setSaving(false); }
  }
  return <Card><div className="review-canvas-heading"><h2>图片审核 · 当前 r{s.revision}</h2><a href={"/review.html?audit=1&object=" + encodeURIComponent(s.id)}>操作历史</a><JudgmentDrawer sampleId={s.id} /></div>
    {!!content.original_assets.length && typeof content.metadata.source_manifest === "string" && <Button disabled={saving || dirty || hasComments || !ready} onClick={async () => { setSaving(true); setError(""); try { await api("/review/samples/" + s.id + "/restore-original", { expected_revision: s.revision, idempotency_key: key() }); await client.invalidateQueries({ queryKey: ["research"] }); } catch(e) { setError(String(e)); } finally { setSaving(false); } }}>接入导入原图及坐标为新版本</Button>}
    {(detail.revision.renderer_version || "pillow-chat.v3") === "pillow-chat.v3" && detail.binding && ["synthetic_render", "transcription_overlay"].includes(detail.binding.visual_role) && <div>
      <Button disabled={!ready || saving || dirty || hasComments || base !== s.revision || !!remoteConflict} onClick={() => { void upgradeRenderer(); }}>按新版排版生成新版本</Button>
      <p className="muted">文字不变，完整保留旧图、审核和发布记录；新图需重新审核。有草稿时请先处理草稿。</p>
    </div>}
    <p role="status">{draftState} · {serverState}</p>
    {base !== s.revision && <div className="research-conflict" role="alert">
      <p>草稿基于 r{base}，服务器已到 r{s.revision}。本地内容保留；请对照下方版本历史合并。</p>
      <Button onClick={() => { setBase(s.revision); setDirty(true); dirtyRef.current = true; }}>已对照并合并，使用 r{s.revision} 为保存基线</Button>
    </div>}
    {remoteConflict && <details open className="research-conflict"><summary>另一份服务器草稿已保留，请对照合并</summary><JsonView value={remoteConflict} /><Button onClick={() => setRemoteConflict(null)}>已对照，继续编辑本地内容</Button></details>}
    {!ready ? <p>正在恢复草稿…</p> : <div>
      <ReviewCanvas detail={detail} content={content} manifest={manifest.data} layout={layout || (manifest.data ? manifestLayout(manifest.data, content) : [])} locked={locked} setLocked={setLocked} change={change} changeLayout={value => { touch(); setLayout(value); setGeometryChanged(true); setDirty(true); dirtyRef.current = true; }} note={note} changeNote={value => { touch(); setNote(value); setDirty(true); }} save={save} saving={saving} saveError={error} ready={ready && base === s.revision} commentDrafts={commentDrafts} changeComment={changeComment} refresh={() => client.invalidateQueries({ queryKey: ["research"] })} />
      <ErrorText error={manifest.error} />
      <details><summary>样本字段、消息列表与题目</summary><ContentFields content={content} change={change} /></details>
      <details><summary>渲染设置</summary><div className="research-grid-3">{(["width", "page_height", "font_size"] as const).map(k => <label key={k}>{({ width: "图片宽度", page_height: "分页高度", font_size: "字号" })[k]}<Input type="number" value={render[k]} onChange={e => { touch(); setRender({ ...render, [k]: Number(e.target.value) }); setDirty(true); dirtyRef.current = true; }} /></label>)}</div></details>
      <label>本轮纠正说明 / 修改意见<textarea required rows={3} value={note} onChange={e => { touch(); setNote(e.target.value); setDirty(true); dirtyRef.current = true; }} /></label>
      <div className="toolbar"><Button variant="primary" type="button" onClick={() => { void save(); }} disabled={saving || !dirty || base !== s.revision || !!remoteConflict}>保存新版本并渲染</Button><span>{dirty ? "存在未提交修改" : "已与服务器版本同步"}</span></div>
    </div>}<ErrorText error={error} />
  </Card>;
}

export function ReviewDesk() {
  const client = useQueryClient();
  const [page, setPage] = useState(new URLSearchParams(location.search).get("section") === "benchmark" ? "benchmark" : new URLSearchParams(location.search).get("section") === "imports" ? "imports" : "samples");
  const [selected, setSelected] = useState(new URLSearchParams(location.search).get("sample") || "");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [dataset, setDataset] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [group, setGroup] = useState("");
  const [importResult, setImportResult] = useState<unknown>(null);
  const [releaseName, setReleaseName] = useState("");
  const [releaseIds, setReleaseIds] = useState<string[]>([]);
  const samples = useQuery({ queryKey: ["research", "samples"], queryFn: () => api<Sample[]>("/review/samples"), refetchInterval: 2500 });
  const releases = useQuery({ queryKey: ["research", "releases"], queryFn: () => api<Release[]>("/review/releases") });
  const catalog = useQuery({ queryKey: ["research", "catalog"], queryFn: () => api<{ id: string; name: string; count: number }[]>("/review/catalog") });
  const detail = useQuery({ queryKey: ["research", "sample", selected], queryFn: () => api<Detail>("/review/samples/" + selected), enabled: !!selected, refetchInterval: 2500 });
  const rows = samples.data || [];
  const filtered = rows.filter(s => (!category || s.category === category) && (!dataset || s.dataset === dataset) && (!status || s.status === status) && [s.title, s.id, s.tags.join(" "), s.category].join(" ").toLowerCase().includes(search.toLowerCase()));
  const refresh = () => client.invalidateQueries({ queryKey: ["research"] });
  async function action(fn: () => Promise<unknown>) {
    setError(""); setBusy(true);
    try { await fn(); await refresh(); } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  function choose(id: string) { setSelected(id); const u = new URL(location.href); u.searchParams.set("sample", id); history.replaceState(null, "", u); }
  return <>
    <div className="research-tabs">{[["benchmark", "KIE / VQA 标注"], ["samples", "样本审核"], ["prompts", "评估规则与修改历史"], ["imports", "导入与发布"]].map(([id, name]) => <Button key={id} aria-current={page === id ? "page" : undefined} onClick={() => setPage(id)}>{name}</Button>)}</div>
    <ErrorText error={error || samples.error} />
    {page === "benchmark" ? <BenchmarkPanel review /> : page === "prompts" ? <PromptEditor purpose="review" /> : page === "imports" ? <>
      <Card><h2>接入历史研究数据</h2><p>导入保留原文、历史候选、题目、来源和原图；不会把历史模型意见认证为人工金标。重复导入复用已有记录。</p>
        <SearchableSelect label={<>来源批次</>} value={group} onChange={e => setGroup(e.target.value)}><option value="">选择 V2 / V3 批次</option>{catalog.data?.map(g => <option key={g.id} value={g.id}>{g.name} · {g.count} 条候选/变体</option>)}</SearchableSelect>
        <Button disabled={busy || !group} onClick={() => action(async () => setImportResult(await api("/review/import", { group_id: group })))}>导入所选批次</Button><ErrorText error={catalog.error} />{importResult != null && <JsonView value={importResult} />}
        <label>导入标准样本 JSON（Content 或 SampleCreate）<Input type="file" accept=".json" disabled={busy} onChange={e => { const file = e.target.files?.[0]; if (file) void action(async () => { const value = JSON.parse(await file.text()); const created = await api<{ sample: Sample }>("/review/samples", { dataset: value.dataset || "manual-import", content: value.content || value, note: "标准样本导入", idempotency_key: key() }); choose(created.sample.id); setPage("samples"); }); e.target.value = ""; }} /></label>
        <label>导入真实原图（保留原貌，转录另存派生图）<Input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} onChange={e => { const file = e.target.files?.[0]; if (file) void action(async () => {
          const body = new FormData(); body.append("file", file); const response = await fetch("/v1/review/assets", { method: "POST", body }); if (!response.ok) throw new Error((await response.json()).detail);
          const asset = await response.json(); const content = { ...emptyContent(), title: file.name, kind: "original", messages: [], questions: [], original_assets: [asset] };
          const created = await api<{ sample: Sample }>("/review/samples", { dataset: "original-upload", content, note: "导入真实原图，等待转录审核", idempotency_key: key() }); choose(created.sample.id); setPage("samples");
        }); e.target.value = ""; }} /></label>
        <Button disabled={busy} onClick={() => action(async () => { const created = await api<{ sample: Sample }>("/review/samples", { dataset: "manual", content: emptyContent(), note: "创建待审核候选", idempotency_key: key() }); choose(created.sample.id); setPage("samples"); })}>新建空白候选</Button>
      </Card>
      <Card><h2>发布已审核的评测集</h2><p>发布会保留一份固定样本，供评测台使用。只有当前文字和图片都经人工确认通过的样本才能加入；之后修改样本不会改变已发布的这一份。</p>
        <form className="research-form" onSubmit={e => { e.preventDefault(); void action(async () => { await api("/review/releases", { name: releaseName, sample_ids: releaseIds, idempotency_key: key() }); setReleaseName(""); setReleaseIds([]); }); }}>
          <label>发布名称<Input required value={releaseName} onChange={e => setReleaseName(e.target.value)} /></label>
          <div className="research-scroll-list">{<Paged items={rows.filter(s => s.status === "approved")} label="可发布的已审样本" layout="block">{(pageItems) => pageItems.map(s => <label className="research-check" key={s.id}><Input type="checkbox" checked={releaseIds.includes(s.id)} onChange={e => setReleaseIds(e.target.checked ? [...releaseIds, s.id] : releaseIds.filter(id => id !== s.id))} />{s.title} · r{s.revision}</label>)}</Paged>}</div>
          <Button disabled={busy || !releaseIds.length}>发布 {releaseIds.length} 条已审核样本</Button>
        </form>
        {<Paged items={releases.data} label="已发布版本" layout="block">{(pageItems) => pageItems.map(r => <details key={r.id}><summary>{r.name} · {r.entries.length} 条 · {stamp(r.created_at)}</summary><p>{r.id} · SHA256 {r.sha256} · {r.contract === "research.v2" ? "已绑定审核与图片" : "历史未绑定版本，需重新复核后新发布"}</p><a href={"/review.html?audit=1&object=" + encodeURIComponent(r.id)}>发布操作历史</a><JsonView value={r.entries.map(e => ({ sample_id: e.sample_id, revision: e.revision.number, binding: e.binding, quality_id: e.quality_id }))} /></details>)}</Paged>}<ErrorText error={releases.error} />
      </Card>
    </> : <>
      <Card><h2>选择一条样本开始审核</h2><div className="research-stat-cards" aria-label="样本审核进度"><div><strong>{rows.filter(s => s.status === "needs_review").length}</strong>等待人工审核</div><div><strong>{rows.filter(s => s.status === "needs_revision").length}</strong>已要求修改</div><div><strong>{rows.filter(s => s.status === "approved").length}</strong>人工已通过</div></div><p>先看截图和判决书，再决定修改文字、留下评论，或记录审核结论。</p>{!selected && rows.some(s => ["needs_revision","needs_review"].includes(s.status)) && <Button className="research-primary-action" onClick={() => choose(rows.find(s => s.status === "needs_revision")?.id || rows.find(s => s.status === "needs_review")!.id)}>从一条待审样本开始</Button>}<div className="research-grid-3"><label>搜索标题、标签、ID<Input type="search" value={search} onChange={e => setSearch(e.target.value)} /></label>
        <SearchableSelect label={<>类别</>} value={category} onChange={e => setCategory(e.target.value)}><option value="">全部类别</option>{[...new Set(rows.map(s => s.category))].map(c => <option key={c}>{c}</option>)}</SearchableSelect>
        <SearchableSelect label={<>数据版本 / 批次</>} value={dataset} onChange={e => setDataset(e.target.value)}><option value="">全部数据集</option>{[...new Set(rows.map(s => s.dataset))].map(c => <option key={c}>{c}</option>)}</SearchableSelect>
        <SearchableSelect label={<>审核状态</>} value={status} onChange={e => setStatus(e.target.value)}><option value="">全部状态</option>{[...new Set(rows.map(s => s.status))].map(c => <option key={c} value={c}>{({ needs_review: "待审核", needs_revision: "需纠正", approved: "人工通过", rejected: "拒绝" } as Record<string, string>)[c] || c}</option>)}</SearchableSelect></div>
        <p>共 {rows.length} 条 · 当前 {filtered.length} 条 · {new Set(rows.map(s => s.category)).size} 类 · {new Set(rows.map(s => s.dataset)).size} 个数据版本</p>
      </Card>
      <div className="research-review-layout"><aside className="research-sample-list" aria-label="样本列表">
        {!filtered.length && <p>暂无样本，请从“导入与发布”创建或导入。</p>}
        {<Paged items={filtered} label="样本列表" layout="block" resetKey={[search, category, dataset, status, selected].join('|')} anchorIndex={filtered.findIndex(s => s.id === selected)} searchable={false}>{(pageItems, pageOffset) => pageItems.map((s, pageIndex) => { const i = pageIndex + pageOffset; return (<Button key={s.id} aria-current={selected === s.id ? "true" : undefined} onClick={() => choose(s.id)}><span>{i + 1}. {s.title}</span><small>第 {s.revision} 版 · <Status value={s.status} /></small></Button>); })}</Paged>}
      </aside><div className="research-detail">
        {selected && <div className="toolbar"><Button disabled={filtered.findIndex(s => s.id === selected) <= 0} onClick={() => choose(filtered[filtered.findIndex(s => s.id === selected) - 1].id)}>上一条</Button><Button disabled={filtered.findIndex(s => s.id === selected) < 0 || filtered.findIndex(s => s.id === selected) >= filtered.length - 1} onClick={() => choose(filtered[filtered.findIndex(s => s.id === selected) + 1].id)}>下一条</Button></div>}
        {detail.isFetching && !detail.data && <p>正在加载样本…</p>}<ErrorText error={detail.error} />
        {detail.data && <>
          <section className="research-orientation" aria-label="审核步骤"><strong>按这三步完成本条审核</strong><ol className="research-steps"><li><a href="#review-image">核对截图和原文</a></li><li>改错处或留下评论</li><li><a href="#review-decision">保存人工审核结论</a></li></ol><p>只想提意见时，可以只保存评论，不需要修改消息。坐标框默认锁定。</p></section><div id="review-image"><SampleEditor key={selected} detail={detail.data} /></div>
          <div id="review-decision"><QualityPanel key={selected + ":" + detail.data.sample.revision} detail={detail.data} /></div>
          <Card><h2>版本与修改历史</h2>{<Paged items={detail.data.revisions} label="样本版本历史" layout="block">{(pageItems) => pageItems.map(r => <details key={r.id}><summary>r{r.number} · {r.note} · {stamp(r.created_at)}</summary><p>{r.editor} · {r.content_hash}</p><JsonView value={{ diff: r.diff, layout: r.layout, content: r.content }} /></details>)}</Paged>}</Card>
          <JobsPanel jobs={detail.data.jobs} refresh={refresh} />
        </>}
      </div></div>
    </>}
  </>;
}

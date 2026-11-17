import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui";
import { api } from "./client";
import { ErrorText } from "./shared";

type Dataset = "A" | "B";
type Verdict = "correct" | "wrong_speaker" | "wrong_text" | "wrong_time" | "extra" | "uncertain" | "wrong_fields";
type Origin = "verbatim_quote" | "judgment_paraphrase" | "synthetic_completion" | "unsupported";
type Basis = "source" | "simulated" | "unknown";
interface Message { id: string; speaker: string; text: string; time: string | null; side: string; side_inferred: boolean; fields: Record<string, string> }
interface Review { message_id: string; verdict: Verdict; corrected_speaker: string | null; corrected_text: string | null; corrected_time: string | null; note: string; field_patch: Record<string, unknown>; origin_type: Origin | null; source_quote: string; time_basis: Basis | null; speaker_basis: Basis | null }
interface Added { id: string; after_message_id: string | null; speaker: string; text: string; time: string | null; fields: Record<string, unknown>; origin_type: Exclude<Origin, "unsupported"> | null; source_quote: string }
interface Whole { verdict: string; comment: string; regen_instruction: string; added_messages: Added[] }
interface Item { id: string; dataset: Dataset; messages: Message[]; speakers: string[]; judgment_excerpt: string; annotation_level: string; asset: { width: number; height: number } }
interface Scope { source_id: string; source_title?: string; source_records?: number; generated_versions?: number; judgment_texts?: number; versions_without_source_text?: number; dataset: Dataset; items: number; messages: number; annotation_level: string; reason: string; fingerprint: string; excluded: { source: string; reason: string }[] }
interface Panel { dataset: Dataset; version: number; updated_at: string | null; locked_at: string | null; items: Item[]; message_reviews: Record<string, Record<string, Review>>; item_reviews: Record<string, Whole>; scope: Scope | null; counts: { items: number; items_reviewed: number; messages: number; messages_reviewed: number } }
interface Source { id: string; dataset: Dataset; title: string; eligible: boolean; reason: string; path?: string }
interface Backup { version: number; export_sha256: string; [key: string]: unknown }
const msgLabels: Record<Verdict, string> = { correct: "内容对", wrong_speaker: "说话人错", wrong_text: "文字错", wrong_time: "时间错", extra: "多余一条", uncertain: "看不清 · 存疑", wrong_fields: "多模态字段错" };
const wholeLabels: Record<string, string> = { pass: "通过", needs_fix: "需改", unreadable: "无法辨认", discard: "废弃", regen: "需重生成" };
const originLabels: Record<Origin, string> = { verbatim_quote: "原文逐字引文", judgment_paraphrase: "原文事实转述", synthetic_completion: "合理模拟措辞", unsupported: "无依据的新增事实" };
const base = (d: Dataset) => "/review/screenshot-panels/" + d;
const time = (s: string | null) => s ? new Date(s).toLocaleString("zh-CN", { timeZone: "Asia/Singapore", hour12: false }) : "尚未保存";
const blank = (m: Message): Review => ({ message_id: m.id, verdict: "correct", corrected_speaker: null, corrected_text: null, corrected_time: null, note: "", field_patch: {}, origin_type: null, source_quote: "", time_basis: null, speaker_basis: null });

function Chips<T extends string>({ values, labels, selected, onChange, disabled, label }: { values: T[]; labels: Record<T, string>; selected?: T; onChange: (v: T) => void; disabled?: boolean; label: string }) {
  return <div className="screenshot-chips" role="group" aria-label={label}>{values.map(v => <Button key={v} disabled={disabled} aria-pressed={v === selected} className={"screenshot-chip screenshot-chip--" + v} onClick={() => onChange(v)}>{labels[v]}</Button>)}</div>;
}

function ScopeSummary({ scope }: { scope: Scope }) {
  if (scope.dataset !== "B") return null;
  return <div className="screenshot-scope-summary" role="note"><p>当前批次：{scope.source_title || scope.source_id.replace("repo:datasets/", "")}</p>
    {scope.generated_versions !== undefined && <dl className="screenshot-scope-counts"><div><dt>判决原文</dt><dd>{scope.judgment_texts} 份</dd></div><div><dt>生成版本</dt><dd>{scope.generated_versions} 个</dd></div><div><dt>截图页数</dt><dd>{scope.items} 张</dd></div><div><dt>消息条数</dt><dd>{scope.messages} 条</dd></div></dl>}
    {scope.source_id === "studio" && <p>此来源仅包含当前账号研究库里已导入或生成的样本。其他历史截图批次需在来源列表单独选择。</p>}
    <p>判决原文按完整文本去重；一个判决可以对应多个生成版本，每个版本可以有多张截图。这里显示的是当前批次。</p>
    {!!scope.versions_without_source_text && <p>{scope.versions_without_source_text} 个版本缺少完整来源原文，未计入判决原文数。</p>}
  </div>;
}

function SourceSetup({ dataset, state, onSaved }: { dataset: Dataset; state: Panel; onSaved: (p: Panel) => void }) {
  const sources = useQuery({ queryKey: ["screenshot-sources"], queryFn: () => api<Source[]>("/review/screenshot-sources") });
  const [sourceId, setSourceId] = useState("");
  const [scope, setScope] = useState<Scope | null>(null);
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const options = (sources.data || []).filter(s => s.dataset === dataset);
  return <section className="card screenshot-setup"><p className="eyebrow">先确定本批范围</p><h2>{dataset === "A" ? "核对旧标注的来源" : "选择待审核的合成截图"}</h2>
    <p>{dataset === "A" ? "ScreenshotLegalBench 包含自动粗标训练数据、人工核对评估数据及 VQA 子集。本批按实际 JSON 和图片确定，不默认全部为人工精标。" : "B 全部标为合成数据。审核确认的是原文约束和模拟质量，不能将模拟对话认定为真实司法证据。"}</p>
    {dataset === "B" && <p>每次建立一个来源批次的审核清单。其他 V2/V3 版本可在<a href="/review.html?view=library">完整数据审核工作区</a>查看。</p>}
    <details><summary>查看来源与标注等级清单（{options.length} 项）</summary>{options.map(s => <article className="screenshot-source" key={s.id}><strong>{s.title}</strong><p>{s.reason}</p>{s.path && <code>{s.path}</code>}</article>)}</details>
    <label>本批来源<select value={sourceId} disabled={busy} onChange={e => { setSourceId(e.target.value); setScope(null); setAck(false); }}><option value="">选择来源</option>{options.filter(s => s.eligible).map(s => <option key={s.id} value={s.id}>{s.title}</option>)}</select></label>
    <Button disabled={!sourceId || busy} onClick={async () => { setBusy(true); setError(""); try { setScope(await api<Scope>("/review/screenshot-prepare", { source_id: sourceId })); } catch (e) { setError(String(e)); } finally { setBusy(false); } }}>{busy ? "正在核对…" : "预检图片、JSON 与消息映射"}</Button>
    {scope && <div className="screenshot-scope"><h3>可纳入 {scope.items} 张截图</h3>{dataset === "A" && <p>消息条数：{scope.messages} 条</p>}<ScopeSummary scope={scope} /><p>{scope.reason}</p><p>异常 {scope.excluded.length} 项。固定顺序与中性编号将在建立清单后保留。</p>
      {!!scope.excluded.length && <><details><summary>逐项查看未纳入原因</summary><ul>{scope.excluded.map((e, i) => <li key={i}><code>{e.source}</code><p>{e.reason}</p></li>)}</ul></details><label className="research-check"><input type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} />已核对异常清单，本批仅审核上述可用截图</label></>}
      <Button variant="primary" disabled={busy || !scope.items || (!!scope.excluded.length && !ack)} onClick={async () => { setBusy(true); setError(""); try { onSaved(await api<Panel>("/review/screenshot-initialize", { source_id: sourceId, fingerprint: scope.fingerprint, expected_version: state.version, acknowledge_exclusions: ack })); } catch (e) { setError(String(e)); } finally { setBusy(false); } }}>建立本批审核清单</Button>
    </div>}<ErrorText error={error || sources.error} />
  </section>;
}

function MessageEditor({ item, message, index, saved, locked, busy, save, dirty, navigate }: { item: Item; message: Message; index: number; saved?: Review; locked: boolean; busy: boolean; save: (r: Review | null) => Promise<void>; dirty: (v: boolean) => void; navigate: (index: number) => void }) {
  const [review, setReview] = useState<Review>(saved || blank(message));
  const [chosen, setChosen] = useState<Verdict | undefined>(saved?.verdict);
  const [patch, setPatch] = useState(JSON.stringify(saved?.field_patch || {}, null, 2));
  const [original, setOriginal] = useState<unknown>();
  const [error, setError] = useState("");
  const update = (r: Partial<Review>) => { setReview(v => ({ ...v, ...r })); dirty(true); };
  const choose = (v: Verdict) => {
    const next = { ...review, verdict: v, corrected_speaker: v === "wrong_speaker" ? message.speaker : null, corrected_text: v === "wrong_text" ? message.text : null, corrected_time: v === "wrong_time" ? message.time || "" : null, field_patch: {} };
    setChosen(v); setReview(next); setPatch("{}"); dirty(true);
    if (v === "correct" && item.dataset === "A") void save(next);
  };
  const requiredValue = review.verdict === "wrong_text" ? review.corrected_text?.trim() : review.verdict === "wrong_time" ? review.corrected_time?.trim() : review.verdict === "wrong_speaker" ? review.corrected_speaker : true;
  const valid = !!chosen && !!requiredValue && (review.verdict === "correct" || !!review.note.trim()) && (item.dataset === "A" || (!!review.origin_type && !!review.time_basis && !!review.speaker_basis));
  return <section className="card screenshot-current" id="current-message"><p className="eyebrow">当前消息 · 第 {index + 1} 条</p><h2>{message.speaker} <small>（{message.side === "left" ? "左" : "右"}） · {message.time || "时间未知"}</small></h2>
    <blockquote>{message.text || "非文本消息，请核对原图及多模态字段"}</blockquote>
    {message.side_inferred && <p className="screenshot-hint">原标注未给出左右方向；气泡位置仅为显示补值，不写入原始数据。</p>}
    <Chips values={(Object.keys(msgLabels) as Verdict[]).filter(v => v !== "wrong_fields")} labels={msgLabels} selected={chosen} onChange={choose} disabled={locked || busy} label="当前消息判项" />
    <fieldset disabled={locked || busy} className="screenshot-fields"><legend>审核内容</legend>
      {item.dataset === "B" && <div className="screenshot-basis">
        <label>内容依据<select aria-label="内容依据" value={review.origin_type || ""} onChange={e => update({ origin_type: e.target.value as Origin })}><option value="">请选择，不能默认真实</option>{(Object.keys(originLabels) as Origin[]).map(k => <option key={k} value={k}>{originLabels[k]}</option>)}</select></label>
        <div className="screenshot-two">{(["speaker_basis", "time_basis"] as const).map(k => <label key={k}>{k === "time_basis" ? "具体时间依据" : "说话人依据"}<select aria-label={k === "time_basis" ? "具体时间依据" : "说话人依据"} value={review[k] || ""} onChange={e => update({ [k]: e.target.value as Basis })}><option value="">请选择</option><option value="source">判决书提供</option><option value="simulated">合理模拟</option><option value="unknown">未知 / 未提供</option></select></label>)}</div>
        <label>支持引文（原文支持时必填）<textarea rows={2} value={review.source_quote} onChange={e => update({ source_quote: e.target.value })} placeholder="粘贴下方判决书摘录中的实际原文" /></label>
      </div>}
      {chosen === "wrong_speaker" && <label>改后说话人<select value={review.corrected_speaker || ""} onChange={e => update({ corrected_speaker: e.target.value })}>{item.speakers.map(s => <option key={s}>{s}</option>)}</select></label>}
      {chosen === "wrong_text" && <label>改后文字<textarea rows={3} value={review.corrected_text || ""} onChange={e => update({ corrected_text: e.target.value })} /></label>}
      {chosen === "wrong_time" && <label>改后时间<input value={review.corrected_time || ""} onChange={e => update({ corrected_time: e.target.value })} /></label>}
      <label>批注{chosen && chosen !== "correct" ? "（必填）" : "（选填）"}<textarea rows={2} value={review.note} onChange={e => update({ note: e.target.value })} placeholder={chosen === "extra" ? "多余原因：截图里没有这条，因为…" : "指出原话、错误原因与应如何处理；看不清时不要猜。"} /></label>
      <details><summary>原始 JSON 与多模态字段修正</summary><p>原值完整保留。附加字段补丁与原对象递归合并，未改字段不会丢失。</p>
        <Button onClick={async () => { try { setOriginal(await api(base(item.dataset) + "/items/" + item.id + "/original")); } catch (e) { setError(String(e)); } }}>查看原始完整 JSON</Button>{original !== undefined && <pre>{JSON.stringify(original, null, 2)}</pre>}
        <Button aria-pressed={chosen === "wrong_fields"} onClick={() => choose("wrong_fields")}>多模态字段错</Button><label>当前消息的附加字段补丁（JSON 对象）<textarea rows={5} value={patch} onChange={e => { setPatch(e.target.value); dirty(true); }} /></label>
      </details>
      <Button variant="primary" disabled={!valid} onClick={async () => { setError(""); try { const fields: unknown = JSON.parse(patch); if (!fields || Array.isArray(fields) || typeof fields !== "object") throw new Error("补丁必须是 JSON 对象"); await save({ ...review, field_patch: fields as Record<string, unknown> }); } catch (e) { setError(String(e)); } }}>保存这条</Button>
      {chosen && chosen !== "correct" && !review.note.trim() && <p className="screenshot-hint">判错或存疑要写一句为什么。</p>}
      {saved && <Button onClick={() => void save(null)}>清除此条审核</Button>}
    </fieldset><ErrorText error={error} />
    <div className="screenshot-current-bar"><div className="screenshot-bar-heading"><span>当前 {index + 1}/{item.messages.length} · {message.speaker}</span><Button aria-label="快捷上一条" disabled={busy || index === 0} onClick={() => navigate(index - 1)}>‹</Button><Button aria-label="快捷下一条" disabled={busy || index === item.messages.length - 1} onClick={() => navigate(index + 1)}>›</Button></div><Chips values={["correct", "wrong_speaker", "wrong_text"]} labels={msgLabels} selected={chosen} onChange={choose} disabled={locked || busy} label="快捷消息判项" /></div>
  </section>;
}

function WholeEditor({ item, saved, busy, locked, save, dirty }: { item: Item; saved?: Whole; busy: boolean; locked: boolean; save: (r: Whole) => Promise<void>; dirty: (v: boolean) => void }) {
  const [review, setReview] = useState<Whole>(saved || { verdict: "", comment: "", regen_instruction: "", added_messages: [] });
  const [error, setError] = useState("");
  const update = (r: Partial<Whole>) => { setReview(v => ({ ...v, ...r })); dirty(true); };
  const labels = { ...wholeLabels, pass: item.dataset === "B" ? "合成审核通过" : "通过" };
  return <section className="card"><h2>整图审核</h2><fieldset disabled={busy || locked} className="screenshot-fields"><legend className="sr-only">整图判项与批注</legend>
    <Chips values={item.dataset === "A" ? ["pass", "needs_fix", "unreadable", "discard"] : ["pass", "regen", "discard"]} labels={labels} selected={review.verdict} onChange={verdict => update({ verdict })} label="整图判项" />
    <label>整图批注<textarea rows={3} value={review.comment} onChange={e => update({ comment: e.target.value })} placeholder="说明整图问题；名单外说话人或缺失内容请在此说明。" /></label>
    <details open={!!review.added_messages.length}><summary>补充缺失消息（{review.added_messages.length} 条）</summary>
      {review.added_messages.map((a, i) => { const change = (v: Partial<Added>) => update({ added_messages: review.added_messages.map((x, j) => j === i ? { ...x, ...v } : x) }); return <div className="screenshot-added" key={a.id}>
        <label>插入位置<select value={a.after_message_id || ""} onChange={e => change({ after_message_id: e.target.value || null })}><option value="">末尾</option>{item.messages.map((m, j) => <option key={m.id} value={m.id}>第 {j + 1} 条之后</option>)}</select></label>
        <label>说话人<select value={a.speaker} onChange={e => change({ speaker: e.target.value })}>{item.speakers.map(s => <option key={s}>{s}</option>)}</select></label>
        <label>缺失文字<textarea value={a.text} onChange={e => change({ text: e.target.value })} /></label><label>时间（未知留空）<input value={a.time || ""} onChange={e => change({ time: e.target.value || null })} /></label>
        {item.dataset === "B" && <><label>新增内容依据<select value={a.origin_type || ""} onChange={e => change({ origin_type: e.target.value as Added["origin_type"] })}><option value="">请选择</option>{(Object.keys(originLabels) as Origin[]).filter(k => k !== "unsupported").map(k => <option key={k} value={k}>{originLabels[k]}</option>)}</select></label><label>支持引文<textarea value={a.source_quote} onChange={e => change({ source_quote: e.target.value })} /></label></>}
        <Button onClick={() => update({ added_messages: review.added_messages.filter((_, j) => j !== i) })}>移除此补充</Button>
      </div>; })}
      <Button onClick={() => update({ added_messages: [...review.added_messages, { id: "added-" + crypto.randomUUID(), after_message_id: null, speaker: item.speakers[0], text: "", time: null, fields: {}, origin_type: null, source_quote: "" }] })}>补一条消息</Button>
    </details>
    {item.dataset === "B" && <><label>重生成总指令<textarea rows={5} value={review.regen_instruction} onChange={e => update({ regen_instruction: e.target.value })} /></label><Button onClick={async () => { setError(""); try { const r = await api<{ instruction: string }>(base("B") + "/items/" + item.id + "/regen-draft"); update({ regen_instruction: r.instruction + review.added_messages.map(a => "\n在 " + (a.after_message_id || "末尾") + " 后增加：" + a.speaker + "：" + a.text).join("") }); } catch (e) { setError(String(e)); } }}>根据已存批注生成指令草稿</Button></>}
    <Button variant="primary" disabled={!review.verdict || (review.verdict !== "pass" && !review.comment.trim()) || (review.verdict === "regen" && !review.regen_instruction.trim())} onClick={() => void save(review)}>保存整图审核</Button>
  </fieldset>
    {item.dataset === "B" && <details><summary>对照判决书摘录（{item.judgment_excerpt ? "仅作事实对照" : "来源摘录缺失"}）</summary><blockquote className="screenshot-excerpt">{item.judgment_excerpt || "未提供摘录，不能选择原文支持。"}</blockquote><p>未载明的逐字措辞、具体时间和身份只能标记为模拟或未知。</p></details>}
    <ErrorText error={error} />
  </section>;
}

export function ScreenshotReviewPanel() {
  const client = useQueryClient();
  const [dataset, setDataset] = useState<Dataset>("A");
  const query = useQuery({ queryKey: ["screenshot-panel", dataset], queryFn: () => api<Panel>(base(dataset)), refetchOnWindowFocus: false });
  const [itemIndex, setItemIndex] = useState(0);
  const [msgIndex, setMsgIndex] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [busy, setBusy] = useState(false);
  const [dirtyMessage, setDirtyMessage] = useState(false);
  const [dirtyWhole, setDirtyWhole] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [exportText, setExportText] = useState("");
  const [backup, setBackup] = useState<Backup | null>(null);
  const [restoreText, setRestoreText] = useState("");
  const [filename, setFilename] = useState("");
  const [imageFailed, setImageFailed] = useState(false);
  const [restoreEpoch, setRestoreEpoch] = useState(0);
  const state = query.data;
  const item = state?.items[itemIndex];
  const message = item?.messages[msgIndex];
  const reviews = state?.message_reviews[item?.id || ""] || {};
  const locked = !!state?.locked_at;
  const pendingEdits = dirtyMessage || dirtyWhole;
  useEffect(() => { const handler = (e: BeforeUnloadEvent) => { if (pendingEdits) { e.preventDefault(); e.returnValue = ""; } }; window.addEventListener("beforeunload", handler); return () => window.removeEventListener("beforeunload", handler); }, [pendingEdits]);
  const onSaved = (p: Panel) => { client.setQueryData(["screenshot-panel", p.dataset], p); setNotice("已保存到服务器 · " + time(p.updated_at)); };
  const canNavigate = () => !pendingEdits || window.confirm("有尚未保存的修改，离开当前消息并放弃这些修改？");
  const navigate = (i: number, m = 0) => { if (i === itemIndex && m === msgIndex) return; if (i === itemIndex) { if (dirtyMessage && !window.confirm("当前消息有未保存修改，放弃并切换消息？")) return; setMsgIndex(m); setDirtyMessage(false); } else { if (!canNavigate()) return; setItemIndex(i); setMsgIndex(m); setZoom(1); setDirtyMessage(false); setDirtyWhole(false); setImageFailed(false); } setError(""); };
  async function action(fn: () => Promise<void>) { setBusy(true); setError(""); setNotice(""); try { await fn(); } catch (e) { setError(String(e)); } finally { setBusy(false); } }
  async function saveMessage(r: Review | null) {
    if (!state || !item || !message) return;
    await action(async () => {
      const p = await api<Panel>(base(dataset) + "/items/" + item.id + "/messages/" + encodeURIComponent(message.id), { expected_version: state.version, review: r }, "PUT");
      onSaved(p); setDirtyMessage(false); if (state.item_reviews[item.id]) setDirtyWhole(true);
      if (r) { const next = item.messages.findIndex((_, i) => i > msgIndex && !p.message_reviews[item.id]?.[item.messages[i].id]); const wrap = item.messages.findIndex(m => !p.message_reviews[item.id]?.[m.id]); if (next >= 0 || wrap >= 0) setMsgIndex(next >= 0 ? next : wrap); }
    });
  }
  return <div className="screenshot-panel">
    <div className="screenshot-progress"><div><strong>已完成 {state?.counts.items_reviewed || 0} / {state?.counts.items || 0} 张</strong><span>消息已判 {state?.counts.messages_reviewed || 0} / {state?.counts.messages || 0}</span></div><small>{state?.updated_at ? "已保存 " + time(state.updated_at) : "审核保存在服务器"}</small><progress max={state?.counts.items || 1} value={state?.counts.items_reviewed || 0} aria-label="当前数据集审核进度" />{locked && <p>数据集 {dataset} 已锁定 · {time(state?.locked_at || null)} · 标注不可再改</p>}</div>
    <div className="screenshot-datasets" role="group" aria-label="选择审核数据集">{(["A", "B"] as Dataset[]).map(d => <Button key={d} disabled={busy} aria-pressed={dataset === d} onClick={() => { if (d === dataset || !canNavigate()) return; setDataset(d); setItemIndex(0); setMsgIndex(0); setZoom(1); setDirtyMessage(false); setDirtyWhole(false); setExportText(""); setBackup(null); setRestoreText(""); setError(""); setNotice(""); setImageFailed(false); }}><strong>数据集 {d}</strong><span>{d === "A" ? "审核旧标注" : "审核模拟生成"}</span></Button>)}</div>
    <div role="status" className="screenshot-notice">{notice}</div><ErrorText error={error} />
    {query.isPending ? <p>正在载入已存审核…</p> : query.error ? <section className="card" role="alert"><p>已存审核载入失败，先别标：刷新页面再试，避免新旧数据对不上。</p><Button onClick={() => void query.refetch()}>重新载入</Button></section> : state && <>
      {!state.items.length ? <SourceSetup key={dataset} dataset={dataset} state={state} onSaved={onSaved} /> : item && message && <>
        <p className="screenshot-scope-note">{dataset === "B" ? "合成数据 · 不是原始聊天记录或司法证据" : "旧标注 · 原始标注等级：" + (state.scope?.annotation_level === "unverified" ? "待核实" : state.scope?.annotation_level)} · 本批 {state.items.length} 张</p>
        {state.scope && <ScopeSummary scope={state.scope} />}
        <div className="screenshot-nav"><Button disabled={busy || itemIndex === 0} onClick={() => navigate(itemIndex - 1)}>‹ 上一张</Button><div><strong>{item.id}</strong><span>第 {itemIndex + 1} / {state.items.length} 张 · 本图 {Object.keys(reviews).length}/{item.messages.length} 条</span></div><Button disabled={busy || itemIndex === state.items.length - 1} onClick={() => navigate(itemIndex + 1)}>下一张 ›</Button></div>
        <figure className="screenshot-figure"><div className="screenshot-image-scroll"><img key={item.id} src={"/v1" + base(dataset) + "/items/" + item.id + "/image"} alt={item.id + " 待审核聊天截图"} width={item.asset.width} height={item.asset.height} style={{ width: zoom === 2 ? "200%" : "100%", maxWidth: "none" }} onError={() => setImageFailed(true)} /></div><Button className="screenshot-zoom" onClick={() => setZoom(zoom === 1 ? 2 : 1)}>{zoom === 1 ? "放大 2×" : "还原 1×"}</Button><figcaption>{dataset === "A" ? "原标注" : "生成对话"}共 {item.messages.length} 条。{dataset === "A" ? "截图模糊请放大看，不要猜。" : "判决书摘录在下方，默认折叠。"}</figcaption></figure>
        {imageFailed && <p role="alert" className="research-error">截图加载失败，审核已暂停。请重新载入。</p>}
        <MessageEditor key={item.id + ":" + message.id + ":" + JSON.stringify(reviews[message.id])} item={item} message={message} index={msgIndex} saved={reviews[message.id]} locked={locked || imageFailed} busy={busy} save={saveMessage} dirty={setDirtyMessage} navigate={m => navigate(itemIndex, m)} />
        <section className="card"><div className="screenshot-message-nav"><h2>消息列表</h2><Button disabled={busy || msgIndex === 0} onClick={() => navigate(itemIndex, msgIndex - 1)}>上一条</Button><Button disabled={busy || msgIndex === item.messages.length - 1} onClick={() => navigate(itemIndex, msgIndex + 1)}>下一条</Button></div><div className="screenshot-bubbles">{item.messages.map((m, i) => <button disabled={busy} key={m.id} className={"screenshot-bubble screenshot-bubble--" + m.side} aria-current={m.id === message.id ? "true" : undefined} onClick={() => navigate(itemIndex, i)}><small>第 {i + 1} 条 · {m.speaker} · {m.time || "时间未知"}</small><span>{m.text || "非文本消息"}</span><em className={reviews[m.id]?.verdict === "correct" ? "is-done" : ""}>{reviews[m.id] ? msgLabels[reviews[m.id].verdict] : "未判"}</em></button>)}</div></section>
        <WholeEditor key={item.id + ":" + restoreEpoch} item={item} saved={state.item_reviews[item.id]} locked={locked || imageFailed} busy={busy} dirty={setDirtyWhole} save={r => action(async () => { const p = await api<Panel>(base(dataset) + "/items/" + item.id, { expected_version: state.version, review: r }, "PUT"); onSaved(p); setDirtyWhole(false); })} />
        <section className="card"><h2>全部截图</h2><div className="screenshot-index">{state.items.map((it, i) => { const count = Object.keys(state.message_reviews[it.id] || {}).length; const whole = state.item_reviews[it.id]; const done = !!whole && count === it.messages.length; return <Button key={it.id} disabled={busy} className={done ? "is-done" : ""} aria-current={i === itemIndex ? "true" : undefined} onClick={() => navigate(i)}><strong>{it.id}</strong><small>{count}/{it.messages.length} · {whole ? wholeLabels[whole.verdict] : "未判"}</small></Button>; })}</div></section>
        <section className="card screenshot-backup"><h2>导出、恢复与锁定</h2><p>A、B 分别保存、分别锁定。锁定前可随时导出完整备份，未判项按原状态保留。</p>
          <div className="toolbar"><Button disabled={busy || pendingEdits} onClick={() => void action(async () => { const b = await api<Backup>(base(dataset) + "/export", {}); setBackup(b); setFilename("review-" + dataset + ".json"); setExportText(JSON.stringify(b, null, 2)); setNotice("完整备份已生成，请下载或复制后核对。"); })}>生成完整导出 JSON</Button>
          {dataset === "B" && <Button disabled={busy || pendingEdits} onClick={() => void action(async () => { const b = await api("/studio/screenshot-regen-package"); setFilename("regen_jobs.json"); setExportText(JSON.stringify(b, null, 2)); })}>导出重生成包</Button>}</div>
          {pendingEdits && <p>请先保存当前修改，再导出或锁定。</p>}
          {exportText && <><label>全量导出 JSON · {filename}<textarea readOnly rows={10} value={exportText} /></label><div className="toolbar"><Button onClick={() => { const url = URL.createObjectURL(new Blob([exportText], { type: "application/json" })); const a = document.createElement("a"); a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }}>下载文件</Button><Button onClick={() => void action(async () => { await navigator.clipboard.writeText(exportText); setNotice("已复制全部 JSON，与下载内容一致。"); })}>复制全部</Button></div></>}
          <details><summary>从完整备份恢复</summary><p>只恢复当前数据集的审核层。清单、原始数据及全部判项验证通过后一次写入；失败时原审核不变。</p><label>粘贴旧导出 JSON<textarea rows={6} disabled={locked || busy} value={restoreText} onChange={e => setRestoreText(e.target.value)} /></label><Button disabled={locked || busy || !restoreText.trim() || pendingEdits} onClick={() => { if (!window.confirm("恢复将替换当前数据集的全部审核层，原始 JSON 保留。确认恢复？")) return; void action(async () => { const p = await api<Panel>(base(dataset) + "/restore", { expected_version: state.version, backup: JSON.parse(restoreText) }); onSaved(p); setRestoreEpoch(v => v + 1); setBackup(null); setNotice("恢复成功，已重新核对截图和消息数量。"); }); }}>验证并恢复当前数据集</Button></details>
          <Button variant="primary" disabled={busy || locked || pendingEdits || state.counts.items_reviewed !== state.counts.items || backup?.version !== state.version} onClick={() => { if (!window.confirm("数据集 " + dataset + " 的 " + state.counts.items + " 张截图、" + state.counts.messages + " 条消息已审核。请确认已核对当前导出备份；锁定后不能修改或恢复。另一数据集不受影响。确认锁定？")) return; void action(async () => { onSaved(await api<Panel>(base(dataset) + "/lock", { expected_version: state.version, export_sha256: backup?.export_sha256 })); }); }}>{locked ? "数据集 " + dataset + " 已锁定" : state.counts.items_reviewed !== state.counts.items ? "锁定（还差 " + (state.counts.items - state.counts.items_reviewed) + " 张）" : backup?.version !== state.version ? "请先导出当前完整版本" : "锁定数据集 " + dataset}</Button>
        </section>
      </>}
    </>}
  </div>;
}

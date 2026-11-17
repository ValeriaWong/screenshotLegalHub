import { Paged } from "../../components/collections";
import { useEffect, useRef, useState, type PointerEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Input } from "../../components/ui";
import { api, key, type Content, type Detail, type Manifest, type PageLayout, type ReviewComment } from "./client";
import { ErrorText } from "./shared";
import { CommentHistory } from "./CommentHistory";

export function FocusDialog({ title, close, children, drawer = false }: { title: string; close: () => void; children: React.ReactNode; drawer?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    ref.current?.showModal();
    return () => { ref.current?.close(); previous?.focus(); };
  }, []);
  return <dialog ref={ref} className={drawer ? "review-source-drawer" : "review-message-dialog"} aria-label={title} onCancel={e => { e.preventDefault(); close(); }} onClick={e => { if (e.target === e.currentTarget) close(); }}>
    <div className="review-dialog-inner"><div className="review-dialog-heading"><h2>{title}</h2><Button type="button" onClick={close}>关闭</Button></div>{children}</div>
  </dialog>;
}
export function JudgmentDrawer({ sampleId }: { sampleId: string }) {
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["research", "judgment", sampleId], queryFn: () => api<{ available: boolean; text: string; revision: number; references: Record<string, unknown>[] }>("/review/samples/" + sampleId + "/judgment"), enabled: open });
  return <>
    <Button type="button" className="review-source-button" onClick={() => setOpen(true)}>判决书原文</Button>
    {open && <FocusDialog title="判决书原文" close={() => setOpen(false)} drawer>
      {q.isPending ? <p>正在读取原文…</p> : q.error ? <ErrorText error={q.error} /> : q.data.available ? <><p>样本 r{q.data.revision} · 来源原文</p><pre className="review-judgment-text">{q.data.text}</pre></> : <div className="review-missing-source" role="status"><h3>此样本未附判决书原文</h3><p>原文位置为你保留。当前可继续审核图片、文本并留下评论；不会用合成消息替代判决书。</p></div>}
      {!!q.data?.references.length && <details><summary>来源引用</summary>{<Paged items={q.data.references} label="判决书来源引用" layout="block">{(pageItems, pageOffset) => pageItems.map((r, pageIndex) => { const i = pageIndex + pageOffset; return (<pre className="research-json" key={i}>{JSON.stringify(r, null, 2)}</pre>); })}</Paged>}</details>}
    </FocusDialog>}
  </>;
}
export function manifestLayout(manifest: Manifest, content: Content): PageLayout[] {
  const ids = new Set(content.messages.map(m => m.id));
  return manifest.pages.map(p => ({ page: p.page, width: p.width, height: p.height, boxes: p.boxes.filter(b => ids.has(b.message_id)).map(b => ({ message_id: b.message_id, bbox: [...b.bbox] })) }));
}
interface Props {
  detail: Detail; content: Content; manifest?: Manifest; layout: PageLayout[]; change: (c: Content) => void;
  changeLayout: (pages: PageLayout[]) => void; locked: boolean; setLocked: (v: boolean) => void;
  note: string; changeNote: (v: string) => void; save: (note?: string) => Promise<boolean>; saving: boolean; ready: boolean;
  commentDrafts: Record<string, string>; changeComment: (target: string, value: string) => void; refresh: () => Promise<unknown>;
  saveError?: string;
}
export function ReviewCanvas({ detail, content, manifest, layout, change, changeLayout, locked, setLocked, note, changeNote, save, saving, ready, commentDrafts, changeComment, refresh, saveError }: Props) {
  const [selection, setSelection] = useState<{ page: number; index: number; messageId: string } | null>(null);
  const [error, setError] = useState("");
  const [commentBusy, setCommentBusy] = useState(false);
  const [commentStatus, setCommentStatus] = useState("");
  const [useForGeneration, setUseForGeneration] = useState(true);
  const [longTerm, setLongTerm] = useState(false);
  const surface = useRef<HTMLDivElement | null>(null);
  const latestComments = useRef(commentDrafts); latestComments.current = commentDrafts;
  const drag = useRef<{ x: number; y: number; box: number[]; page: number; index: number; edge: string; width: number; height: number; rect: DOMRect; moved: boolean } | null>(null);
  const suppressClick = useRef(false);
  const current = !!manifest && manifest.revision === detail.sample.revision;
  const failedRender = detail.jobs.some(j => j.id === detail.sample.render_job_id && ["failed", "cancelled"].includes(j.status));
  const originalsOnly = !content.messages.length && content.original_assets.length > 0;
  const adjustable = !!content.messages.length && !!manifest && ready && !saving && (current || failedRender);
  const editable = current && ready && !saving;
  const target = selection?.messageId || "__sample__";
  const message = selection ? content.messages.find(m => m.id === selection.messageId) : undefined;
  const comments = (detail.comments || []).filter(c => !selection || c.message_id === selection.messageId);
  function update(page: number, index: number, bbox: number[]) {
    changeLayout(layout.map(p => p.page === page ? { ...p, boxes: p.boxes.map((b, i) => i === index ? { ...b, bbox } : b) } : p));
  }
  function start(e: PointerEvent<HTMLElement>, page: PageLayout, index: number, edge: string) {
    if (locked || !adjustable || e.button !== 0) return;
    const element = e.currentTarget.closest(".review-image-surface") as HTMLDivElement;
    surface.current = element;
    drag.current = { x: e.clientX, y: e.clientY, box: [...page.boxes[index].bbox], page: page.page, index, edge, width: page.width, height: page.height, rect: element.getBoundingClientRect(), moved: false };
    suppressClick.current = false; e.currentTarget.setPointerCapture(e.pointerId); e.preventDefault(); e.stopPropagation();
  }
  function adjusted(box: number[], dx: number, dy: number, edge: string, width: number, height: number) {
    let [x1, y1, x2, y2] = box;
    const minW = Math.min(48, x2 - x1), minH = Math.min(48, y2 - y1);
    if (edge === "move") {
      dx = Math.max(-x1, Math.min(width - x2, dx)); dy = Math.max(-y1, Math.min(height - y2, dy));
      x1 += dx; x2 += dx; y1 += dy; y2 += dy;
    } else {
      if (edge.includes("w")) x1 = Math.max(0, Math.min(x2 - minW, x1 + dx));
      if (edge.includes("e")) x2 = Math.min(width, Math.max(x1 + minW, x2 + dx));
      if (edge.includes("n")) y1 = Math.max(0, Math.min(y2 - minH, y1 + dy));
      if (edge.includes("s")) y2 = Math.min(height, Math.max(y1 + minH, y2 + dy));
    }
    return [x1, y1, x2, y2].map(v => Math.round(v * 100) / 100);
  }
  function move(e: PointerEvent<HTMLElement>) {
    const d = drag.current; if (!d || locked) return;
    const dx = (e.clientX - d.x) * d.width / d.rect.width, dy = (e.clientY - d.y) * d.height / d.rect.height;
    d.moved ||= Math.hypot(e.clientX - d.x, e.clientY - d.y) > 3;
    if (d.moved) update(d.page, d.index, adjusted(d.box, dx, dy, d.edge, d.width, d.height));
  }
  function end(e: PointerEvent<HTMLElement>) {
    if (drag.current) { suppressClick.current = drag.current.moved && drag.current.edge === "move"; drag.current = null; if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId); setTimeout(() => { suppressClick.current = false; }, 0); }
  }
  async function comment() {
    const body = commentDrafts[target]?.trim(); if (!body) return;
    setCommentBusy(true); setError(""); setCommentStatus("");
    try {
      const originalBox = selection && manifest?.pages.find(p => p.page === selection.page)?.boxes.filter(b => content.messages.some(m => m.id === b.message_id))[selection.index];
      await api<ReviewComment>("/review/samples/" + detail.sample.id + "/comments", {
        revision: detail.sample.revision, message_id: selection?.messageId || null, body, use_for_generation: useForGeneration, applicability: longTerm ? "source" : "revision",
        manifest_id: selection ? manifest?.id : null, page: selection?.page || null, bbox: originalBox?.bbox || null, idempotency_key: key(),
      });
      if (latestComments.current[target]?.trim() === body) changeComment(target, ""); setCommentStatus("评论已保存，可用于后续 AI 生成迭代；样本文本与坐标未改动。"); await refresh();
    } catch (e) { setError(String(e)); } finally { setCommentBusy(false); }
  }
  function commentFields() {
    return <div className="research-form"><h3>{selection ? "针对这条消息添加评论" : "样本审核评论"}</h3>
      <p>可以只提意见，不必修改消息。评论按图片对应的已保存版本记录，保留消息原文和图片位置作为依据。</p>
      <label>审核评论<textarea aria-label="审核评论" rows={4} value={commentDrafts[target] || ""} onChange={e => changeComment(target, e.target.value)} placeholder="例如：这段话过于书面；金额应与判决书核对；下一轮生成需避免补造时间。" /></label>
      <label className="research-check"><Input type="checkbox" checked={useForGeneration} onChange={e => setUseForGeneration(e.target.checked)} />用于 AI 数据生成迭代</label>
      <label className="research-check"><Input type="checkbox" checked={longTerm} onChange={e => setLongTerm(e.target.checked)} />适用于同源后续版本（长期规则）</label>
      <Button type="button" disabled={commentBusy || !commentDrafts[target]?.trim() || !ready} onClick={comment}>仅保存评论</Button>
    </div>;
  }
  function history() {
    return <CommentHistory comments={comments} refresh={refresh} />;
  }
  return <>
    <div className="review-canvas-toolbar"><div><h3>图片与消息坐标框</h3><p>图片类型：{manifest?.visual_role || "历史未声明"}{manifest?.validation?.unannotated ? " · 原图尚无坐标标注" : ""}</p><p>点击框内的消息即可编辑文本或评论。默认锁定坐标，解锁后可移动框、拖拽边角缩放。</p></div>
      <label className="research-check"><Input type="checkbox" checked={locked} disabled={!adjustable} onChange={e => { drag.current = null; setLocked(e.target.checked); }} />锁定坐标框</label>
    </div>
    {!current && failedRender && <p role="alert" className="research-conflict">当前渲染失败，图片仍为上一成功版本；框显示已保存的新布局。可解锁扩大框后保存，或展开消息列表修正文本。</p>}
    {!current && !failedRender && <p role="status" className="research-conflict">{manifest ? "当前图片仍为 r" + manifest.revision + "；等待 r" + detail.sample.revision + " 渲染完成后才能编辑消息和坐标。" : "图片正在排队渲染，完成后会显示坐标框。"}</p>}
    {!locked && <p role="status">坐标已解锁；拖拽框体移动、拖拽边角缩放，方向键微调，Shift + 方向键每次调整 10 像素。保存后应用到新渲染。</p>}
    {originalsOnly && <><p role="status">原图尚无消息转录与坐标，可先添加样本评论；补充转录并保存后生成对应消息框。</p><div className="research-image-grid">{<Paged items={content.original_assets} label="原始图片" layout="block" pageSize={6}>{(pageItems) => pageItems.map(a => <figure key={a.id}><a href={"/v1/review/assets/" + a.id} target="_blank" rel="noreferrer"><img src={"/v1/review/assets/" + a.id} alt="审核原图（尚无消息坐标）" /></a></figure>)}</Paged>}</div></>}
    <div className="review-canvas-pages">
      {!originalsOnly && manifest && <Paged items={manifest.pages} label="审核图片页" layout="block" resetKey={detail.sample.id} pageSize={4}>{(pageItems) => pageItems.map(p => {
        const page = layout.find(v => v.page === p.page) || { page: p.page, width: p.width, height: p.height, boxes: p.boxes.filter(b => content.messages.some(m => m.id === b.message_id)) };
        return <figure key={p.page}><figcaption>第 {p.page} 页 · 图片 r{manifest.revision} · {page.boxes.length} 个消息框 <a target="_blank" rel="noreferrer" href={"/v1/review/manifests/" + manifest.id + "/pages/" + p.page}>查看原尺寸</a></figcaption>
          <div className="review-image-surface" data-page={p.page} style={{ aspectRatio: p.width + " / " + p.height }} data-locked={locked}>
            <img src={"/v1/review/manifests/" + manifest.id + "/pages/" + p.page} alt={(manifest.visual_role === "original" ? "原图 r" : "派生图 r") + manifest.revision + " 第" + p.page + "页"} draggable={false} />
            {page.boxes.map((b, index) => <div className="review-region" key={b.message_id + ":" + index} style={{ left: b.bbox[0] / page.width * 100 + "%", top: b.bbox[1] / page.height * 100 + "%", width: (b.bbox[2] - b.bbox[0]) / page.width * 100 + "%", height: (b.bbox[3] - b.bbox[1]) / page.height * 100 + "%" }}>
              <button type="button" className="review-region-hit" aria-label={"编辑消息 " + b.message_id + " 第" + p.page + "页"} disabled={!adjustable} onPointerDown={e => start(e, page, index, "move")} onPointerMove={move} onPointerUp={end} onPointerCancel={end} onClick={() => { if (!editable) return; if (suppressClick.current) { suppressClick.current = false; return; } setSelection({ page: p.page, index, messageId: b.message_id }); setCommentStatus(""); setError(""); }} onKeyDown={e => {
                if (!locked && adjustable && ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) { e.preventDefault(); const n = e.shiftKey ? 10 : 1; update(page.page, index, adjusted(b.bbox, e.key === "ArrowLeft" ? -n : e.key === "ArrowRight" ? n : 0, e.key === "ArrowUp" ? -n : e.key === "ArrowDown" ? n : 0, "move", page.width, page.height)); }
              }}><span>{b.message_id}</span></button>
              {!locked && adjustable && ["nw", "n", "ne", "e", "se", "s", "sw", "w"].map(edge => <button key={edge} type="button" className={"review-region-handle review-handle-" + edge} aria-label={"调整 " + b.message_id + " " + edge + " 第" + p.page + "页"} onPointerDown={e => start(e, page, index, edge)} onPointerMove={move} onPointerUp={end} onPointerCancel={end} onKeyDown={e => { if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) { e.preventDefault(); const n = e.shiftKey ? 10 : 1; update(page.page, index, adjusted(b.bbox, e.key === "ArrowLeft" ? -n : e.key === "ArrowRight" ? n : 0, e.key === "ArrowUp" ? -n : e.key === "ArrowDown" ? n : 0, edge, page.width, page.height)); } }} />)}
            </div>)}
          </div>
        </figure>;
      })}</Paged>}
    </div>
    {selection && message && <FocusDialog title={"审核消息 " + message.id} close={() => setSelection(null)}>
      <p>样本 r{detail.sample.revision} · 第{selection.page}页 · {locked ? "坐标已锁定" : "坐标已解锁"} · {message.speaker}</p>
      {!editable && <p role="alert">当前样本或图片版本已变化；请关闭弹窗，对照新版本合并草稿后再保存。</p>}
      <label>消息文本<textarea aria-label="消息文本" rows={5} value={message.text} onChange={e => change({ ...content, messages: content.messages.map(m => m.id === message.id ? { ...m, text: e.target.value } : m) })} /></label>
      <label>修改说明（可选）<textarea aria-label="修改说明（可选）" rows={2} value={note} onChange={e => changeNote(e.target.value)} /></label>
      <Button type="button" disabled={saving || !message.text.trim() || !editable} onClick={async () => { if (await save(note || "人工校正消息 " + message.id)) setSelection(null); }}>保存并重新渲染</Button>
      <p className="review-dialog-hint">关闭窗口会保留未提交草稿。评论可单独保存，不需要改消息。</p>
      {commentFields()}{history()}<p role="status">{commentStatus}</p><ErrorText error={error || saveError} />
    </FocusDialog>}
    {!selection && <details className="review-sample-comments"><summary>添加样本评论 / 查看评论（{detail.comments?.length || 0}）</summary>{commentFields()}{history()}<p role="status">{commentStatus}</p><ErrorText error={error} /></details>}
    {!!detail.generation_feedback?.length && <CommentHistory comments={detail.generation_feedback} refresh={refresh} candidate={{ id: detail.sample.id, revision: detail.sample.revision }} />}
    {!originalsOnly && !!content.original_assets.length && <details><summary>导入原图（{content.original_assets.length} 张，保留原貌）</summary><div className="research-image-grid">{<Paged items={content.original_assets} label="原始图片" layout="block" pageSize={6}>{(pageItems) => pageItems.map(a => <figure key={a.id}><a href={"/v1/review/assets/" + a.id} target="_blank" rel="noreferrer"><img loading="lazy" src={"/v1/review/assets/" + a.id} alt="导入原图" /></a></figure>)}</Paged>}</div></details>}
  </>;
}

import { Paged } from "../../components/collections";
import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "../../components/ui";
import { api, label } from "./client";
import { ErrorText, JsonView } from "./shared";

interface Message { id: string; bbox: number[]; speaker?: string | null; timestamp?: string | null; content?: string | null; image?: string | null; transfer?: string | null; file?: string | null }
interface Detail { node: { id: string; task_id: string; stage: string; variant: string; status: string; reason?: string }; task: { question: string; roi: number[] | null; asset: { id: string; width: number; height: number } }; input: unknown; attempt?: { response?: { raw: string }; parsed?: { answer?: unknown }; request_id?: string }; prediction?: { output?: { conversation: Message[] } }; match?: { status: string; message_id?: string; best_iou?: number; threshold?: number } }
function answerText(value: unknown) { return typeof value === "string" ? value : JSON.stringify(value, null, 2); }
export function PipelineInspector({ dataset, pipelineId, nodeId, onClose }: { dataset: string; pipelineId: string; nodeId: string; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const query = useQuery({ queryKey: ["research", "pipeline-node", pipelineId, nodeId], queryFn: () => api<Detail>("/evaluation/benchmark-pipelines/" + pipelineId + "/nodes/" + nodeId), refetchInterval: 5000 });
  useEffect(() => { const previousFocus = document.activeElement as HTMLElement | null; const el = dialog.current; el?.showModal(); const old = document.body.style.overflow; document.body.style.overflow = "hidden"; return () => { el?.close(); document.body.style.overflow = old; previousFocus?.focus(); }; }, []);
  const data = query.data, matched = data?.match?.status === "matched", blocked = data?.node.status === "blocked_no_match";
  const messages = data?.prediction?.output?.conversation || [];
  return <dialog className="pipeline-inspector" ref={dialog} aria-label="样本阶段详情" onCancel={e => { e.preventDefault(); onClose(); }}>
    <header><div><h2>{data?.node.stage === "kie" ? "消息识别详情" : "问答详情"}</h2><p>{data ? label(data.node.status) : "读取阶段记录…"}</p></div><Button autoFocus onClick={onClose}>关闭详情</Button></header>
    <ErrorText error={query.error} />{data && <>
      {blocked && <section className="pipeline-outcome" aria-label="未执行原因"><h3>这道区域问答没有发送给模型</h3><p>{data.match?.status === "below_threshold" ? "最佳匹配IoU " + data.match.best_iou?.toFixed(4) + "，低于本轮阈值 " + (data.match.threshold ?? .6) + "。" : data.match?.status === "no_message" ? "本图没有可用于匹配的识别消息。" : "没有找到满足本轮条件的消息框。"}本题仍保留在计划分母中。</p><a href={"/review.html?section=benchmark&benchmark=" + dataset + "&benchmark_task=" + data.node.task_id}>去审核本题的参考区域与意见 →</a></section>}
      <div className="pipeline-inspector-grid"><section><h3>原图与本轮识别框</h3><svg role="img" aria-label="当前原图、参考区域和本轮预测消息框" viewBox={"0 0 " + data.task.asset.width + " " + data.task.asset.height}>
        <image href={"/v1/review/assets/" + data.task.asset.id} width={data.task.asset.width} height={data.task.asset.height} />
        {messages.map(m => { const candidate = m.id === data.match?.message_id; return <rect key={m.id} data-role={candidate ? matched ? "selected" : "candidate" : "prediction"} x={m.bbox[0]} y={m.bbox[1]} width={m.bbox[2]-m.bbox[0]} height={m.bbox[3]-m.bbox[1]} fill="none" stroke={candidate ? matched ? "var(--success)" : "var(--warning)" : "var(--muted)"} strokeWidth={3}><title>{m.content || "非文字消息"}</title></rect>; })}
        {data.task.roi && <rect x={data.task.roi[0]} y={data.task.roi[1]} width={data.task.roi[2]-data.task.roi[0]} height={data.task.roi[3]-data.task.roi[1]} fill="none" stroke="var(--warning)" strokeWidth={3} strokeDasharray="8 5" />}
      </svg><p>橙色虚线：参考区域；灰色：预测消息。{matched ? "绿色：已实际选入问答的消息。" : data.match?.message_id ? "橙色实线：最佳候选，未被采用；本题没有区域问答输入。" : "本阶段没有选入区域消息。"}</p></section>
      <section><h3>{data.node.stage === "kie" ? "识别出的消息" : "问题与回答"}</h3><p>{data.task.question}</p>
        {data.node.stage === "kie" ? <><p>识别记录 {messages.length} 条；结构有效不等于内容已人工确认。</p><div className="pipeline-message-list">{<Paged items={messages} label="抽取消息" layout="block">{(pageItems) => pageItems.map(m => <article key={m.id}><strong>{m.speaker || "说话人未知"}</strong>{m.timestamp && <small> · {m.timestamp}</small>}<p>{[m.content,m.image,m.transfer,m.file].filter(Boolean).join(String.fromCharCode(10)) || "没有文本内容"}</p></article>)}</Paged>}</div></> : data.attempt?.parsed?.answer !== undefined ? <div className="pipeline-answer"><h4>模型回答</h4><p>{answerText(data.attempt.parsed.answer)}</p></div> : data.attempt?.response ? <div className="pipeline-answer"><h4>模型返回</h4><p>{data.attempt.response.raw}</p></div> : <p>{blocked ? "本题未调用模型，没有回答或费用。" : "尚无已保存回答，请查看阶段状态。"}</p>}
        <p><a href={"/review.html?section=benchmark&benchmark=" + dataset + "&benchmark_task=" + data.node.task_id}>审核目标、评论和量表 →</a></p><details><summary>真正发送给模型的任务输入</summary>{data.input ? <JsonView value={data.input} /> : <p>本题未生成实际输入，没有发送请求。</p>}</details>
        <details><summary>原始返回与技术记录</summary>{data.attempt?.response && <pre className="research-markdown">{data.attempt.response.raw}</pre>}<JsonView value={data} /></details>
      </section></div>
    </>}
  </dialog>;
}

import { SearchableSelect } from "../../components/collections";
import { Paged } from "../../components/collections";
import {useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {Card} from "../../components/ui";
import {api,stamp} from "./client";
import {ErrorText,JsonView} from "./shared";
export function BenchmarkFeedback(){
 const [selected,setSelected]=useState("");
 const datasets=useQuery({queryKey:["research","benchmarks"],queryFn:()=>api<{id:string;name:string}[]>("/evaluation/benchmarks")});
 const dataset=selected||datasets.data?.[0]?.id||"";
 const feedback=useQuery({queryKey:["research","benchmark-feedback",dataset],queryFn:()=>api<{id:string;body:string;image_name:string;created_at:string;feedback_binding_sha256:string}[]>("/studio/benchmark-feedback?dataset_id="+dataset),enabled:!!dataset});
 if(!datasets.data?.length)return null;
 return <Card><details><summary>KIE / VQA 审核反馈（开发集）</summary><p>这些意见可用于下一轮生成与 Prompt 迭代。留出集意见不会出现在这里；保存评论后还须在审核台确认数据用途为开发集。</p><SearchableSelect label={<>反馈数据来源</>} value={dataset} onChange={e=>setSelected(e.target.value)}>{datasets.data.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</SearchableSelect><ErrorText error={datasets.error||feedback.error}/>{<Paged items={feedback.data} label="开发集审核反馈" layout="block" resetKey={dataset}>{(pageItems) => pageItems.map(f=><article key={f.id}><p>{f.body}</p><small>{f.image_name} · {stamp(f.created_at)}</small><details><summary>来源绑定</summary><JsonView value={f}/></details></article>)}</Paged>}{!feedback.data?.length&&<p>尚无已划入开发集的反馈；原评论仍保留在审核台。</p>}<a href="/review.html?section=benchmark">打开标注与评论 →</a></details></Card>;
}

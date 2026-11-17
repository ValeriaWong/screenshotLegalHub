import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Input } from "../../components/ui";
import { SearchableSelect } from "../../components/collections";
import { api, stamp } from "./client";
import { ErrorText } from "./shared";
import { LeaderboardCharts } from "./LeaderboardCharts";

interface MethodInfo { id:string;name:string;profile:string;paper?:boolean;categories?:string[];available?:boolean;sources?:string[];reproduction_level:string;original_paper_reproduced:boolean;implementation_version?:string }
interface Model { config_id?:string;name:string;model:string;identity?:string;supports_vision?:boolean;enabled?:boolean }
interface Definition { release_hash:string|null;parameters:Record<string,unknown>;scorer:unknown;prompt:unknown;method?:unknown;tasks?:unknown[];budget?:unknown }
interface Cohort { id:string;family:string;dataset_name:string;scope:string;track:string|{track?:string;variant?:string;field?:string;answer_kind?:string};metric:string;models:number;entries?:number;fixed_model_name?:string|null;fixed_model_config_id?:string|null;method_id?:string;eligible:number;planned:number;updated_at:string;definition:Definition }
export interface Entry { entry_id?:string;catalogue?:boolean;active?:boolean;categories?:string[];method?:MethodInfo;baseline?:boolean;baseline_delta?:number|null;pipeline_models?:{extractor:Model;answer:Model};upstream_kie?:{score:number|null;eligible:number;scored:number};model_calls?:number|null;tool_calls?:number|null;input_tokens?:number|null;output_tokens?:number|null;elapsed_ms?:number|null;stale_code?:boolean;engineering?:{quote_spans_validated?:number|null};rank:number|null;model:Model;run_id:string|null;run_name:string;created_at:string|null;status:string;href:string;method_name:string;planned:number;eligible:number;scored:number;score:number|null;conditional_score:number|null;score_coverage:number|null;failed:number;unknown:number;cancelled:number;unreviewed:number;latency_p50_ms:number|null;latency_p95_ms:number|null;cost:number|null;cost_complete:boolean;currencies:string[];failures:Record<string,number>;unranked_reason:string|null;repeated_runs:number }
interface Board { scope?:string;inventory?:{models:Model[];methods:MethodInfo[]};categories?:{id:string;entries:number}[];cohorts:Cohort[];selected_cohort_id:string|null;items:Entry[];total:number;next_offset:number|null;generated_at:string;summary:{available_scopes:Record<string,number>;excluded:{reason:string;label:string;count:number}[]};metric_note:string }
const categories=[
  {id:"oneshot",label:"单模型 One-shot",axis:"models"},
  {id:"kie_enhanced",label:"KIE 增强",axis:"models"},
  {id:"agent",label:"Agent",axis:"methods"},
  {id:"reproductions",label:"推断方法复现",axis:"methods"}
];
const names:Record<string,string>={agent:"案件方法实验",case_analysis:"案件分析",qa:"已发布问答",pipeline:"按图流程",benchmark:"单任务",text:"文本",image:"图片",multi_image:"多图",multimodal:"文本＋图片",kie_image:"KIE 消息抽取",full_image:"整图问答",vqa_image_full:"整图问答",vqa_image_region:"区域问答",vqa_predicted_text:"预测文本问答",reference_guided_prediction:"参考区域引导问答",full_image_control:"整图对照",vqa_text:"文本问答"};
const states:Record<string,string>={not_evaluated:"未评测",not_implemented:"尚未实现",queued:"排队中",running:"运行中",completed:"已完成",completed_with_issues:"完成但有异常",failed:"失败",unknown:"结果未知",cancelled:"已取消",aborted:"已中止"};
const percent=(n:number|null)=>n==null?"—":(100*n).toFixed(1)+"%";
const seconds=(n:number|null)=>n==null?"—":(n/1000).toFixed(2)+" s";
function trackName(c:Cohort){if(typeof c.track==="string")return names[c.track] || c.track;const t=c.track.variant || c.track.track || "";return (names[t] || t)+(c.track.field?" · "+c.track.field:"");}
function cohortName(c:Cohort){return (c.fixed_model_name?c.fixed_model_name+" / ":"")+c.dataset_name+" · "+trackName(c)+" · "+c.planned+(c.family==="agent"?" 案":" 题")+" · "+c.id.slice(0,6);}
function inputMode(c:Cohort){if(c.family==="agent")return "冻结案件资料";if(c.family==="qa")return typeof c.track==="string"?(names[c.track] || c.track):"—";const t=typeof c.track==="string"?c.track:c.track.variant || c.track.track || "";return ["reference_guided_prediction","vqa_predicted_text"].includes(t)?"图片 → KIE → 问答":t==="vqa_text"?"文本":"图片";}
function csvCell(value:unknown){let text=String(value??"");if(/^[=+\-@\t\r]/.test(text))text="'"+text;return '"'+text.replaceAll('"','""')+'"';}
function download(board:Board,category:string,comparison:string){
  const rows:unknown[][]=[["类别","比较方式","成绩性质","名次","模型配置","模型","方法","状态","主指标","基线差值","已计分","有效参考","计分覆盖率","失败","未知","取消","P50毫秒","估算费用","币种","费用完整","模型调用","工具调用","输入token","输出token","总耗时ms","运行","时间"]];
  for(const r of board.items)rows.push([category,comparison,board.scope,r.rank,r.model.name,r.model.model,r.method_name,r.status,r.score,r.baseline_delta,r.scored,r.eligible,r.score_coverage,r.failed,r.unknown,r.cancelled,r.latency_p50_ms,r.cost,r.currencies.join("/"),r.cost_complete,r.model_calls,r.tool_calls,r.input_tokens,r.output_tokens,r.elapsed_ms,r.run_id,r.created_at]);
  const url=URL.createObjectURL(new Blob(["\ufeff"+rows.map(row=>row.map(csvCell).join(",")).join("\r\n")],{type:"text/csv;charset=utf-8"}));
  const a=document.createElement("a");a.href=url;a.download="leaderboard-"+category+".csv";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export function Leaderboard(){
  const initial=new URLSearchParams(location.search);
  const first=categories.find(c=>c.id===initial.get("board_category")) || categories[0];
  const [category,setCategory]=useState(first.id);
  const [comparison,setComparison]=useState(["models","methods"].includes(initial.get("board_compare") || "")?initial.get("board_compare")!:first.axis);
  const [display,setDisplay]=useState("table");
  const [baseline,setBaseline]=useState(initial.get("board_baseline")!=="0");
  const [scope,setScope]=useState(["official","development"].includes(initial.get("board_scope") || "")?initial.get("board_scope")!:"auto");
  const [family,setFamily]=useState(["qa","benchmark","pipeline","agent"].includes(initial.get("board_family") || "")?initial.get("board_family")!:"all");
  const [cohort,setCohort]=useState(initial.get("cohort") || "");
  const [modelId,setModelId]=useState(initial.get("board_model") || "");
  const [methodId,setMethodId]=useState(initial.get("board_method") || "");
  const [sort,setSort]=useState("score"),[offset,setOffset]=useState(0),[search,setSearch]=useState(""),[q,setQ]=useState("");
  const showBaseline=baseline && comparison==="methods" && ["agent","reproductions"].includes(category);
  const query=new URLSearchParams({scope,family,sort,offset:String(offset),limit:"20",q,category,comparison,include_baseline:String(showBaseline),include_active:"true",include_catalogue:"true",model_id:modelId,method_id:methodId});if(cohort)query.set("cohort_id",cohort);
  const board=useQuery({queryKey:["research","leaderboard",query.toString()],queryFn:()=>api<Board>("/evaluation/leaderboard?"+query),refetchInterval:15000});
  const data=board.data,selected=data?.cohorts.find(c=>c.id===data.selected_cohort_id);
  const effectiveScope=data?.scope || selected?.scope || (scope==="auto"?"development":scope);
  const inventory=data?.inventory;
  const availableMethods=inventory?.methods.filter(m=>m.categories?.includes(category)) || [];
  const methodOptions=availableMethods.length?availableMethods:[{id:"E00",name:"One-shot"}];
  const chosenMethod=methodId || selected?.method_id || methodOptions[0]?.id || "";
  const chosenModel=modelId || selected?.fixed_model_config_id || inventory?.models[0]?.config_id || "";
  const pendingGold=selected?.metric==="awaiting_expert_gold";
  const hasBaseline=!!data?.items.some(r=>r.baseline && r.score!=null);
  function change(next:{scope?:string;family?:string;cohort?:string;category?:string;comparison?:string;baseline?:boolean;modelId?:string;methodId?:string}){
    const cat=next.category ?? category,axis=next.comparison ?? comparison,changedCategory=cat!==category || axis!==comparison;
    const values={scope:next.scope ?? scope,family:next.family ?? (changedCategory?"all":family),cohort:next.cohort ?? "",category:cat,comparison:axis,baseline:next.baseline ?? baseline,modelId:next.modelId ?? (changedCategory?"":modelId),methodId:next.methodId ?? (changedCategory?"":methodId)};
    setScope(values.scope);setFamily(values.family);setCohort(values.cohort);setCategory(cat);setComparison(axis);setBaseline(values.baseline);setModelId(values.modelId);setMethodId(values.methodId);setOffset(0);
    if(changedCategory){setSearch("");setQ("");}
    const u=new URL(location.href);u.searchParams.set("view","leaderboard");
    for(const [key,value] of Object.entries({board_scope:values.scope,board_family:values.family,cohort:values.cohort,board_category:cat,board_compare:axis,board_baseline:values.baseline?"1":"0",board_model:values.modelId,board_method:values.methodId})){if(value)u.searchParams.set(key,value);else u.searchParams.delete(key);}
    history.replaceState(null,"",u);
  }
  return <section aria-label="评测排行榜" className="leaderboard-list">
    <Card>
      <div className="leaderboard-heading"><div className="leaderboard-view-toggle" role="group" aria-label="展示形式"><Button aria-pressed={display==="table"} onClick={()=>setDisplay("table")}>排行榜列表</Button><Button aria-pressed={display==="charts"} onClick={()=>setDisplay("charts")}>指标分析</Button></div><div><a href="/evaluation.html?view=benchmark">创建评测</a><Button disabled={board.isFetching} onClick={()=>board.refetch()}>{board.isFetching?"正在更新…":"刷新榜单"}</Button></div></div>
      <nav className="leaderboard-categories" aria-label="比较类别">{categories.map(c=>{
        const methods=inventory?.methods.filter(m=>m.categories?.includes(c.id) && m.available).length ?? 0;
        return <Button key={c.id} aria-pressed={category===c.id} onClick={()=>change({category:c.id,comparison:c.axis})}><strong>{c.label}</strong><small>评测条目 {data?.categories?.find(v=>v.id===c.id)?.entries ?? "—"}{inventory && " · "+(["oneshot","kie_enhanced"].includes(c.id)?inventory.models.length+" 个配置":methods+" 个可用方法")}</small></Button>;
      })}</nav>
      <div className="leaderboard-filters">
        <SearchableSelect label="任务与数据集" value={data?.selected_cohort_id || ""} disabled={!data?.cohorts.length} onChange={e=>change({cohort:e.target.value})}>{!data?.cohorts.length && <option value="">尚无成绩，先查看可评测条目</option>}{data?.cohorts.map(c=><option key={c.id} value={c.id}>{cohortName(c)}</option>)}</SearchableSelect>
        <label>比较方式<select value={comparison} onChange={e=>change({comparison:e.target.value})}><option value="models">比较模型（固定方法）</option><option value="methods">比较方法（固定底座模型）</option></select></label>
        <label>榜单性质<select value={scope} onChange={e=>change({scope:e.target.value})}><option value="auto">自动 · 优先展示已有成绩</option><option value="official">正式榜 · 人工审核发布</option><option value="development">开发参考榜 · 独立展示</option></select></label>

        {comparison==="methods" && <label>底座模型<select value={chosenModel} onChange={e=>change({modelId:e.target.value})}>{!inventory?.models.length && <option value={chosenModel}>{selected?.fixed_model_name || "请先添加模型配置"}</option>}{selected?.fixed_model_config_id && inventory?.models.length && !inventory.models.some(m=>m.config_id===selected.fixed_model_config_id) ? <option value={selected.fixed_model_config_id}>{selected.fixed_model_name}（历史冻结配置）</option>:null}{inventory?.models.map(m=><option key={m.config_id} value={m.config_id}>{m.name} · {m.model}</option>)}</select></label>}
        {comparison==="models" && ["agent","reproductions"].includes(category) && <label>固定方法<select value={chosenMethod} onChange={e=>change({methodId:e.target.value})}>{methodOptions.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></label>}
      </div>
      <details className="leaderboard-tools"><summary>搜索、排序与高级筛选</summary><div className="leaderboard-controls">
        <form className="leaderboard-search" onSubmit={e=>{e.preventDefault();setQ(search);setOffset(0);}}><label>搜索模型或方法<Input value={search} onChange={e=>setSearch(e.target.value)} /></label><Button>查找模型或方法</Button></form>
        <label>表格排序<select value={sort} onChange={e=>{setSort(e.target.value);setOffset(0);}}><option value="score">主指标 · 从高到低</option><option value="coverage">计分覆盖率 · 从高到低</option><option value="latency">P50 延迟 · 从低到高</option><option value="calls">模型调用 · 从低到高</option><option value="elapsed">总耗时 · 从低到高</option></select></label>
        <details className="leaderboard-advanced"><summary>高级筛选</summary><label>评测任务来源<select value={family} onChange={e=>change({family:e.target.value})}><option value="all">全部类型</option><option value="pipeline">按图完整流程</option><option value="benchmark">单任务 KIE / VQA</option><option value="qa">已发布问答</option><option value="agent">案件方法实验</option></select></label>{comparison==="methods" && ["agent","reproductions"].includes(category) && <label className="research-check"><Input type="checkbox" checked={baseline} onChange={e=>change({baseline:e.target.checked})}/>显示同条件 One-shot 对照基线</label>}</details>
      </div></details>
      <div className="leaderboard-context">
        <span className="leaderboard-scope">{effectiveScope==="official"?"正式成绩":"开发参考"}</span>
        <span>{selected?trackName(selected)+" · "+inputMode(selected)+" · "+selected.planned+(selected.family==="agent"?" 案":" 题"):"尚未形成评测成绩；下方列出已配置模型和已登记方法"}</span>
        {effectiveScope==="development" && <span>未人工复核的成绩不代表正式准确率或法律正确性。</span>}
        {pendingGold && <strong>过程对比 · 质量待评</strong>}
        <Button disabled={!data?.items.length} onClick={()=>data && download(data,category,comparison)}>导出本页 CSV</Button>
      </div>
      <ErrorText error={board.error} />
      {board.error && <p><Button onClick={()=>{change({cohort:""});void board.refetch();}}>重置评测组并重新加载</Button></p>}
      {data && !data.cohorts.length && scope==="official" && <p className="leaderboard-notice">正式榜尚无成绩。{data.summary.available_scopes.development?<Button onClick={()=>change({scope:"development"})}>查看开发参考榜（{data.summary.available_scopes.development} 组记录）</Button>:"需要审核发布的数据和可计分的真实运行。"}候选条目仍保留，未评测项不排名。</p>}
      {display==="table" ? <><div className="research-table-wrap leaderboard-table" tabIndex={0} role="region" aria-label="可滚动的模型排名表" aria-busy={board.isFetching}>
        <table><caption>{categories.find(c=>c.id===category)?.label} · {comparison==="methods"?"方法对比":"模型对比"}{selected?"："+selected.dataset_name:" · 评测候选列表"}</caption>
          <thead><tr><th scope="col">名次</th><th scope="col">模型与方法</th><th scope="col">{selected?.metric==="detection_f1"?"消息检测 F1":pendingGold?"质量分":selected?.metric==="exact_match"?"精确匹配得分":"主指标"}<small>{pendingGold?"待专家金标":selected?"固定有效参考范围":"评测后计分"}</small></th><th scope="col">评测样本</th><th scope="col">状态</th><th scope="col">耗时 / 费用</th><th scope="col">详情与来源</th></tr></thead>
          <tbody>
            {data?.items.map(r=><tr key={r.entry_id || r.model.identity} data-catalogue={r.catalogue || undefined}>
              <td><strong className="leaderboard-rank">{r.rank ?? "—"}</strong></td>
              <th scope="row"><strong>{comparison==="methods"?r.method_name:r.model.name}</strong><small>{comparison==="methods"?r.model.name:r.method_name} · {r.model.model}</small>{r.baseline && comparison==="methods" && <small>One-shot 对照基线</small>}
                {r.pipeline_models && category==="kie_enhanced" && <small>KIE：{r.pipeline_models.extractor.name}<br/>回答：{r.pipeline_models.answer.name}</small>}
                {!r.catalogue && (r.categories?.length || 0)>1 && <div className="leaderboard-tags">{r.categories!.map(c=><span key={c}>{categories.find(v=>v.id===c)?.label || c}</span>)}</div>}
              </th>
              <td><strong>{r.score==null?(r.catalogue?"未评测":r.active?"运行中":pendingGold?"待评":"未计分"):percent(r.score)}</strong>{r.score!=null && <progress aria-label={r.model.name+" 得分交付率"} value={r.score} max={1}/>}
                {r.upstream_kie && <small>KIE 抽取 F1 {percent(r.upstream_kie.score)} · {r.upstream_kie.scored}/{r.upstream_kie.eligible} 已计分</small>}
                {r.baseline_delta!=null && !r.baseline && <small>较 One-shot {r.baseline_delta>=0?"+":""}{(100*r.baseline_delta).toFixed(1)} 个百分点</small>}
                {!r.catalogue && ["kie_enhanced","agent","reproductions"].includes(category) && !r.baseline && r.baseline_delta==null && <small>无可计分的同条件基线</small>}
              </td>
              <td>{r.catalogue?<span>—</span>:<><strong>{r.scored} / {r.eligible}</strong><small>{r.eligible?percent(r.score_coverage)+" 已计分":pendingGold?"无质量金标":"无有效计分参考"}</small></>}</td>
              <td><span className="leaderboard-status" data-state={r.status}>{states[r.status] || r.status}</span>{r.unranked_reason && <small>{r.unranked_reason}</small>}{!r.catalogue && <small>失败 {r.failed} · 未知 {r.unknown} · 取消 {r.cancelled}</small>}</td>
              <td>{r.catalogue?"—":<><span>{r.elapsed_ms!=null?"总耗时 "+seconds(r.elapsed_ms):"P50 "+seconds(r.latency_p50_ms)}</span><small>{r.cost==null?"费用未记录":r.cost.toFixed(4)+" "+r.currencies.join(" / ")}{!r.cost_complete && r.cost!=null && "（部分）"}</small></>}</td>
              <td>{r.catalogue?<a href={r.href}>{r.status==="not_implemented"?"查看方法目录":"配置评测 →"}</a>:<a href={r.href}>查看运行与逐题结果 →</a>}
                <details><summary>展开详情</summary>
                  <p>{r.method_name} · {r.method?.id || "E00"}</p>
                  {!r.catalogue && <><p>已计分均分 {percent(r.conditional_score)}；已计分 {r.scored} / 有效参考 {r.eligible} / 计划 {r.planned}。</p><p>模型 {r.model_calls ?? "—"} · 工具 {r.tool_calls ?? "—"}<br/>输入 {r.input_tokens ?? "—"} / 输出 {r.output_tokens ?? "—"} token<br/>总耗时 {seconds(r.elapsed_ms ?? null)}<br/>P50 {seconds(r.latency_p50_ms)} · P95 {seconds(r.latency_p95_ms)}</p><p>{r.cost==null?"费用未记录":r.cost.toFixed(4)+" "+r.currencies.join(" / ")} · {r.cost_complete?"本组请求费用记录完整":"费用记录不完整，不按零计"}</p>{r.unreviewed>0 && <p>{r.unreviewed} 题参考未复核。</p>}<p>{r.run_name} · {r.created_at?stamp(r.created_at):"—"}</p>{r.repeated_runs>1 && <p>同配置 {r.repeated_runs} 次，采用最近一次</p>}{r.stale_code && <p>代码版本已变化，当前显示历史冻结结果。</p>}{r.engineering?.quote_spans_validated!=null && <p>已校验引文范围 {r.engineering.quote_spans_validated} 条，不代表语义正确。</p>}{Object.entries(r.failures).length>0 && <ul>{Object.entries(r.failures).map(([k,n])=><li key={k}>{k}：{n}</li>)}</ul>}</>}
                  {r.method?.paper && <p>复现范围：{r.method.reproduction_level}{!r.method.original_paper_reproduced && "（非原论文成绩）"}</p>}
                  {r.method?.implementation_version && <p>实现版本：{r.method.implementation_version}</p>}
                  {r.method?.sources?.length ? <ul>{r.method.sources.map(url=><li key={url}><a href={url} target="_blank" rel="noreferrer">来源：{url}</a></li>)}</ul>:null}
                </details>
              </td>
            </tr>)}
            {!data?.items.length && <tr><td colSpan={7}><div className="leaderboard-empty" role="status">{board.isPending?"正在读取榜单…":board.error?"暂时无法读取榜单，请检查后端服务并重试。":q?"当前搜索没有匹配的模型或方法。":inventory && !inventory.models.length && comparison==="models"?<>尚未添加模型。<a href="/evaluation.html?view=models">添加模型配置 →</a></>:"当前筛选没有条目。可重置筛选，或创建评测后查看结果。"}</div></td></tr>}
          </tbody>
        </table>
      </div>
      </> : <LeaderboardCharts rows={data?.items || []} total={data?.total || 0} comparison={comparison} metric={selected?.metric || ""}/>}
      <div className="leaderboard-footer"><span>共 {data?.total ?? 0} 个条目 · 未评测和待评项不参与排名</span><div><Button disabled={!offset} onClick={()=>setOffset(n=>Math.max(0,n-20))}>上一页排名</Button><Button disabled={data?.next_offset==null} onClick={()=>setOffset(data!.next_offset!)}>下一页排名</Button></div></div>
      <details className="leaderboard-rules"><summary>比较条件、评分口径与未纳入记录</summary>
        <p>仅同数据版本、固定题目范围、输入轨道、评分器和预算生成排名；比较模型时固定方法，比较方法时固定底座模型。开发参考与正式成绩分别展示。</p>
        <p>{pendingGold?"没有专家 CaseGold，只比较工程过程，不生成法律质量分或名次。":data?.metric_note} 名次按主指标计算；其他排序不改变名次。当前{hasBaseline?"有":"没有"}可计分的 One-shot 对照。</p>
        <p>未评测条目来自当前账号的模型配置和方法目录；表示可配置的候选，不代表已运行或已通过能力验证。目录变更不修改历史成绩。</p>
        {selected && <dl><dt>评测组</dt><dd>{selected.id}</dd><dt>数据版本</dt><dd>{selected.definition.release_hash || "开发参考，无正式发布绑定"}</dd><dt>方法、Prompt、参数、评分协议与预算</dt><dd><pre>{JSON.stringify({method:selected.definition.method,prompt:selected.definition.prompt,parameters:selected.definition.parameters,scorer:selected.definition.scorer,budget:selected.definition.budget},null,2)}</pre></dd></dl>}
        {data?.summary.excluded.length ? <ul>{data.summary.excluded.map(e=><li key={e.reason}>{e.label}：{e.count}</li>)}</ul>:null}
        <p>每 15 秒刷新保存的结果，不会调用模型。{data?"更新于 "+stamp(data.generated_at):""}</p>
      </details>
    </Card>
  </section>;
}

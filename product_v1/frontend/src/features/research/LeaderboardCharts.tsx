import { useState } from "react";
import { Button } from "../../components/ui";
import type { Entry } from "./Leaderboard";
const metrics=[
  {id:"quality",label:"质量表现",unit:"%",direction:"越高越好"},
  {id:"tokens",label:"Token 用量",unit:"token / 全运行",direction:"越少越好"},
  {id:"cost",label:"请求费用",unit:"",direction:"越低越好"},
  {id:"time",label:"执行耗时",unit:"秒",direction:"越短越好"}
];
export function LeaderboardCharts({rows,total,comparison,metric}:{rows:Entry[];total:number;comparison:string;metric:string}){
  const [selected,setSelected]=useState("quality"),[currency,setCurrency]=useState(""),[clock,setClock]=useState("elapsed");
  const current=metrics.find(m=>m.id===selected)!;
  const evaluated=rows.filter(r=>!r.catalogue && !r.active);
  const currencies=[...new Set(evaluated.filter(r=>r.cost!=null && r.cost_complete && r.currencies.length===1).map(r=>r.currencies[0]))].sort();
  const chosenCurrency=currencies.includes(currency)?currency:currencies[0];
  function value(r:Entry):number|null{
    if(selected==="quality")return r.score;
    if(selected==="tokens")return r.input_tokens!=null && r.output_tokens!=null?r.input_tokens+r.output_tokens:null;
    if(selected==="cost")return r.cost_complete && r.currencies.length===1 && r.currencies[0]===chosenCurrency?r.cost:null;
    const ms=clock==="elapsed"?r.elapsed_ms:r.latency_p50_ms;return ms==null?null:ms/1000;
  }
  function label(r:Entry){return comparison==="methods"?r.method_name:r.model.name;}
  function formatted(n:number){return selected==="quality"?(n*100).toFixed(1)+"%":selected==="cost"?n.toFixed(4)+" "+chosenCurrency:selected==="time"?n.toFixed(2)+" s":n.toLocaleString()+" token";}
  const measured=evaluated.filter(r=>value(r)!=null).sort((a,b)=>selected==="quality"?value(b)!-value(a)!:value(a)!-value(b)!);
  const maximum=selected==="quality"?1:Math.max(...measured.map(r=>value(r)!),1);
  const unavailable=evaluated.filter(r=>value(r)==null);
  const points=evaluated.filter(r=>r.score!=null && r.cost!=null && r.cost_complete && r.currencies.length===1 && r.currencies[0]===chosenCurrency);
  const maxCost=Math.max(...points.map(r=>r.cost!),.0001);
  return <div className="leaderboard-analysis">
    <div role="group" aria-label="分析指标" className="leaderboard-metric-tabs">{metrics.map(m=><Button key={m.id} aria-pressed={selected===m.id} onClick={()=>setSelected(m.id)}>{m.label}</Button>)}</div>
    <div className="leaderboard-chart-heading"><div><h2>{current.label}</h2><p>{selected==="quality"?(metric==="detection_f1"?"消息检测 F1":"固定参考范围内的得分交付率"):selected==="tokens"?"输入＋输出 Token；统计整个运行":selected==="cost"?"已记录完整的本组请求费用":"按同一种耗时口径比较"} · {current.direction}</p></div>
      {selected==="cost" && currencies.length>1 && <label>费用币种<select value={chosenCurrency} onChange={e=>setCurrency(e.target.value)}>{currencies.map(c=><option key={c}>{c}</option>)}</select></label>}
      {selected==="time" && <label>耗时口径<select value={clock} onChange={e=>setClock(e.target.value)}><option value="elapsed">全运行耗时</option><option value="p50">单次请求 P50</option></select></label>}
    </div>
    {measured.length ? <ol className="leaderboard-bars" aria-label={current.label+"对比图"}>{measured.map(r=><li key={r.entry_id || r.model.identity}>
      <div><a href={r.href}>{label(r)}</a><small>{comparison==="methods"?r.model.name:r.method_name}</small></div>
      <div className="leaderboard-bar-track"><span style={{width:(100*value(r)!/maximum)+"%"}}/></div><strong>{formatted(value(r)!)}</strong>
    </li>)}</ol>:<div className="leaderboard-chart-empty" role="status">{selected==="quality" && metric==="awaiting_expert_gold"?"待专家金标，当前没有质量分。可以查看 Token、费用或耗时。":"当前评测组没有可用于此图的完整记录。"}</div>}
    <p className="leaderboard-chart-note">图表使用本页 {evaluated.length} 个已结束运行；候选、运行中和缺失指标不补零。{total>rows.length?"可翻页查看其他条目。":""}{selected==="cost"?"不同币种分别展示，部分费用不参与费用排序。":""}</p>
    {unavailable.length>0 && <details><summary>{unavailable.length} 个运行未绘入此指标</summary><ul>{unavailable.map(r=><li key={r.entry_id || r.model.identity}>{label(r)}：{selected==="cost" && r.cost!=null?"费用不完整或属于其他币种":"未记录此指标"}</li>)}</ul></details>}
    {selected==="quality" && <details className="leaderboard-efficiency"><summary>质量与费用关系</summary><p>同一评测组中，越靠左费用越低、越靠上质量越高。仅使用费用完整且同币种的记录。</p>{currencies.length>1 && <label>关系图币种<select value={chosenCurrency} onChange={e=>setCurrency(e.target.value)}>{currencies.map(c=><option key={c}>{c}</option>)}</select></label>}
      {points.length>=2?<svg viewBox="0 0 640 320" role="group" aria-label="同条件质量与费用关系图">
        {[0,.25,.5,.75,1].map(v=><g key={v}><line x1="65" x2="600" y1={270-v*220} y2={270-v*220}/><text x="55" y={274-v*220} textAnchor="end">{100*v}%</text></g>)}
        <line x1="65" x2="65" y1="50" y2="270"/><text x="65" y="294">0</text><text x="600" y="294" textAnchor="end">{maxCost.toFixed(4)+" "+chosenCurrency}</text><text x="65" y="25">主指标 ↑</text><text x="330" y="316" textAnchor="middle">本组请求费用 →</text>
        {points.map(r=><a key={r.entry_id || r.model.identity} href={r.href} aria-label={label(r)+"，得分 "+(100*r.score!).toFixed(1)+"%，费用 "+r.cost+" "+chosenCurrency}><circle cx={65+535*r.cost!/maxCost} cy={270-220*r.score!} r="7"><title>{label(r)+" · "+(100*r.score!).toFixed(1)+"% · "+r.cost+" "+chosenCurrency}</title></circle><text x={Math.min(500,76+535*r.cost!/maxCost)} y={260-220*r.score!}>{label(r)}</text></a>)}
      </svg>:<p>至少需要两个同条件、同币种且质量与费用均完整的运行，才能绘制关系图。</p>}
    </details>}
  </div>;
}

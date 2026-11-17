import { cleanup,fireEvent,render,screen } from "@testing-library/react";
import { afterEach,expect,it } from "vitest";
import { LeaderboardCharts } from "./LeaderboardCharts";
import type { Entry } from "./Leaderboard";
afterEach(cleanup);
const row={entry_id:"a",model:{name:"Alpha",model:"alpha",identity:"a"},method_name:"One-shot",href:"/evaluation.html?view=runs",score:.5,cost:.01,cost_complete:true,currencies:["CNY"],input_tokens:100,output_tokens:20,elapsed_ms:2300,latency_p50_ms:100,status:"completed"} as Entry;
it("keeps unscored Agent quality empty while exposing recorded usage",()=>{
  render(<LeaderboardCharts rows={[{...row,score:null}]} total={1} comparison="methods" metric="awaiting_expert_gold"/>);
  expect(screen.getByRole("status")).toHaveTextContent("待专家金标");
  expect(screen.queryByRole("list",{name:"质量表现对比图"})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"Token 用量"}));
  expect(screen.getByRole("list",{name:"Token 用量对比图"})).toHaveTextContent("120 token");
});
it("separates currencies and excludes partial costs rather than charting them as totals",()=>{
  render(<LeaderboardCharts rows={[row,{...row,entry_id:"b",model:{...row.model,name:"Beta"},currencies:["USD"],cost:.2},{...row,entry_id:"c",cost:10,cost_complete:false}]} total={3} comparison="models" metric="exact_match"/>);
  fireEvent.click(screen.getByRole("button",{name:"请求费用"}));
  expect(screen.getByRole("list",{name:"请求费用对比图"}).querySelectorAll("li")).toHaveLength(1);
  fireEvent.change(screen.getByLabelText("费用币种"),{target:{value:"USD"}});
  expect(screen.getByRole("list",{name:"请求费用对比图"})).toHaveTextContent("Beta");
  expect(screen.getByRole("list",{name:"请求费用对比图"})).toHaveTextContent("0.2000 USD");
});
it("keeps total runtime separate from per-request latency",()=>{
  render(<LeaderboardCharts rows={[row]} total={1} comparison="models" metric="exact_match"/>);
  fireEvent.click(screen.getByRole("button",{name:"执行耗时"}));
  expect(screen.getByRole("list",{name:"执行耗时对比图"})).toHaveTextContent("2.30 s");
  fireEvent.change(screen.getByLabelText("耗时口径"),{target:{value:"p50"}});
  expect(screen.getByRole("list",{name:"执行耗时对比图"})).toHaveTextContent("0.10 s");
});

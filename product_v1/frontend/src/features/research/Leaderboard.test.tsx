import { cleanup,fireEvent,render,screen,waitFor } from "@testing-library/react";
import { afterEach,beforeEach,expect,it,vi } from "vitest";
import { QueryClient,QueryClientProvider } from "@tanstack/react-query";
import { Leaderboard } from "./Leaderboard";
import { api } from "../../api/client";
vi.mock("../../api/client",()=>({api:vi.fn()}));
afterEach(cleanup);
const cohort={id:"cohort-test",family:"qa",dataset_name:"冻结评测集",scope:"official",track:"text",metric:"exact_match",models:1,eligible:2,planned:2,updated_at:"2026-10-29T00:00:00Z",definition:{release_hash:"released",parameters:{temperature:0},scorer:"v1"}};
const entry={rank:2,model:{name:"Alpha",model:"model-alpha",identity:"alpha"},run_id:"run",run_name:"真实冻结运行",created_at:"2026-10-29T00:00:00Z",status:"completed",href:"/evaluation.html?view=runs&run=run",method_name:"直接回答",planned:2,eligible:2,scored:1,score:.5,conditional_score:1,score_coverage:.5,response_coverage:.5,failed:1,unknown:0,cancelled:0,unreviewed:0,latency_p50_ms:1200,latency_p95_ms:1200,cost:null,cost_complete:false,currencies:[],failures:{network:1},unranked_reason:null,repeated_runs:2};
function response(overrides={}){return {cohorts:[cohort],selected_cohort_id:cohort.id,items:[entry],total:1,next_offset:null,generated_at:"2026-10-29T00:00:00Z",summary:{available_scopes:{official:1},excluded:[]},metric_note:"失败仍保留在固定参考分母中",...overrides};}
beforeEach(()=>{history.replaceState({},"","/evaluation.html?view=leaderboard");vi.mocked(api).mockReset();vi.mocked(api).mockResolvedValue(response());});
function view(){return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><Leaderboard/></QueryClientProvider>);}
it("shows rank, score coverage, missing cost and the actual source run",async()=>{
  view();await screen.findByRole("row",{name:/Alpha/});
  const row=screen.getByRole("row",{name:/Alpha/});
  expect(row).toHaveTextContent("50.0%");
  expect(row).toHaveTextContent("1 / 2");
  expect(row).toHaveTextContent("未记录");
  expect(row).toHaveTextContent("同配置 2 次，采用最近一次");
  expect(screen.getByRole("link",{name:"查看运行与逐题结果 →"})).toHaveAttribute("href",entry.href);
  fireEvent.change(screen.getByLabelText("表格排序"),{target:{value:"latency"}});
  await waitFor(()=>expect(vi.mocked(api).mock.calls.at(-1)?.[0]).toContain("sort=latency"));
  expect(row).toHaveTextContent("2");
});
it("keeps development records separate and makes an empty formal board actionable",async()=>{
  history.replaceState({},"","/evaluation.html?view=leaderboard&board_scope=official");
  vi.mocked(api).mockImplementation(async path=>path.includes("scope=development")?response({cohorts:[{...cohort,scope:"development"}]}):response({cohorts:[],items:[],selected_cohort_id:null,summary:{available_scopes:{development:2},excluded:[{reason:"probe",label:"连通性测试与试跑不计分",count:3}]}}));
  view();await screen.findByText(/正式榜尚无成绩/);
  fireEvent.click(screen.getByRole("button",{name:"查看开发参考榜（2 组记录）"}));
  await screen.findByRole("row",{name:/Alpha/});
  expect(screen.getByText(/不代表正式准确率或法律正确性/)).toBeVisible();
  expect(new URL(location.href).searchParams.get("board_scope")).toBe("development");
});
it("preserves filter state after an API failure and offers retry",async()=>{
  vi.mocked(api).mockRejectedValue(new Error("网络中断"));
  view();await screen.findByRole("alert");
  expect(screen.getByRole("alert")).toHaveTextContent("网络中断");
  expect(screen.getByLabelText("榜单性质")).toHaveValue("auto");
  expect(screen.getByRole("button",{name:"重置评测组并重新加载"})).toBeEnabled();
});

it("switches all four categories, selects the appropriate comparison axis and clears stale cohort",async()=>{
  history.replaceState({},"","/evaluation.html?view=leaderboard&cohort=old-cohort");
  view();await screen.findByRole("row",{name:/Alpha/});
  const nav=screen.getByRole("navigation",{name:"比较类别"});
  expect(nav.querySelectorAll("button")).toHaveLength(4);
  fireEvent.click(screen.getByRole("button",{name:/KIE 增强/}));
  await waitFor(()=>expect(vi.mocked(api).mock.calls.at(-1)?.[0]).toContain("category=kie_enhanced"));
  expect(screen.getByLabelText("比较方式")).toHaveValue("models");
  expect(new URL(location.href).searchParams.has("cohort")).toBe(false);
  fireEvent.click(screen.getByRole("button",{name:/推断方法复现/}));
  await waitFor(()=>expect(vi.mocked(api).mock.calls.at(-1)?.[0]).toContain("comparison=methods"));
  expect(screen.getByLabelText("显示同条件 One-shot 对照基线")).toBeChecked();
  expect(new URL(location.href).searchParams.get("board_category")).toBe("reproductions");
  expect(vi.mocked(api).mock.calls.at(-1)?.[0]).toContain("include_baseline=true");
});
it("shows Agent measurements with pending quality instead of a zero quality score",async()=>{
  vi.mocked(api).mockResolvedValue(response({
    cohorts:[{...cohort,family:"agent",metric:"awaiting_expert_gold",track:"case_analysis",eligible:0,planned:1,entries:1,fixed_model_name:"Alpha"}],
    items:[{...entry,entry_id:"agent-method",method_name:"Verifier",rank:null,score:null,conditional_score:null,eligible:0,scored:0,score_coverage:null,model_calls:3,tool_calls:2,input_tokens:100,output_tokens:30,elapsed_ms:2300,unranked_reason:"待专家金标，暂不生成质量名次",href:"/evaluation.html?view=agents&agent_run=a&case=c"}]
  }));
  view();fireEvent.click(screen.getByRole("button",{name:/^Agent/}));
  await screen.findByRole("row",{name:/Verifier/});
  expect(screen.getByText("过程对比 · 质量待评")).toBeVisible();
  expect(screen.getByRole("row",{name:/Verifier/})).toHaveTextContent("模型 3 · 工具 2");
  expect(screen.getByRole("row",{name:/Verifier/})).toHaveTextContent("总耗时 2.30 s");
  expect(screen.queryByRole("progressbar",{name:/得分交付率/})).not.toBeInTheDocument();
  expect(screen.getByRole("link",{name:"查看运行与逐题结果 →"})).toHaveAttribute("href","/evaluation.html?view=agents&agent_run=a&case=c");
});

it("keeps an unranked candidate list visible without a result group",async()=>{
  vi.mocked(api).mockResolvedValue(response({scope:"development",cohorts:[],selected_cohort_id:null,
    items:[{...entry,catalogue:true,entry_id:"candidate",rank:null,score:null,conditional_score:null,score_coverage:null,eligible:0,scored:0,run_id:null,status:"not_evaluated",unranked_reason:"尚未评测"}],
    inventory:{models:[{config_id:"alpha",name:"Alpha",model:"model-alpha"}],methods:[{id:"E00",name:"One-shot",categories:["oneshot"],available:true}]}}));
  view();
  const row=await screen.findByRole("row",{name:/Alpha/});
  expect(row).toHaveTextContent("未评测");
  expect(row).not.toHaveTextContent("0.0%");
  expect(screen.getByRole("table")).toBeVisible();
  expect(screen.getByLabelText("榜单性质")).toHaveValue("auto");
  expect(screen.getByRole("link",{name:"配置评测 →"})).toBeVisible();
});
it("keeps table structure during an unavailable backend",async()=>{
  vi.mocked(api).mockRejectedValue(new Error("连接中断"));
  view();await screen.findByRole("alert");
  expect(screen.getByRole("table")).toBeVisible();
  expect(screen.getByRole("status")).toHaveTextContent("暂时无法读取榜单");
});

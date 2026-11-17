import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "../../components/ui";
import { Icon, type IconName } from "../../components/icons";
import { ProductHeader } from "../../components/shell/ProductHeader";
import { useUser } from "../auth/AuthGate";
import { api } from "./client";
import { ErrorText } from "./shared";
import { ReviewDesk } from "./ReviewDesk";
import { ScreenshotReviewPanel } from "./ScreenshotReviewPanel";
import { DataStudio } from "./DataStudio";
import { EvaluationLab } from "./EvaluationLab";
import { OperationsPanel } from "./OperationsPanel";
import { AuditPanel } from "./AuditPanel";
const products: { id: string; title: string; english: string; icon: IconName; description: string }[] = [
  { id: "evaluation", title: "评测台", english: "EVALUATION LAB", icon: "evaluation", description: "比较模型与推断方法的效果、稳定性和成本，查看逐题结果。" },
  { id: "studio", title: "合成生成台", english: "DATA STUDIO", icon: "studio", description: "根据已有材料生成待审核的聊天样本。生成后，还需要人工核对才能发布。" },
  { id: "review", title: "数据审核台", english: "REVIEW DESK", icon: "review", description: "按消息核对截图，保留原始标注，独立保存修正与合成审核意见。" },
];
export function ResearchApp({ product }: { product: string }) {
  const current = products.find(p => p.id === product)!;
  const user = useUser();
  const client = useQueryClient();
  const [error, setError] = useState("");
  const params = new URLSearchParams(location.search);
  const legacyReview = params.get("view") === "library" || params.has("sample") || params.has("page") || params.has("section");
  const operations = params.get("operations") === "1";
  const audit = !operations && params.get("audit") === "1";
  const title = operations ? "工作进展" : audit ? "操作记录" : current.title;
  return <div className="research-shell">
    <a className="skip-link" href="#research-main">跳转到工作区</a>
    <ProductHeader product={product}>
      <span className="account-name" title={user?.username}><span className="account-avatar" aria-hidden="true">{(user?.display_name || user?.username || "SL").slice(0, 1)}</span>{user?.display_name || user?.username}</span>
      <Button variant="ghost" onClick={async () => { try { await api("/auth/logout", {}); client.clear(); window.location.reload(); } catch (e) { setError(String(e)); } }}><Icon name="logout" size={16} />退出</Button>
    </ProductHeader>
    <div className="context-bar">
      <span><Icon name={current.icon} size={16} />研究工作区<span className="context-separator" aria-hidden="true">/</span><a href={"/" + product + ".html"} aria-current={!operations && !audit ? "page" : undefined}>{current.title}</a>{(operations || audit) && <><span className="context-separator" aria-hidden="true">/</span><strong>{title}</strong></>}</span>
      <div className="context-links"><a href={"/" + product + ".html?operations=1"} aria-current={operations ? "page" : undefined}><Icon name="timeline" size={15} />流程与结果</a><a href={"/" + product + ".html?audit=1"} aria-current={audit ? "page" : undefined}><Icon name="history" size={15} />操作审计</a></div>
    </div>
    <main className="research-main" id="research-main" tabIndex={-1}>
      <div className="research-title">
        <div className="research-title-copy"><p className="eyebrow">LEGAL INTELLIGENCE / {operations ? "OPERATIONS" : audit ? "ACTIVITY LOG" : current.english}</p><h1>{title}</h1><p>{operations ? "先看本轮结论和下一步，需要时再展开过程。" : audit ? "查清谁在什么时候做了什么，以及为什么没有完成。" : current.description}</p></div>
        <span className="research-title-mark" aria-hidden="true"><Icon name={operations ? "timeline" : audit ? "history" : current.icon} size={30} /></span>
        <details className="research-getting-started"><summary>第一次使用？了解三个操作台怎么配合</summary><ol><li><a href="/studio.html">生成候选样本</a>：从已有材料制作新的聊天样本。</li><li><a href="/review.html">审核样本</a>：核对截图、原文和答案，留下修改意见；模型分数只供参考。</li><li><a href="/evaluation.html?view=runs">运行已发布问答评测</a>：使用审核后发布的固定样本比较模型回答。</li></ol><p>“发布”会保存一份固定的评测集；“标准答案（金标）”指人工核对过、可以用于计分的答案。</p></details>
      </div>
      <ErrorText error={error} />
      {product === "review" && !operations && !audit && <div className="research-panel-links"><a href="/review.html" aria-current={!legacyReview ? "page" : undefined}>截图逐条审核</a><a href="/review.html?view=library" aria-current={legacyReview ? "page" : undefined}>样本库、KIE / VQA 与发布</a></div>}
      {operations ? <OperationsPanel /> : audit ? <AuditPanel product={product} /> : product === "review" ? legacyReview ? <ReviewDesk /> : <ScreenshotReviewPanel /> : product === "studio" ? <DataStudio /> : <EvaluationLab />}
    </main>
  </div>;
}

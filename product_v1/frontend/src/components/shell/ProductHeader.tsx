import type { ReactNode } from "react";
import { Icon, Logo, type IconName } from "../icons";

const products: { id: string; href: string; title: string; english: string; icon: IconName }[] = [
  { id: "workbench", href: "/", title: "用户工作台", english: "Case Workbench", icon: "folder" },
  { id: "evaluation", href: "/evaluation.html", title: "评测台", english: "Evaluation Lab", icon: "evaluation" },
  { id: "studio", href: "/studio.html", title: "合成生成台", english: "Data Studio", icon: "studio" },
  { id: "review", href: "/review.html", title: "数据审核台", english: "Review Desk", icon: "review" },
];
export function ProductHeader({ product, children, english = false }: { product: string; children?: ReactNode; english?: boolean }) {
  return <header className="product-header">
    <a href="/" className="product-brand"><Logo /><span><strong>ScreenshotLegal</strong><small>{english ? "LEGAL INTELLIGENCE WORKSPACE" : "法律科技 · 电子证据工作空间"}</small></span></a>
    <div className="product-switcher" role="group" aria-label={english ? "Products" : "产品入口"}>{products.map(p => <a key={p.id} href={p.href} aria-current={product === p.id ? "page" : undefined}><Icon name={p.icon} size={18} /><span>{english ? p.english : p.title}</span></a>)}</div>
    <div className="product-account"><a href="/?account=1">{english ? "Account & permissions" : "账号与权限"}</a>{children}</div>
  </header>;
}

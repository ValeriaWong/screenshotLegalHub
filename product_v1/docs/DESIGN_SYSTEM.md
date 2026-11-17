# 可替换的前端设计系统

Tokens 位于 `src/design-system/tokens.css`：foundation（font/spacing/radius/shadow/z-index）、semantic（background/surface/text/muted/border/primary/success/warning/danger/info/ai）、component（button/rail/bbox）、motion（duration/easing/enabled/reduced）。布局 CSS 位于 `styles/app.css`，Feature 不硬编码品牌 HEX/rgb。

UI 适配层在 `components/ui`，图标在 `components/icons`，动效 hooks 在 `components/motion`。本版使用原生语义 HTML primitives，没有复制 Holmes UI 或绑定第三方组件库。将来换库只改适配层与 tokens；**不允许改变 Feature API / Domain Schema**。

AppShell 统一案件头、导航、工作区和 DetailRail。详情通过 discriminated DetailContentDescriptor 传入，支持 open/close/collapse/range resize，宽度存 localStorage。右栏自动聚焦标题，Escape 关闭；桌面为共享侧栏，小屏固定覆盖，可关闭后继续操作工作区。

Source Navigation 独占来源解析与 URL/ViewerContent 构造。Timeline、Matrix、Claims、Findings、Review 统一使用 Citations；页面不各自创建 SourceViewer。图片按原图尺寸计算百分比高亮，浏览器缩放仍定位一致；无 bbox 显示整图。PDF iframe/音视频类型与图片分离。

URL 保存 tab/case/run/filter/search/date；TanStack Query 负责 loading/error/empty/not-run，业务 review_status 负责 stale。功能级 ErrorBoundary 限制渲染错误范围。

固定 UI 字典在 `i18n/`，支持 zh-CN/en；法律内容保留原始中文，审计 payload 字段保留技术键。支持键盘、焦点可见、语义表格、文字状态，axe 检查 critical/serious violation。复杂动效/视差只能加入 motion 层，并遵循 prefers-reduced-motion；业务流程不得依赖动画完成事件。

## 2026-10-25 法律科技 UI/UX 重构

四产品共享 `ProductHeader`、SVG 图标和语义 tokens。用户工作台的案件选择移入侧栏，窄屏下案件工具使用原生 details 折叠；四项工作区功能保持。研究侧保留各自的页签、审核画布、预算、流程与审计入口。Button 支持 primary / secondary / ghost，Badge 支持带文字的状态语义。

具体颜色、字体、间距、断点与维护规则见 [ScreenshotLegal 设计规范](../frontend/design-system/screenshotlegal/MASTER.md)。界面截图及回归结果见 [UI/UX 重构验收](../reports/ui-ux-refactor-2026-10-25/REPORT.md)。

## 长列表展示（2026-10-25）

统一组件位于 `components/collections`：`Paged` 提供有总数的分页与检索，`SearchableSelect` 限制原生 option 的挂载数量并保留当前选择。已有后端分页沿用原接口。表格检索与分页位于横向滚动区外；跨页多选与评论草稿由上层持有。详见[长列表规范](../frontend/design-system/screenshotlegal/pages/collections.md)与[验收报告](../reports/long-lists-2026-10-25/REPORT.md)。

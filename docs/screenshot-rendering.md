# 截图生成与样式排版修改指南

更新：2026-11-06。适用于 V2 最近多轮合成/重建截图、V3 校准图片及相关历史渲染代码。

本轮微信样式预览：[两张样图](../reports/wechat_style_preview_20261106/index.html)。采用 GitHub 微信聊天模板的布局参考，修正居中标题、头像、气泡间距、输入栏、底部安全区和转账卡片；消息内容与日期精度沿用原数据。历史数据集及 V3 冻结图片未重绘。

## 图片如何生成

最近批次使用统一的样式模板：Python 根据结构化对话生成 HTML/CSS，再由本地 Chromium 渲染并截图为 PNG，没有调用 AI 绘图模型。对话内容与界面样式分别由 JSON 和代码维护。

200 条是来源处理清单；具备足够通信材料的候选才生成对应截图，来源缺口保持缺口。旧库导入的原有图片也不代表本轮重新绘制。

```text
case.json（人物、会话、消息）
    ↓ Python 生成 HTML/CSS
Chromium 计算布局、分页
    ↓ 截图并读取消息坐标
screenshots/*.png + render.json
```

## 主要修改入口

核心文件是 [tools/render_v2_round2.py](../tools/render_v2_round2.py)。虽然文件名叫 round2，后续多轮继续复用它。

微信样式放在 [tools/templates/wechat.css](../tools/templates/wechat.css)，加载时追加到 Python 的基础 `CSS`。新样式仅作用于 `.phone.wechat`；WhatsApp 和中性摘录保留基础样式。[GitHub 参考、提交号和资源说明](../tools/templates/SOURCES.md)。

| 想修改什么 | 代码位置 |
|---|---|
| 字体、字号、气泡颜色和宽度、间距、头像、时间标签、背景 | [微信 CSS](../tools/templates/wechat.css)；其余平台的基础 CSS 位于渲染器 |
| 普通消息、文件、转账卡片、附件表格的 HTML 结构 | [message_html()](../tools/render_v2_round2.py) |
| 顶部状态栏、聊天标题、底部输入栏、研究样本标记 | [phone_html()](../tools/render_v2_round2.py) |
| 本地装饰头像、语音/表情/加号图标 | [avatar_html() / toolbar_icon()](../tools/render_v2_round2.py) |
| 每页容纳消息数、跨页重复、长消息滚动裁切 | [render_case() 分页逻辑](../tools/render_v2_round2.py) |
| 页面尺寸与截图倍率 | [WIDTH、HEIGHT、SCALE](../tools/render_v2_round2.py#L13) |
| 实际截图动作 | [Browser.capture()](../tools/render_v2_round2.py) |

常用 CSS 选择器：

```css
.phone          /* 整体界面 */
.phone.wechat   /* 新版微信样式；不要应用于未知载体的摘录 */
.header         /* 聊天标题栏 */
.content        /* 消息区域 */
.row            /* 单条消息及间距 */
.bubble         /* 消息气泡 */
.bubble-column  /* 气泡所在容器，改宽度时也要检查 */
.avatar         /* 头像 */
.stamp          /* 日期/时间标签 */
.wa             /* WhatsApp 界面根元素，其后代样式有专属覆盖 */
```

例如微信气泡主要看 `.wechat .bubble`、`.wechat .out .bubble` 和 `.wechat .bubble-column`；WhatsApp 还要检查 `.wa .bubble` 等覆盖规则。只调整气泡宽度而不调整容器宽度，可能仍受父容器限制。

默认布局为 **430×932 CSS 像素，2 倍截图，输出 860×1864 PNG**。CSS 中也写有固定宽高，因此只修改 Python 的 WIDTH/HEIGHT 不足以完成尺寸调整。若改变输出尺寸，还需核对相关校验脚本中的固定尺寸断言和坐标边界。

## 各批次额外的样式与调用关系

### 第五、六轮

[tools/v2_full_queue.py 的 render_authored_case()](../tools/v2_full_queue.py#L93) 会针对带有 `source_medium` 的材料追加中性通信摘录 CSS，覆盖背景、气泡、底栏及标记等。修改主模板后，若发现某些截图没有预期变化，应检查这里追加的规则。

[tools/v2_peer_round.py 的 render_current_case()](../tools/v2_peer_round.py#L68) 是第六轮的展示适配入口，处理近似时间、语音转述和原始载体标记，再调用第五轮包装和基础渲染器。

```text
第六轮 render_current_case()
    ↓
第五轮 render_authored_case()（可能追加中性样式）
    ↓
render_v2_round2.render_case()
    ↓
message_html() + CSS → Chromium → PNG / render.json
```

### V3 校准图片

[tools/prepare_v3_calibration.py 的 render_variant()](../tools/prepare_v3_calibration.py#L155) 有自己的页面外壳、分页条件和 CSS 覆盖，例如隐藏合成分钟、移除聊天背景。

同时，[构建入口加载冻结副本中的渲染器](../tools/prepare_v3_calibration.py#L199)，冻结位置由 [configs/v3/calibration_scenarios.json 的 source_baseline](../configs/v3/calibration_scenarios.json) 决定。当前配置指向 `datasets/v3.0.0/baseline_20261023_001`。

因此，只修改当前 `tools/render_v2_round2.py` 不会自动改变现有 V3 构建所用模板。调整 V3 时应使用新的样式/构建版本，并明确其渲染器来源，保留已有冻结快照。

新的 V3 冻结批次如果包含带 `phone_html()` 的渲染器，`render_variant()` 会为中文场景使用同一微信外壳；旧冻结渲染器继续走原布局。未来快照输入清单已补入 `tools/templates/wechat.css` 和来源说明。当前 `source_baseline` 未切换。

### 第一轮旧版

第一轮另用 Pillow 根据坐标绘制界面，相关代码在 [legalhub/synthesis.py](../legalhub/synthesis.py#L388)，其渲染清单标记为 `local-pillow-chat-ui-v1`，采用 540×960 布局。它与后来的 HTML/CSS 模板是两套实现。

## 修改后如何生效

只生成本轮两张样式样图（输出目录必须为新的 `reports/` 子目录）：

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/preview_wechat_style.py --output reports/wechat_style_preview_next
```

脚本选取第六轮两段既有对话，共 11 条消息；在 `provenance.json` 中记录来源哈希、选取及省略的消息 ID。每张图附更新后的 `render.json` 坐标，并核验嵌套卡片、文字换行、标题居中、日期精度、图片尺寸和来源未改动。输出有 `index.html` 和 `verification.json`。截图不联网、不调用模型。

1. 先选一个案件，复制到新的样式预览目录，调整 CSS 或 HTML 结构并重新渲染。
2. 检查文字溢出、气泡宽度、日期和发言者显示、转账/文件卡片、长消息裁切及分页。
3. 样式确认后，按新版本批量生成图片，同时重新生成 `render.json` 中的消息框、相关图片哈希和任务图片引用。
4. 需要在 admin 查看新图片时，再同步新版本到产品运行库，见 [全仓库同步与备份说明](../product_v1/docs/MIGRATION.md)。

注意两个已有行为：

- 直接运行 `tools/render_v2_round2.py` 的 main 默认处理 `round_002`，并非直接重绘全部 200 条清单。
- 第六轮构建会跳过已存在且通过校验的版本，也可能复用父轮图片，见 [已有版本检查](../tools/v2_peer_round.py#L117) 和 [图片复用分支](../tools/v2_peer_round.py#L128)。只改 CSS 后重跑 build，可能不会触发重绘。

admin 保存的是已导入的图片副本；修改 CSS 或数据集中的 HTML，不会自动改变 admin 当前展示的旧图。需要重新渲染、更新坐标和哈希并同步新版本。既有图片和冻结记录应保留，避免让旧哈希及来源引用失效。

## 坐标与后续模型评测

现存消息行、气泡和元素框的粒度不同，评测前需固定bbox_scope。程序参考框、模型预测和语义支持标签分别保存，详见[坐标、代码检索与证据回溯评测](coordinate-retrieval-evaluation.md)。

本轮验证：34 项 V2 回归、41 项 V3 回归通过；长消息生成 9 个连续滚动片段，消息 ID 和原文保持一致、视口覆盖完整。两张样图均为 860×1864 PNG，等待用户视觉检查。

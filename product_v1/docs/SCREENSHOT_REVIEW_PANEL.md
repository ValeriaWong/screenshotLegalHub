# 截图审核面板与 B 修正包

更新日期：2026-11-06。

实现以用户给出的四项修正为准。PDF 提供 Pack 3 配色、单列审核布局、原图、气泡列表、当前消息快捷条和整图索引；数据范围、原始字段、事实约束、锁定与恢复使用本文约定。

## 入口与样式范围

- 数据审核：/review.html。旧 KIE/VQA、导入、质量检查与发布工作区在 /review.html?view=library；原有 sample/section/page 深链接继续可用。
- 合成生成：/studio.html → 从 B 修正包重生成。
- 评测：/evaluation.html。
- 管理控制台：/console.html。
- 仅 research.tsx 和 console.tsx 加载 pack3.css，并设置根元素主题属性。用户工作台入口 main.tsx 不加载这套主题。

浅色使用 #e9e7e1 背景、#f7f5f0 表面和 #b97a0e/#f5a623 强调色；深色使用 #14161a、#1e2126 和 #f5a623。审核内容最大宽度 768px，底部固定当前消息操作，支持窄屏和系统深色模式。

## A 的实际范围

先选来源并预检，查看 JSON、图片哈希、消息映射和逐条异常，再建立固定清单。预检不创建审核记录；存在排除项时必须明确确认范围。

| 已有来源 | 当前分类 | 处理 |
|---|---|---|
| image_structured_info.json | unverified | 450 条记录中 432 条可载入，共 4,143 条消息；18 条解析异常单列展示 |
| Qwen2.5-VL-32B-Instruct_evidence_outputs.json | automatic_prediction | 模型预测，不能直接作人工金标 |
| screenshot_legal_annotations.json | human_tool_export_unverified | LabelU 工具导出；继续在原 KIE/VQA 工作区核对 |
| wechat_screen_vqa_dataset/train、val、test.json | annotation_export_unverified | COCO 检测区域，不能由 split 名称推断是 KIE 人工精标 |
| 论文记载的 39,477 条训练消息 | automatic_preannotation | 当前未找到已认证对应的训练 JSON，不混入清单 |
| 论文记载的 143 张人工核对评估截图 | 论文描述 | 当前旧 JSON 缺少与该子集逐条对应的来源证明，不冒认为该评估集 |

清单建立后固定源快照、图像哈希、消息索引与打乱顺序，A/B 分开存储。中性编号不取代导出包里的来源路径。

可重新生成来源清单，不写入实际审核库：

    python tools/audit_screenshot_sources.py --output reports/screenshot-panel-2026-11-06/source-audit.json

## 原始多模态字段与修正层

原始 JSON 整体冻结，显示模型只负责映射 speaker/text/time/side，不覆盖来源。原始字段名、消息索引、未知字段和嵌套 JSON 字符串均保留。

导出同时提供 original_json、original_messages、message_mapping、reviews、item_review、added_messages、corrected_json 与 corrected_messages：

- 文字、说话人、时间修正回写对应原始字段名；默认时间未知，不补造。
- “多余一条”只从修正消息中排除，原始 JSON 和删除判项仍在包内。
- “漏消息”有独立 ID、插入位置和附加字段。
- 多模态补丁递归合并现有字段；未修改的 image/transfer/file/message_bbox/未知字段保持原值。
- 框坐标校验 min/max 有效性。不能通过附加字段补丁绕过文字、说话人、时间或消息 ID 的专用判项。
- 存疑消息列入 unresolved_message_ids；导出不等于人工金标认证。
- 原标注缺少 side 时，左右气泡仅为显示推断，不写回原始数据。

## B 的事实边界

真实历史批次 round_001 已只读预检：49 张截图、190 条消息、0 项排除。适配 render.json 的 file/messages/evidence_page 旧字段和 path/message_ids/boxes 字段；按逐页消息 ID 与原图坐标显示，原始 case/source/render 全字段留在备份中。

所有 B 原始条目、修正导出和重生成包都明确 synthetic=true，不能当作真实聊天记录或司法证据。

逐条审核分别填写：

1. 内容依据：原文逐字引文、原文事实转述、合理模拟措辞、无依据新增事实。
2. 时间依据：原文明确给出、模拟、未知。
3. 说话人依据：原文支持、模拟、未知。

声明原文支持时必须引用当前判决摘录中的实际文字。逐字引文须包含实际消息文本；具体时间声称来自原文时，引用须包含该时间。“无依据新增事实”不能判“内容对”。事实转述是否忠实仍须人工判断；子串匹配不能证明语义正确。

“内容对”在 B 中表示符合所标依据及模拟约束，不表示聊天曾真实发生。新增消息同样标注来源类型。B 的整图“通过”要求所有消息判对；“需重生成”要求没有未审、存疑或仍保留的无依据事实。

生成台接收审核台导出的 regen_jobs.json，按选定截图建立不可变输入版本。输入只来自包内修正对话、来源摘录、补充/删除目标及总指令，不读取面板当前批注。删除消息不会进入 corrected_dialogue。生成结果继续标为待审核合成数据。

默认“离线演练”不调用模型。选择已配置模型时仍经过现有授权与任务执行机制。本轮验收只运行离线演练。

## 保存、导出、恢复与锁定

- 每个账号的 A、B 独立保存，独立版本，独立锁。
- 所有写入通过服务端事务和 expected_version 检查；旧窗口不能覆盖新版本。
- 修改或清除任一消息会使该截图原整图结论失效，需要重新保存整图审核。
- 未保存草稿会阻止导出/锁定，并在切换或离开时提示。
- 锁定前可完整导出，包括未审核记录和原始字段。下载、复制和文本区使用同一完整 JSON。
- 锁定必须满足：非空清单、所有消息有明确判项、所有截图有有效整图结论、当前版本已经完整导出且校验值一致。服务端重新检查全部条件。
- 锁定只影响当前数据集，锁后允许导出，禁止修改和恢复。
- 恢复仅接受当前固定清单的完整备份。校验合约、数据集、校验值、范围、唯一条目、原始 JSON、图像与消息映射、来源属性、逐条审核、整图结论以及可重算的修正结果。
- 全包校验完成后一次事务提交；任何条目失败，当前原始快照和审核记录都不变。恢复不会从备份复制锁定状态，也不能解锁已锁数据集。
- 初始化、保存、清除、导出、恢复与锁定写入操作审计。

SHA256 用来检查内容一致性，不是数字签名。恢复仍独立验证原始快照和修正规则，重算校验值不能绕过映射核对。备份只能恢复同一固定清单的审核层；不是跨账号或空安装的数据库迁移工具。

## 实现与测试

后端主要模块：

- backend/src/screenshotlegal/research/screenshot_sources.py：来源清单、预检和初始化。
- backend/src/screenshotlegal/research/screenshot_review.py：映射、修正、事务、导出、恢复和锁定。
- backend/src/screenshotlegal/research/screenshot_regeneration.py：修正包输入冻结和生成批次。
- backend/src/screenshotlegal/api/screenshot_review.py：认证后的 API。

前端主要模块：

- frontend/src/features/research/ScreenshotReviewPanel.tsx。
- frontend/src/features/research/RegenerationPackagePanel.tsx。
- frontend/src/styles/pack3.css。

在 product_v1 中运行：

    python -m pytest backend/tests/test_screenshot_review.py backend/tests/test_screenshot_sources.py backend/tests/test_screenshot_regeneration.py -q

在 frontend 中运行：

    npx playwright test --config=playwright.screenshot.config.ts

专用 Playwright 配置会自动建立隔离数据库、种入测试合成截图、启动 20430/20431 服务并在结束后清理服务；不复用正式数据。可用 E2E_BACKEND_PORT、E2E_FRONTEND_PORT 和 SCREENSHOTLEGAL_PYTHON 覆盖端口及解释器。默认 Playwright 测试集排除此专用用例，避免缺少种子数据时误运行。

最新实际结果与截图见 ../reports/screenshot-panel-2026-11-06/REPORT.md。

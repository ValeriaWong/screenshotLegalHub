# 四场景校准与人工复核交接

更新：2026-10-23。本轮按[V3计划](../../V3.0.0_PLAN.md)完成S0–S3当前校准范围的作者/机械交接，进入S4。**独立认证通过题仍为0，未开展正式模型评测或发布。**

## 已交付的范围

| 项目 | 结果 |
|---|---|
| S0 | 774文件基线；两案9页重复渲染两遍；实际浏览器/字体及软件烟测通过 |
| S1 | 4份case scope；144条事实账本（112旧候选陈述+32新合成消息）；62处原文精确定位；11维量表；512条历史行引用映射及抽样方案 |
| S2 | 4个不同源案启发的合成改写场景，中英各2；4种任务结构；节点/来源/作者答案/替代解释/自然度自审 |
| S3 | 20条件、80张860×1864截图、352个完整枚举的页级子集；坐标映射、反事实、顺序、分页、干扰与作者候选充分集 |
| 独立校验 | 391个产物哈希、全部子集、图节点引用与62处原文定位通过；13项工具测试通过 |

当前批次：[calibration_20261023_003](../../datasets/v3.0.0/calibration_20261023_003/mechanical_checks.json)。[S0环境复现](../../reports/v3.0.0/runtime_reproduction_20261023_002/README.md)、[校准检查](../../reports/v3.0.0/calibration_20261023_001/README.md)。旧001批发现查看账号未显示，002补足账号，003补足节点来源及候选充分集契约；旧批次保留但不是当前交接包。

四种任务分别是：账号关联后求和；通知版本与回复态度；本人表达、亲属提议及转述；转发路径与时间比较。仅第一、第四类拟研究链式依赖，其他类型分开报告，不统一宣称多跳。旧判决只作为审核侧的主题来源；新姓名、编号、N2通知及全部新对话为合成改写，不能代表真实原案聊天。显示日期只在合成情境内有效，真实身份、真实发生、实际收件和法律后果保持边界。

评分按事实、身份、时间、条件、意思表示、结论、引用、缺证、来源、自然度、法律范围11维分别记录。旧0–5评分和相关系数保持原值，不能转换成V3充分性/最小性认证。512条旧引用中1空行排除、2重复引用单列；对应510不同原始行。

## 现在需要的人工介入

依据主计划S4，需要两位真实、彼此独立且未参与本批作者设计的复核者；必要分歧需第三位裁决者。当前任务仅做中间事实判断，法律后果维度不适用；若扩为法律后果题，先补法域规则来源与相应复核能力。助手自审和机械检查不能充当独立意见。

- 复核者A：[独立ZIP](../../datasets/v3.0.0/calibration_20261023_003/blind_review/reviewer_a.zip)、[本地预览](../../datasets/v3.0.0/calibration_20261023_003/blind_review/reviewer_a/index.html)。
- 复核者B：[独立ZIP](../../datasets/v3.0.0/calibration_20261023_003/blind_review/reviewer_b.zip)、[本地预览](../../datasets/v3.0.0/calibration_20261023_003/blind_review/reviewer_b/index.html)。
- 每人独立解压一份到新目录；填写reviewer.json的身份与独立性声明、tasks.json的352条子集判断、case_reviews.json的20组页级充分/最小集及缺证/反证见证。不得互看另一位意见或作者答案。
- 从每场景16个基础子集开始；共64条基础子集。协调者按审核侧mapping分发，其余288条是反事实/包装/干扰控制。基础题若有歧义先退回新版本，原意见和旧产物保留。
- 填写内容必须对应实际可见图组；空图不允许图片引用。坐标以原像素xyxy记录，input_page是当前输入顺序，原始evidence_page未知且为null。
- 分歧保留原意见，再形成裁决与通过/退回清单；作者提出的最小集、20场景扩展目标都不能替代认证。

完成后可检查返回目录的完整性（不会自动授予语义认证）：

```powershell
./.venv/Scripts/python.exe -B -X utf8 tools/check_v3_calibration.py --batch datasets/v3.0.0/calibration_20261023_003 --review-a C:/reviews/a --review-b C:/reviews/b
```

未传review目录时检查冻结空白模板，预期ready_for_adjudication=false；这不是程序失败。当前实际为两位reviewer_id空、每人352条子集和20组认证未填写。

## 后续执行条件

[评测草案](../../datasets/v3.0.0/calibration_20261023_003/evaluation_plan.json)只有development，留出0；建议2种模型配置×3次重复×352条件=2112次请求是规划数量，不是授权预算。实际max_requests、max_cost、模型版本和重试策略仍为空。S4通过题、必要裁决及明确预算/服务选择齐备后再探测服务和冻结run spec。当前新API调用0。

[迁移回归](../../reports/v3.0.0/import_atomicity_20261023_001/README.md)已修复I11，并用2案真实既存语料验证来源、未知页码、检索和审计JSON/CSV。后续集成基线选择product_v1；经认证的V3充分路径、完整双模式、专用Excel/PPT、v1全量专业评测及发布/论文仍由G09–G18跟踪。20场景扩展依赖本4场景校准的独立反馈，当前不为凑规模批量扩充。

## 可重复执行

```powershell
./.venv/Scripts/python.exe -B -X utf8 tools/prepare_v3_calibration.py --output datasets/v3.0.0/calibration_NEW
./.venv/Scripts/python.exe -B -X utf8 tools/check_v3_calibration.py --batch datasets/v3.0.0/calibration_NEW
```

输出目录必须新建，原批次与原图不覆盖。生成器复用已冻结的渲染源码和现有Python/Chromium，不增加服务或依赖。

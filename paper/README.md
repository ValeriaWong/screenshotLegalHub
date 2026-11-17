# 论文工作区

当前稿件：`main.tex`，ACL 官方 review 样式，英文研究协议工作稿。不是已完成的新实验论文，也不是对尚未追回的投稿 .tex 的逐段改稿。初版已重写摘要、问题定义、任务/数据口径、来源链、双模式、合成方案、评测协议、局限与伦理部分；说明已有 24 题模型 pilot，全量比较及 v2 实验明确为 pending。

原始素材及缺口：`../reports/research/RESTART_FINDINGS.md`。内部评审与回复证据矩阵：`../reports/research/REVIEW_AND_REBUTTAL.md`。原 reviewer 与 rebuttal 正文仍需追回。此稿不会自动上传或提交会议。

在仓库根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File paper/build.ps1
.\.venv\Scripts\python.exe tools/verify_paper.py
```

产物：`output/pdf/screenshotlegalbench_working_draft.pdf`。逐页图像和检查记录在 `tmp/paper/rendered/` 与 `reports/research/paper_verification.json`。本机默认使用 `D:/texlive/2023/bin/windows`，可通过 build.ps1 的 `-TexBin` 指定路径。编译调用 pdflatex / bibtex，失败立即停止；不启用 shell-escape。

样式来自 `acl-org/acl-style-files`，保持原内容，blob SHA 在 vendor/provenance.json。参考文献只录入核验过的来源；当前相关工作覆盖尚不充分。会议及投稿周期确定后，重新核查当期模板、匿名、长度和声明要求。

提交前必须完成：追回原稿和评审 → 定义与冻结新实验 → 真正运行及核查结果 → 生成数据驱动图表 → 根据证据改写摘要和结论 → 专业与方法审阅 → 重新编译逐页检查。不能将工作稿中的计划改为过去时冒充完成实验。


2026-10-28 已新增 [案件方法实验入口](experiments/README.md) 与 [复现边界矩阵](experiments/METHOD_REPRODUCTION.md)。这轮机制演练的覆盖率属于工程验证；法律质量指标仍未评分，不填入 main.tex 的正式方法效果表。

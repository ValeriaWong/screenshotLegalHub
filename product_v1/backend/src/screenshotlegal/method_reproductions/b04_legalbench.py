"""LegalBench (Guha et al., 2023), https://arxiv.org/abs/2308.11462.
Author https://github.com/HazyResearch/legalbench @ b46bf4ffae90524b2b72aaa30e7745fe9db64481.
Original: 162 legal tasks; task text / few-shot demos -> labels, terms, citations,
numeric or open answers; original per-task metrics. Its notebook uses random
predictions; no original LLM controller is claimed. Native/API/provenance scope is
at paper/author_reproductions/legalbench/product_adapter.py.
复现程度：作者原提示生成/原评分代码直接执行的任务适配；完整原论文benchmark未复现。
原方法/创新：法律专业协作构建162任务、推理分类、few-shot提示和差异化评分。
原输入：原法律文本/问题及固定示例；原输出：类别、术语、引文、数值或开放答案。
原benchmark：162任务；本轮为11任务/12组29原样本及真实产品分类样本。
适配/调试：固定原TSV读pandas、新增远程API；三条截断只提高输出预算单独恢复，
不清洗长解释提高分数。原数字/SSLA/Successor评分缺陷保留，产品不用这些分支。
本项目输入/输出：冻结分类标签或已匹配消息文本 -> 原balanced exact-match补充评分；
不是法律推理正确率，不支持用缺失转录评KIE，也不替代像素/说话人定位评分。

This file dispatches the original normalized exact-match balanced-accuracy scorer
for frozen product labels / matched KIE text. It is a benchmark metric adaptation,
not legal accuracy or a CaseAnalysisOutput-generating agent. Missing references
stay unscored. Original evaluators execute in an independent no-weight environment.
"""
import os
from .author_bridge import REPO,stream_author
IMPLEMENTATION_STATUS='author_prompt_and_metric_product_adapter'
REPRODUCTION_LEVEL='author_source_task_adaptation'
METHOD_NAME='b04_legalbench'
PAPER_ID='B04'
async def score(groups):
    python=REPO/'paper/.author_envs/legalbench'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.is_file():raise ValueError('LegalBench 独立环境未配置：paper/author_reproductions/legalbench/README.md')
    async def forbidden(event):raise ValueError('LegalBench offline scoring must not request a model')
    return await stream_author(python,REPO/'paper/author_reproductions/legalbench/product_adapter.py',dict(mode='score',groups=groups),forbidden,python_utf8=True)

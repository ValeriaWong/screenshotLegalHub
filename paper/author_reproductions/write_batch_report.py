"""Write a factual batch report from method records, durable budgets and test artifacts."""
import json,xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;OUT=ROOT/'reports/author_expansion_20261029'
index=json.loads((HERE/'results/2026-10-29-per-paper/validation_index.json').read_text(encoding='utf-8'))
coverage=json.loads((HERE/'paper_coverage.json').read_text(encoding='utf-8'))
lines=['# 作者原代码复现与产品适配进展（2026-10-29—30）','',
 '更新时间：'+datetime.now(timezone.utc).isoformat(),'',
 '用户目标仍是逐篇完成“可运行环境＋原任务验证＋产品适配”。本批'+str(len(coverage['three_stage_development_completed_papers']))+'篇完成指定开发样本的这三个步骤；51条登记文献的其余工作继续保留，尚未全部完成。完整原论文benchmark完成数为0，专家法律准确率未评测。','',
 '## 主要更改','',
 '1. 直接执行作者原类/函数。新增RAPTOR摘要树与检索、LightRAG实体关系图与双层检索、Reflexion反思记忆的独立产品模块；Self-Refine/ReAct连接原控制器。源码版本、依赖锁、原任务和适配差异分别记录。',
 '2. 产品调用与真实供应商试跑使用一致参数。AIPING DeepSeek作者方法默认关闭思考模式，保留用户显式选择；原参数、有效参数、每次请求和实际响应均存档。',
 '3. 按方法保存输入、prompts、逐次model_responses、output、tools、test_results与provenance；案件导出增加作者摘要树/图谱/反思执行产物。RAPTOR和LightRAG只在冻结KIE文本轨道运行，不当作像素KIE。',
 '4. 每篇100次供应商请求上限由持久预留控制，原任务和产品轨道合并计数；包括历史、失败、未知、在途请求，不按新计划或恢复重置。分词/嵌入/原权重资源开始纳入独立环境校验。','',
 '当前按用户指令先略过本地模型权重推理/训练与重计算分支；API方法继续。SCALE新增产品实现、真实调用和验收见[本轮报告](REPORT_SCALE_API_2026-10-30.md)。','',
 '## 可逐篇检查的真实证据','',
 '|论文|作者执行入口|本批证据|产品轨道|','|---|---|---|---|',
 '|SCALE L09|[作者组件适配](../../paper/author_reproductions/scale/case_adapter.py)|原ECHR双条文＋中国法规案例产品真实6步，结构/引文通过，法律质量待复核|case_product；不是像素KIE|',
 '|ReAct A01|[adapter](../../paper/author_reproductions/react/product_adapter.py)|HotpotQA原题EM命中；真实图像KIE/VQA|kie_image、vqa_image_full；案件run仍原型|',
 '|Self-Refine A02|[adapter](../../paper/author_reproductions/self_refine/product_adapter.py)|作者缩写完整两轮4步；真实KIE/VQA；自评分不当准确率|kie_image、vqa_image_full|',
 '|Reflexion A03|[adapter](../../paper/author_reproductions/reflexion/product_adapter.py)|原Hotpot上下文EM命中；产品VQA实际反思后第二次尝试|kie_image、vqa_image_full|',
 '|RAPTOR R03|[adapter](../../paper/author_reproductions/raptor/product_adapter.py)|17叶子，摘要层16/15/14，45次摘要；答案待人工质量审查|vqa_predicted_text|',
 '|LightRAG R05|[adapter](../../paper/author_reproductions/lightrag/product_adapter.py)|完整UltraDomain法律文档，335节点/657关系；答案待人工审查|vqa_predicted_text|','',
 '[按方法命名的全部实际输入/输出/逐次回复/测试](../../paper/author_reproductions/results/2026-10-29-per-paper/README.md) · [51条目覆盖表](../../paper/author_reproductions/PAPER_COVERAGE.md) · [每个配置的METHOD.md](../../paper/author_reproductions/ADAPTATION_REVIEW.md)','',
 '这些验证使用DeepSeek替代论文底座；RAPTOR/LightRAG嵌入替换为锁定的CPU多语MiniLM。RAPTOR多层样例使用200-token分块、降维2、最多3层，与作者默认100/10/5不同；UMAP/GMM函数体未改。LightRAG使用作者v1.0.3，中文元组字段外全角结束符兼容处理另存转换记录。没有据此宣称原论文分数或方法优于基线。','',
 '## 尚未完成的逐篇工作','',
 '- SOLAR：原Stage II真实执行；精确值未命中，论文10%容差命中。Stage I和中国规则适配未完成。',
 '- AgentsCourt：原庭辩组件已真实执行；完整Legal-KB检索与判决、产品接入未完成。',
 '- PaddleOCR-VL：原0.9B权重已锁定；原0.9B权重CPU核心识别已完成，输出1616字符并达到1024-token上限；原eager内存失败与mask参数名兼容问题已保留记录并修复。完整布局流水线与产品适配未完成。',
 '- LawFlow：作者计划、执行、监控训练Notebook已固定；尚未完成运行/产品适配。其余条目见覆盖表。','',
 '## 调用预算（含历史）','',
 '|论文ID|累计供应商请求/预留|上限|','|---|---:|---:|']
for paper,count in sorted(index['budgets']['used'].items()):lines.append(f'|{paper}|{count}|100|')
lines+=['','历史请求可能引用多篇论文，按各引用保守归属；不得将上表求和当成实际付费总请求。早期145次本地FLAN-T5生成单独记录，供应商请求为0。','',
 '## 已发现并修正的问题','',
 '- ReAct：Chat接口重复Completion前缀、模型伪造Observation、Wikipedia请求User-Agent。保留原始回复，精确兼容前缀并转发原stop；实际工具观察仍来自程序。',
 '- Self-Refine：反馈阶段空正文/输出限制与额外Response前缀。保留实际模型参数与原始回复；不通过截断/补造JSON伪装成功。',
 '- LightRAG：逐条消息建图丢失共现关系，改为单份完整冻结KIE文本；原解析器因全角结束符丢实体，兼容转换仅发生在引号字段外。',
 '- 恢复器曾因R03命名空间硬编码，为SCALE重复发送5次请求，均已计入L09预算。已停止错误进程、统一请求ID；修复后14条原请求的实际回放验证新增供应商请求为0。重复记录未删除。',
 '- 浏览器合成夹具曾缺少run_id导致读取运行结果404；已补齐夹具。后续RAPTOR冷启动验收超时，五种方法已拆分独立用例、隔离端口/数据库/附件并延长CPU等待；五种独立浏览器用例最终全部通过。','',
 '## 工程验证','',
 '|检查|实际结果|记录|','|---|---|---|']
for file,label in [('backend-author-full-suite.xml','早期全套后端'),('test-method-declarations-updated.xml','方法声明/分派/命名导出'),('test-author-supplier-and-recovery.xml','供应商参数/作者执行/恢复/案件产物'),('test-native-paper-namespace.xml','逐论文预算与请求命名空间'),('test-lightrag-protocol-and-core.xml','作者核心与中文元组兼容'),('backend-full-author-final.xml','最终全套后端')]:
    p=OUT/file
    if p.exists():
        root=ET.parse(p).getroot();suites=[root] if root.tag=='testsuite' else list(root)
        tests=sum(int(s.get('tests',0)) for s in suites);fails=sum(int(s.get('failures',0))+int(s.get('errors',0)) for s in suites)
        result=f'{tests-fails}/{tests}通过，{fails}失败'
    else:result='尚未取得终态报告'
    lines.append('|'+label+'|'+result+'|['+file+']('+file+')|')
lines+=['|前端单元测试|54通过（本批选项/预算约束修改后）|[日志](frontend-author-tests.log)|',
 '|前端构建/类型/ESLint/架构守卫|早期检查通过；后续配置检查见日志|[构建](frontend-author-production-build.log) / [类型](frontend-final-typecheck.log) / [ESLint](frontend-final-lint.log)|',
 '|浏览器5种方法|5种独立浏览器用例全部通过（Demo传输，不计模型能力）|[日志](browser-five-separate-methods.log)|','',
 '工程测试中的Demo/确定传输夹具不计模型准确率。KIE无人工消息转录目标时仅报告结构、坐标和旧区域关联；全局VQA旧参考为开发参考，专家法律金标按用户要求后补。','']
(OUT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(dict(report=str(OUT/'REPORT.md'),three_stage_development_completed=coverage['three_stage_development_completed_papers'],scope_complete=False)))

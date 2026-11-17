# VERDICT 作者原代码复现（L08，进行中）

论文：Liao et al., VERDICT, arXiv:2603.19306。作者仓库 https://github.com/luckyhui235/VERDICT ，固定提交见 ../sources.lock.json 。

原方法由五类合议角色与Hybrid Jurisprudential Memory组成：抽取事实、法条检索/重排、草拟、Pass/Reject监督与修订、最终裁判，并将经验证轨迹提炼为Micro-Directives。原任务输入为CAIL2018刑事案件事实；输出法条、罪名、刑期预测及中间轨迹。论文另有CJO2025时间划分实验，但公开runner当前只实现cail2018。

作者README明确提供DeepSeek兼容API运行方式（legal-task/run.py --model deepseek-chat），因此不能笼统判为“缺少训练权重就无法运行”。作者公布的API路径可先验证原控制流；与论文“法律对齐Qwen2.5-7B法官＋DeepSeek-V3辅助角色”的异构设置不同，不能据此声称复现原论文成绩。

当前状态：原源码已固定；正在安装独立Python环境并取得作者法条映射。尚未宣称原任务或产品适配完成。Git索引包含law_article/law_articles_mapping.jsonl，未包含CAIL2018评测数据，需要从原数据发布源取得并保留版本。后续须实际运行原图通信、监督修订与HJM代码，不能以同角色Prompt替代。

本项目适配目标是冻结证据及法源→作者原控制流→带原文引用的产品输出。截图陈述不能直接提升为法院事实；产品没有专家答案键，原生benchmark反馈与产品反馈需要分开记录。每篇最多100次供应商请求，含历史、失败、未知及原任务/产品请求。密钥仅在父网关使用。

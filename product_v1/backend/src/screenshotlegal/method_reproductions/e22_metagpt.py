"""
论文出处：Hong et al., MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework.
https://arxiv.org/abs/2308.00352
作者v0.3.0 / 820fee5df6697b4e85e90c787940de111c3ed05b，paper/upstream_sources/metagpt。
复现程度：author_framework_domain_adaptation；原论文完整benchmark未复现。
原方法/创新：SOP角色、结构化中间产物、按动作类型订阅的共享消息环境。
原输入：一行软件需求（如Write a cli snake game）；原输出：PRD/设计/任务/代码及审查。
原benchmark：HumanEval、MBPP与软件开发任务；本项目样例不声称其论文成绩。
原任务入口：paper/author_reproductions/metagpt/product_adapter.py，执行原startup/软件角色。
本项目输入：冻结原文、citation_units、法源和目标；输出：CaseAnalysisOutput与消息/订阅执行产物。
产品替换四个Action及角色任务为证据抽取、要件映射、证据审查和最终整理；
原Team/Environment/Role/Memory/Action._aask_v1/ActionOutput实际执行，不由三段通用提示替代。
作者SOP消息与结构化输出机制，四角色法律证据任务适配；不加载本地模型权重。
适配调试：API父传输、付费重试禁用、独立环境、可选长期向量记忆保持关闭；
原软件任务与产品任务分别记录，结构/逐字引用验证不等于法律准确率。
真实原任务、产品和原QaEngineer续跑均有逐次记录；QA仍失败，不能把原软件输出当作中国法律能力。

原论文与适配核查（2026-10-29）

复现判定：原论文 benchmark 未复现。run(context)与run_task执行作者核心算法的任务适配；真实原任务及答案验证状态逐项记录。
已取得的作者原代码位于 paper/upstream_sources；未取得的条目在下方明确标记。作者入口与本项目 run(context) 分开记录。

[A04] MetaGPT
原有方法/任务：软件开发SOP协作；E22执行作者Team/Role/Memory与软件原任务，E02保留项目流程基线。
原输入大致形态（结构示意，不是 Gold）：软件需求或带函数签名/测试约束的编程任务。
原输出大致形态：需求/设计/代码/测试等软件产物；不是案件事实或法律分析。
原 benchmark：HumanEval、MBPP、SoftwareDev。
论文创新点（作者方法的组成）：把角色分工、标准操作流程、结构化通信和可执行反馈组合到软件开发团队。
对本工作的可适配性：作者通用团队、结构化ActionOutput与消息订阅可作领域迁移；E22显式替换四角色证据SOP。默认软件流程18次，额外作者审查1次后4项功能通过；原QaEngineer续跑19次仍有测试失败和最终未执行修订，累计45/100；交互终端和整篇方法未验收。
核查依据：https://arxiv.org/html/2308.00352v7
作者代码：https://github.com/FoundationAgents/MetaGPT @ 820fee5df6697b4e85e90c787940de111c3ed05b；本地 paper/upstream_sources/metagpt

本文件当前实际实现：作者SOP消息与结构化输出机制，四角色法律证据任务适配；不加载本地模型权重。
本项目输入：FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus
本项目输出：CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties
原生控制器已接入本文件run()：是；任务提示、输出解析和模型参数差异保留。
KIE/全局VQA原控制器接口：尚未接入
评测边界：用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞
如何适配/还需改什么：将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实；保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动；原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标
已做的适配调试：独立Python3.11、166个作者源文件与25依赖锁定；无本地权重；真实软件原流程18次调用，Windows编码收集失败后0调用恢复；原游戏缺occupied方法；独立功能探针触发1次原WriteCodeReview，核心4检查通过；首次失败保留；中间阶段与最终Schema冲突修正；首次产品3次失败与后续4步成功均保存；两层Tenacity完全unwrap；失败只调用一次测试通过；原Team/Environment/Role/Memory/Action结构化解析执行；四角色案件SOP及机械引用反馈
能否直接适配：条件适配；原输入/标签/评价协议不能直接等同截图证据链
尚未完成/阻塞：v0.3.0原QA续跑19次；2/7测试文件最后执行失败，main最终截断修订未重跑；原Engineer不支持自主开发代码修复；交互终端未验收
当前作者原代码状态：author_software_sop_and_case_product_validated_native_qa_executed_with_failures
复核记录：paper/author_reproductions/；逐配置审查表见 ADAPTATION_REVIEW.md。

"""
METHOD_ID='E22'
METHOD_NAME='e22_metagpt'
IMPLEMENTATION_STATUS='implemented'
REPRODUCTION_LEVEL='author_framework_domain_adaptation'
REPRODUCTION_SCOPE='作者SOP消息与结构化输出机制，四角色法律证据任务适配；不加载本地模型权重。'
PAPER_REFERENCES=[{"paper_id":"A04","reference":"Hong et al. (2023), *MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework*.","sources":["https://arxiv.org/abs/2308.00352"],"verification":"paper_listing_verified_not_code_reproduced"}]


















ORIGINAL_PAPER_CONTRACTS = [{'paper_id': 'A04', 'method': 'MetaGPT', 'task': '软件开发SOP协作；E22执行作者Team/Role/Memory与软件原任务，E02保留项目流程基线。', 'input': '软件需求或带函数签名/测试约束的编程任务。', 'output': '需求/设计/代码/测试等软件产物；不是案件事实或法律分析。', 'benchmark': 'HumanEval、MBPP、SoftwareDev。', 'innovation': '把角色分工、标准操作流程、结构化通信和可执行反馈组合到软件开发团队。', 'repo': 'metagpt', 'source': 'https://arxiv.org/html/2308.00352v7', 'fit': '作者通用团队、结构化ActionOutput与消息订阅可作领域迁移；E22显式替换四角色证据SOP。默认软件流程18次，额外作者审查1次后4项功能通过；原QaEngineer续跑19次仍有测试失败和最终未执行修订，累计45/100；交互终端和整篇方法未验收。', 'pinned_author_source': {'repository': 'https://github.com/FoundationAgents/MetaGPT', 'commit': '820fee5df6697b4e85e90c787940de111c3ed05b', 'local_path': 'paper/upstream_sources/metagpt'}}]
ADAPTATION_AUDIT = {'original_paper_reproduced': False, 'author_code_execution': 'author_software_sop_and_case_product_validated_native_qa_executed_with_failures', 'adaptability': '条件适配；原输入/标签/评价协议不能直接等同截图证据链', 'current_project_implementation': '作者SOP消息与结构化输出机制，四角色法律证据任务适配；不加载本地模型权重。', 'required_adaptation': ['将冻结的原文陈述/否认/未知保留为证据包，不提升为法院已认定事实', '保持作者原任务入口与本项目适配入口分开；逐项记录 prompt、工具、模型、输出 schema 的改动', '原 benchmark 使用原任务指标单独复核；适配任务另用案件组隔离的证据链 Gold 与成本/引用指标'], 'our_input_shape': 'FrozenCaseInput/visible sources: id,text,speaker,timestamp,page_no,source_locator,citation_units；goal；可选 matterpack/legal_corpus', 'our_output_shape': 'CaseAnalysisOutput: summary,claims,elements,facts.citations,evidence_links,uncertainties', 'author_native_interface_connected_to_product': True, 'author_benchmark_tracks': [], 'native_author_controller_real_run_passed': True, 'deferred_evaluation': '用户明确后补专家CaseGold；本轮先KIE/全局VQA，专家法律评测不作为环境/适配阻塞', 'native_author_component_example_passed': False, 'completed_debugging': ['独立Python3.11、166个作者源文件与25依赖锁定；无本地权重', '真实软件原流程18次调用，Windows编码收集失败后0调用恢复', '原游戏缺occupied方法；独立功能探针触发1次原WriteCodeReview，核心4检查通过；首次失败保留', '中间阶段与最终Schema冲突修正；首次产品3次失败与后续4步成功均保存', '两层Tenacity完全unwrap；失败只调用一次测试通过', '原Team/Environment/Role/Memory/Action结构化解析执行；四角色案件SOP及机械引用反馈'], 'blockers': ['v0.3.0原QA续跑19次；2/7测试文件最后执行失败，main最终截断修订未重跑；原Engineer不支持自主开发代码修复；交互终端未验收'], 'native_qa_verification': {'status': 'completed', 'checks': {'original_qa_role_scheduled': True, 'qa_rounds': 5, 'expected_test_files': ['tests/test_config.py', 'tests/test_food.py', 'tests/test_game.py', 'tests/test_input_handler.py', 'tests/test_main.py', 'tests/test_renderer.py', 'tests/test_snake.py'], 'generated_test_files': 7, 'execution_attempts': 9, 'latest_actual_pass': {'tests/test_config.py': True, 'tests/test_food.py': True, 'tests/test_game.py': False, 'tests/test_input_handler.py': True, 'tests/test_main.py': False, 'tests/test_renderer.py': True, 'tests/test_snake.py': True}, 'all_generated_tests_passed': False, 'development_source_unchanged': True, 'development_source_hashes': {'snake_game/snake_game/config.py': '7fbf75fc901af1a4bd9d1742894678642de77624181778934d440aabff0a1fe7', 'snake_game/snake_game/food.py': 'f5965a29cc5f01843647479c010e51d46ff38b3f1152d34fca6ac1546f199cfa', 'snake_game/snake_game/game.py': '94c51a78f4c1a77195650bcc1fa10007592e67308897488427eb8844525abf54', 'snake_game/snake_game/input_handler.py': 'c616522a2c778fc1ea677f1f2bba17eeaad43a548566f36a29835b73f8ff6351', 'snake_game/snake_game/main.py': 'a9164be8622d4864b457ae905db852799683690c242b0a7bff110140a73d3449', 'snake_game/snake_game/renderer.py': 'ad40580cc517c65db47908e72953c1c8c973c8af460f5610d142daa802d4c1da', 'snake_game/snake_game/snake.py': '27d6802dbaa0f841a75508182ffcc117746c50ee4eabe02db2cd9d66c216a046'}, 'unhandled_engineer_feedback': [], 'local_model_inference': False, 'original_complete_benchmark': False, 'seed_after_harness_selected_review': True, 'qa_control_flow_completed': True, 'fresh_full_startup': False, 'legal_accuracy': None}, 'original_complete_benchmark': False}, 'native_verification': {'status': 'completed', 'checks': {'author_controller_completed': True, 'all_software_stages_run': True, 'written_python_files': 7, 'syntax': {'snake_game/snake_game/config.py': True, 'snake_game/snake_game/food.py': True, 'snake_game/snake_game/game.py': True, 'snake_game/snake_game/input_handler.py': True, 'snake_game/snake_game/main.py': True, 'snake_game/snake_game/renderer.py': True, 'snake_game/snake_game/snake.py': True}, 'all_requests_completed': True, 'local_model_inference': False, 'artifact_recovery_without_inference': True, 'functional_task_validation': 'pending generated-code review', 'original_benchmark_score': None}, 'original_complete_benchmark': False}, 'real_product_tracks_completed': ['case_product'], 'product_verification': {'status': 'completed', 'checks': {'author_controller_completed': True, 'product_case_output_schema_valid': True, 'literal_citations_valid': True, 'subscriptions_preserved': True, 'structured_messages': 5, 'local_model_inference': False, 'expert_legal_accuracy': None}, 'original_complete_benchmark': False}, 'local_model_inference': False, 'native_full_method_completed': False, 'adaptation_limitations': ['软件任务Action替换为证据任务，非原软件benchmark条件', '原QA已执行但仍有失败；从额外作者审查后的项目续跑，非fresh startup；最终测试版本未执行不得沿用旧通过']}

async def run(context):
    from .metagpt_bridge import metagpt_case
    return await metagpt_case(context)

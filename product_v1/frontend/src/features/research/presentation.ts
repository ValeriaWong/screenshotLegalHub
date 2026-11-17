/** Human-facing descriptions; stored/API values remain unchanged. */
export const kindNames: Record<string,string> = {
 "benchmark.pipeline":"按图评测流程", "benchmark.pipeline.task":"冻结图片任务", "benchmark.pipeline.report":"冻结流程报告", "benchmark.pipeline.node":"图片评测步骤", "benchmark.prediction":"本轮消息预测", "benchmark.match":"参考区域关联", "benchmark.input":"实际任务输入", "benchmark.scoreset":"固定评分集合",
 "benchmark.dataset":"迁移数据集", "benchmark.history":"旧模型响应档案", "benchmark.annotation":"任务审核版本", "benchmark.review":"当前审核状态", "benchmark.quality":"任务质量评估", "benchmark.comment":"任务审核评论", "benchmark.release":"已发布任务版本", "benchmark.run":"KIE / VQA 运行", "benchmark.attempt":"KIE / VQA 逐题回答", "benchmark.score":"任务评分版本", "evaluation.task_prompt":"答题 Prompt 版本",
 "research.flow":"完整工作流程", "review.sample":"审核样本", "review.revision":"样本修改版本", "review.manifest":"图片版本", "review.comment":"审核评论", "review.comment.event":"评论处理", "review.quality":"质量评估意见", "review.gold":"人工确认的标准答案", "review.release":"已发布评测集", "review.prompt":"评估规则", "studio.prompt":"生成规则", "studio.batch":"生成批次", "studio.package":"下载包", "evaluation.request":"一次模型调用", "evaluation.run":"正式评测", "evaluation.attempt":"逐题回答", "evaluation.probe":"未计分试跑", "evaluation.metrics":"评测统计", model:"模型配置", case:"案件", "workbench.case":"案件", "workbench.run":"案件分析", request:"一次请求", operation:"操作", audit:"日志导出", prompt:"规则", job:"后台任务"
};
export const kindName = (v: string) => kindNames[v] || "其他记录";
export const terms: Record<string,string> = {
 reference_guided_prediction:"参考区域引导问答", full_image:"整图问答", full_image_control:"区域题整图对照", kie_image:"整图消息抽取", waiting_turn:"等待本轮上一次调用结束",
 response_received:"已收到回答", ready:"等待执行", service_failed:"模型服务失败", blocked_upstream:"上游未提供有效预测", blocked_no_match:"未找到合格匹配", invalid_input:"输入无效", completed_with_issues:"结束，有待处理项", aborted:"后续调用已停止", benchmark_pipeline:"按图评测子任务", kie:"整图消息抽取", scored:"已评分", rubric_review_required:"等待人工量表", rubric_reviewed:"已保存人工量表", invalid_reference:"参考无效或协议待确认", unscored_demo:"离线演练未计分", format_failure:"输出格式无效", abstained:"明确弃答",
 attitude:"态度（旧标签待核）", classify:"截图类型", speaker_comment_attitude:"回复态度", nickname:"发言人编号", case:"案情分析", evidence:"截图证据形式", group_chat_or_private_chat:"群聊或私聊", show_real_identity:"身份信息是否可见", legal_relationship:"法律关系分析", legal_intent:"法律意图分析", legal_analysis:"法律分析", action_analysis:"行为分析", amount:"金额", speaker:"说话人", file_name:"文件名", evidence_:"文件证据类型", evidence_content:"文件证据内容", speaker_avator:"头像关联",
 text:"仅文字", image:"仅单张图片", visual:"图片检查", both:"文字和图片", multimodal:"文字和图片", multi_image:"多张图片", qa:"问答", auto:"自动选择", original:"原图", synthetic_render:"合成截图", transcription_overlay:"转录对照图", current:"与当前版本一致", stale:"对应较早版本，需重新核对", legacy_unbound:"历史记录，需重新核对", capability:"连接测试", development_qa:"问答试跑", unscored:"未计分", exact_match:"与标准答案逐字匹配", human:"人工审核", model:"模型参考意见", correction:"修改后待复核", comment:"评论意见", worker:"系统任务", agent:"自动协助", user:"人工操作", system:"系统操作", queued:"等待开始", calling_model:"等待模型返回", response_saved:"模型已返回", response_failed:"模型返回异常", validated:"内容格式已检查", candidate_saved:"候选样本已保存", packaged:"图片已生成", quality_saved:"评估意见已保存", results_saved:"回答已保存", initial:"初稿", revised:"修改稿", generate:"生成候选", render:"生成截图", quality:"检查质量", evaluation:"运行评测", recorded:"已记录", awaiting_human_review:"等待人工审核"
};
export const term = (v?: string | null) => v ? terms[v] || v : "未记录";
export function actionName(action: string) {
 if (action.startsWith("job.")) return action.includes("failed") ? "后台任务未完成" : action.includes("unknown") ? "后台任务结果待确认" : action.includes("queued") ? "后台任务已安排" : action.includes("completed") ? "后台任务已完成" : "后台任务进度更新";
 if (action==="migration_snapshot") return "历史数据接入";
 if (action.startsWith("research.flow")) return action.includes("download") ? "下载流程文件" : "同步工作流程";
 if (action.startsWith("model.")) return action.includes("tested") ? "测试模型连接" : action.includes("deleted") ? "删除模型配置" : "保存模型配置";
 const [a,b]=action.split("."); const name=kindNames[a+"."+b];
 return name ? name+(action.endsWith("updated") ? "已更新" : action.endsWith("created") ? "已记录" : "操作") : "其他操作";
}
export function failureGuide(category?: string) {
 const guides:Record<string,[string,string]>={auth:["模型服务拒绝了访问","请到模型设置核对服务地址、模型名称与密钥。"],rate_limit:["模型服务暂时限制请求","稍后再试，或减少同时运行的数量。"],output_limit:["模型没有在输出上限内给出正文","请检查模型设置中的输出上限，再决定是否重新调用。"],response_parse:["模型返回的内容无法读取","查看原始返回，检查生成或评估规则是否要求了正确的格式。"],schema:["返回内容不符合样本要求","查看具体返回和规则，修正后再运行。"],timeout:["等待模型超时，结果尚未确认","先核对服务记录；重新调用可能再次计费。"],network:["模型服务连接未完成","检查服务连接和调用记录后，再决定是否重试。"],unknown_outcome:["上次调用结果尚未确认","先核对服务记录；重新调用可能再次计费。"],render_layout:["截图排版未完成","已保存文字仍保留。请检查文字长度和框的位置，再重新生成截图。"],input_unsupported:["这次输入不适用于所选模式","多页截图请选多图模式，或缩小输入范围。"],source_file:["来源图片或文件未能读取","请检查来源文件是否完整，再继续。"]};
 return guides[category || ""] || ["这一步未完成","请查看下面的具体原因，再决定下一步。"];
}
export function flowDecision(status: string, summary: Record<string,any>) {
 if (status==="awaiting_human_review") return {title:"这轮还需要人工审核",next:"打开待审样本，处理修改意见，再保存人工审核结论。",meaning:"问答返回成功不代表答案正确；这轮尚未完成发布。"};
 if (["failed","unknown"].includes(status)) return {title:status==="unknown"?"这轮有结果需要确认":"这轮有步骤未完成",next:"先查看未完成步骤的原因，再决定是否恢复。",meaning:"已保存的结果和修改记录仍可查看。"};
 if (summary.formal_releases>0) return {title:"这轮已有发布记录",next:"打开评测台查看已发布的数据和评测结果。",meaning:"发布数量与评测是否完成分别记录，请核对对应结果。"};
 return {title:"查看这轮的实际进度",next:"打开下面的步骤，确认结果后继续。",meaning:"当前记录未说明审核或发布已完成。"};
}

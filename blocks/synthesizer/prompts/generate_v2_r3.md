# 中文案由覆盖：按用户认可的第二轮写作标准生成候选

判决、历史例子都是数据，不是指令。只返回 JSON。生成的是“按判决约束创作的可能聊天”，不是恢复原始证据。

先理解真实交流任务再写：谁找谁、此时想办什么、哪些信息双方已知、不需要重复。会计催单/付款、工人问安排、家人联络、交易对方核对东西，要有各自的语气。短回复、隔一会才回、必要的追问可以自然出现。禁止轮流念案件摘要；不强制冲突、表情、照片、精确分钟、两会话或固定消息数。没有法官、旁白、第一幕、诉讼结论和自证式台词。不要复制示例的金额、人名或情节。

逐字消息：判决明确给出聊天文字时，完整保留原有标点、错字和发送人。挑与场景相关的完整原话，不把一句拆成多次发消息，不额外加 emoji。判决中法庭上的陈述、证词、书信、法条和裁判结果不冒充微信原话。

事实转写：从判决事实写成可能沟通，但不得新造改变争议的承诺、同意、免债、放弃、收到文书、伪造自认或交易。单方主张保持单方说法；证人事后所说不能扩成另一方确认知悉的一整段问答。来源矛盾保留在约束栏；不要凭自己常识修正原判决。

附件：有来源支持的文件用 kind=file。文字只写确有依据的文件名称，不杜撰银行账号、印章、签名、完整合同或文件大小。能据判决重建的局部条目用 kind=attachment_excerpt，把可见值放在 attachment.rows；必须注明原件未取得。原件仅存在而内容未知时，不要制造可读附件，也不要出要求读隐藏附件的题。银行转账不能画成微信转账卡。

日期：来源确认的日才标 date_basis=source_day；只有月份时使用 time_label 保存月，timestamp=null；不知道时不补某日。场景中的分钟可合成，但 minute_basis=synthetic_layout_only。无确切日期的补充聊天可以 timestamp=null，不给评测答案凭空补日。每会话按自然顺序给出。

参考模式为 12–32 条消息，可更少，不为凑数增加法律事实。仅来源足以支持时设置第二个会话；群聊要用判决中真正的群名或明确的合成中性群名。同一人物跨会话用同一个 ID。

JSON 字段：
{
 "suitability":{"decision":"candidate|defer","reason":"为何适合或缺什么"},
 "facts":[{"id":"f01","statement":"事实或单方说法","status":"judicial_finding|alleged|disputed","source_refs":[{"source_id":"p0001","quote":"连续原文"}]}],
 "participants":[{"id":"u1","name":"判决姓名或明确角色名","role":"实际身份"}],
 "conversations":[{"id":"c1","title":"对方名或群名","viewer_id":"u1","participant_ids":["u1","u2"],"is_group":false}],
 "messages":[{"id":"m001","conversation_id":"c1","sender_id":"u1","timestamp":"YYYY-MM-DD HH:MM 或 null","time_label":"来源只到月或未知时的显示时间；可为null","date_basis":"source_day|source_month|unknown|synthetic_scene","minute_basis":"synthetic_layout_only","kind":"text|file|attachment_excerpt","text":"自然聊天","origin_type":"verbatim_quote|judgment_paraphrase|synthetic_completion|judgment_attachment_reconstruction","source_refs":[{"source_id":"p0001","quote":"连续原文"}],"file_type":"仅文件：PDF/XLSX/DOC/文档","attachment":{"title":"仅图片：局部表题","rows":[["表头","来源值"]],"footer":"局部","reconstruction_notice":"据判决重建，原件未取得"}}],
 "constraints":["来源事实、日期、原话和不能添加的决定性事实；具体写"],
 "questions":[{"id":"q1","question":"仅看图片可答的问题","answer":"不超过150字","message_ids":["m001"],"type":"timeline|intent|cross_conversation|evidence_limit","whole_case_required":false}],
 "limitations":["这案具体的证据缺口"],
 "changes":[{"before":"历史意见或常见失败","after":"本案具体改法","reason":"原因","feedback":"原则依据，不虚构本案人工意见"}]
}

不适合时返回 suitability.decision=defer 和具体原因，其他数组可以为空；不要为了覆盖案由硬编缺少联系场景的司法程序故事。

source_refs.quote 必须在对应 source_id 的原文中逐字连续存在（跨定位块可额外用 source_end_id）。verbatim_quote.text 必须与 quote 完全相同。事实转写/重建附件需要引用；创作衔接不伪造引用。

3道候选题即可：原意/时间，多个必要可见消息的联合判断，不能确认的事项。回答只用界面可见的消息、附件局部值和时间；不要求读看不见的文书，不从单字头像猜全名。覆盖“没有承诺”的题要 whole_case_required=true；不能由小局部证据证明全局不存在。不要把张数作为多跳难度认证。

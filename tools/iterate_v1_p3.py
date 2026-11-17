"""Correct the original evidence-form semantics; retain an auditable prior run."""
import json
import iterate_v1_evaluation as p

previous = p.BASE
old_tasks = {x['id']:x for x in [json.loads(s) for s in (previous/'tasks.jsonl').read_text(encoding='utf-8').splitlines()]}
for path in (previous/'runs/holdout-structured').glob('*/predictions.jsonl'):
    for line in path.read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row['track']=='screening_bundle':p.EXTRA_DEV_GROUPS.add(old_tasks[row['id']]['case_id'])
# Two visually audited source groups also stay out of the new screening holdout.
p.EXTRA_DEV_GROUPS.update(['584384f96a6a6950cccebe2b','59f5a00211be107b029ecc99'])
p.BASE = p.b.ART/'iterations/20261004-p3-form'
p.PROTOCOL = 'p3-original-evidence-form-20261004'
p.REPORT_PREFIX = 'v1.0.0_iteration_p3_'
p.EVIDENCE_NOTE = 'evidence follows the original question “规范的聊天截图证据形式”, independently of legal relevance; visual form screening does not establish authenticity or legal admissibility.'
p.DEFINITIONS = '''只根据截图作三项独立判断，不读取或猜测未提供的案情。
classification：legal_dialog=聊天且可见法律相关事实/权利义务表达；not_dialog_but_legal=非聊天但具有法律相关内容；non_legal_dialog=聊天但无可见法律相关内容；not_dialog_and_non_legal=非聊天且无可见法律相关内容。
evidence：原题问“它是规范的聊天截图证据形式吗”，与classification的法律意义独立。is_evidence=从可见形式看是可识别主体和上下文的、结构连贯且清晰可读的聊天截图；not_evidence=非聊天材料，或明显拼接/断裂、关键主体和时间上下文严重缺失、关键内容被遮挡等不规范形式。日常聊天也可以符合规范形式，不能仅因内容无法律意义、含玩笑就判断not_evidence。形式判断不等于核验真实性、法律效力或法院采信；无法判断则unknown。
chat_type：group_chat=可见多人会话界面或群成员发言；private_chat=可见双人会话界面；非聊天或看不清时为unknown。
各字段依据不足时使用unknown。只输出JSON，格式：{"answer":{"classification":"标签","evidence":"标签","chat_type":"标签"}}。'''
p.CASE_CARRYOVER = previous/'runs/holdout-structured'

if __name__=='__main__':p.main()

"""Publish AI review sidecars for the frozen pilot; never rewrite input or scores.

Notes are based on direct inspection of every pilot image and the saved answers.
This is a bounded first review, not a licensed-lawyer adjudication or a new gold.
Run from repository root. Output must not already exist. No network/API calls.
"""
import argparse
import hashlib
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legalhub.benchmark import dataset

RUN = ROOT / 'blocks/evaluator/artifacts/runs/20261004-vision-pilot'
MODELS = ['sf_qwen38_thinking', 'sf_qwen3vl_instruct',
          'sf_qwen3vl_thinking_native', 'kimi3_low', 'kimi26_nonthinking']
LAWS = {
    'civil_code': 'https://www.court.gov.cn/zixun/xiangqing/233181.html',
    'loan_rules': 'https://cicc.court.gov.cn/html/1/380/385/12844.html',
    'electronic_evidence': 'https://www.court.gov.cn/zixun/xiangqing/212721.html',
    'fraud_elements': 'https://www.spp.gov.cn/spp/llyj/202607/t20260704_731273.shtml',
    'causes_2026': 'https://www.court.gov.cn/zixun/xiangqing/484231.html',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def publish(path, value, lines=False):
    # Exclusive creation is intentional: re-running may not overwrite reviews.
    with path.open('x', encoding='utf-8', newline='\n') as out:
        if lines:
            for row in value:
                out.write(json.dumps(row, ensure_ascii=False) + '\n')
        else:
            json.dump(value, out, ensure_ascii=False, indent=2)
            out.write('\n')


def review(task):
    track, idx = task['track'], task['source_index']
    base = {'reviewer_type': 'AI_direct_image_and_saved_answer_review',
            'professional_signoff': False, 'promoted_to_gold': False,
            'evidence_refs': [], 'legal_sources': [], 'minimal_set_status': 'unverified'}

    def note(status, reason, proposed, refs=(), laws=(), **extra):
        return {**base, 'disposition': status, 'reason': reason,
                'proposed_answer': proposed, 'evidence_refs': list(refs),
                'legal_sources': [LAWS[k] for k in laws], **extra}

    def ref(image_index, quote, region):
        return {'image': task['images'][image_index], 'quote': quote,
                'region_description': region, 'bbox': None,
                'evidence_page': None, 'coordinate_status': 'not_annotated'}

    if track == 'case_choice' and idx == 29:
        return note('keep_with_limits', '可见售衣、选衣、问价和付款沟通，买卖关系判断合理；买后送人不改变卖方与买方之间的买卖关系。实际违约、损害及实名主体未被证明。',
                    ['买卖合同纠纷'], [ref(0, '卖衣服哦，欢迎来看看；挑几件最好看的；多少钱报给我', '图0中下部'),
                    ref(5, '给你转了2000；钱收到没，让手下转的；收到了', '图6上部及中部')], ['civil_code'],
                    minimal_set_status='AI_verified_singleton_for_possible_legal_relationship_only',
                    minimal_sets=[[task['images'][0]]],
                    multihop_status='not_required_for_this_question',
                    minimality_reason='图0独立足以判断可能的买卖关系；零图无事实依据。该集合不证明合同全部内容或违约。')
    if track == 'case_choice' and idx == 111:
        return note('revise_proposed', '三图联系人备注均含“杀猪盘骗子”，但正文未展示可核实的欺骗取财链条。备注是持机者标记，不能替代犯罪构成证据。题目问“可能”也应区分风险线索与有证据支持的定性；现选项缺少依据不足。',
                    '仅有诈骗风险备注，正文不足以支持诈骗罪定性；应允许依据不足，补充欺骗、财产处分、损失、主观目的等证据后复核。',
                    [ref(0, '烟雨半生（杀猪盘骗子）', '标题栏'), ref(1, '我目前主要是做健康行业这一块的', '中上部'),
                     ref(2, '养老院福利院都有', '上部')], ['fraud_elements'],
                    multihop_status='unverified_shortcut_risk', minimal_set_status='full_input_insufficient_for_criminal_conclusion')
    if track == 'case_open' and idx == 43:
        return note('revise_proposed', '买卖关系方向正确，但发货/交付通常是主要履行义务，不能把此图仅概括成附随义务；拒绝立即发货不自动等于迟延履行。',
                    '可能涉及买卖合同中的发货/交付期限问题。截图显示买家要求现在发货，客服答下午发；是否违约仍需订单承诺期限及实际履约证据。',
                    [ref(0, '我刚下单了只口红', '下部'), ref(1, '现在给我发货行不行；现在发不了；下午发', '中部至下部')], ['civil_code'],
                    minimal_set_status='AI_verified_singleton_for_possible_dispatch_issue_only',
                    minimal_sets=[[task['images'][1]]], multihop_status='not_required_for_this_question',
                    minimality_reason='图1店铺界面和发货协商足以支持潜在发货期限问题；零图无事实依据。两图均不能证明已经违约。')
    if track == 'case_open' and idx == 59:
        return note('revise_proposed', '亲密关系及资金往来可见；金额大或非520/1314不能推出借贷。图0与图1重叠同一生日1314转账，不能重复计数。图6“实时转入得20000体验金”是广告。图7为多会话拼图，昵称/头像变化，实名同一性未证实；另有实际20000转账卡，需与广告区分。',
                    '可能涉及亲密关系资金往来的赠与/返还争议。若主张借贷需另证借贷合意；款项目的、主体同一性、婚约条件及实际交付待核实，不按金额自动判为借款或彩礼。工资/年总奖文字也不能独立证明劳动关系。',
                    [ref(0, '1314.00；生日快乐', '中下部'), ref(2, '今天除夕；我的红包呢', '中部'),
                     ref(4, '500.00元；实时转入得20000体验金；预支工资', '上中下部不同区域'),
                     ref(5, '我们相恋了2637天；20000.00元', '拼图上方不同块')], ['loan_rules', 'civil_code'],
                    minimal_set_status='full_input_insufficient_for_loan_or_repayment_conclusion', multihop_status='unverified_entity_alignment')
    if track == 'case_single_open' and idx == 396:
        return note('clarify_rubric', '聊天主体为日常交流，但嵌套转发段子提到酒店财损、打架。题目“无相关法律内容”未定义是否包括转发内容；不能认定为聊天当事人的现实纠纷。',
                    '本聊天双方未显示现实法律争议；转发故事抽象涉及财损/冲突，须明确题目是否计入嵌套内容。',
                    [ref(0, '没事，反正我无条件爱你', '上部主聊天')])
    if track == 'case_single_open':
        return note('keep_with_limits', '可见日常安慰与表情，没有本对话的明确法律争议事实。', '无',
                    [ref(0, '我心情已经好了；刚刚去吃饭了；好好好，你心情好就行', '主聊天')])
    if track == 'chat_type':
        observations = {131: '顶部“结婚进度20%(5)”、多位发送者及群内称谓支持群聊。',
                        930: '气泡上有发言者名称及“咱们这个群”，支持群聊；截图裁切未完整展示标题。',
                        1002: '外层为两侧私聊，无群成员名称；内嵌聊天不能替代外层会话类型。',
                        1085: '当前显示单个联系人两侧私聊，无群聊证据。'}
        return note('keep_with_limits', observations[idx], task['answer'])
    if track == 'classification':
        if idx == 683:
            return note('clarify_rubric', '图片是聊天搜索结果列表而非连续对话；结果内有日常聊天文字。按界面类型原金标可成立，按内容类型non_legal_dialog也可成立，提示词未规定层级。',
                        '若dialog指连续会话界面：not_dialog_and_non_legal；若指包含聊天内容：non_legal_dialog。先固定规则。')
        reasons = {66: '交易搜索列表含已收款/已被接收记录，具法律相关事实，非连续会话。不能据此自动认定借贷或可返还。',
                   622: '正文含8300、3000、5300及初八结清的催款/清偿沟通，legal_dialog合理，尚不能仅凭截图确认原始债权性质。',
                   1068: '普通感情疏导，未见足以指向具体权利义务争议的内容。'}
        return note('keep_with_limits', reasons[idx], task['answer'])
    if track == 'evidence':
        reasons = {119: '另一即时通信平台的租赁沟通，有界面标题但非微信；需要说明是否允许平台差异。',
                   613: '裁切图保留气泡和头像，有借钱/不用还等文字；是否符合形式要求须由裁切阈值定义，不能因日常背景否定证据意义。',
                   660: '裁切且缺少完整身份/时间标题；non_legal或日常游戏内容不等于不符合截图形式。',
                   796: '裁切且缺少完整标题，仍有气泡、头像和转账卡；与613的形式差别需要明确规则。'}
        return note('clarify_rubric', reasons[idx] + '现prompt只给evidence标签，没有形式标准；禁止将标签改解释为法院采信。',
                    '保留历史标签待形式标注细则复核；真实性、合法性、关联性、证明力另列字段。', laws=['electronic_evidence'])
    if idx == 3021:
        return note('revise_proposed', '目标“12点10”对应“你啥时候回公司”“12点半要去上岗”等上下文，不足以支持商家/消费者身份。原文为即时通信文字，不应称已证实的口头许诺；8秒语音内容不可见。',
                    '对回公司时间的回复，表示12:10左右返回/到达；仅凭本图不能确定商家与消费者关系或合同履行承诺。',
                    [ref(0, '你啥时候回公司；应该我12点半要去上岗；马上；12点10', '中部至下部')])
    if idx == 2823:
        return note('clarify_rubric', '目标位于左侧消息；昵称标题被遮挡，内部avator编号映射未提供。assisted附文写avator_1，原金标avator_0且历史IoU=0.011，不应把编号猜测计为法律理解错误。顶部19:55是状态栏时间，不能当作消息时间。',
                    '左侧发言者；可见昵称unknown。若要输出avator_0，必须另给该图人工编号映射。',
                    [ref(0, '你已经在慢慢变好了', '顶部左侧气泡')])
    if idx == 3859:
        return note('clarify_rubric', '目标为戴口罩表情；attitude未定义为法律态度还是情绪，且没有给non_legal等枚举。原金标可以是法律态度分类，但普通情绪解释不能直接判错。历史匹配为空且IoU未过，assisted定位还存在误差。',
                    '法律态度：本区域无明确法律意思表示，可标non_legal；情绪：可能无奈/尴尬，不能唯一确定。先明确任务定义。')
    raise ValueError(task['id'])


def model_note(task, prediction, model, note):
    status, answer = prediction['status'], prediction.get('answer')
    if status != 'ok':
        return 'execution_or_format_failure', '保留原失败状态及计划分母；没有可据以完成法律内容评分的解析答案。'
    track, idx = task['track'], task['source_index']
    if track == 'case_choice' and idx == 111:
        return 'unsupported_legal_label', '匹配旧金标，但本题正文不足以支持诈骗罪标签；不得把命中当作犯罪理解已验证。'
    if track == 'case_open' and idx == 43:
        notes = {
            'sf_qwen3vl_thinking_native': ('supported_but_incomplete', '买卖关系方向合理，但没区分发货期限问题与已经违约。'),
            'sf_qwen3vl_instruct': ('reasonable_abstention_with_omission', '正确指出尚无已证实违法，仍可识别潜在买卖/发货问题；不应仅因拒绝确定案由全判错。'),
            'kimi26_nonthinking': ('partly_supported_overclaim', '识别买卖与发货问题合理；把“下午发”直接称合理调整缺少买方同意与订单期限证据，单列服务合同关系也不足。'),
            'kimi3_low': ('supported_with_conditional_extensions', '识别潜在买卖与发货期限、保留证据不足；消费维权是争点，不能把泛称均视为正式案由。'),
            'sf_qwen38_thinking': ('supported_with_conditional_extensions', '识别买卖和发货问题并区分潜在案由与已成立纠纷；消费者保护泛称需规范。'),
        }
        return notes[model]
    if track == 'case_open' and idx == 59:
        if model == 'sf_qwen38_thinking':
            return 'partly_supported_overclaim', '指出赠与与借贷合意不足合理；将大额/恋爱破裂直接推进附条件赠与返还有跳步，不能称工资名义更可能为话术而作事实结论；主体归并未验证。'
        if model == 'kimi26_nonthinking':
            return 'partly_supported_overclaim', '列赠与、借贷等可能方向且提条件；劳动/婚约关系未证实，多会话主体归并未验证，须逐笔说明。'
        if model == 'kimi3_low':
            return 'supported_with_missing_identity_check', '明确借贷合意、婚约和劳动关系证据不足；仍未识别拼图身份风险，也不能把所有转账视作同一对当事人。'
        return 'supported_but_incomplete', '以条件式列借贷/赠与/不当得利较审慎；缺少逐笔证据及主体对齐，不作为已成立返还义务。'
    if track == 'case_single_open' and idx == 396:
        return 'rubric_dependent', '原答无与限定转发段子讨论均可有合理依据；先界定是否分析嵌套内容。'
    if note['disposition'] == 'clarify_rubric':
        return 'rubric_or_input_ambiguous', '见题目复核意见；不把当前标签匹配差异直接归因于法律能力。'
    if track.startswith('message') and idx == 3021:
        if model in ['kimi3_low', 'sf_qwen38_thinking', 'kimi26_nonthinking'] and track == 'message_assisted':
            return 'better_grounded_than_legacy_gold', '时间回复的解释符合图中上下文，优于旧金标的商家/消费者许诺。'
        if track == 'message_grounded' and answer == 'unknown':
            return 'reasonable_abstention_but_incomplete', '不臆造商家/消费者关系合理；仍可描述可见时间回复。'
        return 'supported_text_incomplete_legal_intent', '12点10转录正确，但未分析意思表示及证据限度。'
    return ('supported_at_task_level', '与图中事实及明确任务方向相符，见题目证据限度。') if answer == task['answer'] else (
        'label_disagreement_review_needed', '与当前复核支持的标签有差异，见原图及题目意见；不能用模型多数票改金标。')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    out = Path(args.output).resolve()
    out.relative_to(ROOT)  # All writes must remain inside this repository.
    if out.exists():
        raise FileExistsError('Review directory already exists; choose a new path.')
    cohort_path = RUN / 'cohort.json'
    cohort = json.loads(cohort_path.read_text(encoding='utf-8'))
    manifest, tasks = dataset()
    assert manifest['dataset_sha256'] == cohort['dataset_sha256']
    by_id = {t['id']: t for t in tasks}
    chosen = [by_id[i] for i in cohort['task_ids']]
    protected = {cohort_path, ROOT / 'blocks/evaluator/artifacts/dataset.json'}
    dataset_path = ROOT / json.loads((ROOT / 'blocks/evaluator/artifacts/dataset.json').read_text(encoding='utf-8'))['path']
    protected.update([dataset_path / 'tasks.jsonl', dataset_path / 'manifest.json'])
    for t in chosen:
        protected.add(ROOT / t['source'])
        assert sha(ROOT / t['source']) == t['source_sha256']
        for image, digest in zip(t['images'], t['image_hashes']):
            protected.add(ROOT / image)
            assert sha(ROOT / image) == digest
    predictions = {}
    for model in MODELS:
        path = RUN / model / 'predictions.jsonl'
        protected.add(path)
        for other in ['run.json', 'metrics.json']:
            if (path.parent / other).exists():
                protected.add(path.parent / other)
        rows = [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
        assert len(rows) == len(chosen) and len({r['id'] for r in rows}) == len(chosen)
        assert {r['id'] for r in rows} == set(cohort['task_ids'])
        predictions[model] = {r['id']: r for r in rows}
    before = {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in sorted(protected)}
    notes = {t['id']: review(t) for t in chosen}
    reviewed = [{**t, 'original_answer': t['answer'], 'review': notes[t['id']]} for t in chosen]
    response_review = []
    for model in MODELS:
        for t in chosen:
            p = predictions[model][t['id']]
            disposition, rationale = model_note(t, p, model, notes[t['id']])
            response_review.append({'task_id': t['id'], 'model_config': model,
                'reported_model': p.get('reported_model'), 'original_status': p['status'],
                'original_answer': p.get('answer'), 'original_raw': p.get('raw'),
                'prediction_source': str((RUN/model/'predictions.jsonl').relative_to(ROOT)).replace('\\', '/'),
                'disposition': disposition, 'rationale': rationale,
                'numeric_legal_score': None, 'professional_signoff': False})
    # Image subsets change the request manifest only. No image is cropped/deleted.
    requests, expected = [], []
    for t in chosen:
        n = len(t['images'])
        if n < 2:
            continue
        for size in range(n + 1):
            for indices in itertools.combinations(range(n), size):
                tags = []
                if size == 0: tags.append('question_only')
                if size == 1: tags.append('single_image')
                if size == n - 1: tags.append('leave_one_out')
                if size == n: tags.append('full')
                rid = t['id'] + '__subset_' + ('-'.join(map(str, indices)) or 'none')
                requests.append({'request_id': rid, 'task_id': t['id'], 'tags': tags,
                    'prompt': t['prompt'], 'images': [t['images'][i] for i in indices],
                    'image_hashes': [t['image_hashes'][i] for i in indices]})
                expected.append({'request_id': rid, 'answerability': 'unverified',
                    'expected_claims': [], 'missing_premises': [], 'reviewer': None})
        rid = t['id'] + '__full_reversed'
        requests.append({'request_id': rid, 'task_id': t['id'], 'tags': ['order_control'],
            'prompt': t['prompt'], 'images': list(reversed(t['images'])),
            'image_hashes': list(reversed(t['image_hashes']))})
        expected.append({'request_id': rid, 'answerability': 'unverified',
                         'expected_claims': [], 'missing_premises': [], 'reviewer': None})
    out.mkdir(parents=True, exist_ok=False)
    publish(out/'task_reviews.jsonl', reviewed, lines=True)
    publish(out/'model_answer_reviews.jsonl', response_review, lines=True)
    publish(out/'ablation_requests.jsonl', requests, lines=True)
    publish(out/'ablation_expected.review_pending.jsonl', expected, lines=True)
    after = {p: sha(ROOT/p) for p in before}
    assert before == after, 'A protected input changed during publication.'
    summary = {'dataset_sha256': manifest['dataset_sha256'], 'cohort_tasks': len(chosen),
        'reviewed_unique_images': len({p for t in chosen for p in t['images']}),
        'task_dispositions': dict(Counter(n['disposition'] for n in notes.values())),
        'saved_model_responses': len(response_review),
        'response_dispositions': dict(Counter(r['disposition'] for r in response_review)),
        'ablation_requests_prepared': len(requests), 'ablation_api_calls': 0,
        'legal_sources_checked_date': '2026-10-04', 'legal_sources': LAWS,
        'professional_signoff': False, 'numeric_legal_scores_published': False,
        'original_files_unchanged': before == after, 'protected_files': len(before)}
    publish(out/'summary.json', summary)
    publish(out/'source_integrity.json', {'before': before, 'after': after, 'unchanged': before == after})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

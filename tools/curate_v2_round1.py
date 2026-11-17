"""Logged agent corrections after chat-only audit. This is not human approval."""
from pathlib import Path
import sys
import json
import re
import copy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from legalhub.synthesis import settings,read,write,validate,digest


def main():
    cfg,out=settings()
    for spec in cfg['cases']:
        folder=out/spec['language']/spec['id']
        original=read(folder/'final.json');candidate=copy.deepcopy(original);source=read(folder/'source.json')
        corrections=[]
        def change(target,before,after,reason):
            corrections.append({'target':target,'before':before,'after':after,'reason':reason})
        # Grounding correction is permissible only if the very same literal quote
        # appears in one unique source paragraph. Never manufacture a substitute quote.
        ps={p['id']:p['text'] for p in source['paragraphs']}
        def exact_location(quote):
            first=source['text'].find(quote)
            if first<0 or source['text'].find(quote,first+1)>=0:return None
            last=first+len(quote)
            starts=[p for p in source['paragraphs'] if p['char_start']<=first<p['char_end']]
            ends=[p for p in source['paragraphs'] if p['char_start']<last<=p['char_end']]
            if not starts or not ends:return None
            return starts[0]['id'],ends[0]['id'],first,last
        for fact in candidate['facts']:
            quote=fact['source_quote']
            if quote not in ps.get(fact['source_id'],''):
                matches=[pid for pid,text in ps.items() if quote in text]
                if len(matches)==1:
                    before=fact['source_id'];fact['source_id']=matches[0]
                    change(fact['id']+'.source_id',before,matches[0],'Unique literal quote location; quote and fact wording unchanged')
                else:
                    loc=exact_location(quote)
                    if loc:
                        before=fact['source_id'];fact['source_id']=loc[0];fact['source_end_id']=loc[1]
                        fact['source_char_span']=[loc[2],loc[3]]
                        change(fact['id']+'.source_span',before,[loc[0],loc[1]],'Exact original quote crosses technical source chunks; retain both boundaries without changing quote')
        for message in candidate['messages']:
            for ref in message.get('source_refs',[]):
                if ref['quote'] not in ps.get(ref['source_id'],''):
                    loc=exact_location(ref['quote'])
                    if loc:
                        before=ref['source_id'];ref['source_id']=loc[0]
                        if loc[0]!=loc[1]:ref['source_end_id']=loc[1]
                        ref['source_char_span']=[loc[2],loc[3]]
                        change(message['id']+'.source_ref',before,[loc[0],loc[1]],'Exact unchanged quote located in original source, including chunk boundary when needed')
            if message.get('timestamp') and message.get('time_label','').lower() in ['date','datetime','timestamp','day']:
                before=message['time_label'];message['time_label']=message['timestamp'][:10]
                change(message['id']+'.time_label',before,message['time_label'],'Render stored scenario day instead of placeholder; no time value changed')
        if spec['id']=='en_charter_177':
            for mid,fid,statement in [
                ('m015','f901','In the afternoon of 2 February, Jensen asked Sorensen whether they could expect a counter soon.'),
                ('m022','f902','On 6 February at 09:04, Hoeg sent an invitation for a Teams call at 10:00 that day.')]:
                message=next(m for m in candidate['messages'] if m['id']==mid)
                ref=message['source_refs'][0]
                candidate['facts'].append({'id':fid,'statement':statement,'status':'judicial_finding',
                                          'source_id':ref['source_id'],'source_quote':ref['quote']})
                message['fact_ids']=[fid]
                change(mid+'.fact_ids',[],[fid],'Complete fact-ledger link using existing literal source quote; message text unchanged')
        questions={q['id']:q for q in candidate['questions']}
        if spec['id']=='zh_loan_155':
            q=questions['q01'];before=copy.deepcopy(q)
            q.update(question='按截图显示的情境日期，赵某梅何时发来借据的转述文字？马某名何时表示不管算公司还是个人、他个人都认？',
                     answer='截图将赵某梅发来借据转述文字标为2016年4月3日（m003），将马某名个人认债表态标为2019年1月19日（m017）。这些是合成情境的显示日期，不能据此证明借据实际出具日期或真实电话认债时间。',
                     reasoning_steps=['读取m003旁的显示日期，而非推断未展示照片的落款。','读取m017的表态与显示日期；不能认定这是历史上首次认债。'])
            change('q01',before,q,'Do not infer invisible document date from an old answer or hidden judgment')
            q=questions['q02'];before=copy.deepcopy(q)
            q.update(answer='m003可见转述文字把借款人写作马某名；m021中赵某梅称个人签字、没有公司章，但截图未展示可核验的签名或印章；m017中马某名说个人都认。m022中他反称款用于公司经营。这些是聊天中的文字和主张，不等于验证了借据实物或确定了法律上的债务人。',
                     reasoning_steps=['m003展示个人借款人的转述文字。','m021是赵某梅关于签章的说法，并非截图可见的实物查验。','m017给出对方本人认债表态。','m022提供公司用款抗辩；结论仍限于聊天中双方说法。'])
            change('q02',before,q,'Distinguish displayed text and party assertions from unrendered document verification')
            q=questions['q04'];before=copy.deepcopy(q)
            q.update(question='这些截图能否唯一确定双方借款时有无约定利息？',
                     answer='不能。m003展示的借据转述文字没有利息条款，但未展示完整借据实物；m027中马某名否认当初说过利息，m028中赵某梅表示见面再算。截图既没有双方共同确认的约定，也不能排除未展示的其他沟通。',
                     reasoning_steps=['m003只能证明显示文字中没有利息条款，不能证明完整借据的内容。','m027与m028未形成明确一致的利息约定。','判断仅限提交的截图，未展示沟通仍可能存在。'])
            change('q04',before,q,'No inference about a complete invisible document; remove unseen rate hint')
        if spec['id']=='zh_employment_130':
            q=questions['q01'];before=copy.deepcopy(q)
            q.update(question='按截图显示的情境日期，付晨源发送辞职申请书，与张翔发送调职通知，哪个在先？郭某对调职通知如何回复？',
                     answer='辞职申请书在先：m002的显示日期为2024-04-01，调职通知m016为2024-04-12。郭某回复“我家在酒泉，我不同意”（m019）。这里按合成截图的显示日期排序，不以文件在目录中的顺序推定真实时序。',
                     minimal_message_ids=['m002','m016','m019'],
                     reasoning_steps=['在付晨源会话读取m002显示日期。','在张翔会话读取m016日期并比较。','m019显示郭某对调职通知的拒绝表态。'])
            change('q01',before,q,'Cross-conversation chronology must follow visible dates, not hidden global message ordering')
        if spec['id']=='en_probate_283':
            q=questions['q02'];before=copy.deepcopy(q)
            q.update(task='cross_conversation',
                     question="Compare the beneficiary named in Srimila's August 2016 proposal with the beneficiary Srikumaran names in December 2017. What does Oormila ask for, and do the chats explicitly identify 'amma' as '[mother]'?",
                     answer="Srimila proposes leaving everything to '[mother]' (m013). Srikumaran later says the will leaves everything to 'amma', nothing to the siblings (m031). Oormila asks for what 'papa said was for me' (m030). The displayed chats do not explicitly identify 'amma' as '[mother]'; that equivalence and the actual will's terms cannot be verified from these statements alone.",
                     minimal_message_ids=['m013','m030','m031'],
                     reasoning_steps=['m013 supplies the proposed beneficiary in the sibling conversation.','m030-m031 give the competing request and reported will terms in the later direct conversation.','Compare stated terms across conversations while preserving unresolved alias and document-verification limits.'])
            change('q02',before,q,'Old cross-conversation question cited only one conversation; add necessary evidence from both without assuming alias identity')
        for q in candidate['questions']:
            cited=set(re.findall(r'\bm\d{3}\b',q['answer']+' '+ ' '.join(q['reasoning_steps'])))
            missing=sorted(cited-set(q['minimal_message_ids']))
            if missing:
                before=list(q['minimal_message_ids']);q['minimal_message_ids']+=missing
                change(q['id']+'.minimal_message_ids',before,q['minimal_message_ids'],'Retain every message actually cited by answer or reasoning; necessity still unverified')
            q['minimal_set_status']='proposed_not_certified'
            if re.search(r'whole chat|entire chat|whole conversation|no message|no further message|整个聊天|全部消息|全程|始终',q['answer']+' '+' '.join(q['reasoning_steps']),re.I):
                q['evidence_scope']='whole_case_review_required_for_absence_claim'
                q['minimal_set_status']='local_positive_citations_do_not_prove_global_absence'
            else:q['evidence_scope']='cited_messages_candidate'
        write(folder/'curated.json',candidate)
        write(folder/'curation.json',{'author':'Codex agent review, not human legal approval',
              'input_file':'final.json','input_sha256':digest((folder/'final.json').read_bytes()),
              'output_sha256':digest((folder/'curated.json').read_bytes()),'corrections':corrections,
              'policy':'No judgment facts rewritten; generated candidate messages kept except placeholder display labels. Questions corrected against visible text; difficulty still pending human review.'})
        write(folder/'curated.checks.json',validate(candidate,source))
        print(spec['id'],'logged corrections',len(corrections),'checks',validate(candidate,source)['passed'])


if __name__=='__main__':main()

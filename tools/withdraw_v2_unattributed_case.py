"""Preserve an earlier candidate but exclude it after source-context review."""
import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read,save,status

def main():
    d=OUT/'zh/zh_0226';c=read(d/'case.json')
    reason='全文仅引述一条年卡拼团消息，未明确逐条发送者；胡XX提交截图不等于她发送。此前又将收据字段及双方诉辩写成微信往返，会添加未披露的沟通内容。撤回当前图集候选，保留历史稿和截图，待更完整同案由来源。'
    if not (d/'withdrawn.candidate.json').exists():save(d/'withdrawn.candidate.json',c)
    c=copy.deepcopy(c);c.update(status='withdrawn_source_gap',excluded_from_current_dataset=True)
    save(d/'case.json',c)
    save(d/'root.withdrawal.json',{'full_judgment_read':True,'source_chars':4406,'source_paragraphs':32,
        'review':'../../peer.repeated_long_quotes.review.json','reason':reason,'historical_images_preserved':True,
        'source_refs':[{'source_id':'p0012','quote':'胡XX向从化法院提交了微信聊天截图，内容为：“傅X年卡拼团成功，可再省二百几”'},
                       {'source_id':'p0015','quote':'胡XX向本院申请复议称：'}],
        'model_review_not_human':True})
    for name in ['tasks.image_only.json','questions.review.json']:
        if (d/name).exists() and not (d/('withdrawn.'+name)).exists():save(d/('withdrawn.'+name),read(d/name))
        save(d/name,[])
    for name in ['review.html','JUDGMENT.html']:
        path=d/name
        if path.exists():
            text=path.read_text(encoding='utf-8')
            if 'id="withdrawn-notice"' not in text:
                text=text.replace('<main>','<main><section id="withdrawn-notice" style="border:3px solid #b33434"><h1>已撤回：历史候选，不计入当前数据集</h1><p>'+reason+'</p><a href="root.withdrawal.json">撤回依据</a></section>',1)
                path.write_text(text,encoding='utf-8')
    status(d,'deferred',reason=reason,method='root_full_source_and_peer_review_withdrawal',historical_images_preserved=True)
    print('zh_0226 excluded; historical assets retained')

if __name__=='__main__':main()

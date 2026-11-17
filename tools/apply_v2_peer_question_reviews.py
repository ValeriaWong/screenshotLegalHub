"""Apply actually reviewed image-only question repairs, with before snapshots."""
import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read,save
from tools.v2_root_review import revise

def apply(ident,issues,qkey,akey):
    d=OUT/'zh'/ident;c=copy.deepcopy(read(d/'case.json'));notes=[]
    for issue in issues:
        q=next(q for q in c['questions'] if q['id']==issue.get('question_id'))
        q['question']=issue[qkey];q['answer']=issue[akey]
        notes.append({'severity':'major' if issue.get('priority')!='wording_suggestion' else 'minor',
            'question_ids':[q['id']],'message_ids':issue.get('message_ids',[]),
            'problem':issue.get('visible_evidence') or issue.get('evidence'),
            'change':'纯图片题仅使用可见身份、对象、金额及材料关系：'+issue[qkey]+' / '+issue[akey]})
    if ident=='zh_alt_0088':c['render_notes']='视频文件卡类型标注仅写视频，移除不合适的“视频 文档”；不补视频画面。'
    if issues:print(ident,revise(d,c,notes))

def main():
    numeric=read(OUT/'peer.numeric_questions.review.json');groups={}
    for issue in numeric['issues']:groups.setdefault(issue['case_id'],[]).append(issue)
    for ident,issues in groups.items():apply(ident,issues,'recommended_question','recommended_answer')
    reports=[]
    for item in read(OUT/'manifest.json')['supplemental_representatives']:
        ident=item['id'];r=read(OUT/'zh'/ident/'peer.supplement_questions.review.json')
        reports.append({'case_id':ident,'review_path':f'zh/{ident}/peer.supplement_questions.review.json',**r})
        apply(ident,r['issues'],'suggested_question','suggested_answer')
    save(OUT/'peer.supplement_questions.review.json',{'reviewer':'writer_2','human_review':False,'new_human_score':None,
        'cases':reports,'cases_checked':len(reports),'questions_checked':sum(len(r['questions_checked']) for r in reports),
        'screenshots_viewed':sum(len(r['images_inspected']) for r in reports),
        'issues_applied':sum(len(r['issues']) for r in reports),'difficulty_certified':False})

if __name__=='__main__':main()

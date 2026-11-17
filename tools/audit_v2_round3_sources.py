"""Audit source metadata and communication support, preserving original source cells."""
from pathlib import Path
from collections import Counter
import json,re,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.v2_cause_batch import OUT,read,save,processing_items


def number_key(value):return re.sub(r'\s','',str(value)).replace('（','(').replace('）',')')


def court_key(value):return number_key(re.sub(r'[（(].*?[）)]','',str(value)))


def chinese_date(text):
    digits={'〇':'0','零':'0','○':'0','Ｏ':'0','O':'0','一':'1','二':'2','三':'3','四':'4','五':'5','六':'6','七':'7','八':'8','九':'9'}
    def small(value):
        value=''.join(digits.get(c,c) for c in value)
        if '十' in value:
            left,right=value.split('十');return int(left or '1')*10+int(right or '0')
        return int(value)
    matches=re.findall(r'([〇零○ＯO一二三四五六七八九\d]{4})年([一二三四五六七八九十\d]{1,3})月([一二三四五六七八九十\d]{1,3})日',text)
    if not matches:return None
    y,m,d=matches[-1]
    return f'{small(y):04d}-{small(m):02d}-{small(d):02d}'


def main():
    results=[];counts=Counter()
    for item in processing_items():
        directory=OUT/'zh'/item['id'];s=read(directory/'source.json');meta=read(directory/'source.verification.json')
        text=s['text'];warnings=[]
        candidates=re.findall(r'[（(][12]\d{3}[）)][^\s\n，。；]{2,35}号',text[:1800])
        first=candidates[0] if candidates else None
        raw_has_number=bool(re.search(r'[（(][12]\d{3}[）)].*号',s['case_no']))
        raw_is_date=bool(re.fullmatch(r'\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}',s['case_no']))
        if not raw_has_number:
            warnings.append('归档案号字段不是通常的案号格式'+('，实际形似日期' if raw_is_date else ''))
        rotation=raw_is_date and bool(re.search(r'[（(][12]\d{3}[）)].*号',str(meta.get('court','')))) and '法院' in str(meta.get('date',''))
        heading_court=next((p['text'].strip() for p in s['paragraphs'][:4] if '法院' in p['text']),None)
        heading_date=chinese_date('\n'.join(p['text'] for p in s['paragraphs'][-12:]))
        recovered={};rotation_verified=False
        if rotation:
            raw_day=s['case_no'].replace('.','-').replace('/','-')
            rotation_verified=number_key(first)==number_key(meta['court']) and court_key(heading_court)==court_key(meta['date']) and raw_day==heading_date
            warnings.append('案号/日期/法院三字段循环错位'+('；与正文案号、法院及落款日期核对一致，可用派生字段展示' if rotation_verified else '；正文核对尚未全部一致'))
            if rotation_verified:recovered={'case_no':first,'court':heading_court,'date':heading_date}
        if re.search(r'[（(][12]\d{3}[）)].*号',str(meta.get('date',''))):warnings.append('归档日期字段疑似填入案号，可能为列交换')
        if '行政' in s['title'] and s['cause'].startswith('民事>'):warnings.append('标题显示行政文书，与民事来源标签不一致，需要人工核对或换源')
        # No keyword does not establish impossibility; it identifies a reconstruction-only source.
        communication_keywords=[word for word in ['微信','聊天','短信','QQ','电子邮件','邮件'] if word in text]
        if not communication_keywords:warnings.append('未找到通信关键词；只可考虑明确标注的事实场景创作，不可声称存在聊天原文')
        excerpts=[]
        for p in s['paragraphs']:
            if any(word in p['text'] for word in ['微信','聊天','短信','QQ']):
                excerpts.append({'paragraph_id':p['id'],'char_start':p['char_start'],'char_end':p['char_end'],
                                 'quoted_text_indicator':'“' in p['text'],'characters':len(p['text'])})
        result={'case_id':s['id'],'raw_case_no':s['case_no'],'case_no_from_text':first,
                'raw_date':meta.get('date'),'raw_date_contains_case_no':bool(re.search(r'[（(][12]\d{3}[）)].*号',str(meta.get('date','')))),
                'court':meta.get('court'),'cause':s['cause'],'warnings':warnings,
                'metadata_three_field_rotation':bool(rotation),'metadata_rotation_verified_against_text':rotation_verified,
                'recovered_fields':recovered,'judgment_heading_court':heading_court,'judgment_signature_date':heading_date,
                'court_parenthetical_alias_ignored_for_comparison':bool(rotation and number_key(heading_court)!=number_key(meta.get('date')) and court_key(heading_court)==court_key(meta.get('date'))),
                'communication_keywords':communication_keywords,'communication_paragraphs':excerpts,
                'source_cells_modified':False,'case_number_recovery_basis':'first case-number occurrence in judgment opening; verify identity before release'}
        save(directory/'source.audit.json',result);results.append(result)
        counts['metadata_case_number_warnings']+=not raw_has_number
        counts['metadata_three_field_rotations']+=bool(rotation)
        counts['metadata_rotations_verified']+=rotation_verified
        counts['possible_case_number_date_swaps']+=result['raw_date_contains_case_no']
        counts['title_label_type_mismatches']+=any('标题' in w for w in warnings)
        counts['without_communication_keywords']+=not communication_keywords
    save(OUT/'source_audit.json',{'cases':len(results),'counts':dict(counts),'records':results,
                                  'classification_scope':'historical source labels; not adjudicated/corrected taxonomy'})
    report=['# 中文来源核查','',f'核查207宗原始代表及 {len(results)-207} 宗独立候补判决。统计：{dict(counts)}。','',
            '来源标签、案号与日期字段均保持原始归档值。正文案号候选及字段冲突单独记录；“未找到通信关键词”不代表一定不能生成，只意味着不能宣称有聊天原文。','',
            '三字段错位核对：归档案号实际为日期、归档日期实际为法院、归档法院实际为案号。只有三项与正文首部和落款日期均一致时，生成 recovered_fields 供展示使用；原工作簿与原归档字段不修改。','',
            '| ID | 原案号字段 | 正文首个案号 | 问题 |','|---|---|---|---|']
    for r in results:
        if r['warnings']:report.append(f'| {r["case_id"]} | {r["raw_case_no"]} | {r["case_no_from_text"] or "待核"} | '+ '；'.join(r['warnings']).replace('|','/')+' |')
    (OUT/'SOURCE_AUDIT.md').write_text('\n'.join(report),encoding='utf-8')
    print(json.dumps({'cases':len(results),'counts':dict(counts)},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()

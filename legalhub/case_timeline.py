"""Source-ordered case timeline and bidirectional citation graph; no model calls."""
import re

CLOCK = re.compile(r'(?P<day>前天|昨天|今天)?\s*(?P<period>上午|下午|晚上|凌晨|中午)?\s*(?P<hour>\d{1,2})[:：](?P<minute>\d{2})')

def visible_clock(message):
    # Phone status-bar time and timestamps inferred by extraction are not anchors.
    if message.get('speaker_local_id')!='system':return None
    text=message['text'].strip();match=CLOCK.fullmatch(text)
    if not match:return None
    hour=int(match['hour']);minute=int(match['minute'])
    if hour>23 or minute>59:return None
    if match['period'] in ('下午','晚上') and hour<12:hour+=12
    if match['period'] in ('上午','凌晨') and hour==12:hour=0
    if match['period']=='中午' and hour<11:hour+=12
    return {'raw':text,'label':f"{match['day'] or '日期未明'} {hour:02d}:{minute:02d}",
            'relative_day':match['day'],'minutes':hour*60+minute,'calendar_date':None}

def build_timeline(material, analysis, image_conversations=None):
    images=sorted(material['images'],key=lambda x:x['display_page'])
    image_rank={x['image_id']:n for n,x in enumerate(images)}
    original={m['id']:n for n,m in enumerate(material['records'])}
    messages=sorted(material['records'],key=lambda m:(image_rank[m['image_id']],original[m['id']]))
    position={m['id']:n for n,m in enumerate(messages)}
    meanings=(analysis or {}).get('meanings',[]);facts=(analysis or {}).get('facts',[])
    refs={m['id']:{'meaning_ids':[],'milestone_ids':[]} for m in messages}
    for kind,records in [('meaning_ids',meanings),('milestone_ids',facts)]:
        for record in records:
            for mid in dict.fromkeys(record['supporting_message_ids']):
                if mid not in refs:raise ValueError('Timeline citation outside case')
                refs[mid][kind].append(record['id'])
    timings={};pages=[];last_clock=None;previous_number=None;previous_conversation=None
    for image in images:
        suffix=re.search(r'_image_(\d+)',image['image_id'])
        source_number=int(suffix[1]) if suffix else None
        conversation=(image_conversations or {}).get(image['image_id'])
        if conversation!=previous_conversation:last_clock=None
        if previous_number is None or source_number is None or source_number!=previous_number+1:last_clock=None
        rows=[m for m in messages if m['image_id']==image['image_id']];anchors=[]
        for message in rows:
            clock=visible_clock(message)
            if clock:last_clock=clock;anchors.append(dict(clock,message_id=message['id']))
            timings[message['id']]={'label':clock['label'] if clock else last_clock['label']+'之后' if last_clock else '未显示会话时刻',
                                      'basis':'visible_marker' if clock else 'after_visible_marker_source_order' if last_clock else 'source_order_only',
                                      'anchor_raw':last_clock['raw'] if last_clock else None,'calendar_date':None}
        related_meanings=[r['id'] for r in meanings if any(mid in {m['id'] for m in rows} for mid in r['supporting_message_ids'])]
        related_facts=[r['id'] for r in facts if any(mid in {m['id'] for m in rows} for mid in r['supporting_message_ids'])]
        label=(anchors[0]['label']+(' — '+anchors[-1]['label'].split(' ',1)[-1] if len(anchors)>1 else '')) if anchors else '本图未显示会话时刻'
        pages.append({'image_id':image['image_id'],'page':image['display_page'],'time_label':label,'anchors':anchors,
                      'message_ids':[m['id'] for m in rows],'meaning_ids':related_meanings,'milestone_ids':related_facts,
                      'order_basis':'visible_markers_with_source_order' if anchors else 'source_order_only'})
        previous_number=source_number
        previous_conversation=conversation
    def first(ids):return min(ids,key=position.__getitem__)
    nodes=[]
    for fact in sorted(facts,key=lambda r:position[first(r['supporting_message_ids'])]):
        mids=list(dict.fromkeys(fact['supporting_message_ids']));linked=[r['id'] for r in meanings if set(mids)&set(r['supporting_message_ids'])]
        all_support=set(mids)|{mid for r in meanings if r['id'] in linked for mid in r['supporting_message_ids']}
        nodes.append({'id':fact['id'],'title':fact['title'],'message_ids':mids,'meaning_ids':linked,
                      'image_ids':sorted({m['image_id'] for m in messages if m['id'] in mids},key=image_rank.__getitem__),
                      'source_image_ids':sorted({m['image_id'] for m in messages if m['id'] in all_support},key=image_rank.__getitem__),
                      'time':timings[first(mids)],'basis':'fact_node_from_cited_conversation'})
    meaning_links={r['id']:{'message_ids':list(dict.fromkeys(r['supporting_message_ids'])),
                           'milestone_ids':[n['id'] for n in nodes if r['id'] in n['meaning_ids']],
                           'time':timings[first(r['supporting_message_ids'])]} for r in meanings}
    for links in refs.values():
        links['meaning_milestone_ids']=list(dict.fromkeys(node for mid in links['meaning_ids'] for node in meaning_links[mid]['milestone_ids']))
    return {'pages':pages,'milestones':nodes,'message_links':refs,'meaning_links':meaning_links,'message_times':timings,
            'order_basis':'Visible conversation-time anchors and source sequence; unknown dates stay unknown.',
            'calendar_date_confirmed':False,'model_requests':0,
            'time_note':'按截图中可见的会话时间锚点及消息顺序阅读。“之后”表示相对顺序，不是该消息的确切发送时间；“昨天”的日历日期未核实。缺失截图及未标时刻保留说明。'}

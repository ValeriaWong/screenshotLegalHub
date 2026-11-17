"""Lossless, owner-scoped screenshot review; immutable originals and transactional CAS writes."""
import copy
import json
from collections import Counter
from pydantic import Field
from typing import Literal
from .contracts import Contract, digest, now
from .store import Conflict
from . import audit

VERSION = 'screenshot-review.v1'
POLICY = '本包为合成数据审核结果，不是真实聊天记录或司法证据。引文、事实转述与模拟补全须分别标记；未提供的逐字原话、时间与身份不得声称来自判决书。'
Dataset = Literal['A', 'B']

class MessageReview(Contract):
    message_id: str
    verdict: Literal['correct','wrong_speaker','wrong_text','wrong_time','extra','uncertain','wrong_fields']
    corrected_speaker: str | None = None
    corrected_text: str | None = None
    corrected_time: str | None = None
    note: str = Field(default='', max_length=30000)
    field_patch: dict = Field(default_factory=dict)
    origin_type: Literal['verbatim_quote','judgment_paraphrase','synthetic_completion','unsupported'] | None = None
    source_quote: str = ''
    time_basis: Literal['source','simulated','unknown'] | None = None
    speaker_basis: Literal['source','simulated','unknown'] | None = None

class AddedMessage(Contract):
    id: str = Field(min_length=1, max_length=200)
    after_message_id: str | None = None
    speaker: str = Field(min_length=1)
    text: str = Field(min_length=1)
    time: str | None = None
    fields: dict = Field(default_factory=dict)
    origin_type: Literal['verbatim_quote','judgment_paraphrase','synthetic_completion'] | None = None
    source_quote: str = ''

class ItemReview(Contract):
    verdict: Literal['pass','needs_fix','unreadable','discard','regen']
    comment: str = ''
    regen_instruction: str = ''
    added_messages: list[AddedMessage] = Field(default_factory=list, max_length=1000)

class SaveMessage(Contract):
    expected_version: int = Field(ge=0)
    review: MessageReview | None = None

class SaveItem(Contract):
    expected_version: int = Field(ge=0)
    review: ItemReview

class VersionRequest(Contract):
    expected_version: int = Field(ge=0)

class LockRequest(VersionRequest):
    export_sha256: str

class RestoreRequest(VersionRequest):
    backup: dict

def at(raw, keys):
    value = raw
    for key in keys:
        if isinstance(value, str):
            value = json.loads(value)
        value = value[key]
    return value

def replace_at(raw, keys, value):
    if not keys:
        return copy.deepcopy(value)
    encoded = isinstance(raw, str)
    obj = json.loads(raw) if encoded else copy.deepcopy(raw)
    key, *rest = keys
    obj[key] = replace_at(obj[key], rest, value)
    return json.dumps(obj, ensure_ascii=False) if encoded else obj

def merge_fields(original, patch):
    out = copy.deepcopy(original)
    for key, value in patch.items():
        out[key] = merge_fields(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else copy.deepcopy(value)
    return out

def project(raw, message_path, indices=None):
    messages = at(raw, message_path)
    if not isinstance(messages, list) or not messages:
        raise ValueError('没有可核对的消息列表')
    indices = list(range(len(messages))) if indices is None else indices
    result, speakers = [], []
    for index in indices:
        msg = messages[index]
        if not isinstance(msg, dict):
            raise ValueError('消息必须是 JSON 对象')
        fields = dict(speaker=next((k for k in ['speaker','sender_id','speaker_id'] if k in msg),'speaker'),
                      text=next((k for k in ['text','content'] if k in msg),'content' if 'conversation' in message_path else 'text'),
                      time=next((k for k in ['timestamp','time'] if k in msg),'timestamp' if 'conversation' in message_path else 'time'))
        speaker = str(msg.get(fields['speaker']) or 'unknown')
        if speaker not in speakers:
            speakers.append(speaker)
        side = msg.get('side')
        inferred = side not in ['left','right']
        if inferred:
            side = 'left' if speakers.index(speaker) % 2 == 0 else 'right'
        text = msg.get(fields['text'])
        if text is not None and not isinstance(text, str):
            raise ValueError('消息文本类型需要单独映射')
        result.append(dict(id=str(msg.get('id', 'm'+str(index+1))), source_index=index,
                           speaker=speaker, text=text or '', time=msg.get(fields['time']),
                           side=side, side_inferred=inferred, fields=fields, raw=copy.deepcopy(msg)))
    ids = [m['id'] for m in result]
    if len(ids) != len(set(ids)):
        raise ValueError('消息 ID 重复，需先核对映射')
    return result

def validate_message(item, data):
    review = MessageReview.model_validate(data).model_dump()
    msg = next((m for m in item['messages'] if m['id'] == review['message_id']), None)
    if not msg:
        raise ValueError('消息不属于当前截图')
    verdict = review['verdict']
    if verdict != 'correct' and not review['note'].strip():
        raise ValueError('判错或存疑必须写明原因')
    field = {'wrong_speaker':'corrected_speaker','wrong_text':'corrected_text','wrong_time':'corrected_time'}.get(verdict)
    if field and not (review[field] or '').strip():
        raise ValueError('必须填写对应的改后值；无法辨认请选存疑')
    for key in ['corrected_speaker','corrected_text','corrected_time']:
        if key != field and review[key] is not None:
            raise ValueError('改后值与当前判项不一致')
    if verdict == 'wrong_speaker' and review[field] not in item['speakers']:
        raise ValueError('改后说话人必须来自本图名单')
    patch = review['field_patch']
    json.dumps(patch,allow_nan=False)
    if verdict=='wrong_fields' and not patch:
        raise ValueError('多模态字段改错必须提供字段补丁')
    if 'message_bbox' in patch:
        box=merge_fields(msg['raw'],patch).get('message_bbox')
        if not isinstance(box,dict) or not all(isinstance(box.get(k),(int,float)) and not isinstance(box.get(k),bool) for k in ['min_x','min_y','max_x','max_y']) or not (0 <= box['min_x'] < box['max_x'] and 0 <= box['min_y'] < box['max_y']):
            raise ValueError('消息框必须保留有效的 min/max 坐标')
    if set(patch) - set(msg['raw']) or set(patch) & (set(msg['fields'].values()) | {'id'}):
        raise ValueError('多模态修正只能修改原有附加字段，文字、时间和说话人使用对应判项')
    if patch and (not review['note'].strip() or verdict in ['correct','extra','uncertain']):
        raise ValueError('多模态修正必须选择改错判项并填写原因')
    if item['dataset'] == 'B':
        if not all(review[k] for k in ['origin_type','time_basis','speaker_basis']):
            raise ValueError('合成消息须分别标记内容、时间和说话人的来源依据')
        quote = review['source_quote'].strip()
        needs_quote = review['origin_type'] in ['verbatim_quote','judgment_paraphrase'] or review['time_basis'] == 'source' or review['speaker_basis'] == 'source'
        if needs_quote and (not quote or quote not in item['judgment_excerpt']):
            raise ValueError('来源依据必须引用本图判决书摘录中的实际原文')
        final_text = review['corrected_text'] if verdict == 'wrong_text' else msg['text']
        if review['origin_type'] == 'verbatim_quote' and (not final_text or final_text not in quote):
            raise ValueError('逐字引文必须与引用原文一致')
        if review['time_basis'] == 'source':
            time = review['corrected_time'] if verdict == 'wrong_time' else msg['time']
            if not time or str(time) not in quote:
                raise ValueError('判决书未提供此具体时间；请标记模拟或未知')
        if verdict == 'correct' and review['origin_type'] == 'unsupported':
            raise ValueError('无来源支持的事实不能判为内容对')
    return review

def validate_item(item, data, reviews):
    review = ItemReview.model_validate(data).model_dump()
    allowed = ['pass','needs_fix','unreadable','discard'] if item['dataset']=='A' else ['pass','regen','discard']
    if review['verdict'] not in allowed:
        raise ValueError('整图判项不适用于当前数据集')
    if review['verdict'] != 'pass' and not review['comment'].strip():
        raise ValueError('未通过的整图审核必须写明原因')
    if review['verdict'] == 'regen' and not review['regen_instruction'].strip():
        raise ValueError('需重生成必须填写总指令')
    ids = {m['id'] for m in item['messages']}
    added_ids = set()
    for added in review['added_messages']:
        if added['id'] in ids | added_ids or added['after_message_id'] not in ids | {None}:
            raise ValueError('新增消息 ID 或插入位置无效')
        if added['speaker'] not in item['speakers']:
            raise ValueError('新增消息说话人必须来自本图名单')
        added_ids.add(added['id'])
        if item['dataset']=='B':
            if not added['origin_type']:
                raise ValueError('新增合成消息必须标记来源类型')
            if added['origin_type'] != 'synthetic_completion':
                quote = added['source_quote'].strip()
                if not quote or quote not in item['judgment_excerpt']:
                    raise ValueError('新增消息来源引文无效')
                if added['origin_type']=='verbatim_quote' and added['text'] not in quote:
                    raise ValueError('新增逐字引文与来源不一致')
    if review['verdict']=='regen' and (len(reviews)!=len(ids) or any(r['verdict']=='uncertain' or (r['origin_type']=='unsupported' and r['verdict']!='extra') for r in reviews.values())):
        raise ValueError('重生成前须完成逐条审核并处理存疑及无依据事实')
    if review['verdict'] == 'pass':
        if review['added_messages'] or len(reviews) != len(ids) or any(r['verdict'] != 'correct' or r['field_patch'] or r['origin_type']=='unsupported' for r in reviews.values()):
            raise ValueError('仍有未审、改错或存疑消息，不能判整图通过')
    return review

def added_raw(item, addition):
    fields = item['messages'][0]['fields']
    return {**addition['fields'], 'id':addition['id'], fields['speaker']:addition['speaker'],
            fields['text']:addition['text'], fields['time']:addition['time'], 'added':True}

def corrected(item, reviews, item_review):
    original = copy.deepcopy(at(item['original_json'],item['message_path']))
    additions = (item_review or {}).get('added_messages',[])
    by_index = {m['source_index']:m for m in item['messages']}
    output = []
    for index, raw in enumerate(original):
        msg = by_index.get(index)
        review = reviews.get(msg['id']) if msg else None
        if not review or review['verdict'] != 'extra':
            value = merge_fields(raw,review['field_patch']) if review else copy.deepcopy(raw)
            if review:
                for verdict, target, key in [('wrong_speaker','speaker','corrected_speaker'),('wrong_text','text','corrected_text'),('wrong_time','time','corrected_time')]:
                    if review['verdict']==verdict:
                        value[msg['fields'][target]] = review[key]
            output.append(value)
        if msg:
            output.extend(added_raw(item,a) for a in additions if a['after_message_id']==msg['id'])
    output.extend(added_raw(item,a) for a in additions if a['after_message_id'] is None)
    return replace_at(item['original_json'],item['message_path'],output), output

def regen_draft(item, reviews, item_review):
    rows = [POLICY, '重生成本图的合成对话；以下是修正目标，不是司法事实真值。']
    for index, msg in enumerate(item['messages'],1):
        r = reviews.get(msg['id'])
        if not r:
            rows.append(f'第 {index} 条尚未审核，不得当作正确内容保留。')
            continue
        prefix = '删除' if r['verdict']=='extra' else '存疑待核对' if r['verdict']=='uncertain' else '保留' if r['verdict']=='correct' else '改正'
        rows.append(f'{prefix}第 {index} 条：原话 {msg["text"]}；说话人 {r["corrected_speaker"] or msg["speaker"]}；文字 {r["corrected_text"] or msg["text"]}；时间 {r["corrected_time"] or msg["time"] or "未知"}；依据 {r["origin_type"]}；批注 {r["note"]}')
    for a in (item_review or {}).get('added_messages',[]):
        rows.append(f'在 {a["after_message_id"] or "末尾"} 后增加：{a["speaker"]}：{a["text"]}；时间 {a["time"] or "未知"}；依据 {a["origin_type"]}')
    rows.append('不得添加来源不支持的事实。模拟措辞、时间和身份必须继续标为合成；存疑内容不纳入已核准对话。')
    return '\n'.join(rows)

class ScreenshotReview:
    def __init__(self,store):
        self.store = store

    def state(self, owner, dataset, db=None):
        if dataset not in ['A','B']:
            raise ValueError('未知数据集')
        return self.store.optional('screenshot.panel',dataset,owner,db) or dict(id=dataset,dataset=dataset,version=0,locked_at=None,updated_at=None,items=[],message_reviews={},item_reviews={},scope=None)

    def public(self, state):
        items = [{k:v for k,v in i.items() if k not in ['original_json','source_ref','source_url','judgment_ref']} for i in state['items']]
        for item in items:
            item['messages'] = [{k:v for k,v in m.items() if k!='raw'} for m in item['messages']]
        return {**state, 'items':items, 'counts':self.counts(state)}

    def counts(self, state):
        complete = sum(bool(state['item_reviews'].get(i['id'])) and len(state['message_reviews'].get(i['id'],{}))==len(i['messages']) for i in state['items'])
        return dict(items=len(state['items']),items_reviewed=complete,messages=sum(len(i['messages']) for i in state['items']),
                    messages_reviewed=sum(len(r) for r in state['message_reviews'].values()),
                    by_item_verdict=dict(Counter(r['verdict'] for r in state['item_reviews'].values())))

    def writable(self, owner, dataset, version, db):
        state = self.state(owner,dataset,db)
        if state['locked_at']:
            raise Conflict('当前数据集已锁定，不能修改或恢复；导出仍可用')
        if state['version'] != version:
            raise Conflict('审核已在另一窗口更新，请重新载入后再保存')
        return state

    def commit(self,owner,state,db,action="saved",**details):
        state['version'] += 1
        state['updated_at'] = now()
        state.pop('last_export',None)
        self.store.put('screenshot.panel',state,owner,db)
        audit.emit(db,owner,'screenshot.'+action,'screenshot.panel',state['dataset'],details=dict(dataset=state['dataset'],version=state['version'],counts=self.counts(state),**details))
        return self.public(state)

    def item(self,state,id):
        item=next((i for i in state['items'] if i['id']==id),None)
        if not item:
            raise ValueError('截图不属于当前数据集')
        return item

    def initialize(self,owner,dataset,items,scope,version):
        if not items:
            raise ValueError('没有可用截图')
        with self.store.tx() as db:
            state=self.writable(owner,dataset,version,db)
            if state['items']:
                raise Conflict('本批已有固定清单，不能替换原始数据')
            if any(i['dataset']!=dataset for i in items) or len({i['id'] for i in items})!=len(items):
                raise ValueError('清单 ID 或数据集不一致')
            state.update(items=copy.deepcopy(items),scope=scope,manifest_hash=digest(items))
            return self.commit(owner,state,db,'initialized')

    def save_message(self,owner,dataset,item_id,message_id,payload):
        with self.store.tx() as db:
            state=self.writable(owner,dataset,payload.expected_version,db)
            item=self.item(state,item_id)
            if message_id not in {m['id'] for m in item['messages']}:
                raise ValueError('未知消息')
            reviews=state['message_reviews'].setdefault(item_id,{})
            if payload.review is None:
                reviews.pop(message_id,None)
            else:
                if payload.review.message_id!=message_id:
                    raise ValueError('消息 ID 不一致')
                reviews[message_id]=validate_message(item,payload.review.model_dump())
            state['item_reviews'].pop(item_id,None)
            return self.commit(owner,state,db,'message_saved' if payload.review else 'message_cleared',item_id=item_id,message_id=message_id)

    def save_item(self,owner,dataset,item_id,payload):
        with self.store.tx() as db:
            state=self.writable(owner,dataset,payload.expected_version,db)
            item=self.item(state,item_id)
            state['item_reviews'][item_id]=validate_item(item,payload.review.model_dump(),state['message_reviews'].get(item_id,{}))
            return self.commit(owner,state,db,'item_saved',item_id=item_id)

    def build_export(self,state):
        items=[]
        for item in state['items']:
            reviews=state['message_reviews'].get(item['id'],{})
            ir=state['item_reviews'].get(item['id'])
            raw,messages=corrected(item,reviews,ir)
            items.append(dict(id=item['id'],dataset=state['dataset'],source_ref=item['source_ref'],source_sha256=item['source_sha256'],
                              annotation_level=item['annotation_level'],image=item['asset'],message_path=item['message_path'],
                              message_mapping=[dict(id=m['id'],source_index=m['source_index'],fields=m['fields'],side_inferred=m['side_inferred']) for m in item['messages']],
                              original_json=item['original_json'],original_messages=at(item['original_json'],item['message_path']),
                              reviews=list(reviews.values()),item_review=ir,item_verdict=ir['verdict'] if ir else None,
                              added_messages=(ir or {}).get('added_messages',[]),corrected_messages=messages,corrected_json=raw,
                              judgment_excerpt=item['judgment_excerpt'],judgment_ref=item.get('judgment_ref',''),source_url=item.get('source_url',''),synthetic=state['dataset']=='B',
                              unresolved_message_ids=[m['id'] for m in item['messages'] if m['id'] not in reviews or reviews[m['id']]['verdict']=='uncertain'],
                              correction_status='reviewed' if ir and len(reviews)==len(item['messages']) else 'draft'))
        return dict(contract=VERSION,batch='chat-screenshot-review',dataset=state['dataset'],version=state['version'],locked_at=state['locked_at'],
                    manifest_hash=state.get('manifest_hash'),scope=state['scope'],counts=self.counts(state),items=items,
                    synthetic=state['dataset']=='B',fact_policy=POLICY if state['dataset']=='B' else '原始 JSON 全字段保留，修正层独立存储；标注等级以范围清单为准。')

    def export(self,owner,dataset):
        with self.store.tx() as db:
            state=self.state(owner,dataset,db)
            export=self.build_export(state)
            checksum=digest(export)
            export.update(export_sha256=checksum,exported_at=now())
            state['last_export']=dict(sha256=checksum,version=state['version'])
            self.store.put('screenshot.panel',state,owner,db)
            audit.emit(db,owner,'screenshot.exported','screenshot.panel',dataset,details=dict(dataset=dataset,version=state['version'],export_sha256=checksum))
            return export

    def lock(self,owner,dataset,payload):
        with self.store.tx() as db:
            state=self.writable(owner,dataset,payload.expected_version,db)
            counts=self.counts(state)
            if not counts['items'] or counts['items_reviewed']!=counts['items'] or counts['messages_reviewed']!=counts['messages']:
                raise ValueError('全部截图和全部消息都明确审核后才能锁定')
            for item in state['items']:
                reviews={k:validate_message(item,r) for k,r in state['message_reviews'][item['id']].items()}
                validate_item(item,state['item_reviews'][item['id']],reviews)
            export=state.get('last_export',{})
            if export.get('version')!=state['version'] or export.get('sha256')!=payload.export_sha256 or digest(self.build_export(state))!=payload.export_sha256:
                raise Conflict('请先导出当前完整版本并核对，再锁定')
            state['locked_at']=now()
            return self.commit(owner,state,db,'locked')

    def restore(self,owner,dataset,payload):
        backup=copy.deepcopy(payload.backup)
        checksum=backup.pop('export_sha256',None)
        backup.pop('exported_at',None)
        if not checksum or checksum!=digest(backup) or backup.get('contract')!=VERSION or backup.get('dataset')!=dataset:
            raise ValueError('不是有效的本数据集导出 JSON；未做任何恢复')
        with self.store.tx() as db:
            state=self.writable(owner,dataset,payload.expected_version,db)
            if backup.get('manifest_hash')!=state.get('manifest_hash'):
                raise ValueError('备份与当前原始清单不一致；未做任何恢复')
            entries=backup.get('items',[])
            if not isinstance(entries,list) or any(not isinstance(r,dict) or not isinstance(r.get('id'),str) for r in entries):
                raise ValueError('备份截图清单格式无效')
            if len(entries)!=len(state['items']) or {r['id'] for r in entries}!={i['id'] for i in state['items']}:
                raise ValueError('备份截图清单缺失或重复')
            if backup.get('scope')!=state['scope'] or backup.get('synthetic')!=(dataset=='B'):
                raise ValueError('备份的数据范围或合成标识不一致')
            canonical={r['id']:r for r in self.build_export(state)['items']}
            frozen_fields=['dataset','source_ref','source_sha256','annotation_level','image','message_path','message_mapping','original_json','original_messages','judgment_excerpt','judgment_ref','source_url','synthetic']
            new_messages={};new_items={}
            for entry in entries:
                item=self.item(state,entry['id'])
                if any(entry.get(key)!=canonical[item['id']][key] for key in frozen_fields):
                    raise ValueError('备份原始数据或映射不一致')
                if not isinstance(entry.get('reviews'),list):
                    raise ValueError('备份逐条审核格式无效')
                reviews={}
                for raw in entry['reviews']:
                    review=validate_message(item,raw)
                    if review['message_id'] in reviews:
                        raise ValueError('备份消息审核重复')
                    reviews[review['message_id']]=review
                new_messages[item['id']]=reviews
                if entry.get('item_review') is not None:
                    new_items[item['id']]=validate_item(item,entry['item_review'],reviews)
                ir=new_items.get(item['id'])
                corrected_json,corrected_messages=corrected(item,reviews,ir)
                if entry.get('corrected_json')!=corrected_json or entry.get('corrected_messages')!=corrected_messages:
                    raise ValueError('备份修正结果与审核层不一致')
            state.update(message_reviews=new_messages,item_reviews=new_items)
            return self.commit(owner,state,db,'restored')

    def regen(self,owner):
        state=self.state(owner,'B')
        jobs=[]
        for item in state['items']:
            ir=state['item_reviews'].get(item['id'])
            if not ir or ir['verdict']!='regen':
                continue
            reviews=state['message_reviews'].get(item['id'],{})
            if len(reviews)!=len(item['messages']) or any(r['verdict']=='uncertain' or (r['origin_type']=='unsupported' and r['verdict']!='extra') for r in reviews.values()):
                raise ValueError('重生成包仍有未审、存疑或无依据的事实，请先核对')
            selected={m['id'] for m in item['messages']} | {a['id'] for a in ir['added_messages']}
            original=at(item['original_json'],item['message_path'])
            stable=copy.deepcopy(item)
            original_with_ids=[dict(m,id=str(m.get('id','m'+str(i+1)))) for i,m in enumerate(original)]
            stable['original_json']=replace_at(item['original_json'],item['message_path'],original_with_ids)
            _,all_messages=corrected(stable,reviews,ir)
            jobs.append(dict(item_id=item['id'],synthetic=True,judgment_excerpt=item['judgment_excerpt'],judgment_ref=item.get('judgment_ref',''),source_url=item.get('source_url',''),source_ref=item['source_ref'],
                             instruction=ir['regen_instruction'],review_constraints=regen_draft(item,reviews,ir),
                             corrected_dialogue=[m for m in all_messages if str(m['id']) in selected],
                             factual_basis=list(reviews.values()),must_add=ir['added_messages'],
                             must_delete_message_ids=[k for k,r in reviews.items() if r['verdict']=='extra']))
        return dict(contract=VERSION,batch='chat-screenshot-review-regen',exported_at=now(),synthetic=True,fact_policy=POLICY,jobs=jobs)

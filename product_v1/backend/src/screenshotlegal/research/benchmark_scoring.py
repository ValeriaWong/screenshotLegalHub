"""Versioned, offline benchmark scoring. Legacy arithmetic stays in benchmark_legacy."""
import json
import math
import unicodedata
from decimal import Decimal, InvalidOperation

VERSION='kie-vqa-score.v1'

def normalize(value):
    return unicodedata.normalize('NFC',value).strip() if isinstance(value,str) else value

def box(value,width,height,tolerance=1e-8):
    if isinstance(value,dict): value=[value.get(k) for k in ['min_x','min_y','max_x','max_y']]
    if not isinstance(value,(list,tuple)) or len(value)!=4: raise ValueError('坐标必须为四个原图像素值')
    if any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) for v in value): raise ValueError('坐标必须为有限数字')
    x,y,r,b=value
    if r<=x or b<=y or x < -tolerance or y < -tolerance or r>width+tolerance or b>height+tolerance: raise ValueError('坐标倒置、无面积或超出原图')
    return [max(0.,float(x)),max(0.,float(y)),min(float(width),float(r)),min(float(height),float(b))]

def parse(raw):
    if isinstance(raw,dict):
        json.dumps(raw,allow_nan=False)
        return raw
    if not isinstance(raw,str): raise ValueError('输出必须为JSON字符串或对象')
    text=raw.strip()
    if text.startswith(chr(96)*3): text='\n'.join(text.splitlines()[1:-1])
    data=json.loads(text)
    json.dumps(data,allow_nan=False)
    if not isinstance(data,dict): raise ValueError('输出必须为JSON对象')
    return data

def kie(value,width,height):
    data=parse(value)
    if 'dialog_name' not in data or not isinstance(data.get('conversation'),list) or not isinstance(data.get('dialog_name'),(str,type(None))): raise ValueError('缺少dialog_name或conversation')
    normalized=[]
    for i,m in enumerate(data['conversation']):
        if not isinstance(m,dict): raise ValueError('消息必须为对象')
        if any(k not in m for k in ['timestamp','speaker','content','message_bbox','image','transfer','file']): raise ValueError('消息字段不完整')
        if any(not isinstance(m[k],(str,type(None))) for k in ['timestamp','speaker','content','image','transfer','file']): raise ValueError('消息字段须为字符串或null')
        normalized.append(dict(m,id=str(i),bbox=box(m['message_bbox'],width,height)))
    return dict(data,conversation=normalized)

def iou(a,b):
    inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
    return inter/union if union>0 else 0.

def match(gold,predicted,threshold=.6):
    """Max cardinality, then max IoU via successive shortest augmenting paths; stable index ties."""
    if not 0<threshold<=1: raise ValueError('固定IoU阈值须在(0,1]')
    n,m=len(gold),len(predicted);end=n+m+1;graph=[[] for _ in range(end+1)]
    def edge(a,b,cost):
        f=[b,1,cost,len(graph[b])];r=[a,0,-cost,len(graph[a])];graph[a].append(f);graph[b].append(r);return f
    for a in range(n): edge(0,a+1,0)
    for b in range(m): edge(n+1+b,end,0)
    candidates=[]
    for a,g in enumerate(gold):
        for b,p in enumerate(predicted):
            if g.get('region_type','message')!=p.get('region_type','message'): continue
            v=iou(g['bbox'],p['bbox'])
            if v>=threshold: candidates.append((a,b,v,edge(a+1,n+1+b,-v)))
    while True:
        dist=[float('inf')]*len(graph);prev=[None]*len(graph);dist[0]=0
        for _ in range(len(graph)-1):
            changed=False
            for a,edges in enumerate(graph):
                if not math.isfinite(dist[a]): continue
                for index,e in enumerate(edges):
                    if e[1] and dist[e[0]]>dist[a]+e[2]+1e-12:
                        dist[e[0]]=dist[a]+e[2];prev[e[0]]=(a,index);changed=True
            if not changed: break
        if prev[end] is None: break
        at=end
        while at:
            a,index=prev[at];e=graph[a][index];e[1]-=1;graph[at][e[3]][1]+=1;at=a
    pairs=[dict(gold=a,prediction=b,iou=v) for a,b,v,e in candidates if not e[1]]
    tp=len(pairs);precision=tp/m if m else (1. if not n else 0.);recall=tp/n if n else (1. if not m else 0.)
    return dict(matches=pairs,tp=tp,fp=m-tp,fn=n-tp,precision=precision,recall=recall,f1=2*precision*recall/(precision+recall) if precision+recall else 0.,matched_mean_iou=sum(p['iou'] for p in pairs)/tp if tp else None,threshold=threshold)

def cer(a,b):
    prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        curr=[i]
        for j,y in enumerate(b,1): curr.append(min(curr[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
        prev=curr
    return prev[-1]/len(a) if a else (0. if not b else 1.)

def amount(value):
    if not isinstance(value,dict) or value.get('answer_status')!='known': return None
    if value.get('currency') not in ['CNY','USD','EUR','JPY','HKD','OTHER']: return None
    try:
        number=Decimal(str(value.get('value')))
        if not number.is_finite(): return None
        return number,value['currency']
    except (InvalidOperation,ValueError): return None

def field(kind,target,prediction):
    out=dict(raw_exact=target==prediction,normalized_exact=normalize(target)==normalize(prediction),score=None,status='unscored')
    if kind=='open_text': return dict(out,status='rubric_review_required',reason='开放题须由审核台按量表评估；文本相同不代表法律正确')
    if kind=='amount':
        a,b=amount(target),amount(prediction)
        if a is None: return dict(out,status='invalid_reference',reason='金额或币种未确认；未知不按零计')
        return dict(out,score=int(a==b),status='scored' if b is not None else 'abstained' if prediction is None or isinstance(prediction,dict) and prediction.get('answer_status')=='unknown' else 'format_failure')
    if kind=='set':
        if not isinstance(target,list) or not all(isinstance(v,str) for v in target): return dict(out,status='invalid_reference')
        if not isinstance(prediction,list) or not all(isinstance(v,str) for v in prediction): return dict(out,score=0,status='format_failure')
        a,b=set(map(normalize,target)),set(map(normalize,prediction));tp=len(a&b)
        return dict(out,score=int(a==b),status='scored',precision=tp/len(b) if b else float(not a),recall=tp/len(a) if a else float(not b))
    if kind=='identity': return dict(out,status='identity_dictionary_required',reason='身份别名须在审核台确认；仅列原文比较')
    if not isinstance(target,str): return dict(out,status='invalid_reference')
    if prediction is None: return dict(out,score=0,status='abstained')
    if not isinstance(prediction,str): return dict(out,score=0,status='format_failure')
    return dict(out,score=int(out['normalized_exact']),status='scored',cer=cer(normalize(target),normalize(prediction)) if kind in ['text','filename'] else None)

def score(task,raw,target,width,height,*,threshold=.6):
    # Validate references independently from response formatting.
    if task['task_family']=='kie.extract':
        if target is not None:
            try: kie(target,width,height)
            except (ValueError,TypeError,KeyError,OverflowError):
                return dict(status='invalid_reference',score=None,reason='人工参考结构/坐标无效')
    else:
        reference=field(task['answer_kind'],target,None)
        if reference['status'] in ['invalid_reference','identity_dictionary_required']:
            return dict(reference,structure_valid=None)
    try:
        data=parse(raw)
        if task['task_family']=='kie.extract':
            prediction=kie(data,width,height)
            if target is None: return dict(status='invalid_reference',score=None,structure_valid=True,prediction=prediction,reason='未建立人工消息级参考，不计算检测分')
            reference=kie(target,width,height);detection=match(reference['conversation'],prediction['conversation'],threshold)
            fields=[]
            for pair in detection['matches']:
                a=reference['conversation'][pair['gold']];b=prediction['conversation'][pair['prediction']]
                fields.append(dict(pair=pair,values={k:field('text',a.get(k),b.get(k)) for k in ['timestamp','speaker','content','image','transfer','file']}))
            return dict(status='scored',score=detection['f1'],structure_valid=True,detection=detection,fields=fields,dialog_name=field('text',reference.get('dialog_name'),prediction.get('dialog_name')),prediction=prediction)
        if 'answer' not in data: raise ValueError('VQA输出须含answer')
        return dict(field(task['answer_kind'],target,data['answer']),prediction=data)
    except (ValueError,TypeError,KeyError,OverflowError):
        return dict(status='format_failure',score=0 if target is not None and task.get('answer_kind')!='open_text' else None,structure_valid=False,reason='输出JSON、必需字段或原图坐标校验失败')

def classification_report(pairs,labels=None):
    labels=sorted(set(map(normalize,labels))) if labels is not None else sorted({normalize(x) for pair in pairs for x in pair if isinstance(x,str)})
    confusion={};f1=[]
    for a,b in pairs:
        key=json.dumps([normalize(a),normalize(b)],ensure_ascii=False);confusion[key]=confusion.get(key,0)+1
    for label in labels:
        tp=sum(normalize(a)==label==normalize(b) for a,b in pairs);fp=sum(normalize(a)!=label==normalize(b) for a,b in pairs);fn=sum(normalize(a)==label!=normalize(b) for a,b in pairs)
        f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.)
    return dict(confusion=confusion,macro_f1=sum(f1)/len(f1) if f1 else None,labels=labels)

"""Loopback-only synthetic provider for browser tests; no real keys or evidence."""
import json
import os
import time

PIPELINE_LEDGER=[]
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, status, data):
        content=json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(content)))
        self.send_header('X-Request-ID','mock-provider-'+self.headers.get('X-Request-ID','probe'))
        self.end_headers();self.wfile.write(content)

    def do_GET(self):
        if self.path=='/pipeline-ledger':return self.respond(200,{'requests':PIPELINE_LEDGER})
        self.respond(200,{'status':'ok'})

    def do_POST(self):
        if self.path!='/v1/chat/completions':
            return self.respond(404,{'error':'unknown endpoint'})
        if self.headers.get('Authorization')!='Bearer e2e-placeholder':
            return self.respond(401,{'error':'invalid synthetic key'})
        payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if payload.get('model','').startswith('pipeline-fixture-'):
            user=payload['messages'][1]['content']
            task=json.loads(user[0]['text'] if isinstance(user,list) else user)
            PIPELINE_LEDGER.append(dict(model=payload['model'],request_id=self.headers.get('X-Request-ID'),has_max_tokens='max_tokens' in payload,task_type=task['task_type'],input_text=json.dumps(task,ensure_ascii=False)))
            if '-slow-' in payload['model']:time.sleep(2)
            if task['task_type']=='kie.extract':
                output={'dialog_name':None,'conversation':[dict(timestamp=None,speaker='A',content='Synthetic visible text',message_bbox=dict(min_x=10,min_y=10,max_x=110,max_y=90),image=None,transfer=None,file=None)]}
                if '-lowiou-' in payload['model']:output['conversation'][0]['message_bbox']=dict(min_x=0,min_y=0,max_x=200,max_y=160)
                content='bad JSON' if '-bad-' in payload['model'] else json.dumps(output)
            else:content=json.dumps({'answer':'is_evidence','evidence':['0']})
            return self.respond(200,{'choices':[{'message':{'content':content},'finish_reason':'stop'}],'usage':{'prompt_tokens':20,'completion_tokens':30}})
        content='OK' if payload.get('max_tokens') else json.dumps({'messages':[{'text':'Synthetic screenshot transcript','bbox':[30,130,690,220]}]})
        if any('不可认证人工金标' in str(m.get('content','')) for m in payload.get('messages',[])):
            content=json.dumps({'verdict':'pending','score':None,'findings':'本机模拟仅验证评估输入，不作质量判断','suggestions':'','process':'scope contract fixture'})
        self.respond(200,{'choices':[{'message':{'content':content}}]})


if __name__=='__main__':
    ThreadingHTTPServer(('127.0.0.1',int(os.getenv('E2E_MODEL_PORT','19432'))),Handler).serve_forever()

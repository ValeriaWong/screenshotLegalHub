"""Only this port knows the isolated MinerU interpreter and wire format."""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from screenshotlegal.settings import ROOT

PIN = 'mineru-4.0.12-docvortex-0.6.1-flash-content-list-v1'
WORKER = ROOT / 'scripts/document_worker.py'

class MinerUAdapter:
    def __init__(self):
        self.worker=WORKER
        self.pin=PIN
        default = ROOT / '.tools/mineru-env' / ('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        self.python = Path(os.environ.get('DOCUMENT_PARSER_PYTHON',str(default)))
    def available(self):
        return self.python.is_file()
    def call(self, payload):
        if not self.available(): raise ValueError('本地 MinerU 环境未安装，请执行 scripts/setup-documents.ps1')
        env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True', PADDLE_PDX_CACHE_HOME=str(ROOT/'.tools/parser-models/paddle'), HF_HOME=str(ROOT/'.tools/parser-models/hf'))
        try:
            run=subprocess.run([str(self.python),'-X','utf8',str(self.worker)],input=json.dumps(payload),
                               capture_output=True,text=True,encoding='utf-8',timeout=180,env=env,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        except subprocess.TimeoutExpired:
            raise ValueError('本地解析超时；已保存的页面不受影响，可重试当前窗口') from None
        # Never relay third-party stderr: it may contain document contents or local configuration.
        if run.returncode: raise ValueError('本地解析失败；请检查文件、解析环境和 OCR 模型。原件和已保存页面仍保留')
        try: result=json.loads(run.stdout)
        except (ValueError,TypeError): raise ValueError('解析器未返回有效结构') from None
        if result.get('error'): raise ValueError(result['error'])
        return result
    def parse(self, source, start, count, cache):
        # Original bytes, adapter revision, schema and exact scope identify the artifact.
        source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
        identity=f"{source_sha}:{self.pin}:content-list-v1:{start}:{count}"
        key=hashlib.sha256(identity.encode()).hexdigest()
        target=cache/(key+'.json');checksum=cache/(key+'.sha256')
        if target.is_file() and checksum.is_file():
            data=target.read_bytes()
            if hashlib.sha256(data).hexdigest()!=checksum.read_text(encoding='ascii').strip():
                raise ValueError('解析原始产物完整性校验失败，请保留原件并创建新解析版本')
            result=json.loads(data)
        else:
            result=self.call(dict(action='parse',path=str(source),start=start,count=count))
            cache.mkdir(parents=True,exist_ok=True)
            data=json.dumps(result,ensure_ascii=False).encode('utf-8')
            temporary=target.with_suffix('.tmp')
            with temporary.open('wb') as stream:
                stream.write(data);stream.flush();os.fsync(stream.fileno())
            temporary.replace(target)
            temporary=checksum.with_suffix('.tmp.sha256')
            with temporary.open('w',encoding='ascii') as stream:
                stream.write(hashlib.sha256(data).hexdigest());stream.flush();os.fsync(stream.fileno())
            temporary.replace(checksum)
        return dict(result,artifact_manifest=dict(filename=target.name,sha256=hashlib.sha256(data).hexdigest(),
            size=len(data),source_sha256=source_sha,parser_revision=self.pin,start=start,count=count,output_schema_version='content-list-v1'))
    def preview(self, source, page, target):
        target.parent.mkdir(parents=True,exist_ok=True)
        return self.call(dict(action='preview',path=str(source),page=page,target=str(target)))

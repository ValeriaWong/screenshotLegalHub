"""Parser registry; vendor dependencies stay in isolated interpreters."""
import os
from pathlib import Path
from screenshotlegal.settings import ROOT
from screenshotlegal.domain.evidence.documents import ParserCapabilities
from .adapter import MinerUAdapter, PIN

CONFIGS={
 'mineru':dict(name='MinerU Flash',version=PIN,formats=['.pdf','.docx','.pptx','.xlsx','.csv'],page_ranges=True,ocr=False,description='当前默认，本地文本层/Office 解析'),
 'docling':dict(name='Docling Native',version='docling-slim-2.143.1-native-v1',formats=['.docx','.pptx','.xlsx','.csv'],page_ranges=False,ocr=False,description='原生 Office 对照；此配置不包含 PDF 模型管线'),
 'paddle':dict(name='Paddle PP-StructureV3',version='paddleocr-3.7.0-cpu-v1',formats=['.pdf','.png','.jpg','.jpeg','.webp'],page_ranges=True,ocr=True,description='中文扫描候选；本地模型与原图定位尚未验收，暂不开放运行'),
}
class ExternalParser(MinerUAdapter):
    def __init__(self,engine):
        super().__init__()
        folder=ROOT/'.tools'/(engine+'-env')
        self.python=folder/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        self.worker=ROOT/'scripts/document_candidate_worker.py'
        self.pin=CONFIGS[engine]['version']
        self.engine=engine
    def call(self,payload):return super().call(dict(payload,engine=self.engine))
    def available(self):
        folder=self.python.parent.parent/('Lib/site-packages' if os.name=='nt' else 'lib')
        if self.engine=='paddle' and not (ROOT/'.tools/parser-models/paddle/verified.json').is_file():return False
        return self.python.is_file() and folder.is_dir() and any(folder.glob(('docling_slim' if self.engine=='docling' else 'paddleocr')+'-*.dist-info') if os.name=='nt' else folder.glob('python*/site-packages/'+('docling_slim' if self.engine=='docling' else 'paddleocr')+'-*.dist-info'))
def parser_for(engine):
    return MinerUAdapter() if engine=='mineru' else ExternalParser(engine)
def capabilities():
    return [ParserCapabilities(id=engine,available=parser_for(engine).available(),**config).model_dump() for engine,config in CONFIGS.items()]

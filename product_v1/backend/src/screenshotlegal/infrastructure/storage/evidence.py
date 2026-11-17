from pathlib import Path
import hashlib
from screenshotlegal.domain.evidence.models import EvidenceItem
from screenshotlegal.plugins.ingestion.registry import IngestionRegistry

class EvidenceStorage:
    def __init__(self, settings):
        self.settings = settings
        self.root = (settings.data_dir / 'uploads').resolve()
        self.registry = IngestionRegistry()

    def path(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('Unsafe evidence path')
        return path

    def save(self, case_id, filename, mime, content):
        if not content or len(content)>self.settings.max_upload_bytes:
            raise ValueError('Upload size exceeds configured limit or file is empty')
        prepared = self.registry.prepare(filename, mime, content)
        mime = prepared.mime
        if mime not in self.settings.allowed_mime_types:
            raise ValueError('Unsupported MIME')
        width, height, ext = prepared.width, prepared.height, prepared.extension
        sha=hashlib.sha256(content).hexdigest()
        relative=case_id+'/'+sha+'.'+ext
        path=self.path(relative);path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
                raise ValueError('Stored evidence digest mismatch')
        else:
            with path.open('xb') as stream:
                stream.write(content)
        return EvidenceItem(id='ev.'+sha[:24],case_id=case_id,filename=Path(filename.replace('\\','/')).name[:200],mime_type=mime,sha256=sha,storage_path=relative,size_bytes=len(content),width=width,height=height,kind=prepared.kind)

    def verified_path(self, evidence):
        path=self.path(evidence['storage_path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=evidence['sha256']:
            raise ValueError('Evidence integrity check failed')
        return path

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol
from PIL import Image, UnidentifiedImageError


@dataclass(frozen=True)
class PreparedEvidence:
    mime: str
    extension: str
    kind: str
    width: int | None = None
    height: int | None = None


class EvidenceHandler(Protocol):
    mime_types: dict[str, str]
    def prepare(self, mime: str, content: bytes) -> PreparedEvidence: ...


class ImageHandler:
    mime_types = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp'}

    def prepare(self, mime, content):
        try:
            with Image.open(BytesIO(content)) as image:
                if Image.MIME.get(image.format) != mime:
                    raise ValueError('Image MIME differs from decoded format')
                width, height = image.size
                image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise ValueError('Invalid evidence image') from error
        return PreparedEvidence(mime, self.mime_types[mime], 'image', width, height)


class PDFHandler:
    mime_types = {'application/pdf': 'pdf'}

    def prepare(self, mime, content):
        if not content.startswith(b'%PDF-'):
            raise ValueError('Invalid PDF signature')
        return PreparedEvidence(mime, 'pdf', 'pdf')


class TextHandler:
    mime_types = {'text/plain': 'txt'}

    def prepare(self, mime, content):
        try:
            content.decode('utf-8')
        except UnicodeDecodeError as error:
            raise ValueError('Text evidence must use UTF-8') from error
        return PreparedEvidence(mime, 'txt', 'txt')


class IngestionRegistry:
    def __init__(self, handlers=None):
        self.handlers = {}
        for handler in handlers if handlers is not None else [ImageHandler(), PDFHandler(), TextHandler()]:
            self.register(handler)

    def register(self, handler: EvidenceHandler):
        if set(handler.mime_types) & self.handlers.keys():
            raise ValueError('Duplicate format handler')
        for mime in handler.mime_types:
            self.handlers[mime] = handler

    def prepare(self, filename, mime, content):
        if not mime or mime == 'application/octet-stream':
            ext = Path(filename).suffix.lower().lstrip('.')
            aliases = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg'}
            mime = aliases.get(ext) or next((m for m, h in self.handlers.items() if h.mime_types[m] == ext), '')
        if mime not in self.handlers:
            raise ValueError('Unsupported file format; ZIP extraction is not enabled yet')
        return self.handlers[mime].prepare(mime, content)

    def formats(self):
        return [dict(mime_type=m, extension=h.mime_types[m], processing='image-validation' if m.startswith('image/') else 'original-storage') for m, h in self.handlers.items()]

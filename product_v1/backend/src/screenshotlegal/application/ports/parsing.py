"""Only parser adapters know vendor protocols."""
from pathlib import Path
from typing import Protocol
class DocumentParserPort(Protocol):
    def parse(self, source: Path, start: int, count: int, cache: Path) -> dict: ...

"""Fingerprint caching preserves content checks and reacts to actual source edits."""
import hashlib
from pathlib import Path
from screenshotlegal.method_reproductions.author_bridge import source_file_digest,_source_digest_cached

def test_unchanged_source_is_read_once_and_changed_source_is_rehashed(tmp_path,monkeypatch):
    p=tmp_path/'source.txt';p.write_bytes(b'first');reads=[];original=Path.read_bytes
    def read(path):
        if path==p:reads.append(path)
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',read)
    _source_digest_cached.cache_clear()
    assert source_file_digest(p)==hashlib.sha256(b'first').hexdigest()
    assert source_file_digest(p)==hashlib.sha256(b'first').hexdigest() and len(reads)==1
    p.write_bytes(b'changed source')
    assert source_file_digest(p)==hashlib.sha256(b'changed source').hexdigest() and len(reads)==2
    assert source_file_digest(tmp_path/'missing') is None

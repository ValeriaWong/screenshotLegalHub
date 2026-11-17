"""Download versioned public CPU models; never call a hosted inference API."""
import hashlib
import json
import sys
from pathlib import Path
import requests
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[2]
MODELS = {'embedding': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
          'native_generator': 'google/flan-t5-small'}

def main():
    output = ROOT / 'paper/author_reproductions/local_models.lock.json'
    lock = json.loads(output.read_text(encoding='utf-8')) if output.exists() else {}
    for name in sys.argv[1:] or list(MODELS):
        repo = MODELS[name]
        if name in lock:
            revision = lock[name]['revision']
        else:
            response = requests.get('https://huggingface.co/api/models/' + repo, timeout=30)
            response.raise_for_status()
            revision = response.json()['sha']
        path = ROOT / 'paper/.models' / name / revision
        snapshot_download(repo, revision=revision, local_dir=path, local_dir_use_symlinks=False,
                          allow_patterns=['*.json', '*.txt', '*.model', '*.safetensors', '1_Pooling/*'],
                          ignore_patterns=['onnx/*', 'openvino/*', 'onnx*', '*onnx*'], max_workers=2)
        files = {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in path.rglob('*') if p.is_file() and '.cache' not in p.parts}
        lock[name] = dict(repository=repo, revision=revision, path=path.relative_to(ROOT).as_posix(),
                          files=files, provider_requests=0, purpose='CPU validation; explicitly changed model')
        output.write_text(json.dumps(lock, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        print(json.dumps(dict(name=name, revision=revision, files=len(files))), flush=True)

if __name__ == '__main__': main()

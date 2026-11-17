import json
from pathlib import Path
from screenshotlegal.api.main import app
root=Path(__file__).resolve().parents[1]
directory=root/'artifacts'
directory.mkdir(exist_ok=True)
(directory/'openapi.json').write_text(json.dumps(app.openapi(),ensure_ascii=False,indent=2),encoding='utf-8')
print('Exported OpenAPI schema')

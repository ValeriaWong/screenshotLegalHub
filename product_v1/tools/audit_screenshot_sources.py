"""Read repository source manifests without importing or changing a live panel."""
import argparse
import json
import tempfile
from pathlib import Path
from screenshotlegal.research.store import Store
from screenshotlegal.research.review import ReviewDesk
from screenshotlegal.research.screenshot_sources import ScreenshotSources

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="legacy-kie")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="screenshot-source-audit-") as directory:
        store = Store(Path(directory))
        try:
            sources = ScreenshotSources(store, ReviewDesk(store))
            _, scope = sources.prepare("source-audit", args.source)
            result = dict(inventory=sources.inventory("source-audit"), scope=scope)
        finally:
            store.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(items=scope["items"], messages=scope["messages"], excluded=len(scope["excluded"]), annotation_level=scope["annotation_level"]), ensure_ascii=False))

if __name__ == "__main__":
    main()

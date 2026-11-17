from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legalhub.evidence import extract

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest')
    parser.add_argument('--model', default='kimi3_low')
    parser.add_argument('--output')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--coordinate-space', choices=['pixels', 'normalized_1000'], default='pixels')
    args = parser.parse_args()
    result = extract(args.manifest, args.model, args.output, args.execute, progress=lambda x: print(json.dumps(x, ensure_ascii=True), flush=True), coordinate_space=args.coordinate_space)
    print(json.dumps(result, ensure_ascii=True), flush=True)

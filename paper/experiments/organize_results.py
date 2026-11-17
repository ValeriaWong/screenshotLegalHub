"""Organize saved studies by reproduction name. No model requests are made."""
import argparse
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'product_v1/backend/src'))
from method_artifacts import organize_existing

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    print(json.dumps(organize_existing(parser.parse_args().out),ensure_ascii=False))

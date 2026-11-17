"""Independent bilingual v2 development flywheel. Never modifies v1 assets."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from legalhub.synthesis import main

if __name__ == '__main__':
    main()

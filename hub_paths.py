"""Resolve copied project paths relative to this hub."""
from pathlib import Path
HUB_ROOT = Path(__file__).resolve().parent
def project_path(project, relative=""):
    return str(HUB_ROOT / "projects" / project / relative)

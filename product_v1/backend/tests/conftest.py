from pathlib import Path
import pytest
from alembic.config import Config
from alembic import command
from screenshotlegal.settings import Settings
from screenshotlegal.infrastructure.db.repository import Repository
from screenshotlegal.application.services.workspace import Workspace

@pytest.fixture
def workspace(tmp_path,monkeypatch):
    monkeypatch.setenv('DATA_DIR',str(tmp_path))
    settings=Settings(data_dir=tmp_path,auto_approve_gates=True)
    command.upgrade(Config(str(Path(__file__).parents[1]/'alembic.ini')),'head')
    repo=Repository(settings.database_url)
    result=Workspace(settings,repo)
    yield result
    repo.engine.dispose()

@pytest.fixture
async def demo(workspace):
    from screenshotlegal.cli.seed import seed
    case=await seed(workspace)
    return workspace,case


def pytest_configure(config):
    # API modules construct a default app during collection; isolate that bootstrap too.
    import os,tempfile
    os.environ["DATA_DIR"]=tempfile.mkdtemp(prefix="screenshotlegal-pytest-bootstrap-")

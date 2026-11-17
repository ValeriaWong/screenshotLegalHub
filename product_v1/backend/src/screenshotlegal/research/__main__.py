"""Optional extra worker; the API also runs a worker by default."""
import asyncio
from screenshotlegal.settings import Settings
from screenshotlegal.infrastructure.db.repository import Repository
from screenshotlegal.application.services.workspace import Workspace
from .store import Store
from .review import ReviewDesk
from .gateway import Gateway
from .products import EvaluationLab
from .worker import Worker

async def main():
    settings=Settings()
    repo=Repository(settings.database_url)
    workspace=Workspace(settings,repo)
    store=Store(settings.data_dir)
    review=ReviewDesk(store)
    gateway=Gateway(store,workspace)
    worker=Worker(store,review,gateway,EvaluationLab(store,review,gateway))
    try:
        await worker.loop()
    finally:
        await workspace.runtime.close()
        repo.engine.dispose()

if __name__=='__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

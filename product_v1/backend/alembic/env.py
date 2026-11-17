from alembic import context
from screenshotlegal.settings import Settings
from screenshotlegal.infrastructure.db.repository import Repository
from screenshotlegal.infrastructure.db.models import Base

settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
repo = Repository(settings.database_url)
with repo.engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()

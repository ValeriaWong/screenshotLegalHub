"""Local user and model configuration metadata; encrypted API keys only."""
from alembic import op
from screenshotlegal.infrastructure.db.models import MODELS

revision = '0002'
down_revision = '0001'


def upgrade():
    for name in ('local_users', 'model_configs', 'user_settings'):
        MODELS[name].__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    for name in ('user_settings', 'model_configs', 'local_users'):
        MODELS[name].__table__.drop(op.get_bind(), checkfirst=True)

"""Accounts and hashed, expiring sessions."""
from alembic import op
from screenshotlegal.infrastructure.db.models import MODELS
revision = '0003'
down_revision = '0002'


def upgrade():
    for name in ('auth_users', 'auth_sessions'):
        MODELS[name].__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    for name in ('auth_sessions', 'auth_users'):
        MODELS[name].__table__.drop(op.get_bind(), checkfirst=True)

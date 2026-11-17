"""Select current evidence transcripts without overwriting historical messages."""
from alembic import op
from screenshotlegal.infrastructure.db.models import MODELS
revision='0004'
down_revision='0003'


def upgrade():
    MODELS['active_perceptions'].__table__.create(op.get_bind(),checkfirst=True)


def downgrade():
    MODELS['active_perceptions'].__table__.drop(op.get_bind(),checkfirst=True)

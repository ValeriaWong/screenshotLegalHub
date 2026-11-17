"""Versioned JSON documents in independently indexed domain tables plus local FTS5."""
from alembic import op
from screenshotlegal.infrastructure.db.models import Base
revision = '0001'
down_revision = None

def upgrade():
    Base.metadata.create_all(op.get_bind())
    op.execute('CREATE VIRTUAL TABLE search_index USING fts5(id UNINDEXED, case_id UNINDEXED, terms, body UNINDEXED)')

def downgrade():
    op.execute('DROP TABLE search_index')
    Base.metadata.drop_all(op.get_bind())

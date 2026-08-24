"""Initial PostgreSQL schema.

Revision ID: 0001
"""
from alembic import op

from app.db.base import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)


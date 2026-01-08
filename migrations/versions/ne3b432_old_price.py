"""add old_price

Revision ID: e3b2c1a4d5e6
Revises: 70a694334be2
Create Date: 2026-01-08 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e3b2c1a4d5e6'
down_revision = '70a694334be2'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('public_plan', schema=None) as batch_op:
        batch_op.add_column(sa.Column('old_price', sa.String(length=20), nullable=True))

def downgrade():
    with op.batch_alter_table('public_plan', schema=None) as batch_op:
        batch_op.drop_column('old_price')
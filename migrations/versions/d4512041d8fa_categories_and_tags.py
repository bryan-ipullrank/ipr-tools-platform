"""categories and tags

Revision ID: d4512041d8fa
Revises: 062e7ca83918
Create Date: 2026-06-11 15:37:48.914660

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4512041d8fa'
down_revision = '062e7ca83918'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('plugins', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category', sa.String(), server_default='Uncategorized', nullable=False))
        batch_op.add_column(sa.Column('tags', sa.JSON(), nullable=True))

    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tags', sa.JSON(), nullable=True))

    # Categories are now required; give existing un-categorized tools a home so
    # the grouped views always have a bucket.
    op.execute("UPDATE tools SET category = 'Uncategorized' WHERE category IS NULL OR category = ''")


def downgrade():
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.drop_column('tags')

    with op.batch_alter_table('plugins', schema=None) as batch_op:
        batch_op.drop_column('tags')
        batch_op.drop_column('category')

"""plugins table

Revision ID: 062e7ca83918
Revises: 3ccee508e202
Create Date: 2026-06-05 13:37:29.371315

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '062e7ca83918'
down_revision = '3ccee508e202'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('plugins',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('display_name', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=False),
    sa.Column('repo', sa.String(), nullable=False),
    sa.Column('source_type', sa.String(), server_default='github', nullable=False),
    sa.Column('version', sa.String(), nullable=False),
    sa.Column('status', sa.String(), server_default='draft', nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_plugins_owner_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_plugins'))
    )
    with op.batch_alter_table('plugins', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_plugins_name'), ['name'], unique=True)


def downgrade():
    with op.batch_alter_table('plugins', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_plugins_name'))

    op.drop_table('plugins')

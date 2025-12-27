"""Add canonical_id for identity unification

Revision ID: add_canonical_id
Revises: 
Create Date: 2025-12-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_canonical_id'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add canonical_id column and index to normalized_data table."""
    # Add canonical_id column
    op.add_column('normalized_data', 
        sa.Column('canonical_id', sa.String(), nullable=True)
    )
    
    # Create index on canonical_id
    op.create_index('idx_normalized_canonical_id', 'normalized_data', ['canonical_id'])


def downgrade() -> None:
    """Remove canonical_id column and index."""
    # Drop index
    op.drop_index('idx_normalized_canonical_id', table_name='normalized_data')
    
    # Drop column
    op.drop_column('normalized_data', 'canonical_id')

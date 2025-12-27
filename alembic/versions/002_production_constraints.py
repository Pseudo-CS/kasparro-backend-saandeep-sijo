"""Database migration to add production-grade constraints and indexes.

Revision ID: 002_production_constraints
Revises: add_canonical_id
Create Date: 2025-12-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_production_constraints'
down_revision = 'add_canonical_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add production-grade constraints, string lengths, and composite indexes."""
    
    # ===== raw_csv_data =====
    # Modify string columns to have lengths and NOT NULL constraints
    with op.batch_alter_table('raw_csv_data', schema=None) as batch_op:
        batch_op.alter_column('source_id',
                              existing_type=sa.String(),
                              type_=sa.String(255),
                              nullable=False)
        batch_op.alter_column('raw_data',
                              existing_type=sa.JSON(),
                              nullable=False)
        batch_op.alter_column('ingested_at',
                              existing_type=sa.DateTime(timezone=True),
                              nullable=False)
    
    # ===== raw_api_data =====
    with op.batch_alter_table('raw_api_data', schema=None) as batch_op:
        batch_op.alter_column('source_id',
                              existing_type=sa.String(),
                              type_=sa.String(255),
                              nullable=False)
        batch_op.alter_column('source_name',
                              existing_type=sa.String(),
                              type_=sa.String(50),
                              nullable=False)
        batch_op.alter_column('raw_data',
                              existing_type=sa.JSON(),
                              nullable=False)
        batch_op.alter_column('ingested_at',
                              existing_type=sa.DateTime(timezone=True),
                              nullable=False)
    
    # ===== raw_rss_data =====
    with op.batch_alter_table('raw_rss_data', schema=None) as batch_op:
        batch_op.alter_column('source_id',
                              existing_type=sa.String(),
                              type_=sa.String(500),
                              nullable=False)
        batch_op.alter_column('raw_data',
                              existing_type=sa.JSON(),
                              nullable=False)
        batch_op.alter_column('ingested_at',
                              existing_type=sa.DateTime(timezone=True),
                              nullable=False)
    
    # ===== normalized_data =====
    with op.batch_alter_table('normalized_data', schema=None) as batch_op:
        batch_op.alter_column('source_type',
                              existing_type=sa.String(),
                              type_=sa.String(50),
                              nullable=False)
        batch_op.alter_column('source_id',
                              existing_type=sa.String(),
                              type_=sa.String(255),
                              nullable=False)
        batch_op.alter_column('canonical_id',
                              existing_type=sa.String(),
                              type_=sa.String(255),
                              nullable=True)
        batch_op.alter_column('title',
                              existing_type=sa.String(),
                              type_=sa.String(500),
                              nullable=False)
        batch_op.alter_column('category',
                              existing_type=sa.String(),
                              type_=sa.String(100),
                              nullable=True)
        batch_op.alter_column('created_at',
                              existing_type=sa.DateTime(timezone=True),
                              nullable=False)
        
        # Add new composite indexes
        batch_op.create_index('idx_normalized_source_canonical', 
                             ['source_type', 'canonical_id'])
        batch_op.create_index('idx_normalized_timestamp', 
                             ['source_timestamp'])
    
    # ===== etl_checkpoints =====
    with op.batch_alter_table('etl_checkpoints', schema=None) as batch_op:
        batch_op.alter_column('source_type',
                              existing_type=sa.String(),
                              type_=sa.String(50),
                              nullable=False)
        batch_op.alter_column('last_processed_id',
                              existing_type=sa.String(),
                              type_=sa.String(255),
                              nullable=True)
        batch_op.alter_column('last_success_at',
                              existing_type=sa.DateTime(timezone=True),
                              nullable=True)
        batch_op.alter_column('records_processed',
                              existing_type=sa.Integer(),
                              nullable=False)
        batch_op.alter_column('status',
                              existing_type=sa.String(),
                              type_=sa.String(20),
                              nullable=False)
        
        # Add status index
        batch_op.create_index('idx_checkpoint_status', ['status'])
    
    # ===== etl_run_history =====
    with op.batch_alter_table('etl_run_history', schema=None) as batch_op:
        batch_op.alter_column('run_id',
                              existing_type=sa.String(),
                              type_=sa.String(100),
                              nullable=False)
        batch_op.alter_column('source_type',
                              existing_type=sa.String(),
                              type_=sa.String(50),
                              nullable=False)
        batch_op.alter_column('started_at',
                              existing_type=sa.DateTime(timezone=True),
                              nullable=False)
        batch_op.alter_column('records_processed',
                              existing_type=sa.Integer(),
                              nullable=False)
        batch_op.alter_column('records_inserted',
                              existing_type=sa.Integer(),
                              nullable=False)
        batch_op.alter_column('records_updated',
                              existing_type=sa.Integer(),
                              nullable=False)
        batch_op.alter_column('records_failed',
                              existing_type=sa.Integer(),
                              nullable=False)
        batch_op.alter_column('status',
                              existing_type=sa.String(),
                              type_=sa.String(20),
                              nullable=False)
        
        # Add composite index
        batch_op.create_index('idx_run_history_source_started',
                             ['source_type', 'started_at'])
    
    # ===== schema_drift_logs =====
    with op.batch_alter_table('schema_drift_logs', schema=None) as batch_op:
        batch_op.alter_column('source_name',
                              existing_type=sa.String(),
                              type_=sa.String(50),
                              nullable=False)
        batch_op.alter_column('record_id',
                              existing_type=sa.String(),
                              type_=sa.String(255),
                              nullable=False)
        batch_op.alter_column('confidence_score',
                              existing_type=sa.Float(),
                              nullable=False)
        batch_op.alter_column('detected_at',
                              existing_type=sa.DateTime(timezone=True),
                              nullable=False)
        
        # Add composite index
        batch_op.create_index('idx_drift_source_detected',
                             ['source_name', 'detected_at'])


def downgrade() -> None:
    """Remove production-grade constraints."""
    
    # Remove composite indexes
    with op.batch_alter_table('schema_drift_logs', schema=None) as batch_op:
        batch_op.drop_index('idx_drift_source_detected')
    
    with op.batch_alter_table('etl_run_history', schema=None) as batch_op:
        batch_op.drop_index('idx_run_history_source_started')
    
    with op.batch_alter_table('etl_checkpoints', schema=None) as batch_op:
        batch_op.drop_index('idx_checkpoint_status')
    
    with op.batch_alter_table('normalized_data', schema=None) as batch_op:
        batch_op.drop_index('idx_normalized_timestamp')
        batch_op.drop_index('idx_normalized_source_canonical')
    
    # Revert column constraints (this is a simplified downgrade)
    # In production, you might want to be more careful about reverting constraints

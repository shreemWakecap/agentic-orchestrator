"""Add multi-project support

This migration adds the Project and ProjectEvent tables and adds
project_id foreign key columns to all project-scoped tables.

Revision ID: 001_multiproject
Revises: None
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_multiproject'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('status', sa.Enum('pending', 'indexing', 'ready', 'active', 'archived', name='projectstatus'), default='pending'),
        sa.Column('source_type', sa.Enum('local', 'git', name='projectsourcetype'), default='local'),
        sa.Column('git_url', sa.String(500)),
        sa.Column('git_branch', sa.String(255)),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('last_accessed_at', sa.DateTime()),
        sa.Column('indexed_at', sa.DateTime()),
        sa.Column('archived_at', sa.DateTime()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('ix_projects_project_id', 'projects', ['project_id'])
    op.create_index('ix_projects_slug', 'projects', ['slug'])
    op.create_index('ix_projects_status', 'projects', ['status'])

    # Create project_events table
    op.create_table(
        'project_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_data_json', sa.Text(), default='{}'),
        sa.Column('timestamp', sa.DateTime(), default=sa.func.now()),
        sa.Column('triggered_by', sa.String(100)),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ondelete='CASCADE'),
    )
    op.create_index('ix_project_events_project_id', 'project_events', ['project_id'])
    op.create_index('ix_project_events_event_type', 'project_events', ['event_type'])
    op.create_index('ix_project_events_timestamp', 'project_events', ['timestamp'])

    # Add project_id to plans table
    op.add_column('plans', sa.Column('project_id', sa.String(36)))
    op.create_foreign_key('fk_plans_project_id', 'plans', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE')
    op.create_index('ix_plans_project_id', 'plans', ['project_id'])

    # Add project_id to active_runs table
    op.add_column('active_runs', sa.Column('project_id', sa.String(36)))
    op.create_foreign_key('fk_active_runs_project_id', 'active_runs', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE')
    op.create_index('ix_active_runs_project_id', 'active_runs', ['project_id'])

    # Add project_id to cost_history table
    op.add_column('cost_history', sa.Column('project_id', sa.String(36)))
    op.create_foreign_key('fk_cost_history_project_id', 'cost_history', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE')
    op.create_index('ix_cost_history_project_id', 'cost_history', ['project_id'])

    # Add project_id to token_usage_records table
    op.add_column('token_usage_records', sa.Column('project_id', sa.String(36)))
    op.create_foreign_key('fk_token_usage_records_project_id', 'token_usage_records', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE')
    op.create_index('ix_token_usage_records_project_id', 'token_usage_records', ['project_id'])
    op.create_index('ix_token_usage_project_timestamp', 'token_usage_records', ['project_id', 'timestamp'])

    # Add project_id to codebase_knowledge table
    op.add_column('codebase_knowledge', sa.Column('project_id', sa.String(36)))
    op.create_foreign_key('fk_codebase_knowledge_project_id', 'codebase_knowledge', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE')
    op.create_index('ix_codebase_knowledge_project_id', 'codebase_knowledge', ['project_id'])

    # Add project_id to expert_index table
    op.add_column('expert_index', sa.Column('project_id', sa.String(36)))
    op.create_foreign_key('fk_expert_index_project_id', 'expert_index', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE')
    op.create_index('ix_expert_index_project_id', 'expert_index', ['project_id'])

    # Add project_id to scan_metadata table
    op.add_column('scan_metadata', sa.Column('project_id', sa.String(36)))
    op.create_foreign_key('fk_scan_metadata_project_id', 'scan_metadata', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE')
    op.create_index('ix_scan_metadata_project_id', 'scan_metadata', ['project_id'])

    # Add project_id to extended_scan_metadata table
    op.add_column('extended_scan_metadata', sa.Column('project_id', sa.String(36)))
    op.create_foreign_key('fk_extended_scan_metadata_project_id', 'extended_scan_metadata', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE')
    op.create_index('ix_extended_scan_metadata_project_id', 'extended_scan_metadata', ['project_id'])

    # Add project_id to coding_rules table
    op.add_column('coding_rules', sa.Column('project_id', sa.String(36)))
    op.create_foreign_key('fk_coding_rules_project_id', 'coding_rules', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE')
    op.create_index('ix_coding_rules_project_id', 'coding_rules', ['project_id'])
    # Drop old unique constraint and add new one with project_id
    op.drop_constraint('coding_rules_rule_id_key', 'coding_rules', type_='unique')
    op.create_unique_constraint('uq_coding_rules_project_rule', 'coding_rules', ['project_id', 'rule_id'])

    # Add project_id to file_knowledge table
    op.add_column('file_knowledge', sa.Column('project_id', sa.String(36)))
    op.create_foreign_key('fk_file_knowledge_project_id', 'file_knowledge', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE')
    op.create_index('ix_file_knowledge_project_id', 'file_knowledge', ['project_id'])
    # Drop old unique constraint and add new one with project_id
    op.drop_constraint('file_knowledge_file_path_key', 'file_knowledge', type_='unique')
    op.create_unique_constraint('uq_file_knowledge_project_path', 'file_knowledge', ['project_id', 'file_path'])

    # Add project_id to file_scan_history table
    op.add_column('file_scan_history', sa.Column('project_id', sa.String(36)))
    op.create_foreign_key('fk_file_scan_history_project_id', 'file_scan_history', 'projects', ['project_id'], ['project_id'], ondelete='CASCADE')
    op.create_index('ix_file_scan_history_project_id', 'file_scan_history', ['project_id'])


def downgrade() -> None:
    # Remove project_id from file_scan_history
    op.drop_index('ix_file_scan_history_project_id', 'file_scan_history')
    op.drop_constraint('fk_file_scan_history_project_id', 'file_scan_history', type_='foreignkey')
    op.drop_column('file_scan_history', 'project_id')

    # Remove project_id from file_knowledge
    op.drop_constraint('uq_file_knowledge_project_path', 'file_knowledge', type_='unique')
    op.create_unique_constraint('file_knowledge_file_path_key', 'file_knowledge', ['file_path'])
    op.drop_index('ix_file_knowledge_project_id', 'file_knowledge')
    op.drop_constraint('fk_file_knowledge_project_id', 'file_knowledge', type_='foreignkey')
    op.drop_column('file_knowledge', 'project_id')

    # Remove project_id from coding_rules
    op.drop_constraint('uq_coding_rules_project_rule', 'coding_rules', type_='unique')
    op.create_unique_constraint('coding_rules_rule_id_key', 'coding_rules', ['rule_id'])
    op.drop_index('ix_coding_rules_project_id', 'coding_rules')
    op.drop_constraint('fk_coding_rules_project_id', 'coding_rules', type_='foreignkey')
    op.drop_column('coding_rules', 'project_id')

    # Remove project_id from extended_scan_metadata
    op.drop_index('ix_extended_scan_metadata_project_id', 'extended_scan_metadata')
    op.drop_constraint('fk_extended_scan_metadata_project_id', 'extended_scan_metadata', type_='foreignkey')
    op.drop_column('extended_scan_metadata', 'project_id')

    # Remove project_id from scan_metadata
    op.drop_index('ix_scan_metadata_project_id', 'scan_metadata')
    op.drop_constraint('fk_scan_metadata_project_id', 'scan_metadata', type_='foreignkey')
    op.drop_column('scan_metadata', 'project_id')

    # Remove project_id from expert_index
    op.drop_index('ix_expert_index_project_id', 'expert_index')
    op.drop_constraint('fk_expert_index_project_id', 'expert_index', type_='foreignkey')
    op.drop_column('expert_index', 'project_id')

    # Remove project_id from codebase_knowledge
    op.drop_index('ix_codebase_knowledge_project_id', 'codebase_knowledge')
    op.drop_constraint('fk_codebase_knowledge_project_id', 'codebase_knowledge', type_='foreignkey')
    op.drop_column('codebase_knowledge', 'project_id')

    # Remove project_id from token_usage_records
    op.drop_index('ix_token_usage_project_timestamp', 'token_usage_records')
    op.drop_index('ix_token_usage_records_project_id', 'token_usage_records')
    op.drop_constraint('fk_token_usage_records_project_id', 'token_usage_records', type_='foreignkey')
    op.drop_column('token_usage_records', 'project_id')

    # Remove project_id from cost_history
    op.drop_index('ix_cost_history_project_id', 'cost_history')
    op.drop_constraint('fk_cost_history_project_id', 'cost_history', type_='foreignkey')
    op.drop_column('cost_history', 'project_id')

    # Remove project_id from active_runs
    op.drop_index('ix_active_runs_project_id', 'active_runs')
    op.drop_constraint('fk_active_runs_project_id', 'active_runs', type_='foreignkey')
    op.drop_column('active_runs', 'project_id')

    # Remove project_id from plans
    op.drop_index('ix_plans_project_id', 'plans')
    op.drop_constraint('fk_plans_project_id', 'plans', type_='foreignkey')
    op.drop_column('plans', 'project_id')

    # Drop project_events table
    op.drop_index('ix_project_events_timestamp', 'project_events')
    op.drop_index('ix_project_events_event_type', 'project_events')
    op.drop_index('ix_project_events_project_id', 'project_events')
    op.drop_table('project_events')

    # Drop projects table
    op.drop_index('ix_projects_status', 'projects')
    op.drop_index('ix_projects_slug', 'projects')
    op.drop_index('ix_projects_project_id', 'projects')
    op.drop_table('projects')

    # Drop enums
    sa.Enum(name='projectsourcetype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='projectstatus').drop(op.get_bind(), checkfirst=True)

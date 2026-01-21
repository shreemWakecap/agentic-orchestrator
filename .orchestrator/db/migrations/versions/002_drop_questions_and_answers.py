"""drop_questions_and_answers

Revision ID: 002_drop_qa
Revises: 001_initial
Create Date: 2026-01-21 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_drop_qa'
down_revision: Union[str, Sequence[str], None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop questions and answers tables."""
    # Drop answers table first (has foreign key to questions)
    op.drop_table('answers')
    # Drop questions table
    op.drop_table('questions')


def downgrade() -> None:
    """Recreate questions and answers tables."""
    # Recreate questions table
    op.create_table(
        'questions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('question_id', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('source_type', sa.String(50), server_default='knowledge_base', index=True),
        sa.Column('status', sa.String(50), server_default='pending', index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Recreate answers table
    op.create_table(
        'answers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('answer_id', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('question_id', sa.String(255), sa.ForeignKey('questions.question_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('answer_text', sa.Text(), nullable=False),
        sa.Column('source_details_json', sa.Text()),
        sa.Column('is_obsolete', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

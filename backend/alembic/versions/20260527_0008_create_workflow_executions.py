"""Create workflow_executions table for dashboard-triggered n8n runs.

Revision ID: 20260527_0008
Revises: 20260522_0007
Create Date: 2026-05-27 00:00:00
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260527_0008"
down_revision: Union[str, None] = "20260522_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists public.workflow_executions (
            id              uuid        primary key default gen_random_uuid(),
            workflow_id     text        not null,
            workflow_name   text        not null,
            status          text        not null
                            check (status in ('success', 'failed', 'running'))
                            default 'running',
            triggered_by    text        not null default 'manual_user',
            triggered_at    timestamptz not null default now(),
            execution_time  text,
            response_data   jsonb,
            error_message   text,
            created_at      timestamptz not null default now()
        )
        """
    )

    op.execute(
        """
        create index if not exists idx_workflow_executions_triggered_at
            on public.workflow_executions (triggered_at desc)
        """
    )

    op.execute(
        """
        create index if not exists idx_workflow_executions_workflow_id
            on public.workflow_executions (workflow_id)
        """
    )


def downgrade() -> None:
    op.execute("drop index if exists idx_workflow_executions_workflow_id")
    op.execute("drop index if exists idx_workflow_executions_triggered_at")
    op.execute("drop table if exists public.workflow_executions")

"""Create chat attachments table.

Revision ID: 20260508_0003
Revises: 20260502_0002
Create Date: 2026-05-08 12:00:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260508_0003"
down_revision: Union[str, None] = "20260502_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists public.chat_attachments (
            id uuid primary key default gen_random_uuid(),
            thread_id uuid not null references public.chat_threads(id) on delete cascade,
            message_id uuid references public.chat_messages(id) on delete cascade,
            file_name text not null,
            storage_path text not null,
            mime_type text,
            size_bytes bigint,
            created_at timestamptz not null default now()
        )
        """
    )

    op.execute(
        """
        create index if not exists idx_chat_attachments_thread_created
            on public.chat_attachments(thread_id, created_at asc)
        """
    )

    op.execute(
        """
        create index if not exists idx_chat_attachments_message
            on public.chat_attachments(message_id)
        """
    )


def downgrade() -> None:
    op.execute("drop index if exists public.idx_chat_attachments_message")
    op.execute("drop index if exists public.idx_chat_attachments_thread_created")
    op.execute("drop table if exists public.chat_attachments")
"""Expand chat attachments schema for uploads and persistence.

Revision ID: 20260508_0005
Revises: 20260508_0004
Create Date: 2026-05-08 12:45:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260508_0005"
down_revision: Union[str, None] = "20260508_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        alter table public.chat_attachments
        add column if not exists user_id uuid
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        add column if not exists stored_filename text
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        add column if not exists public_url text
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        add column if not exists file_size bigint
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        add column if not exists attachment_type text
        """
    )
    op.execute(
        """
        update public.chat_attachments a
        set user_id = t.user_id,
            stored_filename = coalesce(a.stored_filename, split_part(a.storage_path, '/', array_length(string_to_array(a.storage_path, '/'), 1))),
            public_url = coalesce(a.public_url, a.storage_path),
            file_size = coalesce(a.file_size, a.size_bytes, 0),
            attachment_type = coalesce(
                a.attachment_type,
                case
                    when lower(coalesce(a.mime_type, '')) like 'image/%' then 'image'
                    when lower(coalesce(a.mime_type, '')) like 'video/%' then 'video'
                    when lower(coalesce(a.mime_type, '')) = 'application/pdf' then 'pdf'
                    when lower(coalesce(a.mime_type, '')) in ('text/csv', 'application/vnd.ms-excel') then 'table'
                    when lower(coalesce(a.mime_type, '')) like 'text/%' then 'text'
                    else 'other'
                end
            )
        from public.chat_threads t
        where t.id = a.thread_id
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        alter column user_id set not null
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        alter column stored_filename set not null
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        alter column file_size set not null
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        alter column attachment_type set not null
        """
    )
    op.execute(
        """
        create index if not exists idx_chat_attachments_user_thread
            on public.chat_attachments(user_id, thread_id, created_at asc)
        """
    )
    op.execute(
        """
        create index if not exists idx_chat_attachments_thread_message
            on public.chat_attachments(thread_id, message_id, created_at asc)
        """
    )


def downgrade() -> None:
    op.execute("drop index if exists public.idx_chat_attachments_thread_message")
    op.execute("drop index if exists public.idx_chat_attachments_user_thread")
    op.execute(
        """
        alter table public.chat_attachments
        drop column if exists attachment_type
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        drop column if exists file_size
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        drop column if exists public_url
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        drop column if exists stored_filename
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        drop column if exists user_id
        """
    )

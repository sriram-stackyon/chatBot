"""Add legacy chat attachment column names.

Revision ID: 20260508_0004
Revises: 20260508_0003
Create Date: 2026-05-08 12:10:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260508_0004"
down_revision: Union[str, None] = "20260508_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        alter table public.chat_attachments
        add column if not exists original_filename text
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        add column if not exists stored_path text
        """
    )
    op.execute(
        """
        update public.chat_attachments
        set original_filename = coalesce(original_filename, file_name),
            stored_path = coalesce(stored_path, storage_path)
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        alter column original_filename set not null
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        alter column stored_path set not null
        """
    )


def downgrade() -> None:
    op.execute(
        """
        alter table public.chat_attachments
        drop column if exists stored_path
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        drop column if exists original_filename
        """
    )
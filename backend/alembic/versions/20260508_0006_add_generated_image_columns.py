"""Add generated image metadata columns to chat attachments.

Revision ID: 20260508_0006
Revises: 20260508_0005
Create Date: 2026-05-08 23:10:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260508_0006"
down_revision: Union[str, None] = "20260508_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        alter table public.chat_attachments
        add column if not exists image_url text
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        add column if not exists prompt_used text
        """
    )


def downgrade() -> None:
    op.execute(
        """
        alter table public.chat_attachments
        drop column if exists prompt_used
        """
    )
    op.execute(
        """
        alter table public.chat_attachments
        drop column if exists image_url
        """
    )

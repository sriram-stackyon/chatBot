"""Drop employee email domain constraint.

Revision ID: 20260502_0002
Revises: 20260502_0001
Create Date: 2026-05-02 00:20:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260502_0002"
down_revision: Union[str, None] = "20260502_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        alter table public.profiles
        drop constraint if exists profiles_employee_email_check
        """
    )


def downgrade() -> None:
    op.execute(
        """
        alter table public.profiles
        add constraint profiles_employee_email_check
        check (email is null or lower(split_part(email, '@', 2)) = 'amzur.com')
        """
    )

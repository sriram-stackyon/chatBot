"""Create user_preferences and digest_history tables for n8n digest workflow.

Revision ID: 20260522_0007
Revises: 20260508_0006
Create Date: 2026-05-22 09:00:00
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260522_0007"
down_revision: Union[str, None] = "20260508_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table: user_preferences — stores per-user digest topic interests
    op.execute(
        """
        create table if not exists public.user_preferences (
            id          uuid primary key default gen_random_uuid(),
            user_id     uuid not null references public.profiles(id) on delete cascade,
            topics      text[]  not null default '{}',
            email       text,
            slack_channel text,
            active      boolean not null default true,
            created_at  timestamptz not null default now(),
            updated_at  timestamptz not null default now()
        )
        """
    )

    op.execute(
        """
        create unique index if not exists idx_user_preferences_user_id
            on public.user_preferences(user_id)
        """
    )

    op.execute(
        """
        create trigger trg_user_preferences_updated_at
        before update on public.user_preferences
        for each row execute function public.touch_updated_at()
        """
    )

    # Table: digest_history — audit trail of every workflow run
    op.execute(
        """
        create table if not exists public.digest_history (
            id              uuid primary key default gen_random_uuid(),
            run_date        date not null default current_date,
            articles_found  integer not null default 0,
            digest_text     text,
            delivery_method text check (delivery_method in ('email', 'slack', 'none')),
            status          text not null check (status in ('success', 'error')) default 'success',
            error_message   text,
            created_at      timestamptz not null default now()
        )
        """
    )

    op.execute(
        """
        create index if not exists idx_digest_history_run_date
            on public.digest_history(run_date desc)
        """
    )


def downgrade() -> None:
    op.execute("drop index if exists idx_digest_history_run_date")
    op.execute("drop table if exists public.digest_history")
    op.execute("drop trigger if exists trg_user_preferences_updated_at on public.user_preferences")
    op.execute("drop index if exists idx_user_preferences_user_id")
    op.execute("drop table if exists public.user_preferences")

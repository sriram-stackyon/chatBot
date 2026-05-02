-- Supabase schema for Amzur AI Chat persistence

create extension if not exists pgcrypto;

create table if not exists public.profiles (
    id uuid primary key,
    email text unique,
    password_hash text,
    full_name text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.profiles
    drop constraint if exists profiles_employee_email_check;

create table if not exists public.chat_threads (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles(id) on delete cascade,
    title text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.chat_messages (
    id uuid primary key default gen_random_uuid(),
    thread_id uuid not null references public.chat_threads(id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    created_at timestamptz not null default now()
);

create index if not exists idx_chat_threads_user_updated
    on public.chat_threads(user_id, updated_at desc);

create index if not exists idx_chat_messages_thread_created
    on public.chat_messages(thread_id, created_at asc);

create or replace function public.touch_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create or replace function public.bump_thread_on_message_insert()
returns trigger as $$
begin
  update public.chat_threads
  set updated_at = now()
  where id = new.thread_id;
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_profiles_touch_updated_at on public.profiles;
create trigger trg_profiles_touch_updated_at
before update on public.profiles
for each row execute procedure public.touch_updated_at();

drop trigger if exists trg_threads_touch_updated_at on public.chat_threads;
create trigger trg_threads_touch_updated_at
before update on public.chat_threads
for each row execute procedure public.touch_updated_at();

drop trigger if exists trg_messages_bump_thread on public.chat_messages;
create trigger trg_messages_bump_thread
after insert on public.chat_messages
for each row execute procedure public.bump_thread_on_message_insert();

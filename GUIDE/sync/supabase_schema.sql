-- WALL-E 同步表（Supabase SQL Editor 中执行）
-- Phase 0：多 Windows 设备登录同一账号后同步待办/记事/提醒/设置

create table if not exists public.sync_records (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id) on delete cascade not null,
  record_id text not null,
  collection text not null check (collection in ('todo', 'note', 'reminder', 'settings')),
  payload jsonb not null default '{}',
  updated_at bigint not null,
  deleted boolean not null default false,
  unique (user_id, collection, record_id)
);

alter table public.sync_records enable row level security;

drop policy if exists "Users manage own sync records" on public.sync_records;
create policy "Users manage own sync records"
  on public.sync_records for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create index if not exists sync_records_user_updated
  on public.sync_records (user_id, updated_at);

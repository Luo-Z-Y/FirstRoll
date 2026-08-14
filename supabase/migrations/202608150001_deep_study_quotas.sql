-- FirstRoll public-demo Deep Study quotas.
-- Three reservations per authenticated account per UTC day; thirty across the demo.

create schema if not exists firstroll_private;
revoke all on schema firstroll_private from public, anon, authenticated;

create table if not exists firstroll_private.deep_study_user_daily (
  usage_day date not null,
  user_id uuid not null references auth.users(id) on delete cascade,
  request_count integer not null default 0 check (request_count >= 0),
  updated_at timestamptz not null default now(),
  primary key (usage_day, user_id)
);

create table if not exists firstroll_private.deep_study_global_daily (
  usage_day date primary key,
  request_count integer not null default 0 check (request_count >= 0),
  updated_at timestamptz not null default now()
);

alter table firstroll_private.deep_study_user_daily enable row level security;
alter table firstroll_private.deep_study_global_daily enable row level security;
revoke all on all tables in schema firstroll_private from public, anon, authenticated;

create or replace function public.deep_study_quota_status()
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  current_user_id uuid := auth.uid();
  current_day date := pg_catalog.timezone('UTC', pg_catalog.now())::date;
  user_count integer := 0;
  global_count integer := 0;
  user_limit constant integer := 3;
  global_limit constant integer := 30;
  reset_time timestamptz := ((current_day + 1)::timestamp at time zone 'UTC');
begin
  if current_user_id is null then
    raise exception 'A signed-in account is required.' using errcode = '42501';
  end if;

  select request_count into user_count
  from firstroll_private.deep_study_user_daily
  where usage_day = current_day and user_id = current_user_id;

  select request_count into global_count
  from firstroll_private.deep_study_global_daily
  where usage_day = current_day;

  user_count := coalesce(user_count, 0);
  global_count := coalesce(global_count, 0);

  return jsonb_build_object(
    'allowed', user_count < user_limit and global_count < global_limit,
    'reason', case
      when user_count >= user_limit then 'user_limit'
      when global_count >= global_limit then 'global_limit'
      else 'available'
    end,
    'user_limit', user_limit,
    'user_used', user_count,
    'user_remaining', greatest(user_limit - user_count, 0),
    'global_limit', global_limit,
    'global_used', global_count,
    'global_remaining', greatest(global_limit - global_count, 0),
    'reset_at', reset_time
  );
end;
$$;

create or replace function public.reserve_deep_study_quota()
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  current_user_id uuid := auth.uid();
  current_day date := pg_catalog.timezone('UTC', pg_catalog.now())::date;
  user_count integer := 0;
  global_count integer := 0;
  user_limit constant integer := 3;
  global_limit constant integer := 30;
  reset_time timestamptz := ((current_day + 1)::timestamp at time zone 'UTC');
  allowed_now boolean := false;
  decision_reason text := 'available';
begin
  if current_user_id is null then
    raise exception 'A signed-in account is required.' using errcode = '42501';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('firstroll-deep-study:' || current_day::text, 0)
  );

  select request_count into user_count
  from firstroll_private.deep_study_user_daily
  where usage_day = current_day and user_id = current_user_id;

  select request_count into global_count
  from firstroll_private.deep_study_global_daily
  where usage_day = current_day;

  user_count := coalesce(user_count, 0);
  global_count := coalesce(global_count, 0);

  if user_count >= user_limit then
    decision_reason := 'user_limit';
  elsif global_count >= global_limit then
    decision_reason := 'global_limit';
  else
    insert into firstroll_private.deep_study_user_daily
      (usage_day, user_id, request_count, updated_at)
    values
      (current_day, current_user_id, 1, pg_catalog.now())
    on conflict (usage_day, user_id) do update
      set request_count = firstroll_private.deep_study_user_daily.request_count + 1,
          updated_at = excluded.updated_at
    returning request_count into user_count;

    insert into firstroll_private.deep_study_global_daily
      (usage_day, request_count, updated_at)
    values
      (current_day, 1, pg_catalog.now())
    on conflict (usage_day) do update
      set request_count = firstroll_private.deep_study_global_daily.request_count + 1,
          updated_at = excluded.updated_at
    returning request_count into global_count;

    allowed_now := true;
  end if;

  return jsonb_build_object(
    'allowed', allowed_now,
    'reason', decision_reason,
    'user_limit', user_limit,
    'user_used', user_count,
    'user_remaining', greatest(user_limit - user_count, 0),
    'global_limit', global_limit,
    'global_used', global_count,
    'global_remaining', greatest(global_limit - global_count, 0),
    'reset_at', reset_time
  );
end;
$$;

revoke all on function public.deep_study_quota_status() from public, anon;
revoke all on function public.reserve_deep_study_quota() from public, anon;
grant execute on function public.deep_study_quota_status() to authenticated;
grant execute on function public.reserve_deep_study_quota() to authenticated;

comment on function public.deep_study_quota_status() is
  'Returns the signed-in FirstRoll account and global Deep Study allowance without consuming it.';
comment on function public.reserve_deep_study_quota() is
  'Atomically reserves one FirstRoll Deep Study request for the signed-in account.';

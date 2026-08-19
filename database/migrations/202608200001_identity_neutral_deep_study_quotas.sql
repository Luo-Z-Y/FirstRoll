-- FirstRoll identity-neutral Deep Study quotas.
--
-- This migration is ordinary PostgreSQL and can run on Supabase PostgreSQL or
-- Azure Database for PostgreSQL. The API connects with a backend-only database
-- credential and passes an identity provider plus immutable subject. A browser
-- access token is never sent to this function.

create schema if not exists firstroll_private;
revoke all on schema firstroll_private from public;

create table if not exists firstroll_private.deep_study_identity_daily (
  usage_day date not null,
  identity_provider varchar(64) not null,
  subject varchar(256) not null,
  request_count integer not null default 0 check (request_count >= 0),
  updated_at timestamptz not null default pg_catalog.now(),
  primary key (usage_day, identity_provider, subject),
  check (identity_provider ~ '^[a-z0-9_-]{1,64}$'),
  check (length(subject) between 1 and 256)
);

create table if not exists firstroll_private.deep_study_global_daily (
  usage_day date primary key,
  request_count integer not null default 0 check (request_count >= 0),
  updated_at timestamptz not null default pg_catalog.now()
);

revoke all on firstroll_private.deep_study_identity_daily from public;
revoke all on firstroll_private.deep_study_global_daily from public;

create or replace function firstroll_private.deep_study_quota_decision(
  p_identity_provider text,
  p_subject text,
  p_reserve boolean default false
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  current_day date := pg_catalog.timezone('UTC', pg_catalog.now())::date;
  account_count integer := 0;
  global_count integer := 0;
  account_limit constant integer := 3;
  global_limit constant integer := 30;
  reset_time timestamptz := ((current_day + 1)::timestamp at time zone 'UTC');
  allowed_now boolean := false;
  decision_reason text := 'available';
begin
  if p_identity_provider is null
     or p_identity_provider !~ '^[a-z0-9_-]{1,64}$' then
    raise exception 'Invalid identity provider.' using errcode = '22023';
  end if;
  if p_subject is null
     or length(p_subject) not between 1 and 256
     or p_subject ~ '[[:cntrl:]]' then
    raise exception 'Invalid identity subject.' using errcode = '22023';
  end if;

  -- One transaction-scoped lock serialises the small public daily allowance.
  -- This makes the account and global increments one atomic decision even when
  -- several Container App replicas receive requests concurrently.
  if p_reserve then
    perform pg_catalog.pg_advisory_xact_lock(
      pg_catalog.hashtextextended('firstroll-deep-study:' || current_day::text, 0)
    );
  end if;

  select request_count into account_count
  from firstroll_private.deep_study_identity_daily
  where usage_day = current_day
    and identity_provider = p_identity_provider
    and subject = p_subject;

  select request_count into global_count
  from firstroll_private.deep_study_global_daily
  where usage_day = current_day;

  account_count := coalesce(account_count, 0);
  global_count := coalesce(global_count, 0);

  if account_count >= account_limit then
    decision_reason := 'user_limit';
  elsif global_count >= global_limit then
    decision_reason := 'global_limit';
  elsif p_reserve then
    insert into firstroll_private.deep_study_identity_daily
      (usage_day, identity_provider, subject, request_count, updated_at)
    values
      (current_day, p_identity_provider, p_subject, 1, pg_catalog.now())
    on conflict (usage_day, identity_provider, subject) do update
      set request_count = firstroll_private.deep_study_identity_daily.request_count + 1,
          updated_at = excluded.updated_at
    returning request_count into account_count;

    insert into firstroll_private.deep_study_global_daily
      (usage_day, request_count, updated_at)
    values
      (current_day, 1, pg_catalog.now())
    on conflict (usage_day) do update
      set request_count = firstroll_private.deep_study_global_daily.request_count + 1,
          updated_at = excluded.updated_at
    returning request_count into global_count;

    allowed_now := true;
  else
    allowed_now := true;
  end if;

  return pg_catalog.jsonb_build_object(
    'allowed', allowed_now,
    'reason', decision_reason,
    'user_limit', account_limit,
    'user_used', account_count,
    'user_remaining', greatest(account_limit - account_count, 0),
    'global_limit', global_limit,
    'global_used', global_count,
    'global_remaining', greatest(global_limit - global_count, 0),
    'reset_at', reset_time
  );
end;
$$;

revoke all on function firstroll_private.deep_study_quota_decision(text, text, boolean)
  from public;

comment on function firstroll_private.deep_study_quota_decision(text, text, boolean) is
  'Returns or atomically reserves FirstRoll quota for a verified provider/subject identity.';

-- Create a dedicated LOGIN role separately, store its password only in Azure
-- Container Apps, then grant the minimum database privileges:
--
-- create role firstroll_backend
--   with login nosuperuser nocreatedb nocreaterole noinherit noreplication
--   connection limit 5 password '<generate a unique password>';
-- alter role firstroll_backend set statement_timeout = '15s';
-- alter role firstroll_backend set idle_in_transaction_session_timeout = '15s';
--
-- grant usage on schema firstroll_private to firstroll_backend;
-- grant execute on function
--   firstroll_private.deep_study_quota_decision(text, text, boolean)
--   to firstroll_backend;
--
-- The role does not need direct SELECT, INSERT, UPDATE or DELETE privileges on
-- either table because the SECURITY DEFINER function owns the data operation.

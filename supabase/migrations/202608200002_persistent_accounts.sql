-- Durable, user-owned FirstRoll account data.
--
-- Supabase Auth remains the identity provider. These public tables contain only
-- application data and every browser-visible operation is constrained by RLS.
-- Passwords, provider API keys, prompts, evidence and generated studies do not
-- belong in this schema.

create table if not exists public.firstroll_profiles (
    user_id uuid primary key references auth.users(id) on delete cascade,
    display_name text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint firstroll_profiles_display_name_length
        check (display_name is null or char_length(display_name) between 1 and 80)
);

create table if not exists public.firstroll_preferences (
    user_id uuid primary key references auth.users(id) on delete cascade,
    theme text not null default 'system',
    shelf_motion boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint firstroll_preferences_theme
        check (theme in ('system', 'light', 'dark'))
);

create table if not exists public.firstroll_saved_films (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    film_id text not null,
    title text not null,
    original_title text,
    release_year smallint,
    director text,
    poster_url text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint firstroll_saved_films_user_film_unique unique (user_id, film_id),
    constraint firstroll_saved_films_film_id_length
        check (char_length(film_id) between 1 and 200),
    constraint firstroll_saved_films_title_length
        check (char_length(title) between 1 and 300),
    constraint firstroll_saved_films_original_title_length
        check (original_title is null or char_length(original_title) between 1 and 300),
    constraint firstroll_saved_films_release_year
        check (release_year is null or release_year between 1888 and 2200),
    constraint firstroll_saved_films_director_length
        check (director is null or char_length(director) between 1 and 300),
    constraint firstroll_saved_films_poster_url
        check (
            poster_url is null
            or (char_length(poster_url) <= 2048 and poster_url ~ '^https://')
        )
);

create index if not exists firstroll_saved_films_user_created_idx
    on public.firstroll_saved_films (user_id, created_at desc);

alter table public.firstroll_profiles enable row level security;
alter table public.firstroll_preferences enable row level security;
alter table public.firstroll_saved_films enable row level security;

-- The publishable key uses the anon role before sign-in. It receives no access.
revoke all on public.firstroll_profiles from public, anon;
revoke all on public.firstroll_preferences from public, anon;
revoke all on public.firstroll_saved_films from public, anon;

grant select, insert, update on public.firstroll_profiles to authenticated;
grant select, insert, update on public.firstroll_preferences to authenticated;
grant select, insert, update, delete on public.firstroll_saved_films to authenticated;

create policy "FirstRoll users can read their own profile"
    on public.firstroll_profiles
    for select
    to authenticated
    using ((select auth.uid()) = user_id);

create policy "FirstRoll users can create their own profile"
    on public.firstroll_profiles
    for insert
    to authenticated
    with check ((select auth.uid()) = user_id);

create policy "FirstRoll users can update their own profile"
    on public.firstroll_profiles
    for update
    to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

create policy "FirstRoll users can read their own preferences"
    on public.firstroll_preferences
    for select
    to authenticated
    using ((select auth.uid()) = user_id);

create policy "FirstRoll users can create their own preferences"
    on public.firstroll_preferences
    for insert
    to authenticated
    with check ((select auth.uid()) = user_id);

create policy "FirstRoll users can update their own preferences"
    on public.firstroll_preferences
    for update
    to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

create policy "FirstRoll users can read their own saved films"
    on public.firstroll_saved_films
    for select
    to authenticated
    using ((select auth.uid()) = user_id);

create policy "FirstRoll users can save films to their own account"
    on public.firstroll_saved_films
    for insert
    to authenticated
    with check ((select auth.uid()) = user_id);

create policy "FirstRoll users can update their own saved films"
    on public.firstroll_saved_films
    for update
    to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

create policy "FirstRoll users can remove their own saved films"
    on public.firstroll_saved_films
    for delete
    to authenticated
    using ((select auth.uid()) = user_id);

create or replace function public.firstroll_touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

revoke all on function public.firstroll_touch_updated_at() from public, anon, authenticated;

drop trigger if exists firstroll_profiles_touch_updated_at on public.firstroll_profiles;
create trigger firstroll_profiles_touch_updated_at
    before update on public.firstroll_profiles
    for each row execute procedure public.firstroll_touch_updated_at();

drop trigger if exists firstroll_preferences_touch_updated_at on public.firstroll_preferences;
create trigger firstroll_preferences_touch_updated_at
    before update on public.firstroll_preferences
    for each row execute procedure public.firstroll_touch_updated_at();

drop trigger if exists firstroll_saved_films_touch_updated_at on public.firstroll_saved_films;
create trigger firstroll_saved_films_touch_updated_at
    before update on public.firstroll_saved_films
    for each row execute procedure public.firstroll_touch_updated_at();

-- A failed auth trigger can block sign-up, so keep this function deliberately
-- small and idempotent. Existing accounts are backfilled below.
create or replace function public.firstroll_handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    insert into public.firstroll_profiles (user_id, display_name)
    values (
        new.id,
        nullif(left(trim(new.raw_user_meta_data ->> 'display_name'), 80), '')
    )
    on conflict (user_id) do nothing;

    insert into public.firstroll_preferences (user_id)
    values (new.id)
    on conflict (user_id) do nothing;

    return new;
end;
$$;

revoke all on function public.firstroll_handle_new_user() from public, anon, authenticated;

drop trigger if exists firstroll_on_auth_user_created on auth.users;
create trigger firstroll_on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.firstroll_handle_new_user();

insert into public.firstroll_profiles (user_id, display_name)
select
    users.id,
    nullif(left(trim(users.raw_user_meta_data ->> 'display_name'), 80), '')
from auth.users as users
on conflict (user_id) do nothing;

insert into public.firstroll_preferences (user_id)
select users.id
from auth.users as users
on conflict (user_id) do nothing;

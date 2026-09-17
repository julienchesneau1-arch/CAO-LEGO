-- =====================================================================
-- Compatibilité Supabase pour les tests locaux UNIQUEMENT.
-- Sur Supabase, les rôles anon / authenticated / service_role et le schéma
-- `auth` existent déjà : ce fichier n'est jamais appliqué en production, il
-- ne fait pas partie des migrations.
-- =====================================================================

do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin noinherit bypassrls;
  end if;
end $$;

grant usage on schema public to anon, authenticated, service_role;

-- Supabase accorde par defaut tous les droits de table a service_role (et a
-- anon/authenticated, que la migration RLS revoque ensuite). On reproduit ce
-- point de depart, sinon les tests seraient plus permissifs que la production.
alter default privileges in schema public grant all on tables to service_role;
alter default privileges in schema public grant all on sequences to service_role;
alter default privileges in schema public grant all on tables to anon, authenticated;

create schema if not exists auth;
grant usage on schema auth to anon, authenticated, service_role;

-- Mêmes signatures que sur Supabase : lecture des revendications du jeton.
create or replace function auth.jwt() returns jsonb
  language sql stable as $$
  select coalesce(
    nullif(current_setting('request.jwt.claims', true), '')::jsonb,
    '{}'::jsonb
  )
$$;

create or replace function auth.uid() returns uuid
  language sql stable as $$
  select nullif(auth.jwt() ->> 'sub', '')::uuid
$$;

create or replace function auth.role() returns text
  language sql stable as $$
  select coalesce(auth.jwt() ->> 'role', current_setting('role', true))
$$;

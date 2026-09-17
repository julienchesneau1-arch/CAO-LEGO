-- =====================================================================
-- V0 — Rétention des données (docs/PLAN.md §4.1, brief §11).
-- Les purges tournent dans Supabase, pas sur le VPS : elles continuent de
-- fonctionner même si le serveur tombe. Chaque fonction est idempotente et
-- renvoie le nombre de lignes supprimées, pour être vérifiable.
-- =====================================================================

create or replace function jl.date_mariage() returns date
  language sql stable set search_path = public, pg_temp as $$
  select date_mariage from public.parametres where id = 1
$$;

-- Allergies = donnée de santé : 30 jours après le mariage (§11).
create or replace function jl.purger_allergies() returns integer
  language plpgsql security definer set search_path = public, pg_temp as $$
declare n integer;
begin
  delete from public.health_allergies where purge_after <= current_date;
  get diagnostics n = row_count;
  return n;
end $$;

-- Réponses : 3 mois après le mariage. Les invités partent avec (cascade).
create or replace function jl.purger_reponses() returns integer
  language plpgsql security definer set search_path = public, pg_temp as $$
declare n integer;
begin
  if current_date < jl.date_mariage() + interval '3 months' then
    return 0;
  end if;
  delete from public.rsvp;
  get diagnostics n = row_count;
  delete from public.guests;
  return n;
end $$;

-- Galerie : 12 mois après le mariage. Les objets du Storage sont supprimés
-- par l'application, qui lit cette même règle — la base reste la référence.
create or replace function jl.purger_medias() returns integer
  language plpgsql security definer set search_path = public, pg_temp as $$
declare n integer;
begin
  delete from public.media
   where created_at < (jl.date_mariage() + interval '12 months');
  get diagnostics n = row_count;
  return n;
end $$;

-- Vœux : supprimés seulement après avoir été remis aux mariés, jamais avant
-- le 3 juin 2029. Tant que `remise_le` est vide, rien ne part.
create or replace function jl.purger_voeux() returns integer
  language plpgsql security definer set search_path = public, pg_temp as $$
declare n integer;
begin
  delete from public.promises
   where remise_le is not null and sealed_until <= current_date;
  get diagnostics n = row_count;
  return n;
end $$;

-- Journaux : 30 jours.
create or replace function jl.purger_journaux() returns integer
  language plpgsql security definer set search_path = public, pg_temp as $$
declare n integer;
begin
  delete from public.audit_log where at < now() - interval '30 days';
  get diagnostics n = row_count;
  return n;
end $$;

-- Jetons de foyer : révoqués 3 mois après le mariage. Le haché reste en base
-- (il ne révèle rien) mais l'accès est clos.
create or replace function jl.revoquer_tokens() returns integer
  language plpgsql security definer set search_path = public, pg_temp as $$
declare n integer;
begin
  if current_date < jl.date_mariage() + interval '3 months' then
    return 0;
  end if;
  update public.households set revoked_at = now() where revoked_at is null;
  get diagnostics n = row_count;
  return n;
end $$;

create or replace function jl.executer_purges()
  returns table (tache text, lignes integer)
  language plpgsql security definer set search_path = public, pg_temp as $$
begin
  return query
    select 'allergies', jl.purger_allergies()
    union all select 'reponses', jl.purger_reponses()
    union all select 'medias', jl.purger_medias()
    union all select 'voeux', jl.purger_voeux()
    union all select 'journaux', jl.purger_journaux()
    union all select 'tokens', jl.revoquer_tokens();
end $$;

-- Personne ne déclenche les purges depuis l'interface.
revoke all on function jl.purger_allergies, jl.purger_reponses, jl.purger_medias,
  jl.purger_voeux, jl.purger_journaux, jl.revoquer_tokens, jl.executer_purges
  from public, anon, authenticated;

-- Planification : pg_cron n'existe que sur Supabase. Ici, on ne suppose rien.
do $$ begin
  if exists (select 1 from pg_extension where extname = 'pg_cron') then
    perform cron.schedule('jl-purges-quotidiennes', '17 3 * * *',
                          'select jl.executer_purges()');
  else
    raise notice 'pg_cron absent : planifier « select jl.executer_purges() » chaque nuit (Supabase → Database → Cron).';
  end if;
end $$;

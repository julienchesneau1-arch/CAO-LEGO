-- =====================================================================
-- V3 — Photos et vidéos : consentement au premier envoi, droits de la
-- régie sur la modération, purge des signalements résolus.
-- =====================================================================

-- Consentement au premier envoi (brief §8.7). Il est enregistré **par
-- foyer** et porte la version du texte accepté : si le texte change, on
-- sait ce qui a réellement été accepté, exactement comme pour les allergies.
create table if not exists public.media_consent (
  household_id uuid primary key references public.households(id) on delete cascade,
  consent_at timestamptz not null default now(),
  consent_text_version text not null,
  -- Prudence demandée par le brief pour les photos d'enfants : le foyer
  -- déclare s'il accepte que ses envois soient visibles des invités, ou
  -- seulement des mariés.
  visibilite text not null default 'invites' check (visibilite in ('invites', 'maries')),
  revoked_at timestamptz
);

alter table public.media_consent enable row level security;
alter table public.media_consent force row level security;
revoke all on public.media_consent from anon, authenticated;

-- L'admin lit les consentements (c'est lui qui répond en cas de demande) ;
-- la régie n'en a pas besoin pour masquer une photo.
grant select on public.media_consent to authenticated;
create policy "admin lit les consentements medias" on public.media_consent
  for select to authenticated using (jl.est_admin());

-- Visibilité « maries » : le média n'est servi qu'aux mariés. La colonne
-- vit sur le média pour que la décision suive le fichier même si le foyer
-- change d'avis ensuite — un consentement retiré ne réécrit pas le passé,
-- il empêche la suite.
alter table public.media
  add column if not exists visibilite text not null default 'invites'
    check (visibilite in ('invites', 'maries'));

-- ------------------------------------------------------- Droits de la régie
-- La régie masque et démasque (elle avait déjà `update` sur public.media),
-- et clôt un signalement.
grant insert, update on public.media_takedown to authenticated;

create policy "regie traite un signalement" on public.media_takedown
  for update to authenticated using (jl.est_regie()) with check (jl.est_regie());

-- ------------------------------------------------------------- Rétention
-- Un signalement résolu n'a plus de raison d'être conservé : il porte un
-- identifiant de foyer, donc une donnée personnelle (§11).
create or replace function jl.purger_signalements() returns integer
  language plpgsql security definer set search_path = public, pg_temp as $$
declare n integer;
begin
  delete from public.media_takedown
   where resolved_at is not null and resolved_at < now() - interval '30 days';
  get diagnostics n = row_count;
  return n;
end $$;

-- La nouvelle purge rejoint l'orchestrateur : une seule tâche planifiée.
create or replace function jl.executer_purges()
  returns table (tache text, lignes integer)
  language plpgsql security definer set search_path = public, pg_temp as $$
begin
  return query
    select 'allergies', jl.purger_allergies()
    union all select 'reponses', jl.purger_reponses()
    union all select 'medias', jl.purger_medias()
    union all select 'signalements', jl.purger_signalements()
    union all select 'voeux', jl.purger_voeux()
    union all select 'journaux', jl.purger_journaux()
    union all select 'tokens', jl.revoquer_tokens();
end $$;

revoke all on function jl.purger_signalements, jl.executer_purges
  from public, anon, authenticated;

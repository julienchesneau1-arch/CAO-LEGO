-- =====================================================================
-- V1 — Accès par QR, code de secours et partage de foyer.
-- Ajoute la traçabilité d'ouverture (indicateur « foyers ayant ouvert leur
-- invitation », brief §16) et la limitation de débit (brief §11).
-- =====================================================================

alter table public.households
  add column first_opened_at timestamptz,
  add column last_seen_at timestamptz;

-- Limitation de débit : recherche d'invitation, formulaires, envois.
-- La clé est déjà hachée par l'application : aucune adresse IP en clair (§11).
create table public.tentatives (
  id bigserial primary key,
  cle text not null,
  at timestamptz not null default now()
);
create index on public.tentatives (cle, at desc);

alter table public.tentatives enable row level security;
alter table public.tentatives force row level security;
revoke all on public.tentatives from anon, authenticated;
revoke all on sequence public.tentatives_id_seq from anon, authenticated;

/**
 * Enregistre une tentative et dit si elle reste sous le plafond.
 * Atomique : le comptage et l'insertion vivent dans la même requête, donc
 * deux appels simultanés ne peuvent pas passer tous les deux.
 */
create or replace function jl.tentative_autorisee(
  p_cle text, p_fenetre interval, p_max integer
) returns boolean
  language plpgsql security definer set search_path = public, pg_temp as $$
declare n integer;
begin
  delete from public.tentatives where at < now() - interval '1 day';
  insert into public.tentatives (cle) values (p_cle);
  select count(*) into n
    from public.tentatives
   where cle = p_cle and at > now() - p_fenetre;
  return n <= p_max;
end $$;

revoke all on function jl.tentative_autorisee from public, anon, authenticated;

-- Ouverture d'une invitation : une seule écriture, sans lire le jeton en clair.
create or replace function jl.marquer_ouverture(p_household uuid) returns void
  language sql security definer set search_path = public, pg_temp as $$
  update public.households
     set first_opened_at = coalesce(first_opened_at, now()),
         last_seen_at = now()
   where id = p_household and revoked_at is null
$$;

revoke all on function jl.marquer_ouverture from public, anon, authenticated;

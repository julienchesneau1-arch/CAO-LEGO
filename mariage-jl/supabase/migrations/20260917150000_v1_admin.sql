-- =====================================================================
-- V1 — Accès administrateur par lien à usage unique.
--
-- Le brief §6 prévoit un lien magique par e-mail. Le prestataire e-mail
-- n'est pas encore choisi (question V1-03) : le mécanisme de jeton est donc
-- livré maintenant, et l'e-mail ne sera qu'un moyen de livraison de plus.
-- En attendant, le lien est généré en ligne de commande par Julien.
-- =====================================================================

create table public.admin_magic_links (
  id uuid primary key default gen_random_uuid(),
  email text not null references public.admin_users(email) on delete cascade,
  token_sha256 bytea not null unique,
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now()
);
create index on public.admin_magic_links (email);

alter table public.admin_magic_links enable row level security;
alter table public.admin_magic_links force row level security;
revoke all on public.admin_magic_links from anon, authenticated;

/**
 * Consommation d'un lien : atomique et à usage unique. Deux ouvertures
 * simultanées ne peuvent pas réussir toutes les deux, et un lien expiré ou
 * déjà utilisé ne renvoie rien.
 */
create or replace function jl.consommer_lien_admin(p_empreinte bytea)
  returns table (email text, role text)
  language sql security definer set search_path = public, pg_temp as $$
  with consomme as (
    update public.admin_magic_links
       set used_at = now()
     where token_sha256 = p_empreinte
       and used_at is null
       and expires_at > now()
    returning admin_magic_links.email
  )
  select u.email, u.role
    from public.admin_users u
    join consomme on consomme.email = u.email
   where u.revoked_at is null
$$;

revoke all on function jl.consommer_lien_admin from public, anon, authenticated;

-- Ménage : les liens expirés ne s'accumulent pas.
create or replace function jl.purger_liens_admin() returns integer
  language plpgsql security definer set search_path = public, pg_temp as $$
declare n integer;
begin
  delete from public.admin_magic_links
   where expires_at < now() - interval '7 days';
  get diagnostics n = row_count;
  return n;
end $$;

revoke all on function jl.purger_liens_admin from public, anon, authenticated;

-- =====================================================================
-- V2 — File d'envoi des e-mails.
--
-- Le prestataire transactionnel n'est pas encore choisi (question V1-03).
-- Plutôt que d'attendre, les e-mails sont **écrits dans une file** : rien
-- n'est perdu, tout est relisible, et le jour où le prestataire est choisi il
-- ne reste qu'un transport à brancher (lib/email.ts).
-- =====================================================================

create table public.emails (
  id uuid primary key default gen_random_uuid(),
  destinataire text not null,
  sujet text not null,
  corps text not null,
  statut text not null default 'en_attente'
    check (statut in ('en_attente', 'envoye', 'echec')),
  tentatives smallint not null default 0,
  erreur text,
  cree_le timestamptz not null default now(),
  envoye_le timestamptz
);
create index on public.emails (statut, cree_le);

alter table public.emails enable row level security;
alter table public.emails force row level security;
revoke all on public.emails from anon, authenticated;

-- Les adresses des invités sont une donnée personnelle : la file est purgée
-- avec le reste (brief §11). 30 jours après l'envoi suffisent pour diagnostiquer.
create or replace function jl.purger_emails() returns integer
  language plpgsql security definer set search_path = public, pg_temp as $$
declare n integer;
begin
  delete from public.emails
   where statut = 'envoye' and envoye_le < now() - interval '30 days';
  get diagnostics n = row_count;
  return n;
end $$;

revoke all on function jl.purger_emails from public, anon, authenticated;

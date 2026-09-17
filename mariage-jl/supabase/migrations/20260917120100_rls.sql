-- =====================================================================
-- V0 — Row Level Security : refus par défaut sur toutes les tables.
--
-- Principe (docs/PLAN.md §3.4) : un invité ne détient aucune clé Supabase.
-- Toutes ses lectures passent par le serveur Next.js, filtrées par foyer.
-- Les rôles `anon` et `authenticated` n'existent ici que pour l'admin et la
-- régie, authentifiés par lien magique. La RLS est la seconde barrière.
-- =====================================================================

grant usage on schema jl to anon, authenticated, service_role;

-- ------------------------------------------------------- Rôle de l'appelant
create or replace function jl.role_courant() returns text
  language sql security definer stable set search_path = public, pg_temp as $$
  select role from public.admin_users
   where user_id = auth.uid() and revoked_at is null
$$;

create or replace function jl.est_admin() returns boolean
  language sql security definer stable set search_path = public, pg_temp as $$
  select coalesce(jl.role_courant() = 'admin', false)
$$;

-- La régie hérite des droits de lecture strictement nécessaires ; l'admin les a tous.
create or replace function jl.est_regie() returns boolean
  language sql security definer stable set search_path = public, pg_temp as $$
  select coalesce(jl.role_courant() in ('admin','regie'), false)
$$;

-- ------------------------------------------------------- Refus par défaut
do $$
declare t record;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t.tablename);
    execute format('alter table public.%I force row level security', t.tablename);
  end loop;
end $$;

revoke all on all tables in schema public from anon, authenticated;

-- Durable : toute table creee par une migration ulterieure part sans droit
-- pour anon et authenticated, au lieu d'heriter des droits par defaut de
-- Supabase. Sans cette ligne, une table oubliee serait lisible par tous.
alter default privileges in schema public revoke all on tables from anon, authenticated;

-- ------------------------------------------------------- Droits de table
-- Le rôle `authenticated` est partagé par l'admin et la régie : ce sont les
-- politiques, et non les droits de table, qui distinguent les deux.
grant select on
  public.parametres, public.moments, public.content_blocks, public.faq,
  public.accommodations, public.announcements, public.photo_challenges,
  public.media, public.media_takedown
  to authenticated;

grant select on
  public.households, public.household_links, public.guests, public.rsvp,
  public.rsvp_attendance, public.health_allergies, public.reminder_optin,
  public.push_subscription, public.absent_messages, public.seating_tables,
  public.seating_assign, public.admin_users, public.audit_log
  to authenticated;

grant insert on public.announcements to authenticated;
grant update on public.moments, public.media, public.media_takedown to authenticated;
grant insert, update, delete on
  public.parametres, public.content_blocks, public.faq, public.accommodations,
  public.photo_challenges, public.households, public.household_links,
  public.guests, public.rsvp, public.rsvp_attendance, public.seating_tables,
  public.seating_assign, public.admin_users
  to authenticated;

-- `promises` et `media_signal` : aucun droit, aucune politique. Seul le
-- serveur (service_role) y écrit, et personne ne les lit avant l'échéance.

-- ------------------------------------------------------- Politiques
-- Contenus : la régie lit, l'admin écrit.
create policy "regie lit les parametres" on public.parametres
  for select to authenticated using (jl.est_regie());
create policy "admin gere les parametres" on public.parametres
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());

create policy "regie lit les moments" on public.moments
  for select to authenticated using (jl.est_regie());
create policy "regie decale un moment" on public.moments
  for update to authenticated using (jl.est_regie()) with check (jl.est_regie());

create policy "regie lit les contenus" on public.content_blocks
  for select to authenticated using (jl.est_regie());
create policy "admin gere les contenus" on public.content_blocks
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());

create policy "regie lit la faq" on public.faq
  for select to authenticated using (jl.est_regie());
create policy "admin gere la faq" on public.faq
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());

create policy "regie lit les hebergements" on public.accommodations
  for select to authenticated using (jl.est_regie());
create policy "admin gere les hebergements" on public.accommodations
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());

create policy "regie lit les defis" on public.photo_challenges
  for select to authenticated using (jl.est_regie());
create policy "admin gere les defis" on public.photo_challenges
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());

-- Annonces : le seul écrit de la régie.
create policy "regie lit les annonces" on public.announcements
  for select to authenticated using (jl.est_regie());
create policy "regie publie une annonce" on public.announcements
  for insert to authenticated with check (jl.est_regie() and author_role in ('admin','regie'));

-- Médias : la régie masque, l'admin fait le reste.
create policy "regie lit les medias" on public.media
  for select to authenticated using (jl.est_regie());
create policy "regie masque un media" on public.media
  for update to authenticated using (jl.est_regie()) with check (jl.est_regie());

create policy "regie lit les demandes de retrait" on public.media_takedown
  for select to authenticated using (jl.est_regie());
create policy "regie traite une demande de retrait" on public.media_takedown
  for update to authenticated using (jl.est_regie()) with check (jl.est_regie());

-- Données personnelles : admin seul. La régie ne voit rien (§9).
create policy "admin gere les foyers" on public.households
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());
create policy "admin gere les liens de partage" on public.household_links
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());
create policy "admin gere les invites" on public.guests
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());
create policy "admin gere les reponses" on public.rsvp
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());
create policy "admin gere les presences" on public.rsvp_attendance
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());
create policy "admin gere le plan de table" on public.seating_tables
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());
create policy "admin gere les places" on public.seating_assign
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());
create policy "admin lit les rappels" on public.reminder_optin
  for select to authenticated using (jl.est_admin());
create policy "admin lit les abonnements push" on public.push_subscription
  for select to authenticated using (jl.est_admin());
create policy "admin lit les messages des absents" on public.absent_messages
  for select to authenticated using (jl.est_admin());
create policy "admin gere les acces" on public.admin_users
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());
create policy "admin lit le journal" on public.audit_log
  for select to authenticated using (jl.est_admin());

-- Donnée de santé : lecture admin uniquement, aucune écriture par l'interface.
create policy "admin lit les allergies" on public.health_allergies
  for select to authenticated using (jl.est_admin());

-- ------------------------------------------------------- Gardes de la régie
-- La régie décale un moment : elle ne peut rien réécrire d'autre.
create or replace function jl.garde_regie_moments() returns trigger
  language plpgsql security definer set search_path = public, pg_temp as $$
begin
  if jl.role_courant() = 'regie' then
    if (new.id, new.name_fr, new.name_en, new.kind_fr, new.kind_en, new.color_token,
        new.place, new.ambience_fr, new.ambience_en, new.detail_fr, new.detail_en)
       is distinct from
       (old.id, old.name_fr, old.name_en, old.kind_fr, old.kind_en, old.color_token,
        old.place, old.ambience_fr, old.ambience_en, old.detail_fr, old.detail_en)
    then
      raise exception 'La régie ne peut modifier que le décalage et les horaires d''un moment.';
    end if;
  end if;
  return new;
end $$;

create trigger garde_regie_moments before update on public.moments
  for each row execute function jl.garde_regie_moments();

-- La régie masque une photo : elle ne peut pas en changer la provenance.
create or replace function jl.garde_regie_media() returns trigger
  language plpgsql security definer set search_path = public, pg_temp as $$
begin
  if jl.role_courant() = 'regie' then
    if (new.id, new.storage_path, new.household_id, new.kind, new.mime, new.bytes,
        new.created_at, new.gps_stripped)
       is distinct from
       (old.id, old.storage_path, old.household_id, old.kind, old.mime, old.bytes,
        old.created_at, old.gps_stripped)
    then
      raise exception 'La régie ne peut modifier que le statut d''un média.';
    end if;
  end if;
  return new;
end $$;

create trigger garde_regie_media before update on public.media
  for each row execute function jl.garde_regie_media();

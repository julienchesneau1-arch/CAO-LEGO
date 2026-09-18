-- =====================================================================
-- V3 — Le jour J : cérémonie débranchée, pause des envois, contacts
-- d'urgence. Rien d'inventé : les numéros restent « [À COMPLÉTER] »
-- jusqu'à ce que les mariés les écrivent depuis l'admin.
-- =====================================================================

-- La cérémonie débranchée est un réglage, pas une fatalité (brief §8.6).
-- `photos_en_pause` est la main de la régie : elle peut couper les envois
-- à tout moment, indépendamment du moment en cours.
alter table public.parametres
  add column if not exists ceremonie_debranchee boolean not null default true,
  add column if not exists photos_en_pause boolean not null default false;

-- Contacts joignables depuis l'écran Aide (brief §0 bis : boutons d'appel,
-- témoin et régie). Le numéro vit dans le même bloc que le nom : les deux
-- s'écrivent ensemble ou pas du tout.
insert into public.content_blocks (key, locale, value) values
  ('aide.regie',  'fr', '{"texte": "[À COMPLÉTER]", "telephone": null}'),
  ('aide.regie',  'en', '{"texte": "[TO BE COMPLETED]", "telephone": null}'),
  ('aide.temoin', 'fr', '{"texte": "[À COMPLÉTER]", "telephone": null}'),
  ('aide.temoin', 'en', '{"texte": "[TO BE COMPLETED]", "telephone": null}'),
  -- Wi-Fi invités : imprimé sur les cartes de table (brief §10), donc écrit
  -- une fois ici et jamais recopié à la main.
  ('jour.wifi',   'fr', '{"texte": "[À COMPLÉTER]", "lien": null}'),
  ('jour.wifi',   'en', '{"texte": "[TO BE COMPLETED]", "lien": null}')
on conflict (key, locale) do nothing;

-- ------------------------------------------------------- Droits de la régie
-- La régie peut décaler un moment (politique existante) et couper les
-- envois de photos. Elle ne touche à rien d'autre dans les paramètres : le
-- garde ci-dessous le vérifie ligne par ligne.
grant update on public.parametres to authenticated;

create policy "regie coupe les envois" on public.parametres
  for update to authenticated using (jl.est_regie()) with check (jl.est_regie());

create or replace function jl.garde_regie_parametres() returns trigger
  language plpgsql security definer set search_path = public, pg_temp as $$
begin
  if jl.role_courant() = 'regie' then
    if (new.date_mariage, new.date_limite_reponse, new.ceremonie_debranchee)
       is distinct from
       (old.date_mariage, old.date_limite_reponse, old.ceremonie_debranchee)
    then
      raise exception 'La régie ne peut que couper ou rouvrir les envois de photos.';
    end if;
  end if;
  return new;
end $$;

create trigger garde_regie_parametres before update on public.parametres
  for each row execute function jl.garde_regie_parametres();

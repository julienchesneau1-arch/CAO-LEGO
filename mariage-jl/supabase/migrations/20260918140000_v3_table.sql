-- =====================================================================
-- V3 — Plan de table : recherche de son prénom sans se soucier des
-- accents, et droits de lecture pour les mariés.
-- =====================================================================

/*
  Repli sans accents, écrit à la main plutôt qu'avec l'extension `unaccent`.
  Deux raisons : l'extension n'est pas garantie sur une base de développement,
  et la liste ci-dessous couvre exactement ce dont on a besoin — des prénoms
  français. « Chloe » trouve « Chloé », « Joel » trouve « Joël ».
*/
create or replace function jl.sans_accents(valeur text) returns text
  language sql immutable strict parallel safe as $$
  -- Les majuscules accentuées sont listées elles aussi : `lower()` ne les
  -- replie pas sous toutes les collations, et une base de développement peut
  -- très bien en utiliser une qui les laisse intactes. On ne dépend donc
  -- d'aucune collation.
  select lower(translate(
    valeur,
    'àáâãäåçèéêëìíîïñòóôõöùúûüýÿœæÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝŸŒÆ',
    'aaaaaaceeeeiiiinooooouuuuyyoaAAAAAACEEEEIIIINOOOOOUUUUYYOA'
  ))
$$;

grant execute on function jl.sans_accents(text) to anon, authenticated, service_role;

-- Un index qui suit exactement la recherche : sans lui, chaque frappe
-- relirait toute la table des invités.
create index if not exists guests_prenom_sans_accents
  on public.guests (jl.sans_accents(first_name));

-- ------------------------------------------------------ Droits des mariés
-- Les tables et les affectations sont déjà lisibles et modifiables par
-- `authenticated` (migration RLS de V0) ; il manquait les politiques.
create policy "admin gere les tables" on public.seating_tables
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());
create policy "regie lit les tables" on public.seating_tables
  for select to authenticated using (jl.est_regie());

create policy "admin gere les affectations" on public.seating_assign
  for all to authenticated using (jl.est_admin()) with check (jl.est_admin());
create policy "regie lit les affectations" on public.seating_assign
  for select to authenticated using (jl.est_regie());

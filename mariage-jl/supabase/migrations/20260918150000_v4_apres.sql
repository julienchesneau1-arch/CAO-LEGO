-- =====================================================================
-- V4 — Après : le regard du photographe, les textes du merci, et les
-- dates de fin d'accès rendues lisibles par l'application.
-- =====================================================================

/*
  Provenance d'un média. Les photos du photographe vivent dans la même
  table que celles des invités — mêmes règles de service, même modération,
  même purge — mais dans une section distincte à l'écran (brief §8.11).

  `invite` par défaut : tout ce qui existe déjà vient des invités.
*/
alter table public.media
  add column if not exists source text not null default 'invite'
    check (source in ('invite', 'photographe'));

create index if not exists media_source_statut on public.media (source, status, created_at desc);

-- Textes de la période « Après » (brief §8.11). Comme le reste, ils
-- s'écrivent depuis l'admin et valent « [À COMPLÉTER] » jusque-là.
insert into public.content_blocks (key, locale, value) values
  ('apres.merci',  'fr', '{"texte": "[À COMPLÉTER]"}'),
  ('apres.merci',  'en', '{"texte": "[TO BE COMPLETED]"}'),
  ('apres.film',   'fr', '{"texte": "[À COMPLÉTER]", "lien": null}'),
  ('apres.film',   'en', '{"texte": "[TO BE COMPLETED]", "lien": null}')
on conflict (key, locale) do nothing;

/*
  Dates de fin d'accès et de suppression, exposées en lecture.

  Elles ne sont pas recalculées dans l'application : elles viennent des
  mêmes expressions que les purges, ici, une seule fois. Si une règle de
  rétention change, l'écran « Mes données » change avec elle — il ne peut
  pas se désynchroniser et annoncer une date fausse (brief §11).
*/
create or replace function jl.echeances()
  returns table (quoi text, le date)
  language sql stable set search_path = public, pg_temp as $$
  select 'allergies', (jl.date_mariage() + interval '30 days')::date
  union all select 'reponses', (jl.date_mariage() + interval '3 months')::date
  union all select 'acces',    (jl.date_mariage() + interval '3 months')::date
  union all select 'medias',   (jl.date_mariage() + interval '12 months')::date
  union all select 'journaux', (current_date + interval '30 days')::date
  union all select 'voeux',    date '2029-06-03'
$$;

grant execute on function jl.echeances() to anon, authenticated, service_role;

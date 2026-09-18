-- =====================================================================
-- Défis photo (brief §8.7, bonus de la section 0 bis) : un défi par
-- moment, dans sa couleur, **sans classement ni compteur** (§17).
-- =====================================================================

/*
  Un média peut répondre à un défi. La colonne vit sur le média plutôt que
  dans une table de liaison : un souvenir répond à un défi au plus, et une
  table de plus n'apporterait qu'une jointure de plus.
*/
alter table public.media
  add column if not exists challenge_id uuid references public.photo_challenges(id) on delete set null;

create index if not exists media_defi on public.media (challenge_id) where challenge_id is not null;

/*
  Un défi par moment, amorcé non publié et sans intitulé : le brief dit
  « intitulés éditables » et ne les fournit pas. Rien n'est inventé ; tant
  qu'un intitulé n'est pas écrit, le défi n'apparaît nulle part.
*/
insert into public.photo_challenges (moment_id, title_fr, title_en, published)
select m.id, '[À COMPLÉTER]', '[TO BE COMPLETED]', false
  from public.moments m
 where not exists (select 1 from public.photo_challenges c where c.moment_id = m.id);

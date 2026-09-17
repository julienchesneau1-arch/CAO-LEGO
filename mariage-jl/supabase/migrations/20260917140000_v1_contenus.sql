-- =====================================================================
-- V1 — Contenus éditables : Infos et FAQ.
-- Les questions viennent du brief §15 ; les réponses sont inconnues et
-- restent « [À COMPLÉTER] » jusqu'à ce que Julien et Lauriane les écrivent
-- depuis l'espace admin. Rien n'est inventé ici.
-- =====================================================================

-- Sections d'Infos (brief §8.4). Une clé par section, deux langues.
insert into public.content_blocks (key, locale, value) values
  ('infos.venir',         'fr', '{"texte": "[À COMPLÉTER]"}'),
  ('infos.venir',         'en', '{"texte": "[TO BE COMPLETED]"}'),
  ('infos.dormir',        'fr', '{"texte": "[À COMPLÉTER]"}'),
  ('infos.dormir',        'en', '{"texte": "[TO BE COMPLETED]"}'),
  ('infos.tenue',         'fr', '{"texte": "[À COMPLÉTER]"}'),
  ('infos.tenue',         'en', '{"texte": "[TO BE COMPLETED]"}'),
  ('infos.enfants',       'fr', '{"texte": "[À COMPLÉTER]"}'),
  ('infos.enfants',       'en', '{"texte": "[TO BE COMPLETED]"}'),
  ('infos.accessibilite', 'fr', '{"texte": "[À COMPLÉTER]"}'),
  ('infos.accessibilite', 'en', '{"texte": "[TO BE COMPLETED]"}'),
  ('infos.rentrer',       'fr', '{"texte": "[À COMPLÉTER]"}'),
  ('infos.rentrer',       'en', '{"texte": "[TO BE COMPLETED]"}'),
  ('infos.covoiturage',   'fr', '{"texte": "[À COMPLÉTER]", "lien": null}'),
  ('infos.covoiturage',   'en', '{"texte": "[TO BE COMPLETED]", "lien": null}'),
  ('infos.liste_mariage', 'fr', '{"texte": "[À COMPLÉTER]", "lien": null}'),
  ('infos.liste_mariage', 'en', '{"texte": "[TO BE COMPLETED]", "lien": null}'),
  -- Lien de diffusion de la cérémonie : rempli plus tard, visible seulement
  -- des foyers reconnus (brief §8.9, arbitrage C9 de la section 0 bis).
  ('loin.diffusion',      'fr', '{"texte": "[À COMPLÉTER]", "lien": null}'),
  ('loin.diffusion',      'en', '{"texte": "[TO BE COMPLETED]", "lien": null}')
on conflict (key, locale) do nothing;

-- Les dix-huit questions du brief §15. Publiées : une question sans réponse
-- vaut mieux qu'une question cachée, et l'invité voit que rien n'est oublié.
insert into public.faq (sort_order, question_fr, question_en, answer_fr, answer_en, published) values
  (1,  'À quelle heure arriver, et combien de temps dure la journée ?', 'What time should I arrive, and how long does the day last?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (2,  'Comment venir ? Où se garer ? Y a-t-il des navettes ou du covoiturage ?', 'How do I get there? Where can I park? Are there shuttles or car-sharing?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (3,  'Où dormir à proximité ?', 'Where can I stay nearby?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (4,  'Quelle tenue prévoir ? Faut-il porter les couleurs du mariage ?', 'What should I wear? Should I wear the wedding colours?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (5,  'Les enfants sont-ils les bienvenus ? Que prévoir pour eux ?', 'Are children welcome? What should I bring for them?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (6,  'Le domaine est-il accessible en fauteuil roulant ?', 'Is the venue wheelchair accessible?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (7,  'Jusqu’à quand répondre ? Puis-je modifier ma réponse ? Un proche peut-il répondre pour moi ?', 'What is the reply deadline? Can I change my reply? Can someone close reply for me?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (8,  'Comment signaler une allergie ou un régime ?', 'How do I report an allergy or a dietary requirement?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (9,  'Puis-je venir accompagné·e ?', 'May I bring someone?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (10, 'Pourquoi une cérémonie sans téléphone ?', 'Why a phone-free ceremony?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (11, 'Comment partager mes photos ? Qui peut les voir ? Comment retirer une photo où j’apparais ?', 'How do I share my photos? Who can see them? How do I have a photo of me removed?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (12, 'Je ne pourrai pas venir : comment suivre la cérémonie ?', 'I cannot come: how can I follow the ceremony?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (13, 'Faut-il installer l’application ? Comment recevoir les rappels sur iPhone ?', 'Do I need to install the app? How do I get reminders on an iPhone?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (14, 'Et s’il pleut ? Et s’il n’y a pas de réseau ?', 'What if it rains? What if there is no mobile network?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (15, 'Y a-t-il une liste de mariage ?', 'Is there a wedding gift list?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (16, 'Qui contacter le jour J ?', 'Who do I contact on the day?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (17, 'Qu’est-ce que « La promesse » ?', 'What is "The promise"?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true),
  (18, 'Mes données sont-elles protégées ? Quand seront-elles supprimées ?', 'Is my data protected? When will it be deleted?', '[À COMPLÉTER]', '[TO BE COMPLETED]', true)
on conflict do nothing;

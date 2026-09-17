# Journal des versions

Les dates sont celles de livraison réelle. Tant qu'une version n'est pas validée, elle reste en « en attente de validation ».

## V0 — Fondations — 17 septembre 2026 — en attente de validation

### Livré

- **Direction artistique** : jetons uniques (`lib/tokens.ts` et `app/globals.css`) pour les 7 couleurs, les 3 tailles de texte, le mode Papier et le mouvement. Les cinq couleurs n'existent que comme fils, pastilles et bordures.
- **Monogramme vectorisé** (`components/monogram.generated.ts`) : J et L romains, & italique à 95 %, ligne de base commune, tracés extraits de Bodoni Moda par `scripts/build-monogram.mjs`. Aucune dépendance au rendu des polices à l'exécution.
- **Composants** : `<Monogram />` (plein et contour 1 px), `<Signature />`, `<PileCouleurs />`, `<Filet />`.
- **Page `/design`** : validation de la direction artistique, avec contrastes calculés et non supposés.
- **Confort de lecture** : trois tailles (18 / 21 / 25 px), mode Papier, animations réduites, bascule français / anglais. Préférences appliquées avant le premier rendu, sans clignotement.
- **Traductions** : dictionnaires français et anglais alignés, 56 clés, vérification bloquante au build (`scripts/check-i18n.mjs`).
- **Page de secours statique** (`secours/index.html`, 7 ko, sans script ni police distante) et son déploiement GitHub Pages, hors du VPS.
- **Base de données** : 24 tables (`supabase/migrations/`), refus par défaut avec RLS activée **et forcée** partout, 31 politiques, droits par défaut révoqués pour `anon` et `authenticated` afin qu'une table future ne soit jamais lisible par oubli, deux déclencheurs qui limitent la régie au décalage d'un moment et au statut d'un média, et six purges de rétention (allergies J+30, réponses J+3 mois, galerie J+12 mois, vœux après remise, journaux 30 jours, jetons révoqués).
- **Sonde** `/api/health` (l'ajout du contrôle Supabase viendra avec la base, en V1).
- **Vérifications** : **50 tests** — 24 côté interface (contrastes, règle des cinq couleurs, parité des traductions, typographie française, monogramme) et **26 tests RLS contre un vrai PostgreSQL 16** (refus par défaut, cloisonnement régie/admin, allergies invisibles de la régie, vœux illisibles même de l'admin, purges de rétention, aucun jeton stocké en clair) — plus TypeScript strict et compilation. L'intégration continue démarre un PostgreSQL et refuse d'ignorer ces tests (`JL_REQUIRE_DB=1`).
- **Captures mobiles** (390 × 844) : accueil, `/design` en taille normale et très grande, mode Papier, page de secours.

### Trois défauts trouvés par les tests, corrigés

- Les droits par défaut de Supabase rendaient lisible par `anon` et
  `authenticated` toute table créée par une migration ultérieure : la
  révocation est désormais permanente (`alter default privileges`).
- `service_role` n'a pas de droits par le seul fait de contourner la RLS : le
  shim de test reproduit maintenant les droits réels de Supabase, sinon les
  tests auraient été plus permissifs que la production.
- La vérification « RLS forcée » interrogeait une colonne inexistante de
  `pg_tables` : elle passait donc sans rien vérifier.

### Écarts et points ouverts

- Le monogramme vectorisé est en **wght 400** : l'API Google Fonts sert une police variable dont l'axe vaut 400 par défaut, et opentype.js n'interpole pas les axes. Le brief demande ≈ 470. La page `/design` affiche les deux côte à côte pour arbitrage (question V0-11).
- La règle « les cinq couleurs ne sont jamais une couleur de texte » est conservée, mais sa justification par le contraste est inexacte : mesuré sur le fond noir, L'Éclat atteint 10,30 et La Rencontre 4,70. C'est donc une décision de direction artistique, et elle est traitée comme telle.
- Aucune dépense, aucune action sur le VPS, aucun projet Supabase : en attente des réponses V0. Le schéma et les politiques sont prêts à être poussés (`supabase db push`) dès que le projet existe (question V0-06).
- Écarts assumés par rapport au modèle de `docs/PLAN.md` §4, pour éviter deux sources de vérité : `periods_override` et la date du mariage sont fusionnées dans une table `parametres` d'une seule ligne ; `admin_users` gagne un `user_id` rempli à la première connexion ; `promises` gagne `remise_le`, sans quoi « remis puis supprimés » n'était pas vérifiable.
- Les types TypeScript de la base seront générés (`supabase gen types`) à la création du projet : les écrire à la main maintenant, c'est garantir une dérive.

### Versions épinglées

Next.js 16.3.5 · React 19.3.0 · Tailwind CSS 4.3.3 · TypeScript 5.9.3 · Vitest 5.0.1 · Playwright 1.63.0 · opentype.js 2.0.0 · wawoff2 2.0.1 (outils de génération, absents du navigateur).

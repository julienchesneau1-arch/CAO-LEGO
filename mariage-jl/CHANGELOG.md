# Journal des versions

Les dates sont celles de livraison réelle. Tant qu'une version n'est pas validée, elle reste en « en attente de validation ».

## V1 — Le socle — en cours — 17 septembre 2026 (seconde tranche)

### Livré depuis la première tranche

- **Navigation** : une seule barre, cinq onglets, contenu selon la période. Elle n'affiche jamais un onglet qui mènerait à un écran non livré, et vit dans l'espace des invités uniquement — l'espace des mariés ne montre pas les onglets des invités.
- **Programme** : les cinq moments en cartes (numéro, nom, genre, horaire, lieu, filet de couleur), « Le déroulé en détail » par moment, et **« Ajouter à mon agenda »**. Tant que les horaires ne sont pas connus, le fichier `.ics` contient la journée entière du 3 juin 2028 — une information certaine — au lieu d'inventer des heures.
- **Infos** : huit sections éditables depuis l'admin (venir, dormir, tenue, enfants, accessibilité, rentrer en sécurité, covoiturage, liste de mariage) et les trois boutons d'itinéraire (Apple Plans, Google Maps, Waze) construits sur le seul élément connu : le nom et la commune du domaine.
- **FAQ** : les dix-huit questions du brief §15, en français et en anglais, avec recherche insensible aux accents qui fonctionne **sans réseau** une fois la page ouverte.
- **Réponse (RSVP)** : un tap enregistre le oui, le non ou le « pas encore sûr » ; le reste est prérempli et facultatif. Présence moment par moment derrière un dépliant, menu, régimes, et **allergies avec consentement explicite, séparé et versionné** — sans la case cochée, la donnée de santé n'est pas écrite, et une saisie précédente est effacée. Parcours « Non » bienveillant : plus rien n'est demandé, seulement un mot si l'envie vient. Verrouillage automatique après la date limite.
- **Espace des mariés** : lien d'accès **à usage unique** vérifié en base (le mécanisme du lien magique, dont l'e-mail ne sera qu'un moyen de livraison), tableau de bord (foyers, ouvertures, réponses, présents par moment, régimes, allergies déclarées), liste des invités, révocation d'un accès, import CSV.
- **Planche QR PDF** : A4, huit foyers par page, en mode Papier (contraste mesuré 14,57), monogramme vectoriel, QR par foyer et code de secours. Les jetons n'existent en clair qu'au moment d'imprimer : l'import **renvoie directement le PDF**, et une réimpression régénère les accès — l'écran le dit avant le clic.

### Six défauts trouvés par la chaîne de vérification, corrigés

- Une connexion coupée par la base (redémarrage Supabase, pgBouncer) émettait un événement non traité qui **arrêtait le serveur** : le pool a désormais son gestionnaire d'erreur.
- Les parcours partageaient leur état entre les deux gabarits de téléphone : le foyer d'essai est remis à zéro avant chaque parcours.
- Les données amorcées en base contenaient des **apostrophes droites** et des espaces simples avant « ? » (contraire au brief §3) : corrigées, et un test couvre désormais les migrations.
- La barre d'onglets débordait de l'écran en taille « très grande » (libellés en `em`), puis coupait les mots en deux : taille fixe de 16 px, sans capitales, sans coupure.
- Le mot « Facultatif » apparaissait deux fois de suite sur la réponse.
- La barre d'onglets des invités s'affichait dans l'espace des mariés : les deux espaces sont séparés par un groupe de routes.

### Reste à faire dans V1

Rien de fonctionnel. Trois dépendances extérieures : le prestataire e-mail pour livrer les liens d'accès (question V1-03, le mécanisme est déjà là), les options de menu (V1-08), et les contenus à écrire dans l'admin. Puis les deux relectures humaines et la passe sur un iPhone réel avant validation.

## V1 — Première tranche — 17 septembre 2026

V0 validée par Julien le 17 septembre 2026. Première tranche de V1 : l'accès.

### Livré

- **Ouverture par QR de foyer** (`/i/<jeton>`) : jeton de 160 bits, stocké seulement haché (SHA-256), cookie signé HMAC `httpOnly` de 18 mois. L'appareil est reconnu ensuite sans compte ni installation. Langue du foyer appliquée, sauf si l'invité a déjà choisi la sienne.
- **Code de secours** (`/retrouver`) : nom + six caractères sans I, O, 0 ni 1. Formulaire HTML classique, **sans JavaScript** — c'est le chemin de secours, il doit marcher sur le téléphone le plus ancien. Cinq essais par heure, message d'échec unique qui ne dit jamais lequel des deux champs est faux.
- **Partage de l'accès au foyer** (`/partager`, `/p/<jeton>`) : un lien, 30 jours, 5 ouvertures, révocable, compté dans la même requête que sa vérification. C'est aussi « un proche répond pour moi » — un seul mécanisme, conformément à l'arbitrage de la section 0 bis.
- **QR générique** (`/g`) : accès sans aucune donnée nominative.
- **Premier lancement en trois écrans**, une seule fois par appareil, « Passer » visible dès la première image : ouverture signature (les cinq filets se déploient, montent, révèlent le contour du monogramme qui se remplit), confort de lecture, « Tout est ici ».
- **Accueil « Avant »** : compte à rebours en Bodoni Moda (valeur initiale calculée par le serveur, donc juste même si le téléphone est mal réglé), fil des cinq étapes, carte « À faire » avec **une seule action à la fois**, emplacement du film qui dit son absence au lieu d'inventer.
- **Périodes** calculées en jour civil parisien, avec bascule manuelle de l'admin et horloge simulable.
- **Limitation de débit** en base, clé d'appelant hachée : aucune adresse IP en clair.
- **Sonde `/api/health`** : vérifie désormais l'application **et** la base, et répond 503 si la base manque.
- **95 tests** (contre 50) et **16 parcours Playwright** sur deux gabarits de téléphone : QR de foyer, trois écrans du premier lancement, absence de défilement derrière l'ouverture, code de secours, partage de l'accès ouvert depuis un second téléphone, confort « très grande » sans débordement, cibles ≥ 48 px, QR générique.

### Quatre défauts trouvés par la chaîne de vérification, corrigés

- `restant()` était exporté d'un module client et appelé côté serveur : l'accueil renvoyait 500. Le décompte vit maintenant dans `lib/compte.ts`.
- Les redirections absolues de Next réécrivaient l'hôte (`127.0.0.1` → `localhost`), ce qui faisait **perdre le cookie de foyer** — et, derrière Caddy, aurait exposé l'hôte interne. Toutes les redirections sont désormais relatives (`lib/http.ts`).
- Le premier lancement laissait la page défiler derrière lui et le focus restait dehors : un lecteur d'écran lisait l'accueil masqué. Défilement bloqué, focus déplacé dans la surcouche.
- Les parcours Playwright ne correspondaient pas au binaire disponible : version alignée sur le Chromium installé (1.56.0) et gabarits forcés en Chromium.

### Limite assumée

Le gabarit « iPhone » de Playwright vérifie la mise en page et les gestes, **pas le moteur de Safari** (WebKit n'est pas installé dans l'environnement de développement). Le brief §12 exige Safari iOS : il devra être vérifié sur un appareil réel avant la validation de V1.

### Reste à faire dans V1

Programme et déroulé détaillé, `.ics`, Infos (six sections), FAQ avec recherche, réponse (RSVP en quatre taps avec parcours « Non » et consentement séparé pour les allergies), admin invités, planche QR PDF, prestataire e-mail pour le lien magique admin (question V1-03).

## V0 — Fondations — 17 septembre 2026 — validée

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

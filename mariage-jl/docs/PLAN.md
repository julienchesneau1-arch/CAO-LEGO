# PLAN.md — L'application du mariage J&L

> Réponse à la section 18 du brief v6. **Aucun code applicatif n'est écrit avant validation.**
> Source de vérité : `JL_prompt_claude_code_app_mariage_v6.md`. La section 0 bis prime sur tout.
> Convention : `[À COMPLÉTER]` = information inconnue, jamais devinée, éditable depuis l'admin.

---

## 0. Statut de ce document

| Livrable section 18 | Fichier |
|---|---|
| PLAN.md complet | ce document |
| Questions bloquantes classées par version | `QUESTIONS_BLOQUANTES.md` |
| 3 micro-interactions signature + 3 idées de confort | `PROPOSITIONS.md` |
| Squelette d'audit serveur (V0) | `INFRA.md` |

Rien n'est déployé, rien n'est acheté, aucune dépendance n'est installée.

---

## 1. Arbitrages appliqués — contradictions du document résolues par la section 0 bis

La section 0 bis contredit 11 passages des sections 4 à 14. Résolution retenue (0 bis fait foi) :

| # | Passage contredit | Ce que dit 0 bis | Conséquence sur le plan |
|---|---|---|---|
| C1 | §5 stack « SMS », §8.2 étape 4, §14 relance SMS, §4 Thomas | SMS **coupé** | Aucun prestataire SMS. Canaux = e-mail + Web Push + fil d'annonces |
| C2 | §13 V2 « terminé quand : rappel reçu sur les 3 canaux » | SMS coupé | Critère ramené à **2 canaux** (e-mail, push) + fil d'annonces vérifié |
| C3 | §8.4 covoiturage avec mise en relation, §14 | **Coupé** | Paragraphe statique dans Infos + lien vers groupe de discussion `[À COMPLÉTER]` |
| C4 | §8.7 « Photos où je suis » (identification manuelle) | **Coupé** | Filtre « Mes photos » (= photos envoyées par mon foyer) + bouton « Demander le retrait » |
| C5 | §8.6 « Je suis en retard », §9 alertes régie | **Coupé** | Bouton d'appel régie (`tel:`) sur la page Aide |
| C6 | §8.6 / §9 objets perdus | **Coupé** | Géré par téléphone, mentionné en FAQ |
| C7 | §4 Karim, §14 plan de table « voisins présentés » | **Coupé** | Plan de table = recherche de son nom + numéro de table uniquement |
| C8 | §8.9 message « écrit, audio ou vidéo » | Audio **coupé**, messages **simplifiés** | Message écrit uniquement ; la vidéo passe par « Partager un souvenir » |
| C9 | §8.9 lecteur de diffusion intégré, §4 Mamie Odette | **Remplacé** par un lien privé externe | Aucun lecteur, aucune infra. Lien affiché aux foyers connectés seulement. Rediffusion = ce que permet la plateforme `[À COMPLÉTER]` |
| C10 | §6 « Un proche répond pour moi » comme lien de délégation distinct | Un **seul** mécanisme | « Partager l'accès au foyer » sert les deux usages. §12 : le parcours Playwright « délégation » devient « partage d'accès » |
| C11 | §13 V3 « page de secours », §8 | Page de secours en **V0**, hors VPS | V0 la livre ; V3 ne fait que la maintenir à jour |

Fonctions conservées malgré leur coût : « Le texte » (V2), La promesse (V2), cérémonie débranchée (V3), mur `/live` (V3), défis photo (V3 si le temps le permet).

---

## 2. Anomalies logiques et contraintes techniques à trancher

Signalées avant tout code, conformément aux méthodes 3 et 4 de la section 0.

**[ANOMALIE_LOGIQUE : dépôt de code — tranchée le 17/09/2026]**
Le dossier de travail initial (`CAO-LEGO`) contient un projet Python sans rapport (BFK001, mosaïques LEGO). Décision : **dépôt dédié `mariage-jl`**. Le dépôt GitHub reste à créer par Julien — l'App GitHub de cette session n'a pas le droit de créer un dépôt (HTTP 403). En attendant, le projet est conservé en transit dans `CAO-LEGO/mariage-jl/` pour ne rien perdre, et sera déplacé dès que le dépôt existe.

**[ANOMALIE_LOGIQUE : durée de vie de l'hébergement vs La promesse]**
§11 conserve les vœux jusqu'au **3 juin 2029**, soit 12 mois après le mariage, alors que §0 bis prévoit un retour à l'offre gratuite Supabase après export et que la galerie est supprimée à 12 mois. L'application doit donc rester en ligne, payée et maintenue, un an après l'événement — ce n'est écrit nulle part. Trois issues possibles (question V2-06) : maintien en ligne jusqu'au 4 juin 2029 ; export chiffré + envoi automatique à la date, puis extinction ; remise manuelle par Julien.

**[ANOMALIE_LOGIQUE : « invisible y compris des mariés » vs base administrable]**
Une RLS ne protège pas des détenteurs de la clé `service_role` (donc de l'admin et du serveur). Tenir la promesse exige un **chiffrement applicatif** dont la clé n'est pas sur le serveur : chaque vœu est chiffré côté navigateur avec une clé publique ; la clé privée est imprimée en V2, conservée hors ligne par un tiers et saisie le 3 juin 2029. Sans cela, la phrase « invisibles de tous, y compris des mariés » est fausse. Décision requise (question V2-05).

**[ANOMALIE_LOGIQUE : test de charge vs limite vidéo]**
§10 demande « 20 vidéos de 200 Mo » alors que §0 bis limite les vidéos à 60 s compressées. 200 Mo pour 60 s correspond à de la 4K brute. Retenu : le test de charge garde 20 × 200 Mo comme **pire cas** (l'envoi va du téléphone vers Supabase, le VPS n'est pas sollicité), mais 4 Go de pointe imposent l'offre Supabase payante sur la fenêtre J-7 → J+30. Chiffrage en §9.

**[ANOMALIE_LOGIQUE : prestataire e-mail nécessaire dès V1]**
§0 bis place les rappels e-mail en V2, mais l'accès admin de V1 se fait par lien magique **par e-mail** (§6). Le prestataire transactionnel et les enregistrements SPF/DKIM/DMARC sont donc des prérequis **V1**, pas V2.

**[CONTRAINTE TECHNIQUE : reprise des envois sur iPhone]**
§8.7 exige une file qui « reprend après coupure, fermeture de l'app ou redémarrage ». Safari iOS n'implémente pas la Background Sync API : un envoi ne peut pas reprendre tant que l'application est fermée. Alternative retenue : file persistante en IndexedDB + envoi reprenable (TUS), reprise automatique **à la réouverture** de l'app, message honnête à l'écran (« 3 souvenirs repartiront à votre prochaine ouverture »). Aucune promesse fausse dans l'interface.

**[CONTRAINTE TECHNIQUE : métadonnées GPS des vidéos]**
§11 impose la suppression des métadonnées GPS. Pour les photos, la réencodage `canvas` les supprime toutes (l'orientation EXIF doit alors être réappliquée à la main). Pour les vidéos, il n'existe pas de recompression réaliste dans le navigateur d'un téléphone d'entrée de gamme (ffmpeg.wasm : poids et lenteur rédhibitoires). Alternative retenue : suppression **sans recompression** des boîtes `moov/udta` et `©xyz` du conteneur MP4 côté navigateur (parcours de boîtes en JavaScript, quelques kilo-octets), avec test unitaire sur un fichier iPhone géolocalisé `[fichier de test À COMPLÉTER]`. Si le fichier n'est pas un MP4/MOV lisible, l'envoi est refusé avec un message clair.

**[CONTRAINTE TECHNIQUE : HEIC hors Safari]**
La conversion HEIC → JPEG n'est native que sur Safari. Ailleurs (Android partageant un HEIC reçu), il faut une bibliothèque WebAssembly chargée **à la demande**, uniquement quand un HEIC est détecté, pour ne pas peser sur le premier chargement.

**[CONTRAINTE TECHNIQUE : Lighthouse ≥ 95 et film de 102 s]**
Atteignable à condition que le film ne soit jamais préchargé : vignette noire au monogramme (image statique < 20 ko), `<video preload="none">`, lecture déclenchée au tap. Le film n'est pas mis en cache hors ligne (poids) — libellé prévu : « Le film a besoin du réseau. »

**[POINT DE VIGILANCE : mise en veille Supabase]**
Un projet Supabase de l'offre gratuite est suspendu après une période d'inactivité (règle à confirmer dans la documentation officielle en V0). La sonde externe interrogeant `/api/health`, qui touche Postgres, suffit à l'empêcher — à vérifier et consigner dans `INFRA.md`, jamais à supposer.

**[CONSTAT MESURÉ : la justification du contraste est inexacte]**
Le brief affirme que les cinq couleurs ne peuvent pas porter de texte par insuffisance de contraste. Mesures sur le fond `#080808` : L'Éclat 10,30 · La Rencontre 4,70 · La Nuit 3,53 · L'Horizon 2,93 · L'Ivresse 1,85. Deux des cinq passeraient le niveau AA. La règle est **conservée telle quelle** — c'est une décision de direction artistique, pas une contrainte d'accessibilité — et elle est désormais tenue par un test automatique plutôt que par la vigilance.

**[POINT DE VIGILANCE : « photos appréciées » vs §17]**
§8.7 prévoit un tri « appréciées » alors que §17 interdit tout compteur de participation ou comparaison entre invités. Proposition : conserver un signal privé (« j'aime » non affiché en nombre) servant uniquement à ordonner, sans jamais montrer de total ni d'auteur. À valider (question V3-09).

---

## 3. Architecture technique

### 3.1 Vue d'ensemble

```
Téléphone invité
  │  HTTPS (domaine définitif)
  ▼
Caddy (conteneur jl-caddy, VPS Hostinger KVM 2)     ← HTTPS auto, HTTP/2+3, compression, en-têtes, cache pages info
  │  proxy interne (réseau Docker dédié jl-net)
  ▼
Next.js standalone (conteneur jl-app, non root, /api/health)
  │  service_role, jamais exposé au navigateur
  ▼
Supabase (région Europe) : Postgres + RLS, Storage, Realtime, Auth (admin/régie), tâches planifiées

Envoi des médias : téléphone ──URL signée──▶ Supabase Storage   (ne traverse pas le VPS)
Page de secours  : hébergeur statique gratuit indépendant du VPS  [choix : question V0-03]
DNS              : zone Hostinger (hPanel) — bascule = changement d'enregistrement
```

### 3.2 Choix techniques et justifications

| Sujet | Décision | Pourquoi |
|---|---|---|
| Framework | Next.js **16.3.5** (App Router, sortie `standalone`), React 19.3.0 — versions relevées sur le registre npm le 17/09/2026 | Rendu serveur pour le premier affichage, images optimisées, un seul artefact Docker |
| TypeScript | `strict` + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` | Exigence du brief, zéro `any` toléré |
| Styles | Tailwind + variables CSS pour les 7 couleurs et les 3 tailles de texte | Le confort de lecture change une variable, pas un composant |
| i18n | Dictionnaires JSON typés (`fr.json`, `en.json`) + cookie `jl_lang`, sans dépendance ni préfixe d'URL | Application privée (pas de SEO), une dépendance de moins, clés vérifiées au build : toute clé manquante casse la compilation |
| Formulaires | react-hook-form + zod (mêmes schémas côté client, route API et variables d'environnement) | Une seule source de validation |
| PWA | Serwist (service worker maintenu), précache de la coquille + pages d'information | §12 : programme, infos, FAQ, table, secours consultables hors ligne |
| File d'attente | IndexedDB (`idb`), une entrée par réponse ou média, reprise TUS | Coupures réseau à la campagne |
| Animations | CSS + Web Animations API, `prefers-reduced-motion` respecté ; aucune bibliothèque d'animation | Budget quasi nul, poids minimal |
| État serveur | Server Components + Server Actions ; aucun client Supabase dans le navigateur invité | L'invité ne détient aucune clé ; toute lecture passe par le serveur, filtrée par foyer |
| Tests | Vitest (unitaire, horloge simulée) + Playwright (iPhone/Android émulés, réseau bridé) | §12 impose 9 parcours |
| CI/CD | GitHub Actions : tests → build image → registre privé → déploiement SSH (utilisateur non root) ; image étiquetée par version | §0 bis : jamais de compilation sur le VPS, retour arrière en une commande |

### 3.3 Arborescence prévue

```
app/
  (invite)/            page.tsx (accueil selon période) · programme · reponse · infos · faq
                       le-texte · photos · ma-table · maintenant · aide · loin · promesse
                       merci · mes-donnees
  i/[token]/           dépôt du cookie de foyer puis redirection
  retrouver/           code de secours à 6 caractères
  g/                   entrée du QR générique (sans données nominatives)
  live/                mur de projection
  admin/               tableau de bord, invités, contenus, plan de table, médias, exports, imprimables
  regie/               annonces, décalage d'un moment, masquage d'une photo
  design/              page de validation de la direction artistique (V0)
  api/health/          état applicatif + ping Postgres
lib/                   auth-foyer · periode · i18n · supabase · media (compression, EXIF, boîtes MP4)
                       file-attente · ics · pdf · rgpd
components/            Monogram · Signature · Filet · CarteMoment · CompteARebours · ...
messages/              fr.json · en.json
supabase/migrations/   schéma + politiques RLS + tâches planifiées
docs/                  PLAN.md · INFRA.md · CHANGELOG.md · RUNBOOK-secours.md
tests/                 unit/ · e2e/
```

### 3.4 Accès et sessions

- QR par foyer → `/i/[token]` : token de 160 bits (32 caractères base32), **stocké haché** (SHA-256) en base, comparé en temps constant, révocable.
- Dépôt d'un cookie `jl_foyer` signé (HMAC), `httpOnly`, `Secure`, `SameSite=Lax`, 18 mois ; miroir non sensible en `localStorage` pour les préférences de lecture.
- Code de secours : 6 caractères d'un alphabet sans ambiguïté (sans O/0, I/1), limité à 5 essais par heure et par adresse IP, puis 1 par heure.
- QR générique : session anonyme sans identité, accès en lecture au programme, aux infos, à la galerie, et droit d'envoi de souvenirs.
- Partage d'accès au foyer : lien à usage limité (durée et nombre d'ouvertures `[À COMPLÉTER]`), journalisé, révocable depuis l'admin — c'est aussi le mécanisme « un proche répond pour moi » (C10).
- Admin et régie : Supabase Auth, lien magique, liste blanche d'adresses `[À COMPLÉTER]`, rôle vérifié côté serveur à chaque requête.

---

## 4. Modèle de données

Schéma Postgres — **figé et appliqué** dans `supabase/migrations/` (24 tables, 31 politiques).
Trois écarts par rapport à l'esquisse ci-dessous, pour n'avoir qu'une source de vérité : `periods_override` et la date du mariage sont fusionnées dans `parametres` (une seule ligne) ; `admin_users` porte un `user_id` rempli à la première connexion ; `promises` porte `remise_le`, faute de quoi la règle « remis puis supprimés » n'était pas vérifiable. **Toutes les tables en RLS active, refus par défaut.** Les lectures invité passent par le serveur Next.js avec filtrage par foyer ; les politiques RLS servent de seconde barrière pour les rôles Supabase (admin, régie).

```sql
-- Accès
households        (id, label_public, token_sha256, backup_code_sha256, lang_default,
                   comfort_prefs jsonb, revoked_at, created_at)
household_links   (id, household_id, purpose 'share', token_sha256, max_opens, opens,
                   expires_at, created_by, revoked_at)          -- partage d'accès (C10)
guests            (id, household_id, first_name, last_name, is_child, age_years,
                   menu_choice, diet_flags text[], sort_order)

-- Réponse
rsvp              (household_id PK, status 'yes'|'no'|'maybe', submitted_at, updated_at,
                   locked_at, song_request, message_to_couple,
                   lodging_note, transport_note)
rsvp_attendance   (guest_id, moment_id, attending)               -- réglage fin par moment
health_allergies  (guest_id PK, content, consent_at, consent_text_version, purge_after)
                   -- donnée de santé : consentement explicite séparé, purge J+30 (§11)
reminder_optin    (household_id PK, email, consent_at, unsubscribe_token, revoked_at)
push_subscription (id, household_id, endpoint, p256dh, auth, created_at)

-- Contenus éditables (aucune chaîne en dur, aucune donnée inventée)
moments           (id '01'..'05', name_fr, name_en, kind, color_token, starts_at, ends_at,
                   place, ambience_fr, ambience_en, detail_fr, detail_en, shift_minutes)
content_blocks    (key, locale, value jsonb, updated_at, updated_by)
faq               (id, sort_order, question_fr, question_en, answer_fr, answer_en, published)
accommodations    (id, name, distance_km, price_hint, url, phone, shuttle, sort_order)
announcements     (id, body_fr, body_en, published_at, author_role)
periods_override  (id PK=1, forced_period, forced_until)          -- bascule manuelle (§7)

-- Médias
media             (id, storage_path, household_id nullable, moment_id, kind 'photo'|'video',
                   mime, bytes, width, height, duration_s, status 'pending'|'published'|'hidden',
                   gps_stripped bool, created_at)
media_takedown    (id, media_id, requester_household_id, reason, created_at, resolved_at)
media_signal      (media_id, household_id)                        -- « j'aime » privé, jamais affiché en nombre
photo_challenges  (id, moment_id, title_fr, title_en, published)

-- Autour
promises          (id, ciphertext, created_at, sealed_until date default '2029-06-03')
                   -- chiffré côté navigateur, illisible du serveur (§2)
absent_messages   (id, household_id, body, visibility 'guestbook'|'private', created_at)
seating_tables    (id, label, capacity, sort_order)
seating_assign    (guest_id PK, table_id)
admin_users       (email PK, role 'admin'|'regie'|'tech', invited_at, last_seen_at)
audit_log         (id, actor, role, action, target, at)           -- sans donnée personnelle
```

### 4.1 Rétention (tâches planifiées Supabase, indépendantes du VPS)

| Donnée | Suppression | Déclencheur |
|---|---|---|
| Allergies (`health_allergies`) | J+30 | tâche quotidienne |
| Réponses (`rsvp`, `rsvp_attendance`, `guests`) | J+3 mois | tâche quotidienne |
| Galerie (`media` + objets Storage) | J+12 mois, après avertissement aux mariés | tâche quotidienne |
| Vœux (`promises`) | remis puis supprimés après le 3 juin 2029 | tâche + décision V2-06 |
| Journaux | 30 jours | rotation Caddy + purge `audit_log` |
| Tokens de foyer | révoqués à J+3 mois | tâche |

« Télécharger mes données » : ZIP JSON + médias du foyer, généré à la demande, lien signé 15 minutes.
« Supprimer mes données » : suppression immédiate du foyer, de ses réponses, de ses médias et de ses abonnements ; les vœux scellés ne sont pas supprimables individuellement (ils sont anonymes et illisibles) — à mentionner explicitement dans la page Confidentialité.

---

## 5. Écrans et routes

| Route | Écran | Périodes | Version |
|---|---|---|---|
| `/i/[token]` | Reconnaissance du foyer | toutes | V1 |
| `/retrouver` | Code de secours | toutes | V1 |
| `/g` | Entrée QR générique | jour J, après | V1 |
| `/` | Accueil (film, compte à rebours, carte « À faire ») | Avant, Semaine J | V1 |
| `/` | Maintenant (moment en cours, annonces, raccourcis) | Jour J | V3 |
| `/` | Merci | Après | V4 |
| `/programme` + `/programme/[moment]` | 5 moments, déroulé en détail, `.ics` | toutes | V1 |
| `/reponse` | RSVP 4 taps, parcours « Non » | Avant | V1 |
| `/infos` (+ 6 sous-sections) | Venir, dormir, tenue, enfants, accessibilité, rentrer en sécurité | toutes | V1 (météo : V3) |
| `/faq` | FAQ avec recherche | toutes | V1 |
| `/confidentialite`, `/mes-donnees` | Page RGPD, export, suppression | toutes | V1 (auto : V4) |
| `/le-texte` | Palindrome + « Sauf que… » | toutes | V2 |
| `/loin` | Ceux qui sont loin : lien privé de diffusion, message écrit | Avant, Jour J | V2/V3 |
| `/promesse` | Vœu scellé jusqu'au 3 juin 2029 | Avant, Après | V2 |
| `/semaine` | Checklist sereine | Semaine J | V3 |
| `/ma-table` | Recherche de son nom, numéro de table | Semaine J, Jour J | V3 |
| `/photos`, `/photos/envoyer` | Galerie, filtres par moment, « Mes photos », file d'envoi | Jour J, Après | V3 |
| `/aide` | « Je suis perdu », boutons d'appel témoin et régie | Jour J | V3 |
| `/live` | Mur de projection | Jour J | V3 |
| `/regie` | Annonces, décalage, masquage | Jour J | V3 |
| `/admin/*` | Tableau de bord, invités, contenus, imprimables, médias, exports | toutes | V1 → V4 |
| `/design` | Validation de la direction artistique | — | V0 |
| `/api/health` | Sonde (app + Postgres) | — | V0 |
| page de secours | Statique, hors VPS | — | **V0** |

Règle transverse : trois taps maximum pour toute information essentielle ; 5 onglets maximum ; les routes d'une version non livrée ne sont pas annoncées dans la navigation (la bascule de période n'expose jamais un onglet vide).

---

## 6. Navigation par période

| Période | Calcul | Onglets |
|---|---|---|
| Avant | jusqu'à J-8 | Accueil · Programme · Réponse · Infos · FAQ |
| Semaine J | J-7 → J-1 | Accueil · Programme · Infos · Ma table · FAQ |
| Jour J | 3 juin 2028, 00:00 → 23:59 Europe/Paris (fin réelle `[À COMPLÉTER]`) | Maintenant · Programme · Photos · Ma table · Aide |
| Après | dès J+1 | Merci · Photos · Film · Messages · Mes données |

Période calculée côté serveur en `Europe/Paris`, surchargeable depuis l'admin (`periods_override`) et simulable en test via un paramètre d'URL actif uniquement si `JL_ALLOW_CLOCK_OVERRIDE=1` (jamais en production).

---

## 7. Personas — critères de validation par écran

Chaque écran est validé contre ces huit lectures avant d'être considéré comme terminé. Les parcours Playwright correspondants sont listés en §10.

| Persona | Critère vérifiable |
|---|---|
| **Jeanne, 84 ans** | Texte « très grande » sans débordement ni troncature ; aucune installation ; « Partager l'accès au foyer » atteignable en 2 taps depuis l'accueil ; bouton d'appel d'un témoin toujours visible sur Aide |
| **Thomas, 35 ans** | QR → réponse envoyée en ≤ 4 taps, sans compte, en moins de 60 s sur réseau bridé ; rappels e-mail strictement en opt-in |
| **Emma, 29 ans** | 10 souvenirs sélectionnés d'un coup, envoi en arrière-plan, coupure réseau simulée, aucun échec définitif |
| **Karim, 42 ans** | Aucune photo de profil, rien de public imposé ; « Le déroulé en détail » accessible depuis chaque moment ; aucun nom d'invité affiché sans son consentement |
| **Sarah & Paul** | Heure de fin visible sur chaque moment ; section « Avec des enfants » ; navettes et taxis à un tap |
| **Mamie Odette** | Lien privé de diffusion visible sans compte dès qu'un lien de foyer est actif ; message écrit aux mariés ; galerie après |
| **Liam** | Bascule FR/EN en un tap, aucune chaîne non traduite (vérification au build) |
| **Lucie** | Section Accessibilité complète et contact direct `[À COMPLÉTER]` ; cibles ≥ 48 px ; navigation clavier et lecteur d'écran |

---

## 8. Découpage en versions

### V0 — Fondations (immédiat)
Domaine acheté ; **page de secours statique en ligne hors VPS** sur le domaine définitif ; audit du VPS en lecture seule consigné dans `INFRA.md` puis validé ; jetons de direction artistique (7 couleurs, 3 tailles de texte, mode Papier), polices auto-hébergées, `<Monogram />` et `<Signature />` en SVG vectorisé, page `/design` ; projet Supabase en Europe, schéma, RLS et tests RLS ; squelette i18n avec vérification des clés au build ; CI (tests + build image).
*Terminé quand* : `/design` validée par Julien ; tests RLS verts ; page de secours servie en HTTPS sur le domaine ; `INFRA.md` complété et validé.

État au 17/09/2026 : **tests RLS verts** (26 tests contre PostgreSQL 16, `supabase/README.md`), jetons de DA, monogramme, `/design` et page de secours **livrés**. Restent : la validation de `/design` par Julien, le domaine (V0-02) pour servir la page de secours en HTTPS, le projet Supabase (V0-06) pour y pousser les migrations, et les accès VPS (V0-05) pour `INFRA.md`.

### V1 — Le socle (avant le faire-part)
Accès QR + code de secours + QR générique ; premier lancement en 3 écrans ; confort de lecture ; accueil « Avant » (film, compte à rebours, carte « À faire ») ; Programme + déroulé + `.ics` ; Infos (venir, dormir, tenue, enfants, accessibilité, liste de mariage, rentrer en sécurité) ; FAQ avec recherche ; RSVP complet avec parcours « Non » et consentement allergies ; partage d'accès au foyer ; admin invités (import CSV, édition, révocation) ; **planche QR PDF** ; pages Confidentialité / Mes données ; prestataire e-mail configuré (lien magique admin, SPF/DKIM/DMARC).
*Terminé quand* : 20 foyers tests répondent sans aide ; les deux relecteurs (§0 bis) ne rencontrent aucun blocage ; Lighthouse mobile ≥ 95 sur les 4 catégories ; checklist de sécurité serveur validée.

### V2 — La préparation (J-6 mois)
Rappels e-mail en opt-in + fil d'annonces dans l'app ; Web Push (VAPID) ; page « Le texte » ; messages écrits des absents ; La promesse (chiffrement côté navigateur, clé privée hors serveur) ; paragraphe covoiturage + lien de groupe ; hébergements éditables.
*Terminé quand* : rappel reçu sur les **2 canaux** (e-mail, push) et visible dans le fil ; un vœu scellé est illisible depuis la base et déchiffrable avec la clé imprimée.

### V3 — Le jour J (J-3 mois)
Semaine J (météo Open-Meteo, checklist) ; Maintenant ; Aide avec boutons d'appel ; régie minimale (annonces, décalage d'un moment, masquage d'une photo) ; cérémonie débranchée ; photos et vidéos complètes (compression, HEIC, suppression GPS, file persistante, Wi-Fi seulement, modération, demande de retrait) ; mur `/live` ; plan de table ; lien privé de diffusion ; cartes de table PDF et fiche régie PDF ; défis photo si le temps le permet.
*Terminé quand* : répétition générale de J-60 réussie ; test de charge exécuté contre la production hors gel et consigné ; procédure de bascule DNS chronométrée pour de vrai.

### V4 — Après (avant J)
Merci ; « Le regard du photographe » (accès protégé) ; archives ZIP ; suppressions automatiques effectives ; dates de fin d'accès affichées.
*Terminé quand* : parcours « Après » validé avec horloge simulée ; une suppression automatique vérifiée sur données de test.

### Gel — J-7 à J+1
Aucun déploiement, aucun projet du VPS déployé, aucune mise à jour système, tâches lourdes des autres projets décalées ; sauvegardes vérifiées la veille et le lendemain.

Échéances calendaires : `[À COMPLÉTER]` (dépendent de la date d'envoi du faire-part, question V1-01).

---

## 9. Infrastructure et exploitation

- **Cohabitation** : audit en lecture seule d'abord (`INFRA.md`), aucune action globale sans accord, intégration au reverse proxy existant s'il occupe déjà 80/443, isolation complète (utilisateur dédié, `/srv/mariage-jl`, réseau `jl-net`, conteneurs préfixés `jl-`), limites processeur/mémoire proposées **après** l'audit, marge garantie pour le jour J.
- **Sécurité serveur** (bloquante avant V1) : SSH par clé seule, root et mot de passe désactivés ; pare-feu 80/443/SSH ; protection contre les tentatives répétées ; mises à jour de sécurité automatiques ; images reconstruites chaque mois ; secrets hors dépôt et hors image ; HSTS, CSP stricte, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` ; journaux plafonnés, sans donnée personnelle.
- **Sauvegardes** : instantanés Hostinger (fréquence à relever) ; sauvegarde externe quotidienne de Postgres et, dès J-7, des médias, vers une destination hors Hostinger et hors Supabase `[À COMPLÉTER]` ; procédure de reconstruction d'un VPS vierge en moins d'une heure, écrite et testée avant J-60.
- **Bascule de secours** : DNS chez Hostinger ; TTL à 5 minutes de J-14 à J+2 ; valeurs exactes d'aller et de retour préparées ; moyen de bascule délégué au référent technique si Hostinger propose un accès restreint ou une API DNS à clé limitée (à vérifier dans la documentation à jour), sinon bascule par Julien ; jamais de mot de passe partagé par message.
- **Surveillance** : sonde externe gratuite sur l'accueil et `/api/health` (qui vérifie Postgres), alertes e-mail au référent technique et à Julien ; alertes disque, mémoire, redémarrage de conteneur.
- **Capacité et coût** (hypothèses explicites, à valider) : 150 invités, ≥ 300 photos à ~600 ko après compression ≈ 180 Mo ; vidéos de 60 s non recompressées, 20 à 100 envois ≈ 0,4 à 4 Go selon les appareils. L'offre gratuite de Supabase ne couvre pas ce volume : **une seule fenêtre payante de J-7 à J+30** est prévue, puis retour au gratuit après export des archives. Tarif à vérifier et à me présenter avant tout paiement (§0 bis).

---

## 10. Qualité

- **Accessibilité WCAG 2.2 AA** : contrastes mesurés (les 5 couleurs ne servent jamais de couleur de texte), cibles ≥ 48 px, clavier et lecteur d'écran en FR et EN, zoom 200 %, sous-titres pour toute vidéo parlée, `prefers-reduced-motion` respecté.
- **Performance** : Lighthouse mobile ≥ 95 sur les 4 catégories ; première page utile < 2 s en 4G lente ; film jamais préchargé ; polices auto-hébergées avec `font-display: swap`.
- **Hors ligne** : programme, infos, FAQ, table et fiche de secours consultables après une première visite ; réponses et médias en file d'attente.
- **Parcours Playwright obligatoires** (§12, corrigé par C10) : QR foyer → réponse en ≤ 4 taps ; parcours « Non » ; **partage d'accès au foyer** (un proche répond) ; confort de lecture « très grande » sans casse ; envoi de 3 photos dont un HEIC et 1 vidéo avec coupure réseau ; bascule des 4 périodes en horloge simulée ; cérémonie débranchée ; régie décalant un moment ; suppression de mes données. Ajouts proposés : code de secours limité en débit ; refus d'un fichier au type réel invalide ; vérification qu'un vœu est illisible en base.
- **Compatibilité** : Safari iOS et Chrome Android (deux dernières versions majeures), un Android d'entrée de gamme, un iPhone ancien encore maintenu `[modèles de test À COMPLÉTER]`.

---

## 11. Risques

| Risque | Impact | Mitigation |
|---|---|---|
| Le VPS tombe le jour J | Application inaccessible | Page de secours hors VPS + bascule DNS testée + TTL 5 min + cartes de table imprimées |
| Un autre projet du VPS sature la machine | Lenteurs le jour J | Limites de ressources dans les deux sens, gel J-7 → J+1 de **tous** les projets, alertes |
| Réseau mobile faible au domaine | Envois bloqués, invités perdus | File persistante, PWA hors ligne, Wi-Fi invités `[À COMPLÉTER]`, plan B imprimé |
| Dépassement du stockage Supabase | Envois en échec | Vidéos plafonnées à 60 s, surveillance du volume, fenêtre payante J-7 → J+30 validée à l'avance |
| Reprise d'envoi impossible sur iOS app fermée | Promesse non tenue | Message honnête + reprise à la réouverture (§2) |
| Chiffrement des vœux : clé perdue | Vœux définitivement illisibles | Clé privée imprimée en deux exemplaires, deux détenteurs distincts, procédure écrite |
| Données manquantes tardives (horaires, adresses) | Contenu vide au faire-part | Tout est éditable dans l'admin ; tableau de bord des `[À COMPLÉTER]` restants avec date butoir |
| Faire-part imprimé avant validation de V1 | QR vers une app non prête | Le QR pointe le domaine ; la page de secours suffit ; règle 0 bis du plan de repli |
| Photo gênante publiée | Malaise | Modération a priori possible, masquage régie en un tap, demande de retrait en un tap |
| Consentement allergies mal recueilli | Donnée de santé non conforme | Consentement séparé, horodaté, version du texte enregistrée, purge J+30 automatique et testée |

---

## 12. Suite immédiate

1. Réponses aux questions bloquantes **V0** (`QUESTIONS_BLOQUANTES.md`) — sans elles, ni domaine, ni page de secours, ni audit serveur.
2. Validation de ce plan et des arbitrages §1 et §2.
3. Arbitrage des 3 micro-interactions et des 3 idées de confort (`PROPOSITIONS.md`) : rien n'est développé sans accord (§17).

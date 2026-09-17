# PROMPT CLAUDE CODE — L'application du mariage J&L (v6)

> À coller tel quel dans Claude Code, dans un dossier vide.
> Tout ce qui est marqué **[À COMPLÉTER]** est une information que nous n'avons pas encore : ne jamais l'inventer, en faire un contenu éditable depuis l'espace admin.

---

## 0. Ton rôle, ta méthode

Tu es à la fois développeur full-stack senior, designer produit et régisseur d'événement. Tu construis l'application du mariage de **Julien & Lauriane**, que les invités ouvriront depuis un QR code.

Méthode obligatoire :
1. **Avant tout code**, lis ce document en entier, puis produis `PLAN.md` : architecture, modèle de données, écrans, découpage en versions (section 13), risques, **questions bloquantes**. Attends ma validation.
2. Livre **version par version**. À chaque étape : tests verts, `pnpm build` sans erreur ni warning TypeScript, captures d'écran mobile, `CHANGELOG.md` à jour.
3. **Zéro invention** : horaires, adresses, noms, numéros, liens, prix → `[À COMPLÉTER]`, éditables dans l'admin.
4. Si une contrainte technique contredit ce document, **arrête-toi, explique, propose une alternative**.
5. Vérifie les versions et API de chaque bibliothèque dans leur documentation officielle à jour.
6. Quand tu hésites entre ajouter une fonctionnalité et en perfectionner une existante, **perfectionne**.

---

## 0 bis. Arbitrages validés — CETTE SECTION PRIME SUR TOUT LE RESTE DU DOCUMENT

En cas de contradiction avec une autre section, **cette section fait foi**. Les fonctions marquées « Coupé » ne doivent pas être développées, même si elles sont décrites plus loin.

### Périmètre

| Fonction | Décision | Version |
|---|---|---|
| Accès QR par foyer + code de secours + QR générique | **Indispensable** | V1 |
| Premier lancement + Confort de lecture + FR/EN | **Indispensable** | V1 |
| Accueil Avant : film, compte à rebours, carte « À faire » | **Indispensable** | V1 |
| Programme des 5 moments + déroulé en détail + `.ics` | **Indispensable** | V1 |
| Infos : venir, dormir, tenue, enfants, accessibilité, liste de mariage | **Indispensable** | V1 |
| FAQ avec recherche | **Indispensable** | V1 |
| RSVP (4 taps, parcours « Non » bienveillant) | **Indispensable** | V1 |
| **Partager l'accès au foyer** — sert aussi de « Un proche répond pour moi » : un seul mécanisme, pas de système de délégation séparé | **Indispensable** | V1 |
| Admin invités + planche QR PDF | **Indispensable** | V1 |
| Page de secours statique | **Indispensable** | **V0, avant tout le reste** |
| Page « Le texte » (palindrome) | Souhaitable (coût faible, forte identité) | V2 |
| Rappels e-mail (opt-in) + fil d'annonces dans l'app | **Indispensable** | V2 |
| Web Push | Souhaitable (bonus pour ceux qui installent l'app) | V2 |
| La promesse (vœux scellés jusqu'au 3 juin 2029) | Souhaitable — **gardé** : signature du projet, coût technique faible | V2 |
| Météo J-7 + checklist semaine J | Souhaitable (coût faible) | V3 |
| Plan de table (recherche de son nom, table) | **Indispensable** | V3 |
| Maintenant (jour J) + Aide avec **boutons d'appel** (témoin, régie) | **Indispensable** | V3 |
| Régie : annonces + décalage d'un moment + masquer une photo | **Indispensable** (version minimale uniquement) | V3 |
| Cérémonie débranchée | Souhaitable (coût quasi nul) | V3 |
| Photos & vidéos : envoi en file persistante, galerie, filtres par moment, modération | **Indispensable** | V3 |
| Mur en direct `/live` | Souhaitable | V3 |
| Défis photo (sans classement) | Bonus | V3 si le temps le permet |
| Cartes de table PDF + fiche régie PDF | **Indispensable** | V3 |
| Merci + photos du photographe + archives ZIP | **Indispensable** | V4 |
| Suppression automatique des données | **Indispensable** | V4 |
| Diffusion en direct intégrée | **Remplacé** : un simple **lien privé** vers une plateforme de diffusion existante, affiché uniquement aux foyers connectés. Aucun lecteur ni infrastructure sur mesure | V3 |
| Messages des absents | **Simplifié** : message écrit uniquement ; les vidéos passent par l'envoi de souvenirs | V2 |
| SMS | **Coupé** (coût et complexité) — e-mail + fil d'annonces + push suffisent | — |
| Covoiturage avec mise en relation | **Coupé** — remplacé par un paragraphe dans Infos et un lien vers un groupe de discussion géré par les mariés [À COMPLÉTER] | — |
| « Photos où je suis » (identification manuelle) | **Coupé** — remplacé par le filtre « Mes photos » et le bouton « Demander le retrait » | — |
| « Je suis en retard » avec alerte à la régie | **Coupé** — remplacé par le bouton d'appel de la régie | — |
| Objets perdus | **Coupé** — géré par téléphone par la régie | — |
| Présentation des voisins de table | **Coupé** | — |
| Messages audio | **Coupé** | — |

### Budget : quasi nul, dépenses uniquement si nécessaires

- **Nom de domaine** : oui, acheté dès V0 (le QR imprimé en dépend ; il ne doit jamais changer).
- **Hébergement : VPS Hostinger KVM 2** (déjà en place, sans surcoût) — voir la section « Hébergement : VPS Hostinger KVM 2 » ci-dessous.
- **Supabase** : offre gratuite jusqu'à 3 mois avant le mariage, puis offre payante **uniquement** si le stockage des médias l'exige, et retour à l'offre gratuite après export des archives.
- **Vidéos des invités** : limitées à **60 secondes**, compressées côté navigateur quand c'est possible. C'est ce qui garde le stockage raisonnable.
- **E-mail** : prestataire transactionnel européen, offre gratuite.
- **Aucun** SMS, aucun service de diffusion payant, aucune bibliothèque payante.
- Avant chaque dépense : me présenter le besoin, l'alternative gratuite et le coût à jour vérifié.

### Hébergement : VPS Hostinger KVM 2

Un VPS est un serveur complet que nous administrons nous-mêmes : plus de liberté, mais la sécurité, les mises à jour et les sauvegardes sont **de ta responsabilité**. Traite-les comme des fonctionnalités à part entière, avec tests et documentation.

**Vérifications en V0**
- Relever dans hPanel les caractéristiques réelles du VPS (processeur, mémoire, disque, bande passante, système, emplacement du centre de données) et les consigner dans `INFRA.md`. Ne pas supposer de chiffres.
- **D'autres projets tournent déjà sur ce VPS (confirmé).** Voir « Cohabitation » ci-dessous : ces règles sont bloquantes.

**Cohabitation avec les projets existants (règles bloquantes)**
1. **Audit en lecture seule d'abord**, sans rien modifier : conteneurs et services actifs, ports utilisés (qui écoute sur 80 et 443), reverse proxy en place et sa configuration, pare-feu, tâches planifiées, utilisation du processeur, de la mémoire et du disque sur plusieurs heures. Résultat consigné dans `INFRA.md`, puis **validation de ma part avant toute action**.
2. **S'intégrer à l'existant** : si un reverse proxy occupe déjà les ports 80/443 (Nginx, Traefik, Caddy…), **ajouter** la configuration du domaine du mariage à ce proxy. Ne jamais installer un second proxy concurrent, ni remplacer celui en place sans accord explicite.
3. **Aucune action globale sans accord** : pas de mise à jour système nécessitant un redémarrage, pas de modification du démon Docker, du pare-feu, de SSH ou des tâches planifiées existantes, pas de `docker system prune`, pas de redémarrage d'un service qui n'appartient pas au mariage.
4. **Isolation** : utilisateur système dédié, dossier dédié (`/srv/mariage-jl`), réseau Docker dédié, fichiers d'environnement et secrets séparés, noms de conteneurs préfixés `jl-`. Aucune base de données ni volume partagé avec les autres projets.
5. **Ressources réservées dans les deux sens** : limites de mémoire et de processeur sur les conteneurs du mariage (ils ne doivent pas étouffer les autres projets) **et** marge garantie pour le mariage le jour J (les autres projets ne doivent pas l'étouffer). Me proposer les valeurs après l'audit.
6. **Période protégée J-7 à J+1** : gel des déploiements **de tous les projets du VPS**, aucune mise à jour système, aucun redémarrage planifié, tâches lourdes des autres projets (sauvegardes, traitements) décalées hors des horaires de la journée. Rappel écrit dans `INFRA.md` et dans le calendrier de Julien.
7. **Sauvegardes** : ne sauvegarder que les éléments du mariage, sans toucher aux sauvegardes des autres projets.

**Architecture**
- **Docker Compose** : conteneur `app` (Next.js en sortie `standalone`, utilisateur non root, `restart: unless-stopped`, contrôle de santé sur `/api/health`, limites de ressources) et reverse proxy **Caddy** (HTTPS automatique, HTTP/2 et HTTP/3, compression, en-têtes de sécurité, redirection vers le domaine canonique).
- **Compilation hors du VPS** : GitHub Actions construit l'image, exécute les tests, publie l'image dans un registre privé, puis déploie par SSH (clé dédiée, utilisateur de déploiement sans droits root). Chaque image est **étiquetée par version** : retour arrière en une commande documentée.
- **Application sans état** : aucune donnée métier sur le VPS. Base de données, photos et vidéos restent sur **Supabase (Europe)**, tâches planifiées incluses (rappels, bascule des périodes, suppressions automatiques) : elles continuent de fonctionner même si le VPS tombe.
- Envoi des médias **directement du téléphone vers Supabase** (URL signées), sans transiter par le VPS : la bande passante et le processeur du serveur restent libres le jour J.

**Sécurité du serveur (checklist bloquante avant V1)**
- Connexion SSH par clé uniquement, mot de passe et connexion root désactivés, port SSH restreint si possible.
- Pare-feu : seuls 80, 443 et SSH ouverts. Protection contre les tentatives de connexion répétées (fail2ban ou équivalent).
- Mises à jour de sécurité automatiques du système, images Docker reconstruites chaque mois.
- Secrets dans des fichiers d'environnement hors dépôt, droits restreints, jamais dans l'image.
- En-têtes de sécurité (HSTS, CSP stricte, X-Content-Type-Options, Referrer-Policy, Permissions-Policy).
- Rotation des journaux (taille limitée), aucune donnée personnelle dans les journaux.

**Sauvegardes et reprise**
- Instantanés du VPS proposés par Hostinger activés (vérifier la fréquence dans hPanel).
- **Sauvegarde externe** quotidienne de la base Supabase et, à partir de J-7, des médias, vers un stockage hors Hostinger et hors Supabase [destination À COMPLÉTER].
- **Procédure de reconstruction complète** d'un VPS vierge en moins d'une heure, écrite et **testée une fois** avant J-60.

**Page de secours : hors du VPS**
- Si le VPS tombe, une page hébergée sur le même VPS tombe avec lui. La page de secours statique est donc déployée **sur un hébergeur statique gratuit indépendant** [choix à me proposer], mise à jour par la même chaîne GitHub Actions.
- **DNS géré chez Hostinger (confirmé)**, dans la zone DNS de hPanel.
- Durée de vie des enregistrements (TTL) abaissée à 5 minutes à partir de J-14, remise à la normale à J+2.
- **Bascule** = modifier l'enregistrement du domaine pour qu'il pointe vers la page de secours. Préparer à l'avance la valeur exacte à saisir et la valeur de retour.
- **Qui peut basculer** : l'accès à hPanel donne un contrôle étendu sur le compte Hostinger. Vérifier dans la documentation Hostinger à jour s'il existe **un accès délégué limité** ou **une API DNS** avec clé restreinte. Si oui : proposer au référent technique un moyen de bascule limité à cette seule action. Si non : la bascule est faite par **Julien ou une personne à qui il confie son accès en connaissance de cause**, jamais par partage de mot de passe par message.
- Procédure pas à pas avec captures dans la fiche du référent, **testée pour de vrai à J-60** avec chronométrage (modification + propagation constatée sur deux opérateurs mobiles).

**E-mails**
- Ne jamais envoyer d'e-mails directement depuis le VPS (mauvaise délivrabilité). Utiliser un **prestataire transactionnel européen** avec offre gratuite, et configurer SPF, DKIM et DMARC sur le domaine.

**Surveillance**
- Sonde de disponibilité externe gratuite (accueil + `/api/health`, qui vérifie aussi Supabase), alerte e-mail au référent technique et à Julien.
- Alertes simples sur le disque, la mémoire et le redémarrage des conteneurs.

**Capacité**
- Test de charge de la section 10 exécuté **contre le VPS de production** (hors période de gel), résultats consignés dans `INFRA.md`.
- Mise en cache des pages d'information par Caddy et Next.js ; optimisation d'images Next.js activée (dépendance `sharp` incluse dans l'image) avec cache disque limité en taille.

### Rôles humains

- **Mainteneur avant le mariage** : Julien. Documentation `README.md` écrite pour lui.
- **Référent technique du jour J** : un proche à l'aise avec le numérique [À COMPLÉTER], **distinct de la régie**. Pas d'accès administrateur au serveur. Un seul pouvoir : exécuter la procédure écrite de bascule vers la page de secours (section 0 bis), avec lecture seule sur la surveillance et Supabase. Fiche de dépannage d'une page (quoi vérifier, comment basculer, qui appeler).
- **Régie du jour J** : **une seule personne** [À COMPLÉTER] + une suppléante. Rôle « Régie » limité aux annonces, au décalage des horaires et au masquage de photos.
- **Julien et Lauriane le jour J** : aucun accès actif, aucune notification admin.

### Plan de repli

- **V0 = page de secours en ligne en premier** : une seule page statique dans la DA (monogramme, date, lieu, programme, accès, contact, lien de réponse par formulaire simple), servie sur le domaine définitif.
- Le QR code pointe toujours vers le domaine : on peut remplacer l'application par la page de secours à tout moment sans réimprimer quoi que ce soit.
- Si la V1 n'est pas validée **1 mois avant l'envoi du faire-part**, le faire-part part avec la page de secours, et l'application la remplace plus tard sur le même domaine.

### Tests humains

- **Avant V1** : deux relecteurs du parcours complet, sur leur propre téléphone et sans explication : un invité de plus de 75 ans et un invité qui déteste les applications [À COMPLÉTER]. Leurs blocages sont corrigés avant l'envoi du faire-part.
- **J-60** : répétition générale (section 10), inchangée.

### Calendrier

- V0 (domaine + page de secours) : immédiatement.
- V1 : validée **au plus tard 1 mois avant l'envoi du faire-part** [date d'envoi À COMPLÉTER].
- V2 : J-6 mois. V3 : J-3 mois. Répétition générale : J-60. V4 : J-30. Gel : J-7 à J+1.

---

## 1. L'idée qui guide tout

**L'application prolonge le film d'annonce.** Même silence, même noir et ivoire, mêmes cinq couleurs, même retenue.

Et une conviction : **une bonne app de mariage se fait oublier.** Elle n'est pas là pour être admirée, mais pour que chaque invité, du témoin de 30 ans à la grand-mère de 88 ans, arrive serein, se sente attendu, ne cherche jamais une information, et reparte avec ses souvenirs.

### Les sept règles
1. **L'app n'affiche que ce qui compte maintenant.** L'interface change avec le temps (avant, semaine J, jour J, après) : jamais plus de 5 onglets, jamais de fonction inutile à l'instant présent.
2. **Trois taps maximum** pour toute information essentielle.
3. **Rien n'est obligatoire.** Pas de compte, pas d'installation imposée, pas de participation forcée : on peut tout faire sans installer l'app, sans activer les notifications, sans publier une seule photo.
4. **Tout fonctionne mal connecté.** Le domaine est à la campagne : l'app doit rester utile sans réseau.
5. **Luxe sobre** : fondus, filets, silence. Aucun confetti, emoji, rebond ou son intempestif.
6. **Personne n'est oublié** : ceux qui lisent mal, ceux qui ne parlent pas français, ceux qui ne peuvent pas venir, ceux qui détestent les applications.
7. **Julien et Lauriane ne touchent pas à l'app le jour J.** Une personne de confiance s'en charge (section 9).

---

## 2. Informations connues (source de vérité)

| Élément | Valeur |
|---|---|
| Couple | Julien & Lauriane |
| Signature | J&L — DEPUIS 2018 |
| Date | 3 juin 2028 — affichage `03 · 06 · 2028` |
| Fuseau | Europe/Paris |
| Lieu | Domaine de Roiffé, 86120 Roiffé (Vienne) |
| Adresse complète, GPS, accès PMR | [À COMPLÉTER] |
| Horaires de la journée | [À COMPLÉTER] |
| Date d'envoi du faire-part | [À COMPLÉTER] — **la version 1 doit être en ligne et testée avant** |
| Date limite de réponse | [À COMPLÉTER] |
| Film d'annonce | `JL_annonce_1080p_version_texte.mp4` (1920×1080, 102 s), fourni séparément |

### Les cinq moments (code couleur officiel)

| # | Nom | Moment | Référence | Hex écran |
|---|---|---|---|---|
| 01 | L'Éclat | Accueil | RAL 1023 | `#E9B131` |
| 02 | L'Horizon | Cérémonie | RAL 5015 | `#365D87` |
| 03 | La Rencontre | Cocktail | RAL 2004 | `#CB5726` |
| 04 | L'Ivresse | Dîner | RAL 3005 | `#721F23` |
| 05 | La Nuit | Fête | RAL 4005 | `#84568D` |
| — | Le Fond | Équilibre | RAL 9010 | `#E9E2D8` |
| — | La Matière | Authenticité | RAL 1019 | `#99836F` |

Hex relevés sur une maquette écran : centralise-les dans les tokens, ils seront remplacés par les références de l'imprimeur.

### Le texte palindrome (lignes identiques dans les deux sens, pivot « Sauf que… »)

```
Julien et Lauriane vont se marier.
Après tout ce temps.
Chacun connaît déjà l'autre par cœur.
Il serait naïf d'imaginer que
Leur plus belle promesse reste à faire.
À vrai dire,
Le quotidien finit toujours par gagner.
Ce serait mentir de dire que
Dix ans, ce n'est qu'un début.
Tout le monde le dit :
Se marier ne change rien.
On aurait tort de croire que
Le 3 juin 2028, au Domaine de Roiffé,
Julien et Lauriane seront plus amoureux qu'en 2018.
```

---

## 3. Direction artistique

### Couleurs
- Fond `#080808` (vignette radiale très légère autorisée). Texte ivoire `#E9E2D8`, secondaire à 60 %, filets à 12 %.
- **Les cinq couleurs ne sont jamais une couleur de texte** (contraste insuffisant). Elles sont des **fils** : filets de 2 px, pastilles, barre de progression, bordure du moment en cours, pile verticale de 5 carrés (signature du faire-part).
- **Mode « Papier »** (fond ivoire, texte `#121212`) : proposé à tous dans « Confort de lecture » et utilisé pour les documents imprimables.

### Typographie (Google Fonts via `next/font`, auto-hébergées)
- **Bodoni Moda** (`opsz` ≈ 24, `wght` ≈ 470) : monogramme, titres, chiffres du compte à rebours.
- **Cormorant Garamond** : textes. Base 18 px mobile, interligne 1,55. **Minimum absolu 16 px** partout.
- **Étiquettes** : Cormorant Garamond Medium, capitales, interlettrage 0,3 em.
- Apostrophes typographiques, chiffres alignés et tabulaires pour les horaires, espaces insécables avant `: ; ? !`.

### Monogramme
- **J** et **L** en Bodoni Moda romain, **&** en Bodoni Moda *italique* à 95 %, ligne de base commune.
- Composant `<Monogram />` en **SVG vectorisé** (tracés), variantes pleine et contour 1 px. Composant `<Signature />` : monogramme, `DEPUIS 2018`, pile des 5 carrés (16 px, espacement 4 px).

### Mouvement
- Fondus, glissements ≤ 12 px, tracés de lignes. Courbe `cubic-bezier(0.22, 1, 0.36, 1)`, 300 à 900 ms.
- **Ouverture signature**, une seule fois par appareil : cinq filets de couleur se déploient, montent, révèlent le contour du monogramme qui se remplit d'ivoire (le final du film). Bouton « Passer » visible immédiatement ; jamais bloquant.
- `prefers-reduced-motion` et réglage « Réduire les animations » → simples fondus.

### Icônes et images
- Icônes filaires fines (1,5 px), ivoire, sans remplissage. Pas de pack d'icônes arrondies colorées.
- Pas de photos de banque d'images. Seules images : le film, vos photos, celles des invités.

### Ton
Calme, chaleureux, légèrement souriant, jamais familier. Vouvoiement. Phrases courtes. Jamais de jargon technique face aux invités.
- Vide : « Les premières images arriveront bientôt. Soyez les premiers. »
- RSVP : « C'est noté. Nous avons hâte. »
- Absence : « Vous nous manquerez. Nous penserons à vous. »
- Hors ligne : « Pas de réseau pour l'instant. Tout ce que vous faites sera envoyé dès son retour. »

---

## 4. Le confort de chacun (personas à tester)

Chaque écran doit être validé mentalement pour ces huit personnes. Ajoute ces personas dans `PLAN.md` et teste les parcours Playwright en conséquence.

| Persona | Ce dont il/elle a besoin | Réponse de l'app |
|---|---|---|
| **Jeanne, 84 ans**, lit mal, smartphone reçu de ses petits-enfants | Gros caractères, rien à installer, une personne pour répondre à sa place | « Confort de lecture » dès l'ouverture, **« Un proche répond pour moi »**, bouton « Appeler un témoin » toujours visible |
| **Thomas, 35 ans**, déteste les applis | Tout en 1 minute, sans compte | QR → réponse en 4 taps, rappels par SMS ou e-mail s'il le souhaite |
| **Emma, 29 ans**, adore partager | Envoyer beaucoup de photos, vite | Envoi multiple en arrière-plan, défis photo, galerie en direct |
| **Karim, 42 ans**, timide, ne connaît que les mariés | Ne pas être exposé, savoir à quoi s'attendre | Aucune photo de profil, rien de public obligatoire, « Le déroulé en détail », voisins de table présentés en une phrase (s'ils l'acceptent) |
| **Sarah & Paul**, parents de deux enfants | Horaires, menu enfant, coin calme, retour tôt | Infos « Avec des enfants », navettes et taxis visibles, heure de fin de chaque moment |
| **Mamie Odette**, ne pourra pas venir | Vivre le mariage de loin | **Diffusion en direct** de la cérémonie, message vidéo ou écrit aux mariés, galerie après |
| **Liam**, cousin anglophone | Comprendre | Anglais complet, bascule en un tap |
| **Lucie**, en fauteuil roulant | Savoir si tout est accessible | Rubrique « Accessibilité » : accès, stationnement, sanitaires, dénivelés, avec contact direct [À COMPLÉTER] |

---

## 5. Stack technique

- **Next.js** (App Router, version stable actuelle), **TypeScript strict** (`strict`, `noUncheckedIndexedAccess`), **Tailwind CSS**.
- **Supabase** en **région Europe** : Postgres, Storage, Realtime, Auth (admin et régie uniquement), tâches planifiées.
- **PWA** : manifeste, service worker maintenu (Serwist ou équivalent), cache hors ligne, file d'attente persistante (IndexedDB) pour réponses et médias.
- **Web Push** (VAPID, `web-push`).
- **E-mail et SMS** transactionnels via un prestataire hébergé dans l'Union européenne, avec opt-in explicite [prestataire et budget À COMPLÉTER].
- **zod** (formulaires, API, variables d'environnement), **react-hook-form**, **Motion** ou CSS pour les animations.
- Médias : compression navigateur, HEIC → JPEG, suppression des métadonnées GPS, **envoi reprenable (TUS)**.
- **i18n** : français et anglais complets dès la version 1 (fichiers de traduction, aucune chaîne en dur).
- Suivi d'erreurs respectueux de la vie privée (hébergé en Europe, sans rejeu de session) et surveillance de disponibilité.
- Tests **Vitest** et **Playwright** (iPhone et Android émulés, réseau lent simulé).
- Déploiement sur **VPS Hostinger KVM 2** via Docker, domaine [À COMPLÉTER] — détails en section 0 bis.

---

## 6. Accès : zéro friction

- **Un QR code par foyer** sur le faire-part → `https://[domaine]/i/[token]` (≥ 128 bits aléatoires, révocable). Première ouverture : « Bienvenue, [prénoms du foyer] ». L'appareil est ensuite reconnu (cookie `httpOnly` + stockage local).
- **Code de secours** à 6 caractères imprimé sous le QR : « Retrouver mon invitation » (nom + code).
- **Un QR générique** (cartes de table, affiches sur place) : programme, infos, galerie et envoi de photos, sans données nominatives.
- **Partager l'accès au foyer** : un lien pour que le conjoint ou un proche ouvre la même invitation sur son téléphone.
- **« Un proche répond pour moi »** : un invité peut déléguer sa réponse à une personne de son choix (lien de délégation).
- **Premier lancement en 3 écrans maximum**, tous passables :
  1. Ouverture signature.
  2. **Confort de lecture** : taille du texte (normale / grande / très grande), mode Papier, réduire les animations, langue.
  3. « Bienvenue, [prénoms]. Tout est ici. » → Accueil.
- Admin (Julien et Lauriane) et régie (section 9) : lien magique par e-mail, liste blanche [À COMPLÉTER].

---

## 7. Une interface qui change avec le temps

Une seule barre de navigation, 5 onglets, dont le contenu évolue automatiquement (bascule manuelle possible dans l'admin, horloge simulable en test).

| Période | Onglets | Priorité à l'accueil |
|---|---|---|
| **Avant** (de l'annonce à J-8) | Accueil · Programme · Réponse · Infos · FAQ | Film, compte à rebours, répondre |
| **Semaine J** (J-7 à J-1) | Accueil · Programme · Infos · Ma table · FAQ | Météo, trajet, tenue, table, checklist |
| **Jour J** | Maintenant · Programme · Photos · Ma table · Aide | Moment en cours, moment suivant, annonces |
| **Après** (dès J+1) | Merci · Photos · Film · Messages · Mes données | Galerie, photos du photographe, remerciements |

---

## 8. Les écrans

### 8.1 Accueil « Avant »
- Ouverture signature, puis **compte à rebours** (jours, heures, minutes, secondes en Bodoni Moda). Sous le compteur, **cinq filets** qui se remplissent au fil des étapes : Annonce → Réponse → J-30 → J-7 → Jour J.
- **Carte « À faire »** : une seule action à la fois (« Répondre avant le [date] », puis « Réserver un hébergement », puis « Consulter votre table »). Quand tout est fait : « Il ne vous reste qu'à venir. »
- **Le film d'annonce** : vignette noire avec le monogramme, plein écran, lecture silencieuse possible.
- Lien discret **« Le texte »** vers la page palindrome (8.8).

### 8.2 Réponse (RSVP) — 4 taps pour la version simple
1. « Serez-vous des nôtres ? » **Oui / Non / Pas encore sûr·e** (rappel automatique dans ce dernier cas).
2. Pour chaque personne du foyer : présence (réglage fin par moment masqué derrière « Préciser », tous cochés par défaut).
3. Menu [options À COMPLÉTER], régime (végétarien, sans porc, sans alcool…), **allergies** dans un champ séparé avec consentement explicite (section 11).
4. Facultatif et replié : hébergement, transport, enfants et âge, chanson pour danser, mot pour les mariés, rappels par SMS ou e-mail.
- **« Non »** ouvre un parcours bienveillant : « Vous nous manquerez. » + proposition de suivre la cérémonie en direct, laisser un message, recevoir les photos après.
- Modifiable jusqu'à la date limite, puis verrouillé avec contact.

### 8.3 Programme
- Les **cinq moments** en cartes : numéro, nom, moment, **heure de début et de fin**, lieu dans le domaine, filet de couleur, une phrase d'ambiance [À COMPLÉTER].
- **« Le déroulé en détail »** (pour les anxieux) : ce qui se passe, où se placer, durée, s'il faut rester debout, s'il y a de l'ombre.
- « Ajouter à mon agenda » (`.ics`, 5 événements).
- Le jour J : moment en cours mis en avant, moments passés estompés.

### 8.4 Infos
- **Venir** : adresse, boutons Apple Plans / Google Maps / Waze, parking, navettes, **covoiturage** (proposer ou chercher une place, contact révélé seulement si les deux acceptent).
- **Dormir** : hébergements éditables (distance, prix indicatif, lien, téléphone, navette ou non) [À COMPLÉTER].
- **Tenue** : indication [À COMPLÉTER], palette en inspiration et non en obligation, conseil chaussures si pelouse ou gravier.
- **Avec des enfants** : horaires adaptés, menu enfant, espace calme, baby-sitting éventuel [À COMPLÉTER].
- **Accessibilité** : accès fauteuil, stationnement proche, sanitaires adaptés, dénivelés, contact [À COMPLÉTER].
- **Météo** dès J-7 (Open-Meteo, sans clé ni cookie) + « En cas de pluie » (plan B) [À COMPLÉTER].
- **Liste de mariage** : lien externe [À COMPLÉTER].
- **Rentrer en sécurité** (visible dès La Nuit) : dernières navettes, numéros de taxi locaux, covoiturage retour, invitation à désigner un conducteur [À COMPLÉTER].

### 8.5 Semaine J — la checklist sereine
Une liste courte cochable, personnalisée selon la réponse : tenue prête, trajet enregistré, hébergement confirmé, table consultée, app ajoutée à l'écran d'accueil (facultatif), batterie externe pour les photos.

### 8.6 Jour J — « Maintenant »
- En grand : **moment en cours** (nom, couleur, heure de fin), **moment suivant** avec compte à rebours discret.
- **Annonces en direct** de la régie (« Le cocktail est servi sur la terrasse »).
- Raccourcis : Ma table · Partager un souvenir · Itinéraire · Aide.
- **Cérémonie débranchée** : pendant L'Horizon, l'app affiche « Profitez de l'instant. Notre photographe s'occupe des images. » L'envoi de photos est mis en pause (réglage admin), puis réactivé automatiquement à la fin.
- Page **Aide** : « Je suis en retard » (prévient la régie), « Je suis perdu » (plan et itinéraire), « J'ai perdu un objet », « Appeler un témoin ».

### 8.7 Photos & vidéos
- **Galerie partagée en direct**, grille sobre 3 colonnes, filtres par **moment** (les 5 couleurs), **« Mes photos »**, **« Photos où je suis »** (voir ci-dessous), récentes / appréciées.
- **« Partager un souvenir »** : sélection multiple ou prise directe, compression, **file d'envoi persistante** (reprend après coupure, fermeture de l'app ou redémarrage), option **« Envoyer seulement en Wi-Fi »**, indicateur discret « 3 souvenirs en attente de réseau ».
- **Consentement** au premier envoi (visibilité aux invités, prudence pour les photos d'enfants). Toute personne peut demander le retrait d'une photo où elle apparaît, en un tap.
- **« Photos où je suis »** : **sans reconnaissance faciale** (données biométriques exclues). Un invité peut identifier manuellement une personne sur une photo ; la personne identifiée reçoit la photo dans son espace et peut retirer l'identification.
- **Défis photo** : un par moment, dans sa couleur [intitulés éditables]. Aucune compétition, aucun classement.
- **Mur en direct** `/live` pour projection : diaporama plein écran, fondu de 6 s, monogramme en filigrane, QR générique en coin.
- **Après** : les **photos du photographe** sont ajoutées dans une section distincte « Le regard du photographe » (accès protégé), puis **archive ZIP** personnelle (« Toutes les photos du mariage » / « Mes photos »).

### 8.8 Le texte
- Le palindrome défile ligne par ligne comme dans le film ; bouton **« Sauf que… »** : la colonne remonte et chaque ligne se rallume en sens inverse. Aucune explication. Lien final « Revoir le film ».

### 8.9 Ceux qui sont loin
- **Diffusion en direct de la cérémonie**, accessible uniquement avec un lien de foyer (lecteur intégré d'un service de diffusion en lien privé [prestataire À COMPLÉTER]), rediffusion 30 jours.
- **Message aux mariés** : écrit, audio ou vidéo courte, publié dans le livre d'or ou gardé privé pour les mariés.

### 8.10 La promesse (création signature)
Écho direct au texte : *« Leur plus belle promesse reste à faire. »*
- Chaque invité peut écrire **un vœu pour Julien et Lauriane**, scellé.
- Les vœux sont **invisibles de tous, y compris des mariés**, jusqu'au **3 juin 2029** (premier anniversaire). Ce jour-là, notification aux mariés : « Vos invités vous ont laissé une promesse. »
- Interface : une enveloppe ivoire, un sceau au monogramme, une animation de fermeture sobre. Aucun compteur de participation.

### 8.11 Après — « Merci »
- Signature, message des mariés [À COMPLÉTER], sélection de photos, film de la journée si fourni, photos du photographe, dates de fin d'accès et de suppression.

---

## 9. Régie du jour J (pour que les mariés ne touchent à rien)

- Rôle **« Régie »** attribué à 1 ou 2 personnes de confiance [À COMPLÉTER — ne pas inventer de noms].
- Écran régie simplifié, utilisable d'une main :
  - publier une annonce (modèles pré-écrits : « Le cocktail est servi », « Le dîner va commencer », « Dernière navette dans 15 minutes ») ;
  - avancer ou retarder un moment (tous les horaires suivants se décalent, notification optionnelle) ;
  - voir les alertes « Je suis en retard » et « Objet perdu » ;
  - masquer une photo signalée en un tap.
- **Fiche régie imprimable** (PDF) : horaires, contacts, procédures en cas de panne (section 10).
- La régie ne voit ni les allergies ni les données personnelles hors besoin.

---

## 10. Fiabilité : penser la panne

- **Répétition générale obligatoire** à J-60 : un repas de famille de 15 à 20 personnes, sur leurs propres téléphones, ouvre les QR, répond, envoie photos et vidéos, reçoit une annonce. Rapport écrit de ce qui a gêné, corrections avant J-30.
- **Test de couverture réseau sur place** (visite du domaine) : mesurer 4G par opérateur dans chaque espace ; si faible, prévoir un **Wi-Fi invités** [À COMPLÉTER] et afficher son nom et son mot de passe sur les cartes de table.
- **Plan B imprimé** : une **carte par table** dans la DA (QR générique, programme des 5 moments, Wi-Fi, numéro d'un témoin) et des panneaux aux points clés. Si l'app ou le réseau tombe, personne n'est perdu.
- **Tests de charge** : 150 invités ouvrant l'app en 5 minutes, 50 envois de photos simultanés, 20 vidéos de 200 Mo.
- **Gel des déploiements** 7 jours avant le mariage (sauf correctif critique validé par moi), sauvegarde complète de la base et des médias la veille et le lendemain.
- **Page de secours statique** (programme, accès, contacts) servie si l'application est indisponible.
- Surveillance de disponibilité avec alerte e-mail à la régie.

---

## 11. Données personnelles et sécurité

- Données en Europe, aucune revente ni partage, aucun traceur publicitaire, uniquement des cookies nécessaires.
- **Allergies = données de santé** : consentement explicite séparé, visibles uniquement des mariés et dans l'export traiteur, **suppression automatique 30 jours après**.
- **Page Confidentialité** en langage simple, boutons **« Télécharger mes données »** et **« Supprimer mes données »**.
- Conservation réglable : réponses supprimées 3 mois après ; galerie 12 mois puis suppression (après avertissement aux mariés) ; vœux de « La promesse » conservés jusqu'au 3 juin 2029 puis remis aux mariés et supprimés du serveur ; journaux 30 jours.
- **Row Level Security sur toutes les tables** ; URL signées à durée limitée pour les médias ; rôles admin, régie et invité vérifiés côté serveur.
- Limitation de débit (recherche d'invitation, envois, formulaires), comparaison de tokens en temps constant, validation du type réel des fichiers, suppression des métadonnées GPS.
- Diffusion en direct et photos du photographe : accès uniquement avec un lien de foyer valide.
- Secrets exclusivement en variables d'environnement.

---

## 12. Qualité

- **Accessibilité WCAG 2.2 AA** : contrastes vérifiés, cibles ≥ 48 px, navigation clavier et lecteur d'écran (libellés français et anglais), zoom 200 %, sous-titres pour toute vidéo parlée.
- **Performance** : Lighthouse mobile ≥ 95 dans les 4 catégories ; première page utile < 2 s en 4G lente ; ouverture signature jamais bloquante.
- **Hors ligne** : programme, infos, FAQ, table et fiche de secours consultables sans réseau une fois ouverts ; réponses et médias en file d'attente.
- **Compatibilité** : Safari iOS et Chrome Android (deux dernières versions majeures), un Android d'entrée de gamme, un iPhone ancien encore maintenu.
- **Parcours Playwright obligatoires** : QR foyer → réponse en ≤ 4 taps ; parcours « Non » ; délégation « Un proche répond pour moi » ; confort de lecture « très grande » sans casse ; envoi de 3 photos (dont HEIC) et 1 vidéo avec coupure réseau simulée ; bascule des 4 périodes avec horloge simulée ; cérémonie débranchée ; régie qui décale un moment ; suppression de mes données.

---

## 13. Versions et calendrier

| Version | Contenu | Échéance | Terminé quand |
|---|---|---|---|
| **V0 — Fondations** | Tokens DA, polices, `<Monogram />`, `<Signature />`, page `/design`, Supabase Europe, schéma, RLS, i18n | [À COMPLÉTER] | `/design` validée ; tests RLS verts |
| **V1 — Le socle** (avant le faire-part) | Accès par QR et code de secours, premier lancement, confort de lecture, Accueil « Avant », film, compte à rebours, Programme, Infos, FAQ, RSVP complet, admin invités, **planche QR PDF** | Avant l'envoi du faire-part | 20 foyers tests répondent sans aide |
| **V2 — La préparation** (J-6 mois) | Notifications et rappels e-mail/SMS, covoiturage, hébergements, page « Le texte », « Ceux qui sont loin » (messages), La promesse | [À COMPLÉTER] | Rappel reçu sur les 3 canaux |
| **V3 — Le jour J** (J-3 mois) | Semaine J, Maintenant, Aide, régie, annonces, cérémonie débranchée, Photos complètes, mur en direct, diffusion en direct, plan de table, cartes de table PDF, page de secours | [À COMPLÉTER] | **Répétition générale réussie (J-60)** |
| **V4 — Après** (avant J) | Merci, photos du photographe, archives ZIP, suppression automatique | Avant J | Parcours « Après » testé avec horloge simulée |
| **Gel** | Aucun déploiement de J-7 à J+1 sauf correctif critique | J-7 | Sauvegardes vérifiées |

---

## 14. Espace admin (Julien et Lauriane)

- **Tableau de bord** : réponses reçues / attendues, présents par moment, menus, régimes, allergies (accès restreint), hébergement, transport, courbe des réponses, foyers à relancer.
- **Invités** : import CSV, édition, relance ciblée (push, e-mail, SMS), révocation de token, délégations.
- **Imprimables dans la DA** (PDF) : planche de QR par foyer (prénoms, QR, code de secours), cartes de table, fiche régie, panneaux sur place.
- **Contenus** : moments, horaires, lieux, déroulé détaillé, FAQ, hébergements, accessibilité, enfants, tenue, rentrer en sécurité, défis, modèles d'annonces, textes de notifications, dates clés, bascule manuelle des périodes.
- **Plan de table** : glisser-déposer, présentation des voisins (opt-in), publication.
- **Médias** : réglage publication immédiate ou validation, modération, mise en avant, import des photos du photographe, exports ZIP.
- **Exports** : CSV des réponses, fiche traiteur (menus, régimes, allergies, sans autre donnée).
- **Indicateurs de réussite** (section 16) visibles en un écran.

---

## 15. FAQ de départ (éditable, français et anglais)

1. À quelle heure arriver, et combien de temps dure la journée ?
2. Comment venir ? Où se garer ? Y a-t-il des navettes ou du covoiturage ?
3. Où dormir à proximité ?
4. Quelle tenue prévoir ? Faut-il porter les couleurs du mariage ?
5. Les enfants sont-ils les bienvenus ? Que prévoir pour eux ?
6. Le domaine est-il accessible en fauteuil roulant ?
7. Jusqu'à quand répondre ? Puis-je modifier ma réponse ? Un proche peut-il répondre pour moi ?
8. Comment signaler une allergie ou un régime ?
9. Puis-je venir accompagné·e ?
10. Pourquoi une cérémonie sans téléphone ?
11. Comment partager mes photos ? Qui peut les voir ? Comment retirer une photo où j'apparais ?
12. Je ne pourrai pas venir : comment suivre la cérémonie ?
13. Faut-il installer l'application ? Comment recevoir les rappels sur iPhone ?
14. Et s'il pleut ? Et s'il n'y a pas de réseau ?
15. Y a-t-il une liste de mariage ?
16. Qui contacter le jour J ?
17. Qu'est-ce que « La promesse » ?
18. Mes données sont-elles protégées ? Quand seront-elles supprimées ?

Réponses dans le ton de la section 3, `[À COMPLÉTER]` pour tout ce qui est inconnu.

---

## 16. Indicateurs de réussite (à suivre dans l'admin, sans traceur)

| Indicateur | Objectif |
|---|---|
| Foyers ayant ouvert leur invitation | ≥ 90 % |
| Réponses reçues via l'app | ≥ 85 % |
| Réponse en moins de 2 minutes | ≥ 80 % des foyers |
| Questions reçues par téléphone ou message | quasiment aucune |
| Souvenirs partagés par les invités | ≥ 300 |
| Envois échoués définitivement | 0 |
| Interventions de Julien et Lauriane le jour J | 0 |
| Incident bloquant le jour J | 0 |

---

## 17. Ce que tu ne dois jamais faire

- Inventer une information, un nom, un numéro, un lien, un prix.
- Utiliser les cinq couleurs comme couleur de texte.
- Ajouter une fonctionnalité non prévue sans me la proposer.
- Exiger un compte, une installation, une photo de profil ou une participation.
- Demander l'autorisation de notifications au premier chargement.
- Utiliser la reconnaissance faciale ou toute donnée biométrique.
- Stocker une donnée de santé sans consentement explicite.
- Afficher un classement, un compteur de participation ou tout ce qui crée une comparaison entre invités.
- Déployer pendant la période de gel.

---

## 18. Ton premier message

1. `PLAN.md` complet (dont les personas et le calendrier des versions), **conforme aux arbitrages de la section 0 bis**.
2. Les **questions bloquantes classées par version**, V1 en premier.
3. **Trois propositions de micro-interactions signature** dans la DA, et **trois idées pour mettre encore plus à l'aise les invités** que tu n'as pas trouvées dans ce document.

Ne commence pas à coder avant ma validation.

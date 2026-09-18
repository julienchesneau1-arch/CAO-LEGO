# Journal des versions

Les dates sont celles de livraison réelle. Tant qu'une version n'est pas validée, elle reste en « en attente de validation ».

## V4 — Après — 18 septembre 2026

La dernière version du plan. Ce qu'il reste quand la fête est finie : le merci, les photos à emporter, et la fin de vie des données.

### Livré

- **« Merci »** (§8.11) : le jour venu, l'accueil bascule une dernière fois. Le mot des mariés (écrit depuis l'admin), quelques vignettes, les liens vers ce qui reste à voir — et, en bas, **jusqu'à quand**.
- **Le regard du photographe** : une section à part, `/photographe`, alimentée depuis `/admin/photographe`. Les photos du photographe n'appartiennent à aucun foyer et n'apparaissent jamais dans la galerie des invités ni sur le mur.
- **Le livre d'or** `/messages` : uniquement les mots dont l'auteur a choisi la visibilité « livre d'or ». Les messages privés n'en sortent pas, et aucun nom de foyer n'est affiché.
- **Le film de la journée** `/film`, dont l'adresse s'écrit depuis l'admin.
- **Archives ZIP** : « Toutes les photos du mariage » et « Mes photos ». Fabriquées à la demande, jamais mises en cache.
- **« Mes données »** `/mes-donnees` (§11) : ce que nous détenons pour ce foyer, **compté et non recopié**, et les dates de suppression automatique.
- **`pnpm purger`** : exécute les purges SQL, puis supprime du disque les fichiers dont la ligne a disparu — ce que SQL ne peut pas faire.

### Ce que le code garantit, et comment c'est vérifié

- **Les dates annoncées sont celles des purges.** Elles viennent d'une fonction SQL, `jl.echeances()`, écrite à partir des mêmes expressions que les fonctions de purge. Un écran ne peut donc pas promettre une date que la base ne tiendra pas ; un test le vérifie en changeant la date du mariage et en relisant l'échéance.
- **Une archive n'est pas une porte dérobée.** Elle contient exactement ce que la galerie montre à ce foyer : un souvenir confié aux seuls mariés n'y est pas, et une photo dont le retrait vient d'être demandé en sort **à la demande suivante** — vérifié par un parcours qui compare les deux archives.
- **L'archive s'ouvre vraiment.** Le ZIP est écrit à la main (méthode `store`, sans dépendance : les JPEG sont déjà compressés) et c'est `unzip -t` qui juge, en vérifiant chaque CRC. Les valeurs de référence du CRC-32 sont testées séparément.
- **Un fichier orphelin quitte le disque**, et **une ligne sans fichier quitte la base**. Tant que sa ligne existe, un fichier reste, même si on demande la purge — perdre une photo coûte bien plus cher que garder un orphelin une nuit de plus.

### Un défaut trouvé par une capture, et corrigé

Les captures d'écran ont montré trois vignettes cassées dans « Merci » : des lignes de médias dont le fichier avait disparu du disque. Cela n'arrive pas en fonctionnement normal — c'est justement pourquoi personne ne l'aurait vu venir : une restauration partielle, un volume remonté de travers, et la galerie affiche des images mortes à tous les invités jusqu'à ce que quelqu'un le remarque. `pnpm purger` travaille désormais **dans les deux sens**, et un test vérifie qu'une seule ligne part quand un seul fichier manque.

### Une mesure à reprendre sur le VPS

Le score Lighthouse de performance oscille entre 94 et 99 selon la charge du conteneur, c'est-à-dire **à cheval sur le seuil de 95** exigé par le brief §12. Une exécution l'a fait passer sous la barre, la suivante l'a remis à 95. Ce n'est pas une mesure exploitable : elle devra être refaite sur le VPS, machine stable, avant de cocher le critère (question V0-05).

### Décisions de produit prises en passant

- **« Accès protégé » pour les photos du photographe veut dire : depuis une invitation reconnue.** Le QR générique ouvre le programme et les infos ; il n'ouvre pas cette section. C'est une interprétation du brief, consignée comme telle (question V4-02) : plutôt qu'inventer un code que les mariés devraient transmettre à cent cinquante personnes, on s'appuie sur la barrière que tout le monde franchit déjà avec son faire-part.
- **« Mes données » compte, il ne recopie pas.** Redire les allergies de chacun à l'écran serait exposer une donnée de santé sans raison. Un test vérifie que la structure ne contient que des nombres et des booléens.
- **Un nom de fichier d'archive ne peut pas sortir du dossier.** Le `..` dans un nom d'entrée ZIP est une vieille attaque toujours efficace ; elle est neutralisée et testée.

### Mesures

303 tests, 158 parcours sur deux gabarits, vingt-trois écrans audités par axe-core sans anomalie, Lighthouse au-dessus du seuil.

### Ce qui reste

Les défis photo (bonus §0 bis, « si le temps le permet ») et le lien privé de diffusion, dont l'emplacement est livré depuis V2 : il attend une adresse, pas du code.

## V3 — Le jour J — 18 septembre 2026 — seconde tranche

Les souvenirs, le mur, le plan de table et les imprimables. V3 est complète côté code.

### Livré

- **Photos et vidéos** (§8.7) : galerie sobre en trois colonnes, filtres par moment et « Mes souvenirs », envoi multiple, compression dans le navigateur, **file d'envoi persistante** dans IndexedDB, option « seulement en Wi-Fi », indicateur discret « 3 souvenirs en attente de réseau ».
- **Consentement au premier envoi**, avec sa version enregistrée — et un choix de visibilité : **aux invités**, ou **aux mariés seulement**, pour la prudence que le brief demande sur les photos d'enfants.
- **Demande de retrait en un tap** : la photo est masquée **avant même que nous la regardions**. Le fichier reste sur le disque : une décision prise dans l'urgence d'une soirée doit pouvoir se défaire.
- **Modération** dans l'écran régie : les signalements avec leur motif, masquer, rendre visible, classer. Les douze derniers souvenirs avec un bouton « Masquer » qui porte son libellé.
- **Mur en direct `/live`** : diaporama plein écran, fondu, monogramme en filigrane, adresse du QR générique dans un coin. Aucun nom, aucun compteur. La liste se renouvelle sans recharger la page — un vidéoprojecteur reste branché des heures.
- **Plan de table** (§0 bis) : `/ma-table` donne votre table et les prénoms qui y sont ; la recherche trouve « Chloé » en tapant « chloe ». Côté mariés, `/admin/table` crée les tables et pose chaque personne.
- **Cartes de table PDF et fiche régie PDF** (§9, §10) : le plan B imprimé. La carte porte le QR générique, les cinq moments, le Wi-Fi et un numéro ; la fiche régie tient sur une page, horaires, contacts et procédures de panne comprises.

### Ce que le code garantit, et comment c'est vérifié

- **Aucune position GPS n'atteint le disque.** Le navigateur ré-encode les images (ce qui perd l'EXIF), et le serveur re-nettoie systématiquement : segments APP de JPEG, blocs de métadonnées de PNG, atomes `udta` et `meta` de MP4/MOV — sans aucune dépendance. Un format que le serveur ne sait pas nettoyer est **refusé**, pas stocké en espérant que personne ne regarde. Un parcours Playwright fabrique une vraie photo géolocalisée, l'envoie, relit le fichier **sur le disque** octet par octet, et vérifie ensuite qu'il se décode toujours.
- **Aucune URL publique.** Un média passe par une route qui vérifie le foyer ; un identifiant deviné donne 404. Un souvenir confié aux mariés n'est servi qu'aux mariés et au foyer qui l'a envoyé.
- **La file d'envoi survit à tout.** Un parcours coupe le serveur pour de vrai, choisit un souvenir, **ferme l'onglet**, rallume le serveur, réouvre l'onglet : le souvenir part tout seul.
- **Aucun compteur** (§17) : le « j'aime » sert au tri et n'est jamais affiché en nombre.

### Défauts trouvés par les tests, et corrigés

- La file d'envoi ne se vidait qu'au bout de vingt secondes ou au retour du réseau : rien à l'ouverture de l'écran. Or sur iPhone la réouverture est le **seul** moment où la file peut partir. Elle tente maintenant l'envoi dès l'affichage.
- Les vignettes de la galerie étaient des liens sans nom accessible — axe-core l'a signalé. Chaque lien porte maintenant le nom de son moment : décrire la photo demanderait de la regarder, ce que personne ne fait ici.

### Décisions de produit prises en passant

- **Le stockage est une interface**, comme le transport e-mail : une mise en œuvre par fichiers aujourd'hui (le VPS de la section 0 bis), et une trentaine de lignes à écrire le jour où le projet Supabase existe.
- **HEIC : aucun décodeur embarqué.** Safari sur iPhone sait le décoder, donc la conversion en JPEG a lieu là où le HEIC est produit. Ailleurs, le serveur refuse avec une explication. Embarquer 400 Ko de WebAssembly pour un cas qui se règle tout seul serait un mauvais marché.
- **La recherche du plan de table se fait côté serveur**, deux lettres minimum, vingt résultats au plus. La recherche de la FAQ tourne dans le téléphone, mais envoyer la liste des invités à quiconque détient une invitation reviendrait à publier le carnet d'adresses du mariage. Le repli hors ligne est le papier : les cartes de table portent le plan.
- **Un « [À COMPLÉTER] » n'est jamais imprimé.** Les imprimables omettent le Wi-Fi ou le contact qui ne sont pas encore écrits, plutôt que d'imprimer la mention.
- **Le repli sans accents est écrit à la main** en SQL, sans l'extension `unaccent` et sans dépendre d'une collation : majuscules accentuées comprises.

### Mesures

274 tests, 151 parcours sur deux gabarits, dix-sept écrans audités par axe-core sans anomalie, Lighthouse au-dessus du seuil.

### Ce qui reste de V3

Les défis photo (bonus §0 bis, « si le temps le permet ») et le lien privé de diffusion, dont l'emplacement est déjà livré en V2 : il attend l'adresse, pas du code.

## V3 — Le jour J — 18 septembre 2026 — première tranche

Tout ce qui rend la journée lisible sans que les mariés touchent à quoi que ce soit.

### Livré

- **« Maintenant »** (§8.6) : le jour J, l'accueil bascule. En grand le moment en cours, son genre et son heure de fin ; en dessous le moment suivant avec un compte à rebours discret ; puis les raccourcis. La date du mariage disparaît de l'en-tête — ce jour-là, elle ne renseigne plus personne.
- **Cérémonie débranchée** (§8.6) : pendant L'Horizon, l'écran demande de ranger son téléphone et l'envoi de souvenirs est suspendu. La coupure **se lève toute seule** à la fin du moment, sans geste de personne. C'est un réglage des mariés, activé par défaut, désactivable depuis l'admin.
- **Semaine J** (§8.5) : la checklist sereine en six points, et la météo du jour via Open-Meteo — gratuit, sans compte, sans clé.
- **Aide** (§8.6, §0 bis) : deux boutons d'appel (l'équipe du jour, un témoin), l'adresse et les trois itinéraires, le Wi-Fi invités. Consultable **sans réseau** : c'est la page dont on a le plus besoin quand le réseau manque.
- **Régie** (§9) : un écran séparé, accessible aux rôles `admin` et `regie`. Publier une annonce depuis quatre modèles pré-écrits ou en texte libre ; décaler un moment **et tous ceux qui le suivent** ; suspendre ou rouvrir les envois. Rien d'autre.
- **Contacts éditables** : l'admin gagne un onglet « Les contacts », et le compteur « à compléter » les prend en compte.

### Décisions de produit prises en passant

- **Un modèle d'annonce est désigné par sa clé, pas par son texte** : la route retrouve alors les deux langues dans les dictionnaires, et un invité anglophone reçoit une vraie traduction. Une annonce **libre**, elle, part telle quelle dans les deux langues — traduire à la volée un soir de fête n'est pas réaliste, et l'écran le dit avant d'envoyer.
- **La checklist de la semaine J ne quitte pas le téléphone.** Savoir si un invité a préparé sa tenue n'intéresse personne d'autre que lui : l'envoyer au serveur serait une donnée personnelle collectée sans raison (§11). Un parcours vérifie qu'aucune table ne porte de colonne de checklist.
- **Un contact sans numéro n'affiche pas de bouton d'appel.** Un bouton qui ne compose rien serait pire que pas de bouton du tout. Un numéro qui ne se compose pas est refusé par le serveur.
- **Le pas de décalage est partagé par tous les moments.** La première version offrait six boutons par moment, soit trente à l'écran : ce n'est pas « utilisable d'une main » (§9). Trois choix de pas, puis deux boutons par moment — l'écran passe de 3 500 à 2 300 px.
- **Décaler un moment entraîne les suivants.** Retarder le dîner de vingt minutes retarde la fête d'autant ; décaler un seul moment produirait des horaires qui se chevauchent. Un bouton remet tout comme prévu.
- **Ce que le brief coupe n'est pas construit** (§0 bis) : ni « Je suis en retard », ni objets perdus. La régie s'appelle, elle ne se notifie pas.
- **La météo échoue en silence.** Coordonnées inconnues (question V1-07), fenêtre de prévision dépassée, réseau coupé : l'écran dit simplement que la météo viendra. Un écran de mariage ne tombe pas parce qu'un service tiers tousse.

### Mesures

232 tests, 108 parcours sur deux gabarits, Lighthouse au-dessus du seuil. Treize écrans d'admin et de régie audités par axe-core, zéro anomalie.

### Ce qui reste de V3

Photos et vidéos, mur `/live`, plan de table, cartes de table et fiche régie PDF, lien privé de diffusion. La modération des photos rejoindra l'écran régie avec elles.

## Contenus éditables — 18 septembre 2026

Jusqu'ici, tout était en base et éditable — à condition d'écrire du SQL. C'est ce qui bloquait le remplissage de chaque « [À COMPLÉTER] ». Cet écran le débloque.

### Livré

- **`/admin/contenus`**, cinq familles de contenu : la journée (date limite de réponse), les cinq moments (horaires, lieu, ambiance, déroulé), les neuf blocs d'Infos, les dix-huit questions de la FAQ, les hébergements. Les noms et les genres des moments ne sont **pas** éditables : ils viennent de la direction artistique du brief §5, pas d'un formulaire.
- **Un compteur « à compléter »** en tête d'écran, et l'état de chaque élément dans sa liste : les mariés voient d'un coup d'œil ce qui reste à écrire avant le faire-part.
- **Liste d'abord, formulaire ensuite.** La première version empilait les dix-huit formulaires de la FAQ : un écran de 17 600 px, impraticable au téléphone. On choisit maintenant dans une liste, puis on écrit. La FAQ tient en 2 800 px.
- **Un formulaire n'écrit qu'un élément.** Une saisie au téléphone, dans le train, ne peut pas écraser ce qui vient d'être écrit ailleurs.
- **Les deux langues d'un seul geste** pour les blocs et la FAQ : laisser une langue en arrière produirait une invitation à moitié traduite, ce que le brief §13 interdit.
- **Journal d'audit** sur chaque écriture — l'action et sa cible, jamais l'adresse de l'éditeur. Purgé au bout de trente jours comme le reste.

### Décisions de produit prises en passant

- **Un champ vidé revient à `null`, jamais à la chaîne vide.** C'est ce qui permet à l'écran invité de dire « Horaire à confirmer » au lieu d'afficher un trou.
- **Une fin d'horaire antérieure au début compte pour le lendemain** : « La Nuit » finit à 03:00, pas la veille du mariage. Sans ce calcul, le fichier d'agenda exporté serait absurde.
- **Un lien qui n'est pas `http` ou `https` est refusé par le serveur**, pas seulement par le navigateur : un `javascript:` collé par erreur finirait dans un `href` vu par tous les invités. Le refus est testé en contournant exprès la validation du navigateur.
- **Le sélecteur de date suit la langue du téléphone**, pas celle de la page : l'écran redit donc la date enregistrée en clair, pour qu'un 15/04 ne soit jamais lu comme un 4 avril.
- **Les cases à cocher passent de 13 à 24 px** et leur étiquette entière reste la cible : le carré par défaut était difficile à viser et trop discret au réglage « très grande ».

### Mesures

203 tests (dont 24 sur cet écran), 86 parcours sur deux gabarits, Lighthouse toujours au-dessus du seuil. L'espace des mariés est désormais **audité par axe-core lui aussi**, sur onze écrans : zéro anomalie, et chaque cible tactile mesurée à 48 px au minimum.

### Ce que cela débloque

La question V1-02 (date limite de réponse) et tous les contenus des questions V1-06 à V1-08 ne demandent plus de code : ce sont des textes à écrire depuis le téléphone.

## V2 — La préparation — 17 septembre 2026 — complète côté code

### Seconde tranche

- **Fil d'annonces** : une page `/annonces` pour les invités, la dernière annonce mise en avant sur l'accueil, et un écran de publication pour les mariés (français et anglais). Aucune donnée personnelle n'y entre : le fil est donc lisible depuis le QR générique.
- **Notifications Web Push**, sans aucun prestataire : le serveur parle directement au service de notification du navigateur, authentifié par une paire de clés VAPID qu'on génère soi-même (`pnpm push:cles`). L'autorisation n'est **jamais** demandée au premier chargement (§17) : elle l'est au clic, et un refus est accepté sans insister. Publier une annonce peut envoyer une notification, ou non — c'est une case à cocher, pas un automatisme.
- **Rappels par e-mail**, en opt-in explicite : l'adresse est demandée dans la réponse, jamais ailleurs ; chaque e-mail porte un lien de désinscription qui fonctionne **en un tap**, sans connexion ni question, et le message est le même que le lien soit valide ou déjà utilisé — inutile d'apprendre à un curieux si une adresse était inscrite.
- **File d'envoi des e-mails** : le prestataire n'étant pas choisi (question V1-03), les e-mails sont écrits dans une file en base et un transport les en sort. Le transport « console » les affiche sans les envoyer : on peut relire exactement ce qui partirait. Le jour où le prestataire est choisi, il y a **une fonction à écrire** dans `lib/email.ts` et rien d'autre à toucher.

### Décisions de produit prises en passant

- Les rappels e-mail ne sont **pas proposés** à un foyer qui a répondu « Non » : lui envoyer des rappels serait au mieux inutile. Recevoir les photos après le mariage viendra avec la version « Après », avec son propre consentement.
- Un abonnement aux notifications déclaré périmé par le navigateur est **supprimé**, pas réessayé : sans cela la liste ne ferait que grossir et chaque envoi ralentirait. Un test le vérifie.

### Mesures

174 tests, 66 parcours sur deux gabarits, Lighthouse toujours au-dessus du seuil.

### Ce qui reste de V2

Le contenu des rappels (question V2-01) et le transport e-mail (V1-03). Les deux sont des décisions, pas du code.

## V2 — Première tranche — 17 septembre 2026

Ce qui ne dépend de personne.

### Livré

- **« Le texte »** : le palindrome du faire-part, quatorze lignes qui s'allument l'une après l'autre comme dans le film. « Sauf que… » les rallume en sens inverse. Aucune explication — c'est le propre du texte. Le changement de sens est annoncé aux lecteurs d'écran par une région vivante, sans que le nom de la liste bouge.
- **« La promesse »** : un vœu écrit par l'invité, **chiffré dans son téléphone** avant d'être envoyé. Le serveur ne reçoit qu'une enveloppe close et n'a aucun moyen de l'ouvrir : c'est ce qui rend vraie la phrase du brief, « invisibles de tous, y compris des mariés ». Schéma hybride avec WebCrypto seul, sans dépendance : une clé AES-256-GCM par vœu, elle-même chiffrée en RSA-OAEP-2048. Le vœu est **anonyme** : la table ne porte aucune colonne de foyer, donc même avec l'accès à la base on ne peut pas deviner qui a écrit quoi. Aucun compteur de participation (§17).
- **Deux outils en ligne de commande** : `pnpm promesse:cles` produit la paire (clé publique pour l'environnement, clé privée à imprimer en deux exemplaires et à confier à deux personnes), et `pnpm promesse:ouvrir` déchiffre les vœux — en refusant de le faire avant le 3 juin 2029.
- **« Ceux qui sont loin »** : un message écrit aux mariés, privé par défaut, ou pour le livre d'or si l'invité le choisit. Emplacement du lien de diffusion, visible seulement depuis une invitation reconnue. Proposé aussi au bout du parcours « Non ».
- **Hébergements** : la liste éditable s'affiche dans Infos (distance, prix indicatif, navette, téléphone, lien de réservation) ; tant qu'elle est vide, la section le dit.

### Mesures

160 tests, 62 parcours sur deux gabarits. Six tests portent sur le seul point qui compte pour La promesse : un vœu scellé ne contient aucun mot du texte, ne s'ouvre pas avec une autre clé, et refuse une enveloppe modifiée d'un seul octet.

### Ce qui attend une décision

`pnpm promesse:cles` est prêt, mais **la garde de la clé privée est une décision, pas du code** (question V2-05) : sans elle, les vœux de 2029 resteront fermés pour toujours. Deux exemplaires papier, deux personnes différentes — à valider.

## V1 — Hors ligne — 17 septembre 2026

« Tout fonctionne mal connecté » est la règle 4 du brief, et le domaine est à la campagne.

### Livré

- **Service worker** (Serwist) : le programme, les infos et la FAQ restent consultables sans réseau une fois ouverts, la recherche de la FAQ comprise — elle se fait dans le téléphone.
- **Écran « Pas de réseau pour l'instant »**, précaché à l'installation, bilingue et sans aucune donnée personnelle : c'est la condition pour qu'il ait le droit de vivre dans un cache.
- **File d'attente persistante** (IndexedDB) pour les réponses : une réponse donnée sans réseau est gardée, annoncée sobrement à l'écran, et repart d'elle-même au retour du réseau. Sans JavaScript, le formulaire part normalement — cette couche n'enlève rien, elle ajoute.
- **Manifeste** de l'application : l'icône et les couleurs sont correctes pour qui ajoute l'app à son écran d'accueil, sans que rien ne le propose jamais.

### Deux failles réelles trouvées et refermées

- **Le cache par défaut conservait les charges RSC de l'accueil et de la réponse** — donc le nom du foyer et sa réponse — sur le disque du téléphone. Un téléphone prêté ou perdu les rendait lisibles. Désormais, **seules les navigations vers les trois pages de contenu** entrent en cache ; tout le reste du domaine passe par le réseau sans laisser de trace, et un test vérifie qu'aucun cache ne contient `/`, `/reponse` ni `/partager`.
- **Le même cache accumulait les préchargements RSC** (`?_rsc=<jeton>`, un jeton différent à chaque chargement) : le cache grossissait sans fin sur le téléphone de l'invité. Les charges RSC n'y entrent plus.

### Deux défauts d'outillage, corrigés à la racine

- La sortie `standalone` de Next ne contient ni `public/` ni `.next/static` : le serveur compilé servait des pages **sans style ni JavaScript**, ce qui faisait échouer les 54 parcours d'un coup sans en dire la cause. Un `postbuild` les copie maintenant à chaque compilation.
- Un serveur orphelin laissé par une exécution interrompue faisait échouer les parcours **et** la mesure Lighthouse (toutes les notes à zéro, message trompeur). La libération du port est partagée par les deux outils.

### Une méthode de test rectifiée

`context.setOffline(true)` met bien `navigator.onLine` à faux, mais **Chromium continue de joindre 127.0.0.1** : des tests hors ligne bâtis dessus passaient sans rien vérifier. Les parcours hors ligne démarrent donc leur propre serveur et **le coupent** — ce qui reproduit ce que vit l'invité : le téléphone se croit connecté, et plus rien ne répond. La file d'attente a été revue en conséquence : elle rattrape aussi bien la coupure du réseau que le serveur injoignable, cas que l'indicateur du navigateur ne signale pas.

### Mesures après ce changement

Lighthouse mobile : Performance 95 à 98, Accessibilité 100, Bonnes pratiques 100. 149 tests, 54 parcours sur deux gabarits.

## V1 — Qualité mesurée — 17 septembre 2026

Les deux critères de fin de V1 que je peux vérifier moi-même sont atteints.

### Mesures

- **Lighthouse mobile** sur l'application compilée (accueil, programme, FAQ) : Performance **99**, Accessibilité **100**, Bonnes pratiques **100**. Seuil vérifié en intégration continue (`pnpm lighthouse`).
- **Accessibilité** : axe-core sur les sept écrans d'invité, étiquettes WCAG 2.0, 2.1 et 2.2 niveaux A et AA — **zéro anomalie**. Plus une mesure de la taille réelle de chaque cible (≥ 48 px, contre 24 px exigés) et un parcours au clavier seul.

### Trois défauts trouvés par ces mesures, corrigés

- **Les polices n'étaient pas préchargées** : le LCP de l'accueil était de 3,1 s, sur la date en Bodoni. Les fichiers sont désormais dans le dépôt (`assets/polices/`, sous-ensembles latins, 148 ko au total) et chargés par `next/font/local` : Next émet le préchargement, la performance passe de 94 à 99, et la compilation ne dépend plus du réseau — ce qui compte pour l'intégration continue et pour le gel de J-7 à J+1.
- **Une icône manquante** provoquait un 404 en console (bonnes pratiques 96). L'icône est maintenant générée depuis les tracés du monogramme, comme le reste, et le manifeste de l'application est en place — sans jamais proposer l'installation, qui reste facultative.
- **La barre d'onglets pouvait masquer la fin d'une page** : le gabarit réserve sa hauteur.

### Une contradiction du brief, tranchée

Le §12 demande Lighthouse ≥ 95 dans les quatre catégories, dont « SEO ». Le §11 interdit d'indexer les données des invités : l'application est en `noindex`, donc l'audit « page indexable » échoue et la catégorie plafonne à 60. C'est la confidentialité qui gagne. Le seuil est vérifié sur les trois autres catégories, et cet audit est explicitement exclu — pas ignoré en silence.

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

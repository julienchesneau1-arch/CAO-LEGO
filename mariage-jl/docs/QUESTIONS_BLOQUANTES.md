# Questions bloquantes — classées par version, V0/V1 d'abord

Règle : aucune valeur n'est devinée. Tant qu'une question marquée **bloquante** est ouverte, le travail qui en dépend n'est pas commencé. Les questions « non bloquante » n'empêchent pas d'avancer : le contenu reste `[À COMPLÉTER]` et éditable dans l'admin.

---

## V0 — Fondations (bloque tout le reste)

| # | Question | Ce qu'elle bloque | Réponse attendue |
|---|---|---|---|
| V0-01 | ~~**Où vit le code ?**~~ | — | **Répondu le 17/09/2026 : dépôt dédié `mariage-jl`.** Reste à le créer sur GitHub : l'App n'a pas le droit de créer un dépôt (403) |
| V0-02 | **Nom de domaine exact à acheter** (il sera imprimé sur le faire-part et ne changera jamais) | Achat du domaine, page de secours, QR, HTTPS | `exemple.fr` |
| V0-03 | ~~**Hébergeur statique de la page de secours**~~ | — | **Répondu le 17/09/2026 : GitHub Pages.** Workflow livré ; à activer une fois dans `Settings → Pages → Source : GitHub Actions` |
| V0-04 | ~~**Version de Next.js**~~ | — | **Répondu le 17/09/2026 : dernière stable vérifiée.** Épinglé : Next 16.3.5, React 19.3.0, Tailwind 4.3.3 |
| V0-05 | **Accès VPS pour l'audit en lecture seule** : hôte, port SSH, nom d'utilisateur, clé publique à autoriser | `INFRA.md`, donc tout le déploiement | accès SSH ou séance partagée |
| V0-06 | **Compte Supabase** : organisation existante ou à créer, et **région européenne** retenue (par exemple Paris ou Francfort) | Création du projet, schéma, RLS | un choix |
| V0-07 | **Registre d'images privé** : GitHub Container Registry du dépôt, ou autre | Chaîne CI/CD, déploiement | un choix |
| V0-08 | **Références couleur définitives** : les 7 hex du brief sont relevés sur une maquette écran. Les valeurs de l'imprimeur sont-elles disponibles, ou travaille-t-on avec ces hex en attendant ? | Jetons de direction artistique, page `/design`, imprimables | 7 valeurs ou « on garde les hex » |
| V0-09 | **Film d'annonce** : où récupérer `JL_annonce_1080p_version_texte.mp4` et son image d'affiche (première frame noire au monogramme) ? | Accueil V1, page `/design` | fichier + affiche |
| V0-10 | **Monogramme définitif** : le faire-part et le film ont-ils un monogramme déjà vectorisé (SVG, AI, PDF) ? Si oui, il remplace le tracé généré et devient la référence unique | Monogramme, imprimables, page de secours | fichier ou « non » |
| V0-11 | **Graisse du monogramme** : les tracés générés sont en wght 400, le brief demande ≈ 470 (l'API Google Fonts ne sert pas l'instance 470 en fichier statique). On garde 400, ou tu fournis l'instance 470 exportée depuis un logiciel de dessin ? Comparaison visible sur `/design` | Monogramme | un choix |

---

## V1 — Le socle, avant le faire-part

| # | Question | Ce qu'elle bloque | Statut |
|---|---|---|---|
| V1-01 | **Date d'envoi du faire-part** | Toutes les échéances du calendrier, la date butoir de V1 | bloquante |
| V1-02 | **Date limite de réponse** | Carte « À faire », verrouillage du RSVP, rappels | bloquante |
| V1-03 | **Prestataire e-mail transactionnel européen** (offre gratuite) + accès à la zone DNS pour SPF, DKIM, DMARC. *Nécessaire dès V1 : l'accès admin se fait par lien magique par e-mail* | Accès admin, donc l'admin invités et la planche QR | bloquante |
| V1-04 | **Adresses e-mail de la liste blanche admin** (Julien, Lauriane) | Accès admin | bloquante |
| V1-05 | **Liste des foyers** : prénoms par foyer et composition. Fichier existant à importer, ou saisie dans l'admin ? | Planche QR PDF, donc l'impression du faire-part | bloquante |
| V1-06 | **Horaires des 5 moments** (début et fin) et **lieu de chacun dans le domaine** | Programme, `.ics`, cartes de table | non bloquante (éditable, mais requise avant impression) |
| V1-07 | **Adresse complète, coordonnées GPS, accès PMR** du Domaine de Roiffé | Infos « Venir », Accessibilité | non bloquante |
| V1-08 | **Options de menu** et régimes proposés | Étape 3 du RSVP, export traiteur | non bloquante (mais requise avant ouverture des réponses) |
| V1-09 | **Tenue** souhaitée, formulée par vous | Infos « Tenue » | non bloquante |
| V1-10 | **Hébergements** : liste, distances, prix indicatifs, liens, téléphones, navette ou non | Infos « Dormir » | non bloquante |
| V1-11 | **Liste de mariage** : lien externe | Infos | non bloquante |
| V1-12 | **Contact accessibilité** (nom + moyen de contact) | Infos « Accessibilité » | non bloquante |
| V1-13 | **Avec des enfants** : menu enfant, espace calme, garde éventuelle | Infos « Enfants » | non bloquante |
| V1-14 | **Rentrer en sécurité** : dernières navettes, numéros de taxi locaux | Infos | non bloquante |
| V1-15 | **Les deux relecteurs** du parcours complet (un invité de plus de 75 ans, un invité qui déteste les applications) | Critère de fin de V1 | bloquante pour clore V1 |
| V1-16 | **Phrase d'ambiance** pour chacun des 5 moments | Cartes du programme | non bloquante |
| V1-17 | Le partage d'accès au foyer : **durée de validité et nombre d'ouvertures** du lien ? (proposition : 30 jours, 5 ouvertures) | Règles du partage d'accès | non bloquante |

---

## V2 — La préparation

| # | Question | Ce qu'elle bloque |
|---|---|---|
| V2-01 | Textes des rappels e-mail (contenu, nombre, dates d'envoi) | Rappels |
| V2-02 | Lien du **groupe de discussion covoiturage** géré par les mariés | Paragraphe Infos |
| V2-03 | Messages des absents : visibilité par défaut, livre d'or public aux invités ou privé aux mariés ? | Écran « Ceux qui sont loin » |
| V2-04 | Clés VAPID : générées par moi et conservées où ? | Web Push |
| V2-05 | **La promesse** : validez-vous le chiffrement côté navigateur avec clé privée imprimée et confiée à deux personnes distinctes ? Sans cela, « invisible y compris des mariés » est faux | La promesse |
| V2-06 | **L'application reste-t-elle en ligne jusqu'au 4 juin 2029** pour La promesse, ou les vœux sont-ils exportés et envoyés automatiquement puis l'app éteinte ? | Coût d'hébergement, plan de rétention |

---

## V3 — Le jour J

| # | Question | Ce qu'elle bloque |
|---|---|---|
| V3-01 | **Régie** : une personne + une suppléante (nom, e-mail, téléphone) | Rôle régie, fiche régie PDF |
| V3-02 | **Référent technique** du jour J, distinct de la régie (nom, e-mail, téléphone) | Fiche de dépannage, procédure de bascule |
| V3-03 | **Témoin(s) joignables** : quel numéro derrière le bouton « Appeler un témoin » ? | Page Aide |
| V3-04 | **Plateforme de diffusion** retenue et qui filme ; le lien privé est-il connu à l'avance ou saisi le jour J dans l'admin ? | Écran « Ceux qui sont loin » |
| V3-05 | **Wi-Fi invités** : existe-t-il ? nom et mot de passe ? | Cartes de table, FAQ |
| V3-06 | **Plan B pluie** | Infos, FAQ |
| V3-07 | **Plan de table** : source des tables et des places (fichier, ou construction dans l'admin) | Ma table, cartes de table |
| V3-08 | **Modération des médias** : publication immédiate ou validation préalable ? | Galerie, charge de la régie |
| V3-09 | Tri « photos appréciées » : conservé sous forme de signal privé sans compteur visible, ou supprimé pour respecter §17 ? | Galerie |
| V3-10 | **Défis photo** : intitulés, ou renoncement ? | Défis |
| V3-11 | **Cérémonie débranchée** : plage exacte de mise en pause des envois | Jour J |
| V3-12 | Visite du domaine pour le **test de couverture réseau** : date possible ? | Plan B, Wi-Fi |

---

## V4 — Après

| # | Question | Ce qu'elle bloque |
|---|---|---|
| V4-01 | Message de remerciement des mariés | Écran Merci |
| V4-02 | **Photographe** : format de livraison, volume attendu, date | « Le regard du photographe », archives |
| V4-03 | **Destination de la sauvegarde externe** (hors Hostinger, hors Supabase) | Sauvegardes, archives ZIP |
| V4-04 | Date de fin d'accès annoncée aux invités | Écran Merci, page Confidentialité |

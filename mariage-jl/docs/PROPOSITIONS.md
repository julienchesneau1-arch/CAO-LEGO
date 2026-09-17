# Propositions — section 18, points 2 et 3

Rien de ce qui suit n'est développé sans votre accord (§17 : aucune fonctionnalité non prévue sans vous la proposer).

---

## A. Trois micro-interactions signature, dans la direction artistique

Contraintes respectées : fondus et glissements ≤ 12 px, `cubic-bezier(0.22, 1, 0.36, 1)`, 300 à 900 ms, aucun confetti, aucun emoji, aucun son, `prefers-reduced-motion` → simple fondu, les 5 couleurs restent des fils et jamais du texte.

### A1. Le sceau qui se ferme sous le doigt — écran La promesse (V2)

Sceller un vœu ne se fait pas d'un tap mais d'un **appui maintenu de 900 ms**. Pendant l'appui, le sceau au monogramme s'enfonce et la cire s'étale en un tracé circulaire ; relâcher avant la fin rouvre l'enveloppe, sans message d'erreur. Le geste dure exactement le temps d'un vrai cachet de cire, et rend un scellement accidentel impossible.
- Repli mouvement réduit : bouton « Sceller » classique, fondu de 200 ms.
- Accessibilité : alternative clavier (Entrée maintenue) et bouton explicite pour lecteur d'écran ; libellé annonçant que l'action est définitive.
- Coût : une animation SVG, aucune dépendance.

### A2. Le pouls du moment — écran Maintenant (V3)

Sous le nom du moment en cours, un filet de 2 px dans sa couleur, dont la **longueur est la part du moment déjà écoulée**. Il progresse d'un cran à chaque minute, par un glissement de 300 ms. Aucun chiffre, aucun compte à rebours agressif : on lit d'un coup d'œil « c'est le début » ou « ça se termine ». Un tap révèle l'heure de fin en clair.
- Si la régie décale un moment, le filet se rétracte puis repart : le décalage devient perceptible sans notification.
- Repli mouvement réduit : le filet se redessine sans transition.
- Accessibilité : `aria-label` textuel (« La Rencontre, environ 40 minutes restantes »), jamais la seule couleur pour porter l'information.

### A3. L'encre qui sèche — confirmations (V1, réutilisée partout)

Toute confirmation — réponse envoyée, souvenir parti, hébergement noté — s'affiche en une ligne de texte ivoire, **soulignée par un filet de 1 px qui se trace de gauche à droite en 600 ms**, puis s'immobilise et s'estompe à 12 %. Pas de coche verte, pas de rebond, pas de bandeau : la trace reste, comme une signature qui sèche. La couleur du filet est celle du moment concerné, ou La Matière (`#99836F`) hors contexte.
- Repli mouvement réduit : le filet apparaît directement.
- Accessibilité : la confirmation est aussi annoncée par une région `aria-live="polite"`.
- Coût : un composant `<Confirmation />` unique, réutilisé par tous les formulaires.

---

## B. Trois idées pour mettre les invités plus à l'aise, absentes du document

### B1. « Votre journée en une page » — fiche A5 personnalisée, imprimable et hors ligne (proposition pour V3)

Chaque foyer peut télécharger, depuis son invitation, un PDF A5 dans la direction artistique, en mode Papier : prénoms du foyer, heure d'arrivée, les 5 moments avec horaires et lieux, numéro de table, menu retenu, adresse et plan d'accès, numéro du témoin, nom du Wi-Fi. Une page, à imprimer ou à garder en pellicule photo.
- Pourquoi : c'est la réponse à Jeanne (84 ans), à Thomas (déteste les applications), à la batterie vide à 23 h et à l'absence de réseau. Les trois problèmes se règlent avec un objet, pas avec une fonctionnalité.
- Coût : faible. La chaîne PDF existe déjà pour la planche QR, les cartes de table et la fiche régie ; c'est un quatrième modèle qui réutilise les mêmes données.

### B2. « Préférez-vous qu'on vous appelle ? » (proposition pour V1)

Sur l'écran de réponse et sur la FAQ, un lien discret : l'invité laisse son prénom et son numéro, sans rien d'autre, et apparaît dans une liste « À rappeler » de l'admin. Aucune obligation de répondre dans l'app, aucune délégation à demander à un proche, aucun aveu d'échec.
- Pourquoi : aujourd'hui, un invité qui ne s'en sort pas n'a que deux issues — abandonner, ou déranger quelqu'un. Cette porte de sortie est ce qui fait tomber les derniers foyers sans réponse, et elle sert directement l'indicateur « réponses reçues ≥ 85 % ».
- Coût : très faible. Un champ, une table, une liste dans l'admin. Numéro supprimé dès le rappel effectué, et au plus tard à J+3 mois.

### B3. « Ce que vous recevrez » — engagement de sobriété affiché avant tout opt-in (proposition pour V2)

Avant la case « Recevoir les rappels », une phrase chiffrée et vraie : « Trois e-mails au maximum : à la réception de votre réponse, une semaine avant, et le lendemain du mariage. Aucun autre message. Se désinscrire prend un tap. » Le compteur réel d'envois est visible dans l'admin, et l'engagement est repris dans la page Confidentialité.
- Pourquoi : la première peur devant un opt-in n'est pas la donnée, c'est le harcèlement. Dire le nombre exact à l'avance transforme le refus réflexe en acceptation. C'est aussi ce qui rend le canal e-mail crédible une fois le SMS coupé.
- Coût : quasi nul, et cela nous engage à ne pas dépasser trois envois.

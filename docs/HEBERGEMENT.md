# Héberger l'atelier

Ce document est destiné à qui **installe** l'atelier sur un serveur, pas à qui
s'en sert. Il dit ce qu'il faut, ce que ça coûte, et — c'est le plus important
— ce que ce montage **ne fait pas**.

---

## 1. Ce qu'une seule requête peut coûter

Tout part de là. Avant de choisir un hébergeur, il fallait mesurer le pire cas
qu'un visiteur peut imposer. Chaîne complète, photo 512 × 512, temps
processeur et pointe de mémoire du processus :

| Mosaïque | Tenons | Calcul | Mémoire | Fichiers |
|---:|---:|---:|---:|---:|
| 32 × 32 | 1 024 | 0,6 s | 31 Mo | 0,8 Mo |
| 64 × 64 | 4 096 | 2,2 s | 50 Mo | 2,7 Mo |
| 96 × 96 | 9 216 | 4,2 s | 85 Mo | 5,8 Mo |
| 128 × 128 | 16 384 | 8,5 s | 126 Mo | 9,4 Mo |
| 200 × 200 | 40 000 | 20,3 s | 254 Mo | 19,9 Mo |
| **500 × 500** | **250 000** | **260,7 s** | **2 315 Mo** | **104,2 Mo** |

La dernière ligne a été **mesurée**, pas déduite : une droite ajustée sur les
cinq premières annonce 135 s et 1,6 Go. Le coût est linéaire *plus quelque
chose*, et ce quelque chose se paie là où il reste le moins de marge. C'est
pour cette raison que les pentes employées par `bfk001/heberge.py` sont celles
du **haut** du tableau et non la moyenne : un plafond calculé trop large ne
donne pas une erreur, il donne un processus tué en plein calcul.

### Mémoire et temps ne se transposent pas de la même façon

Le tableau refait sur une seconde machine du même environnement a rendu la
colonne mémoire **à l'octet près** — 135 Mo, 217 Mo, identiques — et la colonne
temps **multipliée par 1,8**. La mémoire est une propriété du logiciel ; la
vitesse est une propriété de la machine.

L'atelier hébergé s'**étalonne donc au démarrage** : il fabrique une mosaïque
de 32 × 32, la chronomètre, et applique à cette mesure le rapport entre le
régime de l'étalon et celui du plafond — rapport qui, lui, est bien une
propriété du logiciel et a été mesuré une fois. Coût : environ deux secondes,
une fois, imprimées au démarrage :

```
vitesse  : 2.51 ms/tenon, mesure ici en 1.9 s (1.57 x la machine de reference)
plafond  : 23942 tenons (~154 x 154) — le temps de reponse borne, 23942 contre 77706
```

`BFK_CPU_PAR_TENON` court-circuite l'étalonnage si vous préférez poser la
valeur vous-même.

### Conséquence n° 1 — pas de sans-serveur

Aucune fonction hébergée ne tient quatre minutes et demie de calcul ni deux
giga-octets et demi de mémoire. Ce n'est pas une préférence d'architecture,
c'est la mesure. **Il faut un conteneur.**

### Conséquence n° 2 — le plafond se recalcule

Le plafond du noyau (250 000 tenons) dit ce que la chaîne tient sur une machine
de développement. Hébergé, il est recalculé sur deux bornes, et c'est la plus
basse qui s'applique :

| Mémoire du conteneur | Borne mémoire | Borne durée¹ | Plafond appliqué |
|---:|---:|---:|---:|
| 512 Mo | 17 367 | 57 142 | **17 367** (~131 × 131) |
| 1 Go | 46 202 | 57 142 | **46 202** (~214 × 214) |
| 2 Go | 103 874 | 57 142 | **57 142** (~239 × 239) |
| 4 Go | 219 217 | 57 142 | **57 142** (~239 × 239) |

¹ à la vitesse de la machine de référence. Sur une machine deux fois plus
lente, la borne de durée tombe vers 20 000 et devient contraignante dès 1 Go —
c'est l'étalonnage du démarrage qui le dit, pas ce tableau, et il l'a déjà dit :
la même machine s'est mesurée à 1,57× puis à 0,89× de la référence à quelques
heures d'intervalle.

Sous un giga-octet, c'est la mémoire qui mord ; au-dessus, c'est le temps de
réponse. Même le plus petit des quatre — 131 tenons de côté — reste **sept fois la
surface d'un set LEGO Art officiel** (48 × 48). Le plafond n'est pas une limite de qualité.

La mémoire est lue dans le **cgroup**, pas dans `/proc/meminfo` : dans un
conteneur, le second parle de la machine entière, et le croire ne produit pas
une erreur lisible mais un processus tué sans message.

### Conséquence n° 3 — une fabrication à la fois

| En parallèle | Durée de chacune | Débit total |
|---:|---:|---:|
| 1 | 8,3 s | 0,120 mosaïque/s |
| 2 | 17,8 s | 0,112 mosaïque/s |
| 4 | 37,2 s | 0,107 mosaïque/s |

Le débit **baisse**. La chaîne est du Python pur : le verrou global la
sérialise. Une deuxième place tiendrait deux pointes de mémoire en même temps
pour rendre les deux réponses deux fois plus tard. Le second visiteur reçoit
donc un **503 immédiat** (mesuré : 0,1 s) avec un `Retry-After`, plutôt qu'une
attente muette d'une minute.

---

## 2. Répétition générale, sur votre machine

```bash
docker build -t brickforge .

docker run --rm -p 8000:8000 --memory 1g \
  -e BFK_CLE="$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')" \
  -e BFK_SANS_TLS=1 \
  brickforge
```

Le démarrage imprime le plafond calculé et le lien à suivre. Remplacez
`VOTRE-DOMAINE` par `127.0.0.1:8000` pour l'essai local.

`--memory 1g` n'est pas décoratif : **c'est lui que le lanceur lit** pour
calculer ce qu'il accepte de fabriquer. Sans limite posée, il lit la mémoire de
la machine entière et autorise des mosaïques que le conteneur ne tiendra pas.

`BFK_SANS_TLS=1` retire `Secure` du témoin, faute de quoi le navigateur le
refuse en HTTP simple. **À ne jamais poser sur l'Internet.**

Sans conteneur, directement :

```bash
BFK_CLE="…" BFK_SANS_TLS=1 BFK_MEMOIRE_MO=1024 python3 heberger_lego_art.py
```

---

## 3. Chez un hébergeur de conteneurs

Ce qu'il faut demander à la plateforme, quelle qu'elle soit :

| Réglage | Valeur | Pourquoi |
|---|---|---|
| Mémoire | **1 Go au moins** | En dessous, le lanceur refuse de démarrer plutôt que de servir un atelier qui refuse tout. 512 Mo donnent 131 tenons de côté, 1 Go en donnent 214. Le budget compte les caches de couleur **une fois chauds** (mesure : 16 Mo au démarrage, 61 Mo après vingt-quatre fabrications) — sans quoi la quarante-cinquième mosaïque de la journée se ferait tuer sans un mot. |
| Processeur | **1 vCPU** | Au-delà, rien : la chaîne ne parallélise pas. |
| Délai de requête | **90 s au moins** | Une fabrication au plafond en prend 60. Une passerelle qui coupe à 30 s laisse le calcul continuer pour personne. |
| Instances | **exactement 1** (min = max = 1) | Voir ci-dessous — c'est la contrainte la plus facile à manquer. |
| Port | lu dans `PORT` | Le lanceur écoute sur `0.0.0.0:$PORT`. |
| HTTPS | **terminé par la plateforme** | Ce programme ne chiffre rien. |
| Sonde de santé | `GET /sante` | La page répond 401 sans la clé ; une sonde branchée dessus redémarrerait en boucle un atelier qui va très bien. |

### Ce que le serveur consomme sur la durée — mesuré

Trente fabrications successives à travers le vrai serveur HTTP, chacune pour un
visiteur différent, une session neuve tous les cinq tours :

```
RSS au démarrage :  34 Mo
après  6 fabrications :  73 Mo
après 12 fabrications :  89 Mo
après 18 fabrications :  86 Mo
après 24 fabrications :  92 Mo
après 30 fabrications :  85 Mo   (pointe 92)
```

La mémoire **oscille et ne monte pas** : les caches de couleur se vident quand
ils sont pleins, les sessions et les résultats sont bornés. C'est cette mesure,
et non un raisonnement, qui valide `MEMOIRE_DE_BASE`.

Avant correction, la même série montait sans jamais redescendre, et le cache de
conversion cessait purement et simplement de garder passé la quarante-cinquième
mosaïque — le serveur ralentissait de moitié sans qu'aucune trace ne le dise.

### Une seule instance, et c'est important

Les sessions et les résultats vivent **dans le processus**. Avec deux
instances derrière un répartiteur, le témoin posé par l'une n'est pas reconnu
par l'autre : le visiteur se retrouve devant « atelier privé » au milieu de son
travail, et le fichier qu'il télécharge tombe en 404 une fois sur deux.

Ce n'est pas un défaut caché, c'est un choix : partager cet état demanderait un
Redis ou une base, donc une dépendance, alors que ce dépôt n'en a **aucune**
hors bibliothèque standard. Pour un atelier privé partagé par lien, une
instance suffit — elle ne fabrique de toute façon qu'une mosaïque à la fois.

Si un jour il en faut plusieurs : le témoin devrait être signé (HMAC de la clé)
pour être reconnu partout, et le magasin de résultats déplacé hors du
processus. Ce sont deux chantiers distincts, pas un réglage.

### Exemple, à vérifier contre la documentation de l'hébergeur

Les options des plateformes changent plus vite que ce fichier. Le principe :

```bash
# Google Cloud Run, à titre d'illustration
gcloud run deploy brickforge \
  --source . \
  --memory 1Gi --cpu 1 --timeout 120 \
  --min-instances 1 --max-instances 1 \
  --set-env-vars "BFK_RELAIS=1" \
  --set-secrets "BFK_CLE=brickforge-cle:latest"
```

`BFK_RELAIS=1` parce qu'il y a **un** relais devant. Tant que cette variable
vaut 0, `X-Forwarded-For` n'est pas cru du tout — et c'est le bon défaut : cet
en-tête est écrit par le client autant que par les relais, et le croire sans
condition offrirait à n'importe qui une adresse neuve à chaque requête, donc un
compteur de débit remis à zéro à volonté.

---

## 4. Les variables

| Variable | Défaut | Rôle |
|---|---|---|
| `BFK_CLE` | — | **Obligatoire**, seize caractères au moins. C'est elle qui est dans le lien. |
| `PORT` | 8000 | Posé par la plupart des hébergeurs. |
| `BFK_MEMOIRE_MO` | lu dans le cgroup | Force la mémoire supposée, quand le cgroup ment ou est absent. |
| `BFK_DUREE` | 60 | Secondes qu'une fabrication a le droit de prendre. |
| `BFK_CPU_PAR_TENON` | étalonné | Secondes de calcul par tenon. Mesuré au démarrage en ~2 s si absent. |
| `BFK_SIMULTANEES` | 1 | Places de fabrication. La mesure dit 1. |
| `BFK_RELAIS` | 0 | Nombre de relais devant le serveur. |
| `BFK_SANS_TLS` | — | Témoin sans `Secure`. Essais locaux uniquement. |
| `BFK_LDCONFIG` | cherché | Palette officielle LDraw. |
| `BFK_BRICKLINK` | — | Table de couleurs BrickLink de l'installation. |
| `BFK_ELEMENTS` | — | Catalogue d'element ids de l'installation. |
| `BFK_ELEMENTS_COULEURS` | — | Sa table « id, nom », si le catalogue ne désigne ses couleurs que par un numéro. |

---

## 5. Ce qui est partagé, et ce qui ne l'est pas

| | Portée | Pourquoi |
|---|---|---|
| Palette LDraw | **installation** | C'est une donnée, pas un réglage. Hébergée, elle ne se change pas depuis la page : `POST /palette` répond 403, faute de quoi un visiteur ferait sortir une requête de votre machine et changerait la palette de tout le monde. |
| Catalogues de commande | **par visiteur** | L'exploitant fournit les siens ; un visiteur peut déposer les siens, qui ne valent que pour sa session et ne touchent pas le disque. Un catalogue partiel déposé par l'un dégraderait sinon la liste de course de l'autre, sans que personne comprenne pourquoi. |
| Résultats fabriqués | **magasin unique, borné en octets** | Les jetons sont imprévisibles, donc partager le magasin ne partage pas la lecture. Un magasin par visiteur multiplierait la borne par le nombre de visiteurs — c'est-à-dire ne bornerait plus rien. |
| Sessions | **mémoire du processus** | 64 au plus, oubliées après 4 h d'inactivité. Un redémarrage les perd toutes : le lien reste valable, il suffit de le rouvrir. |

Rien n'est écrit hors du processus. L'image tourne donc en lecture seule :

```bash
docker run --read-only --tmpfs /tmp …
```

---

## 6. Ce que ce montage ne fait pas

À lire avant d'envoyer le lien à qui que ce soit.

- **Il ne chiffre rien.** Sans HTTPS terminé par l'hébergeur, la clé passe en
  clair. Le témoin porte `Secure` par défaut, ce qui le rend inopérant en HTTP
  simple — c'est délibéré.
- **Une seule clé pour tout le monde.** Il n'y a pas de comptes. Qui a le lien
  entre ; on ne peut pas retirer l'accès à une personne sans le retirer à
  toutes (changer `BFK_CLE` invalide tous les liens d'un coup).
- **Aucune trace de qui a fabriqué quoi.** Le serveur n'écrit aucun journal
  d'accès. C'est bien pour la vie privée, moins bien le jour où l'on voudrait
  savoir ce qui s'est passé.
- **Les résultats ne survivent pas au processus.** Un redémarrage de
  l'hébergeur perd les mosaïques qui n'ont pas encore été téléchargées. Elles
  se refabriquent, mais il faut refaire l'attente.
- **Un seul visiteur occupe l'atelier pendant sa fabrication.** Les autres sont
  refusés poliment. Pour un atelier privé, c'est le bon compromis ; pour un
  service ouvert, il en faudrait un autre.
- **Les photos déposées passent par la mémoire de votre serveur.** Elles n'y
  sont pas écrites et n'en ressortent pas, mais qui héberge devient
  responsable de ce que d'autres y envoient.

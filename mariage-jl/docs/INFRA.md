# INFRA.md — audit du VPS Hostinger KVM 2 (à remplir en V0)

**État : non commencé.** Aucune commande n'a été exécutée sur le VPS : les accès ne sont pas disponibles (question V0-05). Aucune valeur de ce document ne doit être supposée.

## 1. Caractéristiques relevées dans hPanel

| Élément | Valeur |
|---|---|
| Processeur (cœurs) | [DONNÉE_MANQUANTE] |
| Mémoire | [DONNÉE_MANQUANTE] |
| Disque | [DONNÉE_MANQUANTE] |
| Bande passante | [DONNÉE_MANQUANTE] |
| Système d'exploitation | [DONNÉE_MANQUANTE] |
| Centre de données | [DONNÉE_MANQUANTE] |
| Instantanés : activés / fréquence | [DONNÉE_MANQUANTE] |
| Zone DNS du domaine | Hostinger (confirmé) — domaine [À COMPLÉTER] |

## 2. Audit de cohabitation — commandes en lecture seule uniquement

À exécuter telles quelles, sans aucune modification, puis coller les sorties ci-dessous.

```bash
# Identité et système
hostnamectl; uname -a; uptime
# Services et conteneurs existants
systemctl list-units --type=service --state=running
docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker network ls; docker volume ls
# Qui écoute sur 80 et 443
ss -tulpn | grep -E ':(80|443|22)\b'
# Reverse proxy en place (selon ce qui existe)
ls -la /etc/nginx/sites-enabled/ 2>/dev/null
ls -la /etc/caddy/ 2>/dev/null
docker inspect <proxy> --format '{{json .Config.Labels}}' 2>/dev/null
# Pare-feu et protections
ufw status verbose 2>/dev/null; iptables -S 2>/dev/null | head -40
fail2ban-client status 2>/dev/null
# Tâches planifiées
crontab -l 2>/dev/null; ls -la /etc/cron.d/; systemctl list-timers --all
# Ressources : plusieurs relevés espacés dans le temps, pas un seul
free -m; df -h; docker stats --no-stream
```

Relevés de charge : au moins **6 mesures réparties sur plusieurs heures**, dont une en soirée.

| Horodatage | Charge processeur | Mémoire utilisée | Disque | Remarque |
|---|---|---|---|---|
| [DONNÉE_MANQUANTE] | | | | |

## 3. Décisions à valider par Julien après l'audit — aucune action avant

1. Intégration au reverse proxy existant (lequel, comment) ou installation de Caddy si les ports 80/443 sont libres.
2. Limites processeur et mémoire des conteneurs `jl-*`, et marge garantie pour le jour J.
3. Fenêtre de gel J-7 → J+1 acceptée par les autres projets du VPS.
4. Destination de la sauvegarde externe (hors Hostinger, hors Supabase).

## 4. Rappels bloquants

- Période protégée **J-7 à J+1** : aucun déploiement, aucune mise à jour système, aucun redémarrage planifié, tâches lourdes des autres projets décalées. À inscrire dans le calendrier de Julien.
- Jamais : `docker system prune`, modification du démon Docker, du pare-feu, de SSH ou des tâches planifiées existantes, redémarrage d'un service qui n'appartient pas au mariage.
- Les sauvegardes des autres projets ne sont ni lues ni touchées.

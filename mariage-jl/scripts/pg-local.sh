#!/usr/bin/env bash
# Démarre un PostgreSQL local jetable pour les tests RLS, sans Docker.
# Usage : ./scripts/pg-local.sh [start|stop]
# La base ne contient que des données de test et disparaît avec le dossier.
set -euo pipefail

PGBIN="${PGBIN:-/usr/lib/postgresql/16/bin}"
PGDIR="${PGDIR:-/var/tmp/jl-pg}"
PORT="${PORT:-55432}"
UTILISATEUR="${PGUSER_SYS:-postgres}"

case "${1:-start}" in
  start)
    if [ ! -f "$PGDIR/data/PG_VERSION" ]; then
      mkdir -p "$PGDIR/data" "$PGDIR/sock"
      touch "$PGDIR/pg.log"
      chown -R "$UTILISATEUR":"$UTILISATEUR" "$PGDIR"
      su "$UTILISATEUR" -s /bin/bash -c \
        "$PGBIN/initdb -D $PGDIR/data -U postgres --auth=trust -E UTF8 --locale=C" >/dev/null
    fi
    su "$UTILISATEUR" -s /bin/bash -c \
      "$PGBIN/pg_ctl -D $PGDIR/data -l $PGDIR/pg.log \
       -o '-p $PORT -k $PGDIR/sock -c listen_addresses=127.0.0.1' start"
    echo "PostgreSQL écoute sur 127.0.0.1:$PORT"
    echo "JL_TEST_DATABASE_URL=postgres://postgres@127.0.0.1:$PORT/postgres"
    ;;
  stop)
    su "$UTILISATEUR" -s /bin/bash -c "$PGBIN/pg_ctl -D $PGDIR/data stop"
    ;;
  *)
    echo "Usage : $0 [start|stop]" >&2
    exit 2
    ;;
esac

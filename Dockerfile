# BrickForge — l'atelier LEGO Art, heberge.
#
#   docker build -t brickforge .
#   docker run --rm -p 8000:8000 --memory 1g \
#     -e BFK_CLE="$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')" \
#     -e BFK_SANS_TLS=1 brickforge
#
# Puis suivre le lien que le demarrage imprime.
#
# `--memory` n'est pas decoratif : c'est LUI que le lanceur lit pour calculer
# ce qu'il accepte de fabriquer. Sans limite posee, il lit la memoire de la
# machine entiere et autorise des mosaiques que le conteneur ne tiendra pas.

FROM python:3.13-slim

# Rien a installer : la chaine n'a aucune dependance hors bibliotheque
# standard. C'est ce qui rend cette image petite et sa reconstruction sure.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY bfk001/ ./bfk001/
COPY heberger_lego_art.py app_lego_art.py demo_lego_art.py bfk001_kernel.py ./

# La palette officielle LDraw est TELECHARGEE ICI, a la construction, et non
# redistribuee par ce depot : le fichier appartient a LDraw.org et ne porte
# aucune mention de licence qu'on puisse verifier. L'installer sur la machine
# de qui heberge est ce que fait tout outil de CAO LEGO ; le recopier dans un
# depot public serait autre chose.
#
# La construction ECHOUE si la palette n'arrive pas. Ce n'est pas de la
# severite gratuite : sans elle, la chaine tombe sur douze couleurs recopiees
# a la main et fabrique des mosaiques deux fois plus fausses, sans que
# personne le remarque. Un service silencieusement degrade est pire qu'un
# service qui ne demarre pas. Pour construire hors reseau :
#   docker build --build-arg SANS_PALETTE=1 .
# puis monter votre propre LDConfig.ldr et poser BFK_LDCONFIG.
ARG SANS_PALETTE=""
RUN if [ -z "$SANS_PALETTE" ]; then \
      python3 -c "import sys; \
from bfk001.palette import installer_palette, PaletteRefusee; \
chemin, palette = installer_palette('/usr/share/ldraw/LDConfig.ldr'); \
print(f'palette : {len(palette)} couleurs installees dans {chemin}')" ; \
    else \
      echo "palette : NON installee (SANS_PALETTE). Montez LDConfig.ldr et posez BFK_LDCONFIG." ; \
    fi

# Precompile : avec un systeme de fichiers en lecture seule, Python ne pourra
# pas ecrire ses .pyc, et les recompiler a chaque demarrage coute une seconde
# a chaque redemarrage d'instance.
RUN python3 -m compileall -q /app/bfk001 && \
    python3 -c "import bfk001.heberge, bfk001.webapp; print('modules ok')"

# Rien n'est ecrit hors du processus : les catalogues d'une session vivent en
# memoire et meurent avec elle. L'image tourne donc sans droit d'ecriture.
#   docker run --read-only --tmpfs /tmp ...
RUN useradd --create-home --uid 10001 brickforge
USER brickforge

ENV PORT=8000
EXPOSE 8000

# Le controle de sante ne passe PAS par la page : hebergee, elle repond 401
# sans la cle, et un hebergeur qui la sonderait redemarrerait en boucle un
# atelier qui va tres bien.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import http.client, os, sys; \
lien = http.client.HTTPConnection('127.0.0.1', int(os.environ.get('PORT', '8000')), timeout=4); \
lien.request('GET', '/sante'); \
sys.exit(0 if lien.getresponse().status == 200 else 1)"

CMD ["python3", "heberger_lego_art.py"]

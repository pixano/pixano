# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

# Le contexte de build est la racine du dépôt, pas ce dossier : le worker dépend de `pixano`
# par chemin, et un contexte réduit au paquet ne peut pas voir cette source.
#
#   docker build -f packages/pixano-worker/Dockerfile .

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# `git` parce que `pixano-inference-client` n'est pas publié sur PyPI et vient d'un dépôt git.
# Les bibliothèques X11 parce qu'opencv entre par `pixano.schemas` et les réclame au chargement
# — un service sans écran qui a besoin de libxcb, ce qui mesure bien ce que coûte cet import.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# La source de pixano, dont le worker dépend. `hatch_build.py` et `README.md` sont copiés
# parce que le build du paquet les réclame, même quand il est installé en éditable.
COPY pyproject.toml uv.lock hatch_build.py README.md ./
COPY src/ ./src/

COPY packages/pixano-worker/ ./packages/pixano-worker/
WORKDIR /app/packages/pixano-worker

# Une seule étape, et l'installation reste éditable : `pixano` s'installe depuis un chemin,
# et son hook de build compilerait le frontend si on le forçait en non-éditable — il faudrait
# alors node et pnpm dans l'image d'un service qui ne sert aucune page.
RUN uv sync --frozen --no-dev

ENV PATH="/app/packages/pixano-worker/.venv/bin:$PATH"
CMD ["pixano-worker"]

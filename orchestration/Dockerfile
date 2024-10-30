## Builds the dagster "user code deployment" image that will
## hold our ingest ops & jobs.

FROM python:3-slim AS build
RUN python -m venv /venv

# Accept the SENTRY_DSN as a build arg
ARG SENTRY_DSN

ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  POETRY_VERSION=1.1.8 \
  SENTRY_DSN=$SENTRY_DSN

RUN pip install "poetry==$POETRY_VERSION"

# ==> Add Dagster layer
RUN apt-get update -yqq

COPY pyproject.toml /

RUN mkdir /logs \
    # TODO figure out how to expose this install to the dev env so we don't have to install twice
    # && poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-dev | tee /logs/poetry_install.log

# Cleanup
RUN  rm -rf /var/lib/apt/lists/* \
    &&  rm -rf /root/.cache  \
    # &&  rm -rf /usr/lib/python3.12 \
    &&  rm -rf /usr/lib/x86_64-linux-gnu/guile

FROM us.gcr.io/broad-dsp-gcr-public/base/python:distroless

# ==> Add user code layer
WORKDIR /app
COPY --from=build /venv /venv \
    /logs /logs/
COPY ./ /

# builds with GitHub Action "Main Validation and Release" ../.github/workflows/build-and-publish-main.yaml
# tag = us.gcr.io/broad-dsp-gcr-public/monster-hca-dagster:${{steps.get-artifact-slug.outputs.slug}}
#
# For Dev
# to build and run locally
# docker build -t us.gcr.io/broad-dsp-gcr-public/monster-hca-dagster:<new_version> .
# docker run --rm -it us.gcr.io/broad-dsp-gcr-public/monster-hca-dagster:<new_version>
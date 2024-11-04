## Builds the dagster "user code deployment" image that will
## hold our ingest ops & jobs.

# base python image, blessed by AppSec
FROM us.gcr.io/broad-dsp-gcr-public/base/python:3.12-debian AS base

ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  # TODO upgrade poetry & add recommended env vars docker-examples/poetry-multistage/Dockerfile
  POETRY_VERSION=1.1.8

RUN pip install "poetry==$POETRY_VERSION"

# WORKDIR /app

# Install Dagster and its dependencies
RUN apt-get update -yqq

# TODO add app back
COPY pyproject.toml poetry.lock /

RUN mkdir /logs \
    # TODO figure out how to expose this install to the dev env so we don't have to install twice  \
    # docker-examples/poetry-multistage/Dockerfile
    # && poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-dev | tee /logs/poetry_install.log

# Cleanup - I think this can actually be done in the apt-get layer - ask CoPilot
RUN  rm -rf /var/lib/apt/lists/* \
    &&  rm -rf /root/.cache  \
    # &&  rm -rf /usr/lib/python3.12 \
    &&  rm -rf /usr/lib/x86_64-linux-gnu/guile

# copy the user code into the blessed final image with minimal footprint
FROM base as runtime

# Accept the SENTRY_DSN as a build arg
ARG SENTRY_DSN
ENV SENTRY_DSN=$SENTRY_DSN

# ==> Add user code layer
COPY ./ /

# builds with GitHub Action "Main Validation and Release" ../.github/workflows/build-and-publish-main.yaml
# tag = us.gcr.io/broad-dsp-gcr-public/monster-hca-dagster:${{steps.get-artifact-slug.outputs.slug}}
#
# For Dev
# to build and run locally
# docker build -t us.gcr.io/broad-dsp-gcr-public/monster-hca-dagster:<new_version> .
# docker run --rm -it us.gcr.io/broad-dsp-gcr-public/monster-hca-dagster:<new_version>
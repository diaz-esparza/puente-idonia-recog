FROM ghcr.io/astral-sh/uv@sha256:1b882e1fa1834b0c26764ad6494e3151de499ed34dfa13826f9f395f5110f519

ARG UID=10001
ARG GID=10001

LABEL org.opencontainers.image.title="Puente Idonia-Recog" \
      org.opencontainers.image.description="Interoperability bridge between Idonia medical imaging middleware and Recog AI report humanization." \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.source="https://github.com/diaz-esparza/puente-idonia-recog"

# Rootless improves security
RUN groupadd --system --gid ${GID} appgroup \
    && useradd --system --uid ${UID} --gid appgroup --home-dir /app appuser \
    && mkdir -p /app/.cache/uv /app/.private /app/.keys \
    && chown -R appuser:appgroup /app

USER appuser

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/app/.cache/uv

# Only copying lockfiles first makes dependency cache not break
COPY --chown=appuser:appgroup pyproject.toml .
COPY --chown=appuser:appgroup uv.lock .

RUN --mount=type=cache,target=/app/.cache/uv,id=uv-deps,uid=${UID},gid=${GID} \
    uv sync --locked --no-install-project

# We then copy the code and build the project
COPY --chown=appuser:appgroup README.md .
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup tests/ ./tests/
COPY --chown=appuser:appgroup config/ ./config/

RUN --mount=type=cache,target=/app/.cache/uv,id=uv-deps,uid=${UID},gid=${GID} \
    uv sync --locked

EXPOSE 8000

ENTRYPOINT ["uv", "run", "puente"]

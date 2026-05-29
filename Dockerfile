FROM ghcr.io/astral-sh/uv@sha256:1b882e1fa1834b0c26764ad6494e3151de499ed34dfa13826f9f395f5110f519

LABEL org.opencontainers.image.title="Puente Idonia-Recog" \
      org.opencontainers.image.description="Interoperability bridge between Idonia medical imaging middleware and Recog AI report humanization." \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.source="https://github.com/diaz-esparza/puente-idonia-recog"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Only copying lockfiles first makes dependency cache not break
COPY pyproject.toml .
COPY uv.lock .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project

# We then copy the code and build the project
COPY README.md .
COPY src/ ./src/
COPY tests/ ./tests/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

COPY Makefile .

# Rootless improves security
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --home-dir /app appuser \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["make", "up"]

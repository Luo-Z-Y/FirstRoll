FROM node:22-bookworm-slim AS douban-mcp-builder

ARG DOUBAN_MCP_REPOSITORY=https://github.com/moria97/douban-mcp.git
ARG DOUBAN_MCP_REF=1adc26d39532db893616ceb7ea851733948ae69e

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && git clone --filter=blob:none "$DOUBAN_MCP_REPOSITORY" /opt/douban-mcp \
    && cd /opt/douban-mcp \
    && git checkout --detach "$DOUBAN_MCP_REF" \
    && npm ci --ignore-scripts --audit=false \
    && npm run build \
    && npm pkg set \
        dependencies.@modelcontextprotocol/sdk=1.30.0 \
        overrides.body-parser=2.3.0 \
        overrides.express=5.2.1 \
        overrides.path-to-regexp=8.4.2 \
        overrides.qs=6.15.3 \
    && npm install --ignore-scripts --audit=false \
    && npm prune --omit=dev --ignore-scripts --audit=false \
    && npm audit --omit=dev --audit-level=high \
    && rm -rf .git src

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FIRSTROLL_DOUBAN_MCP_PATH=/opt/douban-mcp/dist/index.js

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=douban-mcp-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=douban-mcp-builder /opt/douban-mcp /opt/douban-mcp

COPY requirements-hosted.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-hosted.txt

COPY app ./app

EXPOSE 10000

CMD ["sh", "-c", "exec uvicorn app.backend.main:app --host 0.0.0.0 --port ${PORT:-10000}"]

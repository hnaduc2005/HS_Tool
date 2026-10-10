FROM node:22-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g pnpm@11.7.0

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY backend/package.json ./backend/package.json
RUN pnpm install --frozen-lockfile --filter hs-ai-backend...

COPY ai-service/requirements.txt ./ai-service/requirements.txt
RUN python3 -m venv /opt/hs-ai-venv \
    && /opt/hs-ai-venv/bin/pip install --no-cache-dir -r ai-service/requirements.txt

COPY backend ./backend
COPY ai-service/app ./ai-service/app
COPY scripts/render-start.sh ./scripts/render-start.sh

RUN pnpm --dir backend prisma:generate \
    && pnpm --dir backend build \
    && chmod +x scripts/render-start.sh

ENV PATH="/opt/hs-ai-venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    NODE_ENV=production \
    AI_SERVICE_URL=http://127.0.0.1:8000 \
    DOCUMENT_STORAGE_PATH=/app/storage

EXPOSE 10000
CMD ["/bin/bash", "scripts/render-start.sh"]

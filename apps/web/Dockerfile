# syntax=docker/dockerfile:1
# Janus web (Next.js standalone). Build context: repository root.
# Base images are multi-arch (linux/amd64, linux/arm64).
FROM node:24-alpine AS base
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
WORKDIR /app

FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile --filter @janus/web

FROM deps AS build
# Address of the API for the /api/* rewrite (read by next.config.ts at build time).
ARG JANUS_API_ORIGIN=http://api:8000
ENV JANUS_API_ORIGIN=$JANUS_API_ORIGIN
COPY apps/web ./apps/web
RUN pnpm --filter @janus/web build

FROM node:24-alpine AS runner
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
WORKDIR /app
COPY --from=build --chown=node:node /app/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /app/apps/web/.next/static ./apps/web/.next/static
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]

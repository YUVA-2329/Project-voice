# PROJECT VOICE — frontend (Next.js 15, standalone output)
# Build:  docker build -t project-voice-frontend ./frontend
# Run:    docker run -p 3000:3000 -e API_INTERNAL_URL=http://api:8000 project-voice-frontend

FROM node:22-alpine AS base
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable && corepack prepare pnpm@10.28.0 --activate
WORKDIR /app

# ---- dependencies ----------------------------------------------------------------------------
FROM base AS deps
COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile

# ---- build -------------------------------------------------------------------------------------
FROM base AS build
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# API_INTERNAL_URL is read at runtime by next.config.ts rewrites; NEXT_PUBLIC_* are inlined here.
ARG NEXT_PUBLIC_WS_BASE=
ENV NEXT_PUBLIC_WS_BASE=$NEXT_PUBLIC_WS_BASE
RUN pnpm build

# ---- runtime -----------------------------------------------------------------------------------
FROM node:22-alpine AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
WORKDIR /app

RUN addgroup -S -g 1001 nodejs && adduser -S -u 1001 -G nodejs nextjs

COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=build --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/login >/dev/null || exit 1

CMD ["node", "server.js"]

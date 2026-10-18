FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=$API_INTERNAL_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S tracelore && adduser -S tracelore -G tracelore
COPY --from=builder --chown=tracelore:tracelore /app/.next/standalone ./
COPY --from=builder --chown=tracelore:tracelore /app/.next/static ./.next/static
COPY --from=builder --chown=tracelore:tracelore /app/public ./public
USER tracelore
EXPOSE 3000
CMD ["node", "server.js"]

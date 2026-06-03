# Stage 1: Build Next.js application
FROM node:20-alpine AS builder
WORKDIR /app

# Copy dependency manifests
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy full frontend codebase
COPY . .

# Set env to disable telemetry during build
ENV NEXT_TELEMETRY_DISABLED=1

# Build Next.js app in standalone mode
RUN npm run build

# Stage 2: Clean and lightweight runner
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Copy only the compiled standalone builds
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Expose port and run server.js
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]

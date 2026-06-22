# Lightweight production runner for Next.js
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Copy pre-built standalone folder, static files, and public assets directly from the build context
COPY .next/standalone ./
COPY .next/static ./.next/static
COPY public ./public

# Expose port and run server.js
EXPOSE 3000
CMD ["node", "server.js"]

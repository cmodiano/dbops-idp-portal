# =============================================================================
# IDP Portal - Frontend React/Vite Dockerfile
# Multi-stage build: Node.js builder → Nginx production
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder (Node.js build)
# ---------------------------------------------------------------------------
FROM node:20-alpine AS builder

# Vite build mode: "production" (default) or "docker" for local Docker Compose
ARG VITE_MODE=production

WORKDIR /build

# Copy package files first for layer caching
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci --ignore-scripts

# Copy source code
COPY . .

# Build production assets (vite build only, TypeScript checking is done in CI)
RUN npx vite build --mode ${VITE_MODE} && \
    test -f dist/index.html || (echo "ERROR: Vite build failed - dist/index.html missing" && exit 1)

# ---------------------------------------------------------------------------
# Stage 2: Production (Nginx)
# ---------------------------------------------------------------------------
FROM nginx:alpine

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder stage
COPY --from=builder /build/dist /usr/share/nginx/html

# Create non-root user for nginx
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

# Expose port 80
EXPOSE 80

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:80/ || exit 1

# Start Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]

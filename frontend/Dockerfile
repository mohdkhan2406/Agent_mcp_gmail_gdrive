# ==============================================================
# Frontend: Vite build -> nginx
# ==============================================================

# ---------- build stage ----------
FROM node:22-alpine AS build

WORKDIR /app

# npm ci needs both files and uses the lockfile exactly.
COPY package.json package-lock.json ./

RUN npm ci

COPY . .

RUN npm run build

# ---------- serve stage ----------
FROM nginx:1.27-alpine

# Our config proxies /api to the backend, so the browser never
# makes a cross-origin request and CORS is not involved.
COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]

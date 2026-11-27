FROM node:22-alpine AS frontend-build

WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
ENV VITE_API_BASE=/api
RUN npm run build


# Official image rather than nginx-unprivileged: the master process runs as
# root (workers drop to the nginx user), so it can read a root-only private
# key straight from the host's cert dir without loosening its permissions.
FROM nginx:1.27-alpine

ENV NGINX_ENVSUBST_FILTER=^(CERT_|HTTPS_PORT$|BACKEND_PORT$) \
    CERT_FULLCHAIN_FILE=fullchain.pem \
    CERT_KEY_FILE=privkey.pem \
    HTTPS_PORT=8443 \
    BACKEND_PORT=8000

RUN rm /etc/nginx/conf.d/default.conf
COPY docker/nginx.conf.template /etc/nginx/templates/default.conf.template
# After 20-envsubst-on-templates.sh has rendered default.conf.
COPY --chmod=755 docker/ipv6-listen.sh /docker-entrypoint.d/25-ipv6-listen.sh
COPY --chmod=755 docker/cert-reload.sh /docker-entrypoint.d/90-cert-reload.sh
COPY --from=frontend-build /src/dist/ /usr/share/nginx/html/

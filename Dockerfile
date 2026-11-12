FROM nginxinc/nginx-unprivileged:stable-alpine
COPY web/index.html /usr/share/nginx/html/index.html
COPY results/ /usr/share/nginx/html/results/
COPY research/validation-2026-10-28/ /usr/share/nginx/html/validation/
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1

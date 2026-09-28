# --- Development stage ---
FROM node:20-alpine AS dev
WORKDIR /usr/src/app

COPY package*.json ./
RUN npm install

COPY . .
RUN chmod +x dev-entrypoint.sh

EXPOSE 3000
CMD ["./dev-entrypoint.sh"]

# --- Build stage ---
FROM node:20-alpine AS build
WORKDIR /usr/src/app

# パッケージのインストール
COPY package*.json ./
RUN npm ci

# ソースをコピーしてビルド
COPY . .
RUN npm run build

# --- Runtime stage ---
FROM nginx:1.25-alpine
COPY --from=build /usr/src/app/dist /usr/share/nginx/html
# Add simple nginx config to serve SPA and proxy /api to backend service
RUN printf '%s\n' \
	'server {' \
	'  listen 80;' \
	'  server_name _;' \
	'  root /usr/share/nginx/html;' \
	'  index index.html;' \
	'  location /api/ {' \
	'    proxy_pass http://backend:8000/api/;' \
	'    proxy_set_header Host $host;' \
	'    proxy_set_header X-Real-IP $remote_addr;' \
	'    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;' \
	'    proxy_set_header X-Forwarded-Proto $scheme;' \
	'  }' \
	'  location / {' \
	'    try_files $uri /index.html;' \
	'  }' \
	'}' \
	> /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
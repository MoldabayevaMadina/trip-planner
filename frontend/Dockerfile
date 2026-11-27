# ---------- stage 1: build the React app into static files ----------
FROM node:22-alpine AS build
WORKDIR /app

# dependencies first: this layer is cached while package*.json don't change
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build            # → /app/dist: index.html + assets/*.js, *.css

# ---------- stage 2: serve the files with nginx ----------
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
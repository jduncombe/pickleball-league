# Builds the static export (same output that is deployed to S3) and serves it
# with nginx, which also proxies /api/* to the API - mirroring CloudFront.

FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.29-alpine
# API_URL is substituted into the template at container start.
ENV API_URL=http://api:8000
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/out /usr/share/nginx/html
EXPOSE 8080

FROM node:20-alpine AS build
WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./

# Static export bakes env vars at build time.
ARG NEXT_PUBLIC_API_BASE_URL=/api
ARG NEXT_PUBLIC_DEMO_KEY=
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_DEMO_KEY=$NEXT_PUBLIC_DEMO_KEY

RUN npm run build

FROM nginx:alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/out /usr/share/nginx/html
EXPOSE 80


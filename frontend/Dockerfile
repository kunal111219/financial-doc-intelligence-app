# Multi-stage build: compile the Vite/React app, then serve the static
# output with nginx — not the Vite dev server, which isn't meant for
# anything beyond local development.

FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
ARG VITE_API_BASE
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

# Client-side routing fallback — not currently needed (this is a
# single-page app with no router), but harmless and avoids a 404 if
# routing is ever added later.
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

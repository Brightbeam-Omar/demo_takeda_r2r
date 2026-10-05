# The React app (F10). Two targets share one dependency layer:
#   dev  : the Vite dev server on 5173, proxying /api to app-api (the compose `frontend` service)
#   prod : the static build behind nginx on 8080, proxying the same paths (the `frontend-web` service, profile `prod`)
FROM node:20-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM deps AS dev
COPY frontend/ ./
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

FROM deps AS build
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine AS prod
COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080

FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_ENABLE_GRAFANA_LINK=true
ARG VITE_GRAFANA_URL=http://localhost:3000/d/cloudpilot-main
ENV VITE_ENABLE_GRAFANA_LINK=$VITE_ENABLE_GRAFANA_LINK
ENV VITE_GRAFANA_URL=$VITE_GRAFANA_URL
RUN npm run build

FROM nginx:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

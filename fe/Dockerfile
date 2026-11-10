# Фронтенд reo: dev-сервер Vite на порту 5173 (docs/conventions.md, раздел 2)
FROM node:26-slim

WORKDIR /app
RUN chown node:node /app
USER node

# Сначала только зависимости: слой пересобирается, только когда меняется package-lock.json
COPY --chown=node:node package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY --chown=node:node . .

# Адрес API для браузера пользователя. В compose можно переопределить через environment
ENV VITE_API_URL=http://localhost:8000

EXPOSE 5173

# --host 0.0.0.0 — чтобы dev-сервер был доступен снаружи контейнера
CMD ["./node_modules/.bin/vite", "--host", "0.0.0.0", "--port", "5173"]

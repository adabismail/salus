# Salus — single-service image: build the React app, then serve it + the API from FastAPI.

# ---- stage 1: build the frontend ----
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- stage 2: python runtime ----
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
# built static assets from stage 1
COPY --from=web /web/dist ./static
ENV SALUS_STATIC_DIR=/app/static
ENV PYTHONPATH=/app
EXPOSE 8000
# Render (and most hosts) inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

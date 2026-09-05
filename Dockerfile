# ==============================================================================
# Multi-stage Dockerfile for RazorRecover
# Stage 1: Build React Dashboard (Vite)
# Stage 2: Run Python FastAPI Backend & serve dashboard static files
# ==============================================================================

# --- Stage 1: Build Frontend Assets ---
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy frontend dependency manifests
COPY frontend/dashboard/package*.json ./
RUN npm ci

# Copy frontend source code and build production bundle
COPY frontend/dashboard/ ./
RUN npm run build

# --- Stage 2: Production Python Runtime ---
FROM python:3.10-slim AS runner

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Install system dependencies (if needed) and Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application directories
COPY backend/ ./backend/
COPY data/ ./data/
COPY eval/ ./eval/

# Copy built frontend assets from Stage 1 into the expected dist path
COPY --from=frontend-builder /app/frontend/dist ./frontend/dashboard/dist

# Expose server port
EXPOSE 8000

# Launch Uvicorn server (shell execution allows reading dynamic $PORT env var)
CMD sh -c "uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"

FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY src ./src
COPY public ./public
COPY index.html ./
COPY postcss.config.js ./
COPY tailwind.config.js ./
COPY vite.config.js ./

RUN npm run build:web


FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

COPY backend ./backend
COPY .env.railway ./.env.railway
COPY public ./public
COPY tests ./tests
COPY *.py ./
COPY pytest.ini ./
COPY README.md ./
COPY LICENSE ./
COPY --from=frontend-builder /app/dist ./dist

EXPOSE 8080

CMD ["python", "backend/server.py"]

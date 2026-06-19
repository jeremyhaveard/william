# ── Stage 1: Build React UI ───────────────────────────────────────
FROM public.ecr.aws/docker/library/node:20-slim AS ui-builder

WORKDIR /ui
COPY ui/package*.json ./
RUN npm install

COPY ui/ ./
# Inject Cognito config at build time via build args (stored in Secrets Manager)
ARG VITE_COGNITO_USER_POOL_ID
ARG VITE_COGNITO_CLIENT_ID
ARG VITE_AWS_REGION=us-east-1
RUN npm run build

# ── Stage 2: Python API ───────────────────────────────────────────
FROM public.ecr.aws/docker/library/python:3.12-slim AS api

# System deps for Playwright (Chromium) and psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser
RUN playwright install chromium --with-deps 2>/dev/null || true

# Copy application code
COPY . .

# Copy built UI into the API container so we can serve it via FastAPI/nginx
COPY --from=ui-builder /ui/dist /app/ui/dist

# Runtime directories (data, logs, output) — in production these are EFS mounts or S3
RUN mkdir -p data logs output

# Non-root user for security
RUN useradd -m -u 1000 william && chown -R william:william /app
USER william

EXPOSE 8000

# Env vars are injected by ECS task definition / Secrets Manager at runtime
# Required: AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (or IAM role)
# Optional: DATABASE_URL, WILLIAM_S3_BUCKET, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID

CMD ["python", "api.py"]

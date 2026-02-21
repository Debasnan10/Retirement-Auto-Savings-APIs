# docker build -t blk-hacking-ind-debasnan-singh .
# docker run -d -p 5477:5477 blk-hacking-ind-debasnan-singh

# ── Base image ────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm

# ── Metadata ──────────────────────────────────────────────────────────────
LABEL maintainer="Debasnan Singh"
LABEL description="Retirement Auto-Savings API — BlackRock Hackathon Challenge"
LABEL image.name="blk-hacking-ind-debasnan-singh"

# ── System dependencies ───────────────────────────────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies (layer-cached) ───────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application source ──────────────────────────────────────────────
COPY . .

# ── Expose the required port ─────────────────────────────────────────────
EXPOSE 5477

# ── Health check ──────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5477/health || exit 1

# ── Run the application ──────────────────────────────────────────────────
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5477"]

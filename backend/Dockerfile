# ── Stage 1: Builder ─────────────────────────────────────────────────
# Install system deps and Python packages in a throwaway layer.
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed to compile Python C-extensions and install s(CASP)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        swi-prolog \
        build-essential \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# Install s(CASP) into a persistent SWI-Prolog pack directory
ENV SWIPL_PACK_DIR=/opt/swipl-packs
RUN mkdir -p $SWIPL_PACK_DIR && \
    swipl -g "pack_install(scasp, [interactive(false), pack_directory('/opt/swipl-packs')])" -t halt

# Install Python deps — use CPU-only PyTorch to save ~2GB
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────────────
# Slim final image: no build-essential, no git, no pip cache.
FROM python:3.11-slim

WORKDIR /app

# Only the runtime system deps (no build-essential, no git)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        swi-prolog \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy s(CASP) packs from builder
COPY --from=builder /opt/swipl-packs /opt/swipl-packs
ENV SWIPL_PACK_DIR=/opt/swipl-packs

# Copy backend source
COPY backend/ .

# Create runtime directories
RUN mkdir -p uploads logs

EXPOSE 5000

CMD ["bash", "-c", "python docker_init.py && python app.py"]

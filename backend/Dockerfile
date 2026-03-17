FROM python:3.11-slim

WORKDIR /app

# Install system deps for SWI-Prolog and build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        swi-prolog \
        build-essential \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# Install scasp package for SWI-Prolog
RUN swipl -g "pack_install(scasp, [interactive(false)])" -t halt

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

# Create uploads directory
RUN mkdir -p uploads logs

EXPOSE 5000

CMD ["bash", "-c", "python docker_init.py && python app.py"]

FROM python:3.11-slim

WORKDIR /app

# Install system deps for SWI-Prolog and build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        swi-prolog \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

# Create uploads directory
RUN mkdir -p uploads logs

EXPOSE 5000

CMD ["python", "app.py"]

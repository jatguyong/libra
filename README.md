# Libra: Prolog-GraphRAG Educational Assistant

Libra is an advanced GraphRAG system that combines Neo4j Knowledge Graphs with Prolog-based logical reasoning (s(CASP)) to provide verifiable, evidence-based answers to educational queries.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.
- A [Together AI](https://www.together.ai/) API key for the Llama-3.3-70B model.

## Docker Setup Instructions

### 1. Environment Configuration
Copy the `.env.example` file to create your own `.env` file:
```bash
cp .env.example .env
```
Open `.env` and fill in your **Together AI API key**:
```bash
TOGETHER_API_KEY=your_actual_key_here
```
*(Default Neo4j credentials are `neo4j/graphrag` and are already pre-configured for Docker).*

### 2. Knowledge Base Data
Ensure the `neo4j_kbpedia/` directory contains the necessary TTL/CSV files for the Knowledge Graph. These are mounted automatically into the Neo4j container.

### 3. Build and Start
Run the following command to build the images and start the services (Backend, Frontend, and Neo4j):
```bash
docker compose up --build
```
- **Backend API**: Runs on `http://localhost:5000`
- **Frontend UI**: Runs on `http://localhost:80` (or `http://localhost`)
- **Neo4j Browser**: Accessible at `http://localhost:7474`

### 4. Running in Background
To run the containers in the background, use:
```bash
docker compose up -d
```
To stop them:
```bash
docker compose down
```
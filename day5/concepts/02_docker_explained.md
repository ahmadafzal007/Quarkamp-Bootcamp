# Docker for Agentic AI — Explained

## Why Docker?

Without Docker, your agent runs on *your* machine. With Docker:
- It runs identically on any machine
- Students, clients, and cloud servers all get the same environment
- No "works on my machine" problems

## How our project uses Docker

```
docker-compose.yml
├── backend   (FastAPI + LangGraph pipeline)   port 8000
├── frontend  (React + Vite)                   port 3000
└── chromadb  (vector store server)            port 8001
```

One command starts everything:
```bash
docker compose up --build
```

## Dockerfile anatomy

```dockerfile
# Dockerfile.backend

# 1. Start from a known base image
FROM python:3.12-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy dependency file first (Docker caches this layer)
COPY requirements.txt .

# 4. Install dependencies (cached if requirements.txt unchanged)
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of the code
COPY . .

# 6. Tell Docker which port the app uses
EXPOSE 8000

# 7. The command to start the app
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## docker-compose.yml anatomy

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"         # host:container
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}   # from .env file
    depends_on:
      - chromadb            # start chromadb first
    volumes:
      - ./data:/app/data    # persist ChromaDB data

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - chroma_data:/chroma/chroma

volumes:
  chroma_data:
```

## Useful commands

```bash
# Build and start all services
docker compose up --build

# Start in background (detached mode)
docker compose up -d

# View logs for a specific service
docker compose logs -f backend

# Stop everything
docker compose down

# Stop and delete volumes (wipes ChromaDB data!)
docker compose down -v

# Rebuild just one service
docker compose up --build backend

# Open a shell inside a running container
docker compose exec backend bash
```

## Environment variables and secrets

Never put API keys in a Dockerfile.
Use `.env` files and the `environment:` key in docker-compose.yml:

```bash
# .env (gitignored)
ANTHROPIC_API_KEY=sk-ant-...
AGENTOPS_API_KEY=...
```

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
```

Docker Compose automatically reads `.env` from the same directory.

## Layer caching — the #1 performance tip

Docker builds images in layers. If a layer hasn't changed, it's reused.

**Slow (invalidates cache on every code change):**
```dockerfile
COPY . .
RUN pip install -r requirements.txt   # reinstalls every time!
```

**Fast (cache survives code changes):**
```dockerfile
COPY requirements.txt .
RUN pip install -r requirements.txt   # cached unless requirements change
COPY . .                               # only this layer re-runs on code change
```

## Multi-stage builds (bonus)

Use multi-stage builds to keep the final image small:
```dockerfile
# Stage 1: build
FROM node:20 AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: serve (tiny nginx image)
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
```

The final image only contains the built static files — no Node.js, no source code.

# L2P-Online Backend

Backend API for L2P-Online built with FastAPI, Redis, PostgreSQL, and MinIO.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Development Setup](#development-setup)
- [Database Migrations](#database-migrations)
- [Testing](#testing)
- [Available Services](#available-services)

## Prerequisites

- Docker and Docker Compose (recommended)
- Python 3.11+ (for local development)
- Git

## Quick Start

The fastest way to get started is using Docker Compose:

```bash
# Clone the repository
git clone <repository-url>
cd l2p-backend

# Copy environment configuration
cp .env.example .env

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

The application will be available at:
- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Configuration

### Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

#### Redis Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Redis server host | `localhost` |
| `REDIS_PORT` | Redis server port | `6379` |
| `REDIS_DB` | Redis database number | `0` |
| `REDIS_PASSWORD` | Redis password | (empty) |

#### PostgreSQL Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_HOST` | PostgreSQL server host | `localhost` |
| `POSTGRES_PORT` | PostgreSQL server port | `5432` |
| `POSTGRES_USER` | PostgreSQL username | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `postgres` |
| `POSTGRES_DB` | Database name | `l2p_db` |

#### MinIO Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `MINIO_ENDPOINT` | MinIO server endpoint | `localhost:9000` |
| `MINIO_ACCESS_KEY` | MinIO access key | `minioadmin` |
| `MINIO_SECRET_KEY` | MinIO secret key | `minioadmin` |
| `MINIO_BUCKET_NAME` | Bucket name | `l2p-bucket` |
| `MINIO_SECURE` | Use HTTPS | `false` |
| `MINIO_PORT` | API port | `9000` |
| `MINIO_CONSOLE_PORT` | Console UI port | `9001` |

## Development Setup

### Option 1: Full Docker Environment (Recommended)

Run everything in Docker containers:

```bash
# Start all services
docker-compose up -d

# Rebuild after changes
docker-compose up -d --build

# Check status
docker-compose ps

# View logs for specific service
docker-compose logs -f app

# Stop all services
docker-compose down

# Stop and remove all data (⚠️ WARNING: Deletes all data!)
docker-compose down -v
```

### Option 2: Local Development with Dockerized Services

Run the application locally while using Docker for dependencies:

```bash
# Start only the services (PostgreSQL, Redis, MinIO)
docker-compose up -d postgres redis minio minio-client

# Install Python dependencies
cd app
pip install -r requirements.txt

# Run the application
uvicorn main:app --reload
```

### Option 3: Manual Docker Setup

<details>
<summary>Start services individually without Docker Compose</summary>

**Redis:**
```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

**PostgreSQL:**
```bash
docker run -d --name postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=l2p_db \
  -p 5432:5432 \
  postgres:16-alpine
```

**MinIO:**
```bash
docker run -d --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  -v minio-data:/data \
  quay.io/minio/minio server /data --console-address ":9001"
```

**Create MinIO bucket:**
```bash
docker run --rm --network host minio/mc \
  alias set local http://localhost:9000 minioadmin minioadmin && \
  mc mb --ignore-existing local/l2p-bucket
```

</details>

## Database Migrations

This project uses Alembic for database migrations.

### First-time Setup

```bash
cd app
alembic init alembic
```

### Create and Apply Migrations

```bash
# Generate a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply all pending migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# View migration history
alembic history
```

## Testing

### Install Test Dependencies

```bash
cd app
pip install -r requirements-test.txt
```

### Run Tests

**Run all tests with coverage (recommended):**

```bash
python3 -m pytest -q --cov=services --cov-report=term-missing
```

Options explained:
- `-q`: Quiet mode - shows only test progress
- `--cov=services`: Measures coverage for services directory
- `--cov-report=term-missing`: Shows which lines are not covered

**Run all tests with verbose output:**

```bash
python3 -m pytest tests/ -v
```

**Run specific test file:**

```bash
python3 -m pytest tests/test_friendship_service.py -v
python3 -m pytest tests/test_chat_service.py -v
```

**Generate HTML coverage report:**

```bash
python3 -m pytest --cov=services --cov-report=html
# Open htmlcov/index.html in your browser
```

## Available Services

When running with Docker Compose, the following services are available:

| Service | URL | Credentials |
|---------|-----|-------------|
| FastAPI Application | http://localhost:8000 | - |
| API Documentation (Swagger) | http://localhost:8000/docs | - |
| PostgreSQL | localhost:5432 | postgres/postgres |
| Redis | localhost:6379 | - |
| MinIO API | http://localhost:9000 | minioadmin/minioadmin |
| MinIO Console | http://localhost:9001 | minioadmin/minioadmin |

## Project Structure

```
l2p-backend/
├── app/
│   ├── main.py              # Application entry point
│   ├── requirements.txt     # Production dependencies
│   ├── requirements-test.txt # Test dependencies
│   ├── api/                 # API routes and handlers
│   ├── config/              # Configuration settings
│   ├── exceptions/          # Custom exceptions
│   ├── infrastructure/      # External services setup
│   ├── models/              # Database models
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic
│   └── tests/               # Test suite
├── docker-compose.yml       # Docker services configuration
├── Dockerfile              # Application container
└── README.md               # This file
```

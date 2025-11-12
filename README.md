# L2P-Online Backend

Backend API for L2P-Online built with FastAPI, Redis, and PostgreSQL.

## Setup

### 1. Install Dependencies

Install all required Python packages:

```bash
pip install -r app/requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

**Redis Configuration:**

-   `REDIS_HOST`: Redis server host (default: localhost)
-   `REDIS_PORT`: Redis server port (default: 6379)
-   `REDIS_DB`: Redis database number (default: 0)
-   `REDIS_PASSWORD`: Redis password (leave empty if not set)

**PostgreSQL Configuration:**

-   `POSTGRES_HOST`: PostgreSQL server host (default: localhost)
-   `POSTGRES_PORT`: PostgreSQL server port (default: 5432)
-   `POSTGRES_USER`: PostgreSQL username (default: postgres)
-   `POSTGRES_PASSWORD`: PostgreSQL password (default: postgres)
-   `POSTGRES_DB`: Database name (default: l2p_db)

### 3. Start Services with Docker Compose (Recommended)

**The easiest way to start all required services (PostgreSQL, Redis, MinIO) is using Docker Compose:**

```bash
# Start all services
docker-compose up -d

# Check services status
docker-compose ps

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Stop and remove all data (WARNING: This will delete all data!)
docker-compose down -v
```

**Services will be available at:**
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- MinIO API: `localhost:9000`
- MinIO Console: `localhost:9001` (login: minioadmin / minioadmin)

**MinIO Configuration:**

The MinIO bucket (`l2p-bucket` by default) is automatically created on startup. You can customize settings in `.env`:

-   `MINIO_ENDPOINT`: MinIO server endpoint (default: localhost:9000)
-   `MINIO_ACCESS_KEY`: MinIO access key (default: minioadmin)
-   `MINIO_SECRET_KEY`: MinIO secret key (default: minioadmin)
-   `MINIO_BUCKET_NAME`: Bucket name (default: l2p-bucket)
-   `MINIO_SECURE`: Use HTTPS (default: false for local development)
-   `MINIO_PORT`: API port (default: 9000)
-   `MINIO_CONSOLE_PORT`: Console UI port (default: 9001)

### 3b. Alternative: Start Services Individually

<details>
<summary>Click to expand manual Docker commands</summary>

If you prefer to start services individually without Docker Compose:

**Start Redis:**
```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

**Start PostgreSQL:**
```bash
docker run -d --name postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=l2p_db \
  -p 5432:5432 \
  postgres:16-alpine
```

**Start MinIO:**
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
# Install mc (MinIO Client) or use Docker
docker run --rm --network host minio/mc \
  alias set local http://localhost:9000 minioadmin minioadmin && \
  mc mb --ignore-existing local/l2p-bucket
```

</details>

### 4. Run Database Migrations

Initialize Alembic for database migrations (first time only):

```bash
cd app
alembic init alembic
```

After creating models, generate and apply migrations:

```bash
# Generate migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head
```

## Running the Application

To start the development server:

```bash
cd app
uvicorn main:app --reload
```

## Testing

### Running Tests

The project uses pytest for testing.

**Run all tests with coverage (recommended):**

```bash
cd app
python3 -m pytest -q --cov=services --cov-report=term-missing
```

This command provides:
- `-q`: Quiet mode - shows only test file progress (dots)
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

### Installing Test Dependencies

Test dependencies are separate from the main application requirements:

```bash
cd app
pip install -r requirements-test.txt
```

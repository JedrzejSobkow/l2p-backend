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

- `REDIS_HOST`: Redis server host (default: localhost)
- `REDIS_PORT`: Redis server port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)
- `REDIS_PASSWORD`: Redis password (leave empty if not set)

**PostgreSQL Configuration:**

- `POSTGRES_HOST`: PostgreSQL server host (default: localhost)
- `POSTGRES_PORT`: PostgreSQL server port (default: 5432)
- `POSTGRES_USER`: PostgreSQL username (default: postgres)
- `POSTGRES_PASSWORD`: PostgreSQL password (default: postgres)
- `POSTGRES_DB`: Database name (default: l2p_db)

### 3. Start Redis

Make sure Redis is running. If you have Docker:

```bash
docker run -d --name redis -p 6379:6379 redis:latest
```

### 4. Start PostgreSQL

Make sure PostgreSQL is running. If you have Docker:

```bash
docker run -d --name postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=l2p_db \
  -p 5432:5432 \
  postgres
```

### 5. Start MinIO

MinIO is used for object storage (chat images, files, etc.). Start MinIO using Docker:

```bash
docker run -d --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  -v minio-data:/data \
  quay.io/minio/minio server /data --console-address ":9001"
```

Access the MinIO Console at `http://localhost:9001` (login: minioadmin / minioadmin)

**MinIO Environment Variables:**

Add these to your `.env` file:

- `MINIO_ENDPOINT`: MinIO server endpoint (default: localhost:9000)
- `MINIO_ACCESS_KEY`: MinIO access key (default: minioadmin)
- `MINIO_SECRET_KEY`: MinIO secret key (default: minioadmin)
- `MINIO_BUCKET_NAME`: Bucket name (default: l2p-bucket)
- `MINIO_SECURE`: Use HTTPS (default: False for local development)

### 6. Run Database Migrations

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

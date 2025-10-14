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

Or install Redis locally and start it:

```bash
# On Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# On macOS
brew install redis
brew services start redis
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

Or install PostgreSQL locally:

```bash
# On Ubuntu/Debian
sudo apt-get install postgresql
sudo systemctl start postgresql

# On macOS
brew install postgresql@16
brew services start postgresql@16
```

Create the database (if not using Docker with pre-created DB):

```bash
psql -U postgres -c "CREATE DATABASE l2p_db;"
```

### 5. Run Database Migrations

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

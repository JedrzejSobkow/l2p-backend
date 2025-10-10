# L2P-Online

## Setup

### 1. Install Dependencies

```bash
pip install -r app/requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` with your Redis configuration:

- `REDIS_HOST`: Redis server host (default: localhost)
- `REDIS_PORT`: Redis server port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)
- `REDIS_PASSWORD`: Redis password (leave empty if not set)

### 3. Start Redis

Make sure Redis is running. If you have Docker:

```bash
docker run -d -p 6379:6379 redis:latest
```

Or install Redis locally and start it.

## Running the Application

To start the development server, run:

```bash
cd app
uvicorn main:app --reload
```

# embedding-service

Text embedding generation

## Port
- Default: 8096

## Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run locally
python -m uvicorn src.main:app --reload --port 8096

# Run tests
pytest

# Build Docker image
docker build -t embedding-service .
```

## API Endpoints

- `GET /health` - Health check
- `GET /ready` - Readiness check
- `GET /api/v1/info` - Service information

## Environment Variables

- `PORT` - Service port (default: 8096)
- `ENV` - Environment (development/production)

# airtable-gateway

Airtable API integration gateway

## Port
- Default: 8093

## Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run locally
python -m uvicorn src.main:app --reload --port 8093

# Run tests
pytest

# Build Docker image
docker build -t airtable-gateway .
```

## API Endpoints

- `GET /health` - Health check
- `GET /ready` - Readiness check
- `GET /api/v1/info` - Service information

## Environment Variables

- `PORT` - Service port (default: 8093)
- `ENV` - Environment (development/production)

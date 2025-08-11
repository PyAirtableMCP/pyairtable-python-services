# chat-service

Chat and conversation management

## Port
- Default: 8098

## Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run locally
python -m uvicorn src.main:app --reload --port 8098

# Run tests
pytest

# Build Docker image
docker build -t chat-service .
```

## API Endpoints

- `GET /health` - Health check
- `GET /ready` - Readiness check
- `GET /api/v1/info` - Service information

## Environment Variables

- `PORT` - Service port (default: 8098)
- `ENV` - Environment (development/production)

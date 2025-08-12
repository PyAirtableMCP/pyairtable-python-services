# Workspace Service

A comprehensive workspace management and collaboration service for the PyAirtable platform. This service provides CRUD operations for workspaces, member management, and invitation systems with role-based access control.

## Features

- ✅ **Workspace CRUD Operations** - Create, read, update, and delete workspaces
- ✅ **Member Management** - Add, update, and remove workspace members
- ✅ **Invitation System** - Invite users via email with expiration and token-based acceptance
- ✅ **Role-based Permissions** - Owner, Admin, Member, and Viewer roles with granular permissions
- ✅ **Template Support** - Pre-configured workspace templates (blank, project management, CRM, etc.)
- ✅ **Authorization** - JWT-based authentication with workspace-level access control
- ✅ **Pagination** - Efficient listing with pagination support
- ✅ **Database Optimization** - Proper indexing and constraints for performance
- ✅ **Health Checks** - Kubernetes-ready health and readiness endpoints
- ✅ **Structured Logging** - JSON structured logs for observability

## API Endpoints

### Health Checks
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed health check with dependency status
- `GET /ready` - Kubernetes readiness probe

### Workspace Management
- `POST /api/v1/workspaces` - Create a new workspace
- `GET /api/v1/workspaces` - List user's workspaces (with pagination)
- `GET /api/v1/workspaces/{id}` - Get specific workspace details
- `PUT /api/v1/workspaces/{id}` - Update workspace settings
- `DELETE /api/v1/workspaces/{id}` - Delete workspace (owner only)

### Member Management
- `POST /api/v1/workspaces/{id}/members` - Add member to workspace
- `PUT /api/v1/workspaces/{id}/members/{user_id}` - Update member permissions
- `DELETE /api/v1/workspaces/{id}/members/{user_id}` - Remove member from workspace

### Invitation System
- `POST /api/v1/workspaces/{id}/invitations` - Create workspace invitation

## Data Models

### Workspace
```json
{
  "id": "workspace-uuid",
  "name": "My Workspace",
  "description": "A sample workspace",
  "template": "project_management",
  "owner_id": "user-123",
  "is_public": false,
  "allow_member_invites": true,
  "max_members": 100,
  "created_at": "2025-01-12T10:00:00Z",
  "updated_at": "2025-01-12T10:00:00Z"
}
```

### Workspace Member
```json
{
  "id": "member-uuid",
  "workspace_id": "workspace-uuid",
  "user_id": "user-123",
  "role": "member",
  "can_edit": true,
  "can_delete": false,
  "can_invite": false,
  "joined_at": "2025-01-12T10:00:00Z",
  "last_activity_at": "2025-01-12T11:00:00Z"
}
```

### Workspace Invitation
```json
{
  "id": "invitation-uuid",
  "workspace_id": "workspace-uuid",
  "email": "user@example.com",
  "role": "member",
  "invited_by_user_id": "user-123",
  "invitation_token": "secure-token-here",
  "message": "Welcome to our workspace!",
  "is_accepted": false,
  "is_expired": false,
  "created_at": "2025-01-12T10:00:00Z",
  "expires_at": "2025-01-19T10:00:00Z",
  "accepted_at": null
}
```

## Roles and Permissions

| Role | Can Edit | Can Delete | Can Invite | Can Manage Members | Notes |
|------|----------|------------|------------|-------------------|-------|
| Owner | ✅ | ✅ | ✅ | ✅ | Full workspace control, cannot be removed |
| Admin | ✅ | ✅ | ✅ | ✅ | Nearly full control, can be demoted by owner |
| Member | ✅ | ❌ | ❌ | ❌ | Can edit workspace content, limited permissions |
| Viewer | ❌ | ❌ | ❌ | ❌ | Read-only access |

## Workspace Templates

- **blank** - Empty workspace with no pre-configured structure
- **project_management** - Project tracking and task management
- **crm** - Customer relationship management
- **content_calendar** - Content planning and scheduling
- **inventory_management** - Stock and inventory tracking
- **event_planning** - Event coordination and planning

## Authentication

All endpoints require JWT authentication via Bearer token:

```bash
curl -H "Authorization: Bearer <jwt-token>" \
     -H "X-API-Key: <api-key>" \
     http://localhost:8003/api/v1/workspaces
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SERVICE_NAME` | Service name | workspace-service |
| `SERVICE_VERSION` | Service version | 1.0.0 |
| `HOST` | Server host | 0.0.0.0 |
| `PORT` | Server port | 8003 |
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | Required |
| `JWT_SECRET` | JWT signing secret | Required |
| `API_KEY` | API key for service access | Required |
| `MAX_WORKSPACES_PER_USER` | Workspace limit per user | 50 |
| `MAX_MEMBERS_PER_WORKSPACE` | Member limit per workspace | 100 |
| `LOG_LEVEL` | Logging level | INFO |
| `ENVIRONMENT` | Environment name | development |

## Database Schema

The service creates three main tables:
- `workspaces` - Core workspace information
- `workspace_members` - User membership in workspaces
- `workspace_invitations` - Pending workspace invitations

See `migrations/004_create_workspace_tables.sql` for the complete schema.

## Development

### Prerequisites
- Python 3.11+
- PostgreSQL 16+
- Redis 7+

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/pyairtable"
export REDIS_URL="redis://localhost:6379/0"
export JWT_SECRET="your-secret-key"
export API_KEY="your-api-key"

# Run the service
python -m uvicorn src.main:app --host 0.0.0.0 --port 8003 --reload
```

### Docker Development
```bash
# Build and run with docker-compose
cd /Users/kg/IdeaProjects/pyairtable-compose
docker-compose up workspace-service
```

### Testing
```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## API Examples

### Create Workspace
```bash
curl -X POST http://localhost:8003/api/v1/workspaces \
  -H "Authorization: Bearer <jwt-token>" \
  -H "X-API-Key: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My New Workspace",
    "description": "A workspace for project collaboration",
    "template": "project_management",
    "is_public": false,
    "max_members": 50
  }'
```

### List Workspaces
```bash
curl "http://localhost:8003/api/v1/workspaces?page=1&limit=10" \
  -H "Authorization: Bearer <jwt-token>" \
  -H "X-API-Key: <api-key>"
```

### Add Member
```bash
curl -X POST http://localhost:8003/api/v1/workspaces/{workspace_id}/members \
  -H "Authorization: Bearer <jwt-token>" \
  -H "X-API-Key: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-456",
    "role": "member",
    "can_edit": true,
    "can_invite": false
  }'
```

### Create Invitation
```bash
curl -X POST http://localhost:8003/api/v1/workspaces/{workspace_id}/invitations \
  -H "Authorization: Bearer <jwt-token>" \
  -H "X-API-Key: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "role": "member",
    "message": "Welcome to our workspace!"
  }'
```

## Monitoring

The service provides comprehensive health checks and structured logging:

- **Health**: `GET /health` - Basic service status
- **Detailed Health**: `GET /health/detailed` - Includes database and Redis status
- **Readiness**: `GET /ready` - Kubernetes readiness probe
- **Metrics**: Structured JSON logs for observability
- **Database Performance**: Optimized queries with proper indexing

## Security Considerations

- JWT tokens are required for all API access
- API keys provide additional service-level security
- Workspace access is strictly controlled by membership
- Invitation tokens are cryptographically secure and time-limited
- Input validation and sanitization on all endpoints
- SQL injection protection via SQLAlchemy ORM
- CORS properly configured for cross-origin requests

## Architecture Integration

This service integrates with the PyAirtable platform:

- **API Gateway**: Routes workspace requests to this service
- **Database**: Shares PostgreSQL database with other platform services
- **Redis**: Uses Redis for caching and session management
- **Authentication**: Integrates with platform JWT authentication
- **Monitoring**: Compatible with LGTM stack (Loki, Grafana, Tempo, Mimir)

## Support

For issues and questions:
- Check the service logs at `/health/detailed`
- Review the API documentation at `/docs`
- Monitor service metrics via structured logging
- Validate database connectivity and migrations
#!/usr/bin/env python3
"""
Simple test script for workspace service
Run this after starting the service to verify basic functionality
"""
import asyncio
import httpx
import json
from datetime import datetime, timedelta
from jose import jwt

# Configuration
BASE_URL = "http://localhost:8003"
API_KEY = "test-api-key"
JWT_SECRET = "your-secret-key-here-change-in-production"
TEST_USER_ID = "test-user-123"

# Create a test JWT token
def create_test_jwt(user_id: str = TEST_USER_ID) -> str:
    """Create a test JWT token for authentication"""
    payload = {
        "sub": user_id,
        "email": f"{user_id}@example.com",
        "name": f"Test User {user_id}",
        "role": "user",
        "permissions": ["workspace:create", "workspace:manage"],
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

async def test_health():
    """Test health endpoints"""
    print("🏥 Testing health endpoints...")
    
    async with httpx.AsyncClient() as client:
        # Basic health check
        response = await client.get(f"{BASE_URL}/health")
        print(f"Health check: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ Health: {response.json()}")
        else:
            print(f"❌ Health failed: {response.text}")
        
        # Service info
        response = await client.get(f"{BASE_URL}/api/v1/info")
        print(f"Info check: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ Info: {response.json()}")
        else:
            print(f"❌ Info failed: {response.text}")

async def test_workspace_crud():
    """Test workspace CRUD operations"""
    print("🏢 Testing workspace CRUD operations...")
    
    # Create JWT token
    token = create_test_jwt()
    headers = {
        "Authorization": f"Bearer {token}",
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    workspace_id = None
    
    async with httpx.AsyncClient() as client:
        # Create workspace
        print("\n📝 Creating workspace...")
        workspace_data = {
            "name": "Test Workspace",
            "description": "A test workspace created by the test script",
            "template": "project_management",
            "is_public": False,
            "max_members": 10
        }
        
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/workspaces",
                headers=headers,
                json=workspace_data
            )
            print(f"Create workspace: {response.status_code}")
            if response.status_code == 201:
                workspace = response.json()["data"]
                workspace_id = workspace["id"]
                print(f"✅ Created workspace: {workspace['name']} (ID: {workspace_id})")
            else:
                print(f"❌ Create failed: {response.text}")
                return
        except Exception as e:
            print(f"❌ Create error: {e}")
            return
        
        # List workspaces
        print("\n📋 Listing workspaces...")
        try:
            response = await client.get(
                f"{BASE_URL}/api/v1/workspaces?page=1&limit=10",
                headers=headers
            )
            print(f"List workspaces: {response.status_code}")
            if response.status_code == 200:
                workspaces = response.json()["data"]
                print(f"✅ Found {workspaces['total']} workspace(s)")
                for ws in workspaces["workspaces"]:
                    print(f"  - {ws['name']} (ID: {ws['id']})")
            else:
                print(f"❌ List failed: {response.text}")
        except Exception as e:
            print(f"❌ List error: {e}")
        
        # Get specific workspace
        if workspace_id:
            print(f"\n🔍 Getting workspace {workspace_id}...")
            try:
                response = await client.get(
                    f"{BASE_URL}/api/v1/workspaces/{workspace_id}",
                    headers=headers
                )
                print(f"Get workspace: {response.status_code}")
                if response.status_code == 200:
                    workspace = response.json()["data"]
                    print(f"✅ Retrieved: {workspace['name']}")
                    print(f"   Description: {workspace['description']}")
                    print(f"   Template: {workspace['template']}")
                else:
                    print(f"❌ Get failed: {response.text}")
            except Exception as e:
                print(f"❌ Get error: {e}")
        
        # Update workspace
        if workspace_id:
            print(f"\n✏️ Updating workspace {workspace_id}...")
            update_data = {
                "description": "Updated description from test script",
                "max_members": 20
            }
            try:
                response = await client.put(
                    f"{BASE_URL}/api/v1/workspaces/{workspace_id}",
                    headers=headers,
                    json=update_data
                )
                print(f"Update workspace: {response.status_code}")
                if response.status_code == 200:
                    workspace = response.json()["data"]
                    print(f"✅ Updated: {workspace['name']}")
                    print(f"   New description: {workspace['description']}")
                    print(f"   New max members: {workspace['max_members']}")
                else:
                    print(f"❌ Update failed: {response.text}")
            except Exception as e:
                print(f"❌ Update error: {e}")
        
        # Test member operations
        if workspace_id:
            print(f"\n👥 Testing member operations...")
            member_data = {
                "user_id": "test-user-456",
                "role": "member",
                "can_edit": True,
                "can_invite": False
            }
            try:
                response = await client.post(
                    f"{BASE_URL}/api/v1/workspaces/{workspace_id}/members",
                    headers=headers,
                    json=member_data
                )
                print(f"Add member: {response.status_code}")
                if response.status_code == 201:
                    member = response.json()["data"]
                    print(f"✅ Added member: {member['user_id']} as {member['role']}")
                else:
                    print(f"❌ Add member failed: {response.text}")
            except Exception as e:
                print(f"❌ Add member error: {e}")
        
        # Test invitation system
        if workspace_id:
            print(f"\n✉️ Testing invitation system...")
            invitation_data = {
                "email": "newuser@example.com",
                "role": "member",
                "message": "Welcome to our test workspace!"
            }
            try:
                response = await client.post(
                    f"{BASE_URL}/api/v1/workspaces/{workspace_id}/invitations",
                    headers=headers,
                    json=invitation_data
                )
                print(f"Create invitation: {response.status_code}")
                if response.status_code == 201:
                    invitation = response.json()["data"]
                    print(f"✅ Created invitation for: {invitation['email']}")
                    print(f"   Token: {invitation['invitation_token'][:20]}...")
                    print(f"   Expires: {invitation['expires_at']}")
                else:
                    print(f"❌ Create invitation failed: {response.text}")
            except Exception as e:
                print(f"❌ Create invitation error: {e}")
        
        # Clean up - delete workspace
        if workspace_id:
            print(f"\n🗑️ Cleaning up - deleting workspace {workspace_id}...")
            try:
                response = await client.delete(
                    f"{BASE_URL}/api/v1/workspaces/{workspace_id}",
                    headers=headers
                )
                print(f"Delete workspace: {response.status_code}")
                if response.status_code == 200:
                    print(f"✅ Deleted workspace successfully")
                else:
                    print(f"❌ Delete failed: {response.text}")
            except Exception as e:
                print(f"❌ Delete error: {e}")

async def main():
    """Main test function"""
    print("🚀 Starting workspace service tests...\n")
    
    try:
        await test_health()
        print("\n" + "="*50)
        await test_workspace_crud()
        print("\n" + "="*50)
        print("✅ All tests completed!")
    except Exception as e:
        print(f"❌ Test suite failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
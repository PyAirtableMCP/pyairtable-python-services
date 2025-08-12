#!/usr/bin/env python3
"""
Test script to verify Airtable Gateway integration
Tests both mock data fallback and real API calls
"""
import asyncio
import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from services.airtable import AirtableService
from config import get_settings
import redis.asyncio as aioredis


async def test_airtable_integration():
    """Test the Airtable service integration"""
    print("🧪 Testing Airtable Gateway Integration")
    print("=" * 50)
    
    # Get settings
    settings = get_settings()
    print(f"📋 Configuration:")
    print(f"   - Use Mock Data: {settings.use_mock_data}")
    print(f"   - Airtable Token: {'***' if settings.airtable_token else 'NOT SET'}")
    print(f"   - Redis URL: {settings.redis_url}")
    print()
    
    # Connect to Redis
    try:
        redis_client = aioredis.from_url(settings.redis_url)
        await redis_client.ping()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("   Using fallback behavior")
        redis_client = None
    
    # Create Airtable service
    service = AirtableService(redis_client) if redis_client else None
    
    if not service:
        print("❌ Cannot create AirtableService without Redis")
        return
    
    print("\n🔍 Testing API Endpoints:")
    print("-" * 30)
    
    # Test 1: List Bases
    try:
        print("1. Testing list_bases()...")
        bases = await service.list_bases()
        print(f"   ✅ Success: Found {len(bases)} bases")
        for base in bases[:2]:  # Show first 2
            print(f"      - {base.get('name')} ({base.get('id')})")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Test 2: Get Base Schema
    try:
        print("2. Testing get_base_schema()...")
        # Use first base from previous test or mock base
        base_id = bases[0]['id'] if bases else 'appMockBase001'
        schema = await service.get_base_schema(base_id)
        tables = schema.get('tables', [])
        print(f"   ✅ Success: Found {len(tables)} tables")
        for table in tables[:2]:  # Show first 2
            print(f"      - {table.get('name')} ({table.get('id')})")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Test 3: List Records
    try:
        print("3. Testing list_records()...")
        # Use first table from previous test or mock table
        table_id = tables[0]['id'] if tables else 'tblMockTable001'
        records_response = await service.list_records(base_id, table_id, max_records=5)
        records = records_response.get('records', [])
        print(f"   ✅ Success: Found {len(records)} records")
        for record in records[:2]:  # Show first 2
            fields = record.get('fields', {})
            field_names = list(fields.keys())[:2]  # Show first 2 fields
            print(f"      - Record {record.get('id')}: {field_names}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Cleanup
    if redis_client:
        await redis_client.close()
    
    print("\n✨ Integration test completed!")
    print("   Check logs above for any issues.")


async def test_api_endpoints():
    """Test the actual HTTP endpoints"""
    import httpx
    
    print("\n🌐 Testing HTTP API Endpoints:")
    print("-" * 30)
    
    base_url = "http://localhost:8002"
    headers = {
        "X-Internal-API-Key": "internal-api-key-dev",
        "Content-Type": "application/json"
    }
    
    endpoints = [
        ("GET", "/", "Root endpoint"),
        ("GET", "/api/v1/info", "Service info"),
        ("GET", "/api/v1/airtable/test", "Test connection"),
        ("GET", "/api/v1/airtable/bases", "List bases"),
    ]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for method, endpoint, description in endpoints:
            try:
                print(f"Testing {method} {endpoint} - {description}")
                response = await client.request(
                    method=method,
                    url=f"{base_url}{endpoint}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    print(f"   ✅ Success: {response.status_code}")
                    # Show partial response for bases endpoint
                    if "bases" in endpoint:
                        data = response.json()
                        if isinstance(data, dict) and 'bases' in data:
                            print(f"      Found {len(data['bases'])} bases")
                        elif isinstance(data, list):
                            print(f"      Found {len(data)} bases")
                else:
                    print(f"   ⚠️  Status: {response.status_code}")
                    print(f"      Response: {response.text[:100]}...")
                    
            except Exception as e:
                print(f"   ❌ Failed: {e}")


if __name__ == "__main__":
    # Set environment variables for testing
    os.environ.setdefault("USE_MOCK_DATA", "true")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("INTERNAL_API_KEY", "internal-api-key-dev")
    
    try:
        asyncio.run(test_airtable_integration())
        asyncio.run(test_api_endpoints())
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        sys.exit(1)
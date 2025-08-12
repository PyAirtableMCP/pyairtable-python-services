#!/usr/bin/env python3
"""
Minimal service starter for testing Airtable Gateway
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    # Try to import and run the service
    from main import app
    import uvicorn
    
    if __name__ == "__main__":
        print("🚀 Starting Airtable Gateway Service...")
        print("   Port: 8002")
        print("   Mock Data: Enabled")
        print("   CORS: Enabled for all origins")
        print("")
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8002,
            reload=False,
            log_level="info"
        )
        
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("   Please install: pip install fastapi uvicorn httpx redis pydantic-settings python-jose")
    sys.exit(1)
except Exception as e:
    print(f"💥 Failed to start service: {e}")
    sys.exit(1)
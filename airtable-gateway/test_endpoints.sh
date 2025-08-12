#!/bin/bash

echo "🧪 Testing Airtable Gateway API Endpoints"
echo "========================================"

BASE_URL="http://localhost:8002"
API_KEY="internal-api-key-dev"

# Test endpoints
endpoints=(
    "GET:/:Root endpoint"
    "GET:/api/v1/info:Service info"
    "GET:/api/v1/airtable/test:Test connection"
    "GET:/api/v1/airtable/bases:List bases"
)

echo "📋 Testing ${#endpoints[@]} endpoints..."
echo

for endpoint in "${endpoints[@]}"; do
    IFS=':' read -r method path description <<< "$endpoint"
    
    echo "Testing $method $path - $description"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "HTTP_STATUS:%{http_code}" \
            -H "X-Internal-API-Key: $API_KEY" \
            -H "Content-Type: application/json" \
            "$BASE_URL$path")
        
        http_status=$(echo "$response" | sed -n 's/.*HTTP_STATUS:\([0-9]*\)$/\1/p')
        response_body=$(echo "$response" | sed 's/HTTP_STATUS:[0-9]*$//')
        
        if [ "$http_status" = "200" ]; then
            echo "   ✅ Success: $http_status"
            if [[ "$path" == *"bases"* ]]; then
                # Show bases count for list bases endpoint
                bases_count=$(echo "$response_body" | grep -o '"id"' | wc -l | xargs)
                echo "      Found $bases_count bases"
            fi
        else
            echo "   ❌ Failed: $http_status"
            echo "      Response: $(echo "$response_body" | head -c 100)..."
        fi
    fi
    echo
done

echo "✨ Test completed!"
echo "   If service is not running, start it with:"
echo "   cd src && python3 main.py"
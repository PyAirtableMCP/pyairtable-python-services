"""Tool executor service for MCP"""
import time
import httpx
import json
from typing import Any, Dict, Optional
from datetime import datetime

from ..config import get_settings
from ..models.mcp import ToolCall, ToolResult, ToolType


class ToolExecutor:
    """Service for executing MCP tools"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call"""
        start_time = time.time()
        
        try:
            # Route to appropriate handler
            if tool_call.tool.startswith("airtable_"):
                result = await self._execute_airtable_tool(tool_call)
            elif tool_call.tool == "calculate":
                result = await self._execute_calculate(tool_call)
            elif tool_call.tool == "search":
                result = await self._execute_search(tool_call)
            elif tool_call.tool == "query_database":
                result = await self._execute_query(tool_call)
            else:
                raise ValueError(f"Unknown tool: {tool_call.tool}")
            
            duration_ms = (time.time() - start_time) * 1000
            
            return ToolResult(
                call_id=tool_call.id,
                tool=tool_call.tool,
                result=result,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return ToolResult(
                call_id=tool_call.id,
                tool=tool_call.tool,
                result=None,
                error=str(e),
                duration_ms=duration_ms
            )
    
    async def _execute_airtable_tool(self, tool_call: ToolCall) -> Any:
        """Execute Airtable-related tools"""
        tool_name = tool_call.tool
        args = tool_call.arguments
        
        # Build URL based on tool
        base_url = self.settings.airtable_gateway_url
        
        if tool_name == "airtable_list_bases":
            url = f"{base_url}/api/v1/airtable/bases"
            response = await self.client.get(url)
            
        elif tool_name == "airtable_get_schema":
            base_id = args["base_id"]
            url = f"{base_url}/api/v1/airtable/bases/{base_id}/schema"
            response = await self.client.get(url)
            
        elif tool_name == "airtable_list_records":
            base_id = args["base_id"]
            table_id = args["table_id"]
            url = f"{base_url}/api/v1/airtable/bases/{base_id}/tables/{table_id}/records"
            
            # Build query params
            params = {}
            if "view" in args:
                params["view"] = args["view"]
            if "max_records" in args:
                params["max_records"] = args["max_records"]
            if "filter_by_formula" in args:
                params["filter_by_formula"] = args["filter_by_formula"]
            if "sort" in args and isinstance(args["sort"], list):
                for i, sort_item in enumerate(args["sort"]):
                    params[f"sort_field"] = sort_item.get("field")
                    params[f"sort_direction"] = sort_item.get("direction", "asc")
            
            response = await self.client.get(url, params=params)
            
        elif tool_name == "airtable_get_record":
            base_id = args["base_id"]
            table_id = args["table_id"]
            record_id = args["record_id"]
            url = f"{base_url}/api/v1/airtable/bases/{base_id}/tables/{table_id}/records/{record_id}"
            response = await self.client.get(url)
            
        elif tool_name == "airtable_create_records":
            base_id = args["base_id"]
            table_id = args["table_id"]
            url = f"{base_url}/api/v1/airtable/bases/{base_id}/tables/{table_id}/records"
            
            params = {"typecast": args.get("typecast", False)}
            response = await self.client.post(url, json=args["records"], params=params)
            
        elif tool_name == "airtable_update_records":
            base_id = args["base_id"]
            table_id = args["table_id"]
            
            if args.get("replace", False):
                url = f"{base_url}/api/v1/airtable/bases/{base_id}/tables/{table_id}/records"
                method = "PUT"
            else:
                url = f"{base_url}/api/v1/airtable/bases/{base_id}/tables/{table_id}/records"
                method = "PATCH"
            
            params = {"typecast": args.get("typecast", False)}
            response = await self.client.request(method, url, json=args["records"], params=params)
            
        elif tool_name == "airtable_delete_records":
            base_id = args["base_id"]
            table_id = args["table_id"]
            url = f"{base_url}/api/v1/airtable/bases/{base_id}/tables/{table_id}/records"
            
            params = {"record_ids": args["record_ids"]}
            response = await self.client.delete(url, params=params)
            
        else:
            raise ValueError(f"Unknown Airtable tool: {tool_name}")
        
        response.raise_for_status()
        return response.json()
    
    async def _execute_calculate(self, tool_call: ToolCall) -> Any:
        """Execute mathematical calculations"""
        expression = tool_call.arguments["expression"]
        
        # Basic safety check - only allow certain characters
        allowed_chars = "0123456789+-*/()., "
        if not all(c in allowed_chars for c in expression):
            raise ValueError("Invalid characters in expression")
        
        try:
            # Evaluate the expression
            result = eval(expression)
            return {
                "expression": expression,
                "result": result,
                "type": type(result).__name__
            }
        except Exception as e:
            raise ValueError(f"Calculation error: {str(e)}")
    
    async def _execute_search(self, tool_call: ToolCall) -> Any:
        """Execute search across Airtable data"""
        query = tool_call.arguments["query"]
        base_id = tool_call.arguments.get("base_id")
        table_id = tool_call.arguments.get("table_id")
        
        # For now, return a placeholder
        # In a real implementation, this would search across indexed data
        return {
            "query": query,
            "results": [],
            "message": "Search functionality not yet implemented"
        }
    
    async def _execute_query(self, tool_call: ToolCall) -> Any:
        """Execute database query"""
        query = tool_call.arguments["query"]
        params = tool_call.arguments.get("params", {})
        
        # For now, return a placeholder
        # In a real implementation, this would execute against a metadata DB
        return {
            "query": query,
            "params": params,
            "results": [],
            "message": "Database query functionality not yet implemented"
        }
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
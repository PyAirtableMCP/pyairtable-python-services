"""MCP protocol routes"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..models.mcp import (
    MCPRequest, MCPResponse, MCPError,
    Tool, ToolCall, ToolResult, AVAILABLE_TOOLS
)
from ..services.tool_executor import ToolExecutor

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])

# Tool executor instance
tool_executor = None


async def get_tool_executor() -> ToolExecutor:
    """Get tool executor instance"""
    global tool_executor
    if tool_executor is None:
        tool_executor = ToolExecutor()
    return tool_executor


@router.post("/rpc")
async def mcp_rpc(request: MCPRequest) -> MCPResponse:
    """Handle MCP RPC requests"""
    try:
        # Route based on method
        if request.method == "initialize":
            result = await handle_initialize(request.params)
        elif request.method == "list_tools":
            result = await handle_list_tools()
        elif request.method == "call_tool":
            result = await handle_call_tool(request.params)
        elif request.method == "complete":
            result = await handle_complete(request.params)
        else:
            return MCPResponse(
                id=request.id,
                error={
                    "code": -32601,
                    "message": f"Method not found: {request.method}"
                }
            )
        
        return MCPResponse(
            id=request.id,
            result=result
        )
        
    except Exception as e:
        return MCPResponse(
            id=request.id,
            error={
                "code": -32603,
                "message": "Internal error",
                "data": str(e)
            }
        )


async def handle_initialize(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle initialize request"""
    return {
        "protocol_version": "1.0",
        "server_info": {
            "name": "pyairtable-mcp-server",
            "version": "1.0.0",
            "capabilities": {
                "tools": True,
                "completion": True,
                "resources": False
            }
        }
    }


async def handle_list_tools() -> List[Dict[str, Any]]:
    """Handle list_tools request"""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    param.name: {
                        "type": param.type,
                        "description": param.description,
                        **({"default": param.default} if param.default is not None else {})
                    }
                    for param in tool.parameters
                },
                "required": [
                    param.name for param in tool.parameters if param.required
                ]
            }
        }
        for tool in AVAILABLE_TOOLS
    ]


async def handle_call_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle call_tool request"""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    
    # Validate tool exists
    if not any(tool.name == tool_name for tool in AVAILABLE_TOOLS):
        raise ValueError(f"Unknown tool: {tool_name}")
    
    # Create tool call
    tool_call = ToolCall(
        tool=tool_name,
        arguments=arguments
    )
    
    # Execute tool
    executor = await get_tool_executor()
    result = await executor.execute(tool_call)
    
    if result.error:
        return {
            "error": result.error,
            "duration_ms": result.duration_ms
        }
    
    return {
        "result": result.result,
        "duration_ms": result.duration_ms
    }


async def handle_complete(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle completion request"""
    # This would integrate with LLM orchestrator for completions
    return {
        "completion": "Completion functionality not yet implemented",
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }


@router.get("/tools", response_model=List[Dict[str, Any]])
async def list_tools():
    """List available tools (REST endpoint)"""
    return await handle_list_tools()


@router.post("/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, arguments: Dict[str, Any]):
    """Execute a specific tool (REST endpoint)"""
    try:
        result = await handle_call_tool({
            "name": tool_name,
            "arguments": arguments
        })
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def mcp_info():
    """Get MCP server information"""
    return {
        "protocol_version": "1.0",
        "server": {
            "name": "pyairtable-mcp-server",
            "version": "1.0.0",
            "description": "Model Context Protocol server for PyAirtable"
        },
        "capabilities": {
            "tools": len(AVAILABLE_TOOLS),
            "completion": False,
            "resources": False
        },
        "available_tools": [tool.name for tool in AVAILABLE_TOOLS]
    }
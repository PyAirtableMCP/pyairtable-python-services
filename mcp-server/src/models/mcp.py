"""MCP (Model Context Protocol) models"""
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class ToolType(str, Enum):
    """MCP tool types"""
    AIRTABLE_LIST_BASES = "airtable_list_bases"
    AIRTABLE_GET_SCHEMA = "airtable_get_schema"
    AIRTABLE_LIST_RECORDS = "airtable_list_records"
    AIRTABLE_GET_RECORD = "airtable_get_record"
    AIRTABLE_CREATE_RECORDS = "airtable_create_records"
    AIRTABLE_UPDATE_RECORDS = "airtable_update_records"
    AIRTABLE_DELETE_RECORDS = "airtable_delete_records"
    CALCULATE = "calculate"
    SEARCH = "search"
    QUERY_DATABASE = "query_database"


class ToolParameter(BaseModel):
    """Tool parameter definition"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


class Tool(BaseModel):
    """MCP tool definition"""
    name: str
    type: ToolType
    description: str
    parameters: List[ToolParameter]


class ToolCall(BaseModel):
    """Tool call request"""
    id: str = Field(default_factory=lambda: f"call_{datetime.utcnow().timestamp()}")
    tool: str
    arguments: Dict[str, Any]


class ToolResult(BaseModel):
    """Tool execution result"""
    call_id: str
    tool: str
    result: Any
    error: Optional[str] = None
    duration_ms: Optional[float] = None


class MCPRequest(BaseModel):
    """MCP request"""
    version: str = "1.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None


class MCPResponse(BaseModel):
    """MCP response"""
    version: str = "1.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None


class MCPError(BaseModel):
    """MCP error"""
    code: int
    message: str
    data: Optional[Any] = None


# Tool definitions
AVAILABLE_TOOLS = [
    Tool(
        name="airtable_list_bases",
        type=ToolType.AIRTABLE_LIST_BASES,
        description="List all accessible Airtable bases",
        parameters=[]
    ),
    Tool(
        name="airtable_get_schema",
        type=ToolType.AIRTABLE_GET_SCHEMA,
        description="Get schema for an Airtable base",
        parameters=[
            ToolParameter(name="base_id", type="string", description="Airtable base ID")
        ]
    ),
    Tool(
        name="airtable_list_records",
        type=ToolType.AIRTABLE_LIST_RECORDS,
        description="List records from an Airtable table",
        parameters=[
            ToolParameter(name="base_id", type="string", description="Airtable base ID"),
            ToolParameter(name="table_id", type="string", description="Airtable table ID"),
            ToolParameter(name="view", type="string", description="View name", required=False),
            ToolParameter(name="max_records", type="integer", description="Maximum records", required=False),
            ToolParameter(name="filter_by_formula", type="string", description="Filter formula", required=False),
            ToolParameter(name="sort", type="array", description="Sort configuration", required=False)
        ]
    ),
    Tool(
        name="airtable_get_record",
        type=ToolType.AIRTABLE_GET_RECORD,
        description="Get a single Airtable record",
        parameters=[
            ToolParameter(name="base_id", type="string", description="Airtable base ID"),
            ToolParameter(name="table_id", type="string", description="Airtable table ID"),
            ToolParameter(name="record_id", type="string", description="Record ID")
        ]
    ),
    Tool(
        name="airtable_create_records",
        type=ToolType.AIRTABLE_CREATE_RECORDS,
        description="Create new Airtable records",
        parameters=[
            ToolParameter(name="base_id", type="string", description="Airtable base ID"),
            ToolParameter(name="table_id", type="string", description="Airtable table ID"),
            ToolParameter(name="records", type="array", description="Records to create"),
            ToolParameter(name="typecast", type="boolean", description="Enable typecasting", required=False, default=False)
        ]
    ),
    Tool(
        name="airtable_update_records",
        type=ToolType.AIRTABLE_UPDATE_RECORDS,
        description="Update existing Airtable records",
        parameters=[
            ToolParameter(name="base_id", type="string", description="Airtable base ID"),
            ToolParameter(name="table_id", type="string", description="Airtable table ID"),
            ToolParameter(name="records", type="array", description="Records to update"),
            ToolParameter(name="typecast", type="boolean", description="Enable typecasting", required=False, default=False),
            ToolParameter(name="replace", type="boolean", description="Replace entire record", required=False, default=False)
        ]
    ),
    Tool(
        name="airtable_delete_records",
        type=ToolType.AIRTABLE_DELETE_RECORDS,
        description="Delete Airtable records",
        parameters=[
            ToolParameter(name="base_id", type="string", description="Airtable base ID"),
            ToolParameter(name="table_id", type="string", description="Airtable table ID"),
            ToolParameter(name="record_ids", type="array", description="Record IDs to delete")
        ]
    ),
    Tool(
        name="calculate",
        type=ToolType.CALCULATE,
        description="Perform mathematical calculations",
        parameters=[
            ToolParameter(name="expression", type="string", description="Mathematical expression to evaluate")
        ]
    ),
    Tool(
        name="search",
        type=ToolType.SEARCH,
        description="Search across Airtable data",
        parameters=[
            ToolParameter(name="query", type="string", description="Search query"),
            ToolParameter(name="base_id", type="string", description="Limit to specific base", required=False),
            ToolParameter(name="table_id", type="string", description="Limit to specific table", required=False)
        ]
    ),
    Tool(
        name="query_database",
        type=ToolType.QUERY_DATABASE,
        description="Execute SQL query on metadata database",
        parameters=[
            ToolParameter(name="query", type="string", description="SQL query to execute"),
            ToolParameter(name="params", type="object", description="Query parameters", required=False)
        ]
    )
]
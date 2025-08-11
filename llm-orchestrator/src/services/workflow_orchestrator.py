"""
Workflow orchestrator for integrating table analysis with MCP server and Airtable updates
"""
import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import httpx
from dataclasses import dataclass

from config import get_settings
from .table_analysis import TableAnalysisService, AnalysisCategory, TableMetadata, AnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class WorkflowConfig:
    """Configuration for analysis workflow"""
    mcp_server_url: str
    airtable_base_id: str
    metadata_table_id: str
    batch_size: int = 5
    max_concurrent: int = 3
    categories: Optional[List[AnalysisCategory]] = None
    auto_update_airtable: bool = True
    quality_threshold: float = 0.7
    

class WorkflowOrchestrator:
    """Orchestrates the complete table analysis workflow"""
    
    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.settings = get_settings()
        self.analysis_service = TableAnalysisService()
        
        # HTTP client for MCP server communication
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Workflow state
        self.workflow_results = {}
        self.failed_tables = []
        
    async def run_complete_workflow(
        self, 
        base_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run complete workflow: fetch tables -> analyze -> update Airtable
        
        Args:
            base_ids: Specific base IDs to analyze (default: all accessible)
            
        Returns:
            Workflow execution summary
        """
        workflow_start = datetime.utcnow()
        
        try:
            # Step 1: Discover tables
            logger.info("Starting table discovery...")
            tables = await self._discover_tables(base_ids)
            logger.info(f"Discovered {len(tables)} tables for analysis")
            
            # Step 2: Run batch analysis
            logger.info("Starting batch analysis...")
            analysis_results = await self._run_batch_analysis(tables)
            logger.info(f"Completed analysis for {len(analysis_results)} tables")
            
            # Step 3: Process and quality check results
            logger.info("Processing analysis results...")
            processed_results = await self._process_results(analysis_results)
            
            # Step 4: Update Airtable metadata (if enabled)
            if self.config.auto_update_airtable:
                logger.info("Updating Airtable with results...")
                update_results = await self._update_airtable_metadata(processed_results)
            else:
                update_results = {"skipped": True}
            
            # Step 5: Generate summary
            workflow_end = datetime.utcnow()
            duration = (workflow_end - workflow_start).total_seconds()
            
            summary = {
                "workflow_id": f"workflow_{int(workflow_start.timestamp())}",
                "status": "completed",
                "duration_seconds": duration,
                "tables_discovered": len(tables),
                "tables_analyzed": len(analysis_results),
                "tables_failed": len(self.failed_tables),
                "cost_summary": self.analysis_service.get_cost_summary(),
                "airtable_updates": update_results,
                "failed_tables": self.failed_tables,
                "started_at": workflow_start.isoformat(),
                "completed_at": workflow_end.isoformat()
            }
            
            logger.info(f"Workflow completed successfully: {summary}")
            return summary
            
        except Exception as e:
            logger.error(f"Workflow failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "duration_seconds": (datetime.utcnow() - workflow_start).total_seconds(),
                "tables_discovered": len(getattr(self, 'tables', [])),
                "tables_analyzed": len(self.workflow_results),
                "failed_tables": self.failed_tables
            }
    
    async def _discover_tables(self, base_ids: Optional[List[str]] = None) -> List[TableMetadata]:
        """Discover tables using MCP server"""
        tables = []
        
        try:
            # Get list of bases
            if base_ids is None:
                bases = await self._call_mcp_tool("airtable_list_bases", {})
                base_ids = [base["id"] for base in bases.get("bases", [])]
            
            # Get schema for each base
            for base_id in base_ids:
                try:
                    schema = await self._call_mcp_tool("airtable_get_schema", {"base_id": base_id})
                    
                    # Extract table metadata
                    for table in schema.get("tables", []):
                        # Get record count (sample a few records to estimate)
                        try:
                            records = await self._call_mcp_tool("airtable_list_records", {
                                "base_id": base_id,
                                "table_id": table["id"],
                                "max_records": 1
                            })
                            # Note: This is a simplification - Airtable API doesn't return total count
                            # In practice, you might need to implement a more sophisticated counting method
                            record_count = None
                        except:
                            record_count = None
                        
                        table_metadata = TableMetadata(
                            base_id=base_id,
                            table_id=table["id"],
                            table_name=table["name"],
                            fields=table.get("fields", []),
                            record_count=record_count,
                            relationships=self._extract_relationships(table.get("fields", [])),
                            views=table.get("views", [])
                        )
                        tables.append(table_metadata)
                        
                except Exception as e:
                    logger.warning(f"Failed to get schema for base {base_id}: {str(e)}")
                    continue
            
            return tables
            
        except Exception as e:
            logger.error(f"Table discovery failed: {str(e)}")
            raise
    
    async def _run_batch_analysis(self, tables: List[TableMetadata]) -> Dict[str, Dict[str, List[AnalysisResult]]]:
        """Run batch analysis with error handling"""
        results = {}
        
        try:
            results = await self.analysis_service.analyze_tables_batch(
                tables=tables,
                batch_size=self.config.batch_size,
                max_concurrent=self.config.max_concurrent
            )
            
            # Track failed tables
            for table in tables:
                if table.table_id not in results:
                    self.failed_tables.append({
                        "table_id": table.table_id,
                        "table_name": table.table_name,
                        "error": "Analysis failed or timed out"
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Batch analysis failed: {str(e)}")
            raise
    
    async def _process_results(self, analysis_results: Dict[str, Dict[str, List[AnalysisResult]]]) -> Dict[str, Any]:
        """Process and quality check analysis results"""
        processed = {
            "high_priority_issues": [],
            "medium_priority_issues": [],
            "low_priority_issues": [],
            "quality_filtered": [],
            "summary_by_category": {},
            "table_summaries": {}
        }
        
        category_counts = {cat.value: 0 for cat in AnalysisCategory}
        
        for table_id, table_results in analysis_results.items():
            table_summary = {
                "table_id": table_id,
                "total_issues": 0,
                "high_priority": 0,
                "medium_priority": 0,
                "low_priority": 0,
                "categories_analyzed": list(table_results.keys()),
                "top_recommendations": []
            }
            
            for category, results in table_results.items():
                category_counts[category] += len(results)
                
                for result in results:
                    table_summary["total_issues"] += 1
                    
                    # Quality filter
                    if result.confidence_score < self.config.quality_threshold:
                        processed["quality_filtered"].append(result.to_dict())
                        continue
                    
                    # Categorize by priority
                    result_dict = result.to_dict()
                    if result.priority == "high":
                        processed["high_priority_issues"].append(result_dict)
                        table_summary["high_priority"] += 1
                    elif result.priority == "medium":
                        processed["medium_priority_issues"].append(result_dict)
                        table_summary["medium_priority"] += 1
                    else:
                        processed["low_priority_issues"].append(result_dict)
                        table_summary["low_priority"] += 1
                    
                    # Track top recommendations (high confidence, high priority)
                    if result.confidence_score >= 0.8 and result.priority in ["high", "medium"]:
                        table_summary["top_recommendations"].append({
                            "category": result.category.value,
                            "recommendation": result.recommendation,
                            "confidence": result.confidence_score
                        })
            
            processed["table_summaries"][table_id] = table_summary
        
        processed["summary_by_category"] = category_counts
        
        return processed
    
    async def _update_airtable_metadata(self, processed_results: Dict[str, Any]) -> Dict[str, Any]:
        """Update Airtable metadata table with analysis results"""
        update_results = {
            "updated_records": 0,
            "failed_updates": 0,
            "errors": []
        }
        
        try:
            # Prepare records for update
            updates = []
            
            for table_id, summary in processed_results["table_summaries"].items():
                # Format improvements data for Airtable
                improvements_data = {
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                    "total_issues": summary["total_issues"],
                    "high_priority_count": summary["high_priority"],
                    "medium_priority_count": summary["medium_priority"],
                    "low_priority_count": summary["low_priority"],
                    "categories_analyzed": summary["categories_analyzed"],
                    "top_recommendations": summary["top_recommendations"][:5],  # Limit to top 5
                    "analysis_status": "completed"
                }
                
                # Find the metadata record for this table
                try:
                    # Query metadata table to find record
                    metadata_records = await self._call_mcp_tool("airtable_list_records", {
                        "base_id": self.config.airtable_base_id,
                        "table_id": self.config.metadata_table_id,
                        "filter_by_formula": f"{{table_id}} = '{table_id}'"
                    })
                    
                    if metadata_records.get("records"):
                        # Update existing record
                        record_id = metadata_records["records"][0]["id"]
                        updates.append({
                            "id": record_id,
                            "fields": {
                                "improvements": json.dumps(improvements_data),
                                "last_analysis": datetime.utcnow().isoformat(),
                                "analysis_status": "completed"
                            }
                        })
                    else:
                        # Create new metadata record
                        updates.append({
                            "fields": {
                                "table_id": table_id,
                                "improvements": json.dumps(improvements_data),
                                "last_analysis": datetime.utcnow().isoformat(),
                                "analysis_status": "completed"
                            }
                        })
                        
                except Exception as e:
                    logger.warning(f"Failed to query metadata for table {table_id}: {str(e)}")
                    update_results["errors"].append(f"Query failed for {table_id}: {str(e)}")
            
            # Batch update records
            if updates:
                # Split into update and create batches
                update_records = [r for r in updates if "id" in r]
                create_records = [r for r in updates if "id" not in r]
                
                # Update existing records
                if update_records:
                    try:
                        await self._call_mcp_tool("airtable_update_records", {
                            "base_id": self.config.airtable_base_id,
                            "table_id": self.config.metadata_table_id,
                            "records": update_records
                        })
                        update_results["updated_records"] += len(update_records)
                    except Exception as e:
                        logger.error(f"Failed to update records: {str(e)}")
                        update_results["failed_updates"] += len(update_records)
                        update_results["errors"].append(f"Update failed: {str(e)}")
                
                # Create new records
                if create_records:
                    try:
                        await self._call_mcp_tool("airtable_create_records", {
                            "base_id": self.config.airtable_base_id,
                            "table_id": self.config.metadata_table_id,
                            "records": create_records
                        })
                        update_results["updated_records"] += len(create_records)
                    except Exception as e:
                        logger.error(f"Failed to create records: {str(e)}")
                        update_results["failed_updates"] += len(create_records)
                        update_results["errors"].append(f"Create failed: {str(e)}")
            
            return update_results
            
        except Exception as e:
            logger.error(f"Airtable metadata update failed: {str(e)}")
            update_results["errors"].append(f"General update failure: {str(e)}")
            return update_results
    
    async def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call MCP server tool"""
        try:
            response = await self.http_client.post(
                f"{self.config.mcp_server_url}/api/v1/tools/execute",
                json={
                    "tool": tool_name,
                    "arguments": arguments
                }
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            logger.error(f"MCP tool call failed: {tool_name} - {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling MCP tool {tool_name}: {str(e)}")
            raise
    
    def _extract_relationships(self, fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract relationship information from field definitions"""
        relationships = []
        
        for field in fields:
            field_type = field.get("type", "")
            
            if field_type == "multipleRecordLinks":
                relationships.append({
                    "field_name": field.get("name"),
                    "field_id": field.get("id"),
                    "type": "link",
                    "linked_table_id": field.get("options", {}).get("linkedTableId"),
                    "is_reversed": field.get("options", {}).get("isReversed", False)
                })
            elif field_type == "lookup":
                relationships.append({
                    "field_name": field.get("name"),
                    "field_id": field.get("id"),
                    "type": "lookup",
                    "record_link_field": field.get("options", {}).get("recordLinkFieldId"),
                    "field_id_in_linked_table": field.get("options", {}).get("fieldIdInLinkedTable")
                })
            elif field_type == "rollup":
                relationships.append({
                    "field_name": field.get("name"),
                    "field_id": field.get("id"),
                    "type": "rollup",
                    "record_link_field": field.get("options", {}).get("recordLinkFieldId"),
                    "field_id_in_linked_table": field.get("options", {}).get("fieldIdInLinkedTable"),
                    "formula": field.get("options", {}).get("formula")
                })
        
        return relationships
    
    async def close(self):
        """Clean up resources"""
        await self.http_client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
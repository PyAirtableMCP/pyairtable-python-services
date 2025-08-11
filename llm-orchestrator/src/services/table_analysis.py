"""
LLM-powered table analysis service for Airtable optimization
"""
import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
import logging

from config import get_settings
from models.chat import Message, MessageRole, ChatRequest
from .gemini import GeminiService

logger = logging.getLogger(__name__)


class AnalysisCategory(str, Enum):
    """Analysis categories for table optimization"""
    STRUCTURE = "structure"
    NORMALIZATION = "normalization"
    FIELD_TYPES = "field_types"
    RELATIONSHIPS = "relationships"
    PERFORMANCE = "performance"
    DATA_QUALITY = "data_quality"
    NAMING_CONVENTIONS = "naming_conventions"
    INDEXING = "indexing"


@dataclass
class AnalysisResult:
    """Result of table analysis"""
    table_id: str
    table_name: str
    category: AnalysisCategory
    priority: str  # high, medium, low
    issue_type: str
    description: str
    recommendation: str
    impact: str
    effort: str  # low, medium, high
    estimated_improvement: str
    implementation_steps: List[str]
    confidence_score: float  # 0-1
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TableMetadata:
    """Table metadata for analysis"""
    base_id: str
    table_id: str
    table_name: str
    fields: List[Dict[str, Any]]
    record_count: Optional[int] = None
    relationships: Optional[List[Dict[str, Any]]] = None
    views: Optional[List[Dict[str, Any]]] = None


class PromptTemplates:
    """Collection of specialized prompt templates for table analysis"""
    
    @staticmethod
    def get_structure_analysis_prompt(table_data: TableMetadata) -> str:
        """Prompt for analyzing table structure and design"""
        return f"""
You are an expert Airtable database analyst. Analyze the following table structure and provide detailed improvement recommendations.

TABLE INFORMATION:
- Base ID: {table_data.base_id}
- Table Name: {table_data.table_name}
- Table ID: {table_data.table_id}
- Record Count: {table_data.record_count or 'Unknown'}

FIELDS:
{json.dumps(table_data.fields, indent=2)}

RELATIONSHIPS:
{json.dumps(table_data.relationships or [], indent=2)}

VIEWS:
{json.dumps(table_data.views or [], indent=2)}

ANALYSIS FOCUS:
Analyze this table for structural improvements including:
1. Field organization and grouping
2. Primary key effectiveness
3. Field dependencies and redundancy
4. Table size and complexity
5. View organization efficiency

For each issue identified, provide:
- Issue Type: Brief category
- Priority: high/medium/low
- Description: Clear explanation of the problem
- Recommendation: Specific actionable solution
- Impact: Expected benefit of implementing the change
- Effort: low/medium/high implementation difficulty
- Estimated Improvement: Quantified benefit where possible
- Implementation Steps: Ordered list of actions needed
- Confidence Score: 0-1 rating of recommendation certainty

Respond in JSON format with an array of findings:
```json
[
  {{
    "issue_type": "string",
    "priority": "high|medium|low",
    "description": "string",
    "recommendation": "string", 
    "impact": "string",
    "effort": "low|medium|high",
    "estimated_improvement": "string",
    "implementation_steps": ["step1", "step2", "..."],
    "confidence_score": 0.0-1.0
  }}
]
```
"""

    @staticmethod
    def get_normalization_analysis_prompt(table_data: TableMetadata) -> str:
        """Prompt for analyzing data normalization opportunities"""
        return f"""
You are a database normalization expert. Analyze this Airtable for normalization improvements.

TABLE: {table_data.table_name}
FIELDS: {json.dumps(table_data.fields, indent=2)}
RECORD COUNT: {table_data.record_count or 'Unknown'}

NORMALIZATION ANALYSIS:
Identify violations of database normal forms (1NF, 2NF, 3NF) and suggest improvements:

1. First Normal Form (1NF) violations:
   - Multi-value fields that should be separate records
   - Atomic value violations
   - Repeating groups

2. Second Normal Form (2NF) violations:
   - Partial dependencies on composite keys
   - Fields that depend on only part of the primary key

3. Third Normal Form (3NF) violations:
   - Transitive dependencies
   - Fields that depend on non-key fields
   - Calculated fields that could be derived

4. Denormalization opportunities:
   - When to intentionally violate normal forms for performance
   - Lookup field optimizations
   - Calculated field efficiency

For each normalization issue, suggest:
- Table splitting strategies
- New relationship creation
- Field relocation recommendations
- Performance vs. normalization trade-offs

Return JSON format with findings array as specified in the structure analysis.
"""

    @staticmethod
    def get_field_optimization_prompt(table_data: TableMetadata) -> str:
        """Prompt for analyzing field types and configurations"""
        return f"""
You are an Airtable field optimization specialist. Analyze field types and configurations for efficiency.

TABLE: {table_data.table_name}
FIELDS: {json.dumps(table_data.fields, indent=2)}

FIELD OPTIMIZATION ANALYSIS:
Examine each field for:

1. Field Type Optimization:
   - Incorrect field types for data content
   - Single line text vs. Long text efficiency
   - Number field precision and formatting
   - Date/DateTime field usage
   - Select vs. Multi-select appropriateness
   - Attachment field optimization

2. Field Configuration:
   - Missing field descriptions
   - Inadequate validation rules
   - Inefficient formatting options
   - Default value opportunities
   - Required field settings

3. Lookup and Formula Fields:
   - Complex formulas that could be simplified
   - Lookup fields causing performance issues
   - Rollup field efficiency
   - Calculated vs. stored data decisions

4. Field Naming and Organization:
   - Inconsistent naming conventions
   - Non-descriptive field names
   - Field grouping opportunities
   - Field ordering optimization

Identify specific improvements for data integrity, performance, and user experience.

Return JSON format with findings array.
"""

    @staticmethod
    def get_relationships_analysis_prompt(table_data: TableMetadata, related_tables: List[TableMetadata]) -> str:
        """Prompt for analyzing table relationships"""
        return f"""
You are a database relationship design expert. Analyze table relationships and suggest improvements.

PRIMARY TABLE: {table_data.table_name}
FIELDS: {json.dumps(table_data.fields, indent=2)}
EXISTING RELATIONSHIPS: {json.dumps(table_data.relationships or [], indent=2)}

RELATED TABLES:
{json.dumps([{"name": t.table_name, "fields": [f["name"] for f in t.fields]} for t in related_tables], indent=2)}

RELATIONSHIP ANALYSIS:

1. Missing Relationships:
   - Identify fields that should be linked to other tables
   - Potential many-to-many relationships
   - Lookup opportunities for data consistency

2. Relationship Optimization:
   - Inefficient relationship configurations
   - Bidirectional vs. unidirectional links
   - Link field naming conventions
   - Cascade delete considerations

3. Data Integrity:
   - Orphaned records potential
   - Referential integrity issues
   - Circular reference problems
   - Relationship constraint violations

4. Performance Impact:
   - Complex relationship chains
   - Lookup field performance issues
   - Rollup calculation efficiency
   - View filtering on relationships

Suggest relationship improvements including new links, relationship modifications, and data integrity enhancements.

Return JSON format with findings array.
"""

    @staticmethod
    def get_performance_analysis_prompt(table_data: TableMetadata) -> str:
        """Prompt for analyzing performance optimization opportunities"""
        return f"""
You are an Airtable performance optimization expert. Analyze this table for performance improvements.

TABLE: {table_data.table_name} ({table_data.record_count or 'Unknown'} records)
FIELDS: {json.dumps(table_data.fields, indent=2)}
VIEWS: {json.dumps(table_data.views or [], indent=2)}

PERFORMANCE ANALYSIS:

1. Record Count Optimization:
   - Table size impact on performance
   - Record archiving strategies
   - Data lifecycle management
   - Historical data handling

2. Field Performance:
   - Complex formula fields causing slowdowns
   - Lookup field chain length
   - Attachment field sizes
   - Rollup calculation efficiency

3. View Optimization:
   - Excessive view count
   - Complex filtering and sorting
   - Grouping performance impact
   - View-specific field visibility

4. Query Optimization:
   - Most commonly filtered fields
   - Indexing opportunities (conceptual for Airtable)
   - Search performance improvements
   - API access patterns

5. Automation Impact:
   - Formula recalculation triggers
   - Webhook frequency and efficiency
   - Sync performance considerations

Provide specific recommendations for improving table performance, load times, and user experience.

Return JSON format with findings array.
"""

    @staticmethod
    def get_data_quality_analysis_prompt(table_data: TableMetadata) -> str:
        """Prompt for analyzing data quality issues"""
        return f"""
You are a data quality expert. Analyze this Airtable for data quality improvements.

TABLE: {table_data.table_name}
FIELDS: {json.dumps(table_data.fields, indent=2)}

DATA QUALITY ANALYSIS:

1. Data Validation:
   - Missing validation rules
   - Inconsistent data formats
   - Invalid data patterns
   - Constraint violations

2. Data Completeness:
   - Fields with high null rates
   - Required fields not enforced
   - Incomplete record patterns
   - Missing mandatory relationships

3. Data Consistency:
   - Inconsistent naming conventions
   - Duplicate record potential
   - Format standardization needs
   - Cross-field validation rules

4. Data Accuracy:
   - Potential data entry errors
   - Outdated information patterns
   - Calculated field accuracy
   - Reference data consistency

5. Data Standardization:
   - Text formatting inconsistencies
   - Date format variations
   - Number precision issues
   - Selection option optimization

Suggest improvements for data quality, validation rules, and consistency enforcement.

Return JSON format with findings array.
"""


class TableAnalysisService:
    """Service for LLM-powered table analysis and optimization recommendations"""
    
    def __init__(self):
        self.settings = get_settings()
        self.gemini_service = GeminiService()
        self.prompt_templates = PromptTemplates()
        
        # Cost tracking
        self.total_cost = 0.0
        self.analysis_count = 0
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # seconds between requests
        
    async def analyze_table_comprehensive(
        self, 
        table_data: TableMetadata,
        categories: List[AnalysisCategory] = None,
        related_tables: List[TableMetadata] = None
    ) -> Dict[str, List[AnalysisResult]]:
        """
        Perform comprehensive analysis of a table across multiple categories
        
        Args:
            table_data: Table metadata to analyze
            categories: Specific categories to analyze (default: all)
            related_tables: Related tables for relationship analysis
            
        Returns:
            Dictionary mapping categories to analysis results
        """
        if categories is None:
            categories = list(AnalysisCategory)
            
        results = {}
        
        for category in categories:
            try:
                await self._rate_limit()
                category_results = await self._analyze_category(
                    table_data, category, related_tables
                )
                results[category.value] = category_results
                
                logger.info(f"Completed {category.value} analysis for table {table_data.table_name}")
                
            except Exception as e:
                logger.error(f"Error analyzing category {category.value}: {str(e)}")
                results[category.value] = []
                
        return results
    
    async def analyze_tables_batch(
        self, 
        tables: List[TableMetadata],
        batch_size: int = 5,
        max_concurrent: int = 3
    ) -> Dict[str, Dict[str, List[AnalysisResult]]]:
        """
        Analyze multiple tables in batches with concurrency control
        
        Args:
            tables: List of table metadata to analyze
            batch_size: Number of tables per batch
            max_concurrent: Maximum concurrent analyses
            
        Returns:
            Dictionary mapping table IDs to analysis results
        """
        results = {}
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def analyze_single_table(table_data: TableMetadata) -> Tuple[str, Dict[str, List[AnalysisResult]]]:
            async with semaphore:
                table_results = await self.analyze_table_comprehensive(table_data)
                return table_data.table_id, table_results
        
        # Process in batches
        for i in range(0, len(tables), batch_size):
            batch = tables[i:i + batch_size]
            batch_tasks = [analyze_single_table(table) for table in batch]
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch analysis error: {str(result)}")
                else:
                    table_id, table_results = result
                    results[table_id] = table_results
            
            # Progress logging
            logger.info(f"Completed batch {i//batch_size + 1}/{(len(tables) + batch_size - 1)//batch_size}")
            
        return results
    
    async def _analyze_category(
        self, 
        table_data: TableMetadata, 
        category: AnalysisCategory,
        related_tables: List[TableMetadata] = None
    ) -> List[AnalysisResult]:
        """Analyze a specific category for a table"""
        
        # Get appropriate prompt for category
        prompt = self._get_category_prompt(table_data, category, related_tables)
        
        # Create chat request
        messages = [
            Message(role=MessageRole.SYSTEM, content="You are an expert Airtable optimization consultant."),
            Message(role=MessageRole.USER, content=prompt)
        ]
        
        chat_request = ChatRequest(
            messages=messages,
            model=self.settings.gemini_model,
            temperature=0.1,  # Low temperature for consistent analysis
            max_tokens=4000
        )
        
        # Get LLM response
        response = await self.gemini_service.complete(chat_request)
        
        # Track cost
        self.total_cost += response.usage.get("cost", 0)
        self.analysis_count += 1
        
        # Parse response
        analysis_results = self._parse_analysis_response(
            response.choices[0]["message"]["content"],
            table_data,
            category
        )
        
        return analysis_results
    
    def _get_category_prompt(
        self, 
        table_data: TableMetadata, 
        category: AnalysisCategory,
        related_tables: List[TableMetadata] = None
    ) -> str:
        """Get the appropriate prompt for analysis category"""
        
        prompt_map = {
            AnalysisCategory.STRUCTURE: self.prompt_templates.get_structure_analysis_prompt,
            AnalysisCategory.NORMALIZATION: self.prompt_templates.get_normalization_analysis_prompt,
            AnalysisCategory.FIELD_TYPES: self.prompt_templates.get_field_optimization_prompt,
            AnalysisCategory.RELATIONSHIPS: lambda td: self.prompt_templates.get_relationships_analysis_prompt(td, related_tables or []),
            AnalysisCategory.PERFORMANCE: self.prompt_templates.get_performance_analysis_prompt,
            AnalysisCategory.DATA_QUALITY: self.prompt_templates.get_data_quality_analysis_prompt,
        }
        
        # Default to structure analysis for unmapped categories
        prompt_func = prompt_map.get(category, self.prompt_templates.get_structure_analysis_prompt)
        return prompt_func(table_data)
    
    def _parse_analysis_response(
        self, 
        response_text: str, 
        table_data: TableMetadata, 
        category: AnalysisCategory
    ) -> List[AnalysisResult]:
        """Parse LLM response into structured analysis results"""
        
        try:
            # Extract JSON from response
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            
            if json_start == -1 or json_end == 0:
                logger.warning(f"No JSON found in response for {table_data.table_name}")
                return []
            
            json_text = response_text[json_start:json_end]
            findings = json.loads(json_text)
            
            # Convert to AnalysisResult objects
            results = []
            for finding in findings:
                try:
                    result = AnalysisResult(
                        table_id=table_data.table_id,
                        table_name=table_data.table_name,
                        category=category,
                        priority=finding.get("priority", "medium"),
                        issue_type=finding.get("issue_type", ""),
                        description=finding.get("description", ""),
                        recommendation=finding.get("recommendation", ""),
                        impact=finding.get("impact", ""),
                        effort=finding.get("effort", "medium"),
                        estimated_improvement=finding.get("estimated_improvement", ""),
                        implementation_steps=finding.get("implementation_steps", []),
                        confidence_score=float(finding.get("confidence_score", 0.7))
                    )
                    results.append(result)
                    
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"Error parsing finding: {e}")
                    continue
            
            return results
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            return []
    
    async def _rate_limit(self):
        """Implement rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        self.last_request_time = time.time()
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get analysis cost summary"""
        return {
            "total_cost": round(self.total_cost, 4),
            "analysis_count": self.analysis_count,
            "average_cost_per_analysis": round(
                self.total_cost / max(self.analysis_count, 1), 4
            ),
            "estimated_cost_per_table": round(
                self.total_cost / max(self.analysis_count / len(AnalysisCategory), 1), 4
            )
        }
    
    def estimate_batch_cost(self, table_count: int, categories: List[AnalysisCategory] = None) -> Dict[str, Any]:
        """Estimate cost for batch analysis"""
        if categories is None:
            categories = list(AnalysisCategory)
        
        # Rough estimates based on prompt complexity and expected response length
        category_costs = {
            AnalysisCategory.STRUCTURE: 0.02,
            AnalysisCategory.NORMALIZATION: 0.025,
            AnalysisCategory.FIELD_TYPES: 0.015,
            AnalysisCategory.RELATIONSHIPS: 0.03,
            AnalysisCategory.PERFORMANCE: 0.02,
            AnalysisCategory.DATA_QUALITY: 0.02,
            AnalysisCategory.NAMING_CONVENTIONS: 0.01,
            AnalysisCategory.INDEXING: 0.015,
        }
        
        total_estimated_cost = sum(
            category_costs.get(cat, 0.02) for cat in categories
        ) * table_count
        
        return {
            "estimated_total_cost": round(total_estimated_cost, 4),
            "cost_per_table": round(total_estimated_cost / table_count, 4),
            "categories_count": len(categories),
            "table_count": table_count,
            "estimated_time_minutes": table_count * len(categories) * 0.5  # 30 seconds per analysis
        }
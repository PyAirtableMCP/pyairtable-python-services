# LLM-Powered Table Analysis Workflow Design

## Overview

This document outlines the comprehensive LLM-powered table analysis and improvement recommendation workflow for the pyairtable MCP system. The system uses Gemini API integration to analyze 35 Airtable tables and provide actionable optimization recommendations.

## Architecture

```
Frontend → API Gateway → LLM Orchestrator → Gemini API
                                        ↓
Airtable ← MCP Server ← ← ← ← ← Analysis Results
```

### Components

1. **LLM Orchestrator Service** (Port 8003)
   - Table analysis service with specialized prompts
   - Batch processing with concurrency control
   - Cost optimization and rate limiting
   - Quality assurance and validation

2. **MCP Server Integration**
   - Airtable data fetching and schema analysis
   - Results storage in metadata table
   - Tool execution for data operations

3. **Workflow Orchestrator**
   - End-to-end workflow management
   - Progress tracking and error handling
   - Result processing and formatting

## Analysis Categories

### 1. Structure Analysis
- Field organization and grouping
- Primary key effectiveness  
- Field dependencies and redundancy
- Table size and complexity
- View organization efficiency

### 2. Normalization Analysis
- 1NF, 2NF, 3NF violation detection
- Multi-value field identification
- Partial and transitive dependencies
- Table splitting recommendations
- Denormalization opportunities

### 3. Field Type Optimization
- Incorrect field type detection
- Validation rule improvements
- Format optimization suggestions
- Default value opportunities
- Required field recommendations

### 4. Relationship Analysis
- Missing relationship detection
- Link field optimization
- Lookup and rollup efficiency
- Referential integrity checks
- Cascade delete considerations

### 5. Performance Optimization
- Query performance improvements
- Complex formula optimization
- View configuration efficiency
- Record count optimization
- Automation impact analysis

### 6. Data Quality Assessment
- Validation rule gaps
- Data consistency issues
- Completeness analysis
- Accuracy improvements
- Standardization opportunities

## API Endpoints

### Table Analysis Endpoints

#### Single Table Analysis
```http
POST /api/v1/analysis/table
Content-Type: application/json

{
  "base_id": "appXXXXXXXXXXXXXX",
  "table_id": "tblXXXXXXXXXXXXXX",
  "table_name": "Customer Data",
  "fields": [...],
  "categories": ["structure", "field_types", "data_quality"],
  "record_count": 1500,
  "relationships": [...],
  "views": [...]
}
```

Response:
```json
{
  "table_id": "tblXXXXXXXXXXXXXX",
  "table_name": "Customer Data",
  "analysis_results": {
    "structure": [
      {
        "issue_type": "field_organization",
        "priority": "medium",
        "description": "Related fields are scattered across the table without logical grouping",
        "recommendation": "Group related fields together: contact information, address details, and preferences",
        "impact": "Improved user experience and data entry efficiency",
        "effort": "low",
        "estimated_improvement": "25% faster data entry",
        "implementation_steps": [
          "Identify field groupings",
          "Reorder fields in table",
          "Update forms and views"
        ],
        "confidence_score": 0.85
      }
    ]
  },
  "cost_summary": {
    "total_cost": 0.0234,
    "analysis_count": 3,
    "average_cost_per_analysis": 0.0078
  },
  "analysis_duration_seconds": 12.5,
  "timestamp": "1641234567"
}
```

#### Batch Analysis
```http
POST /api/v1/analysis/batch
Content-Type: application/json

{
  "tables": [...],
  "batch_size": 5,
  "max_concurrent": 3,
  "categories": ["structure", "normalization", "field_types"]
}
```

#### Workflow Endpoints

#### Complete Analysis Workflow
```http
POST /api/v1/workflow/start-complete-analysis
Content-Type: application/json

{
  "mcp_server_url": "http://mcp-server:8092",
  "airtable_base_id": "appMetadataBase",
  "metadata_table_id": "tblMetadataTable",
  "target_base_ids": ["appBase1", "appBase2"],
  "batch_size": 5,
  "max_concurrent": 3,
  "categories": null,
  "auto_update_airtable": true,
  "quality_threshold": 0.7
}
```

Response:
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started",
  "message": "Complete analysis workflow started"
}
```

#### Workflow Status
```http
GET /api/v1/workflow/status/{workflow_id}
```

Response:
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress": {
    "phase": "analyzing_tables",
    "completed": 15,
    "total": 35
  },
  "started_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:15:00Z"
}
```

## Prompt Engineering

### Structure Analysis Prompt Template
```
You are an expert Airtable database analyst. Analyze the following table structure and provide detailed improvement recommendations.

TABLE INFORMATION:
- Base ID: {base_id}
- Table Name: {table_name}
- Table ID: {table_id}
- Record Count: {record_count}

FIELDS:
{fields_json}

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

Respond in JSON format with an array of findings.
```

### Field Optimization Prompt Template
```
You are an Airtable field optimization specialist. Analyze field types and configurations for efficiency.

TABLE: {table_name}
FIELDS: {fields_json}

FIELD OPTIMIZATION ANALYSIS:
Examine each field for:

1. Field Type Optimization:
   - Incorrect field types for data content
   - Single line text vs. Long text efficiency
   - Number field precision and formatting
   - Date/DateTime field usage
   - Select vs. Multi-select appropriateness

2. Field Configuration:
   - Missing field descriptions
   - Inadequate validation rules
   - Inefficient formatting options
   - Default value opportunities

Identify specific improvements for data integrity, performance, and user experience.

Return JSON format with findings array.
```

## Cost Estimation

### Per-Table Analysis Cost
- **Structure Analysis**: ~$0.020
- **Normalization Analysis**: ~$0.025  
- **Field Types Analysis**: ~$0.015
- **Relationships Analysis**: ~$0.030
- **Performance Analysis**: ~$0.020
- **Data Quality Analysis**: ~$0.020

### Total Cost for 35 Tables
- **Complete Analysis (all categories)**: ~$4.55
- **Essential Analysis (3 categories)**: ~$2.28
- **Basic Analysis (structure only)**: ~$0.70

### Time Estimation
- **Per table analysis**: ~30 seconds
- **Complete workflow (35 tables)**: ~15-20 minutes
- **With error handling and retries**: ~25-30 minutes

## Quality Assurance

### Validation Checks
1. **Confidence Score Validation**: Minimum 0.5 threshold
2. **Content Quality**: Length, clarity, specificity checks
3. **Actionability**: Implementation steps, effort alignment
4. **Consistency**: Priority vs confidence alignment
5. **Category Alignment**: Content matches analysis category

### Quality Scoring
```python
quality_weights = {
    "confidence_score": 0.3,
    "content_quality": 0.25,
    "actionability": 0.2,
    "specificity": 0.15,
    "consistency": 0.1
}
```

### Filtering Thresholds
- **High Quality**: Score ≥ 0.8
- **Acceptable**: Score ≥ 0.7 (default threshold)
- **Review Required**: Score 0.5-0.7
- **Rejected**: Score < 0.5

## Error Handling & Fallback Strategies

### Error Categories
- **Network**: Connection issues, timeouts
- **API Limits**: Rate limiting, quota exceeded
- **Authentication**: API key issues
- **Parsing**: JSON decode errors
- **Validation**: Data validation failures

### Fallback Strategies

#### 1. Simplified Analysis Fallback
When complex analysis fails, use simplified prompts:
```json
{
  "fallback_used": true,
  "fallback_type": "simplified_analysis",
  "analysis_results": {
    "structure": [{
      "issue_type": "analysis_fallback",
      "priority": "medium",
      "description": "Full analysis failed. Manual review recommended.",
      "recommendation": "Perform manual analysis of table structure.",
      "confidence_score": 0.3
    }]
  }
}
```

#### 2. Cached Results Fallback
Use previous successful analysis results when available.

#### 3. Partial Results Fallback
Salvage partial analysis when response is incomplete.

### Circuit Breaker Pattern
- **Failure Threshold**: 5 consecutive failures
- **Timeout**: 60 seconds
- **Half-open**: Test single request after timeout

## Integration Flow

### Complete Workflow Steps

1. **Table Discovery**
   ```
   MCP Server: airtable_list_bases() → Get all accessible bases
   MCP Server: airtable_get_schema(base_id) → Get table schemas
   Extract: TableMetadata objects for analysis
   ```

2. **Batch Analysis**
   ```
   For each table:
     - Create analysis context
     - Execute category analyses with error handling
     - Apply quality validation
     - Store results
   ```

3. **Result Processing**
   ```
   Filter by quality threshold
   Categorize by priority (high/medium/low)
   Generate summary statistics
   Create improvement recommendations
   ```

4. **Airtable Updates**
   ```
   MCP Server: airtable_list_records() → Find metadata records
   MCP Server: airtable_update_records() → Update with results
   MCP Server: airtable_create_records() → Create new metadata
   ```

## Example Improvements by Pattern

### Common Table Structure Issues

#### 1. Poor Field Organization
**Problem**: Related fields scattered across table
**Recommendation**: Group contact info, addresses, preferences
**Impact**: 25% faster data entry
**Effort**: Low

#### 2. Inefficient Field Types
**Problem**: Using Long Text for short identifiers
**Recommendation**: Convert to Single Line Text with validation
**Impact**: Improved data consistency, faster queries
**Effort**: Medium

#### 3. Missing Relationships
**Problem**: Duplicate customer data across tables
**Recommendation**: Create Customer table with linked records
**Impact**: Eliminate data redundancy, improve consistency
**Effort**: High

#### 4. Complex Formulas
**Problem**: Nested formula causing performance issues
**Recommendation**: Break into multiple calculated fields
**Impact**: 40% faster table loading
**Effort**: Medium

#### 5. Data Quality Issues
**Problem**: Inconsistent date formats, missing validation
**Recommendation**: Add date field validation, standardize format
**Impact**: Reduce data entry errors by 60%
**Effort**: Low

## Production Deployment

### Environment Variables
```bash
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash-exp
TEMPERATURE=0.1
MAX_TOKENS=4000
THINKING_BUDGET=10000
RATE_LIMIT_RPM=60
```

### Docker Configuration
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ ./src/
EXPOSE 8003
CMD ["python", "-m", "src.main"]
```

### Health Monitoring
- Service health checks at `/api/v1/analysis/health`
- Cost tracking and budget alerts
- Error rate monitoring
- Quality score trending

## Security Considerations

1. **API Key Management**: Secure storage of Gemini API keys
2. **Rate Limiting**: Prevent API abuse
3. **Input Validation**: Sanitize all inputs
4. **Access Control**: Authenticate workflow requests
5. **Audit Logging**: Track all analysis activities

## Performance Optimization

### Batch Processing
- Process tables in batches of 5
- Maximum 3 concurrent analyses
- Rate limiting: 1 second between requests

### Caching Strategy
- Cache successful analysis results
- TTL: 24 hours for structure analysis
- Cache key: `{table_id}_{category}_{schema_hash}`

### Memory Management
- Stream large responses
- Cleanup resources after analysis
- Monitor memory usage during batch processing

This comprehensive workflow design ensures reliable, cost-effective, and high-quality table analysis with robust error handling and quality assurance mechanisms.
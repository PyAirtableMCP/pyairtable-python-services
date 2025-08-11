#!/usr/bin/env python3
"""
Example usage of the LLM-powered table analysis workflow

This script demonstrates how to use the table analysis system to analyze
Airtable tables and generate optimization recommendations.
"""

import asyncio
import json
import logging
from typing import Dict, List, Any
from datetime import datetime

# Import our services
from src.services.table_analysis import TableAnalysisService, AnalysisCategory, TableMetadata
from src.services.workflow_orchestrator import WorkflowOrchestrator, WorkflowConfig
from src.services.quality_assurance import QualityAssuranceService
from src.services.error_handling import ErrorHandlingService, ErrorContext

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_single_table_analysis():
    """
    Example: Analyze a single table
    """
    print("\n" + "="*50)
    print("EXAMPLE 1: Single Table Analysis")
    print("="*50)
    
    # Sample table metadata (this would come from MCP server in practice)
    sample_table = TableMetadata(
        base_id="appSampleBase123",
        table_id="tblCustomers456",
        table_name="Customer Database",
        fields=[
            {
                "id": "fldName",
                "name": "Full Name",
                "type": "singleLineText",
                "description": "Customer's full name"
            },
            {
                "id": "fldEmail",
                "name": "Email",
                "type": "email",
                "description": "Primary email address"
            },
            {
                "id": "fldPhone",
                "name": "Phone Number",
                "type": "singleLineText",
                "description": "Contact phone number"
            },
            {
                "id": "fldAddress",
                "name": "Full Address",
                "type": "multilineText",
                "description": "Complete mailing address"
            },
            {
                "id": "fldPurchaseHistory",
                "name": "Purchase History",
                "type": "multilineText",
                "description": "All purchase details"
            },
            {
                "id": "fldTotalSpent",
                "name": "Total Spent",
                "type": "currency",
                "options": {"precision": 2}
            }
        ],
        record_count=1250,
        relationships=[],
        views=[
            {"id": "viwAll", "name": "All Customers"},
            {"id": "viwVIP", "name": "VIP Customers"}
        ]
    )
    
    try:
        # Create analysis service
        analysis_service = TableAnalysisService()
        
        # Run comprehensive analysis
        print(f"Analyzing table: {sample_table.table_name}")
        results = await analysis_service.analyze_table_comprehensive(
            table_data=sample_table,
            categories=[
                AnalysisCategory.STRUCTURE,
                AnalysisCategory.FIELD_TYPES,
                AnalysisCategory.NORMALIZATION
            ]
        )
        
        # Display results
        print(f"\nAnalysis completed for {len(results)} categories:")
        
        for category, analysis_list in results.items():
            print(f"\n--- {category.upper()} ANALYSIS ---")
            for i, result in enumerate(analysis_list, 1):
                print(f"\nIssue {i}:")
                print(f"  Type: {result.issue_type}")
                print(f"  Priority: {result.priority}")
                print(f"  Description: {result.description}")
                print(f"  Recommendation: {result.recommendation}")
                print(f"  Impact: {result.impact}")
                print(f"  Effort: {result.effort}")
                print(f"  Confidence: {result.confidence_score}")
                print(f"  Implementation Steps:")
                for step in result.implementation_steps:
                    print(f"    - {step}")
        
        # Show cost summary
        cost_summary = analysis_service.get_cost_summary()
        print(f"\n--- COST SUMMARY ---")
        print(f"Total Cost: ${cost_summary['total_cost']}")
        print(f"Analyses Run: {cost_summary['analysis_count']}")
        print(f"Average Cost per Analysis: ${cost_summary['average_cost_per_analysis']}")
        
    except Exception as e:
        logger.error(f"Single table analysis failed: {e}")


async def example_quality_assurance():
    """
    Example: Quality assurance validation
    """
    print("\n" + "="*50)
    print("EXAMPLE 2: Quality Assurance Validation")
    print("="*50)
    
    # Sample analysis results for validation
    from src.services.table_analysis import AnalysisResult
    
    sample_results = {
        "tblSample": {
            AnalysisCategory.STRUCTURE: [
                AnalysisResult(
                    table_id="tblSample",
                    table_name="Sample Table",
                    category=AnalysisCategory.STRUCTURE,
                    priority="high",
                    issue_type="field_organization",
                    description="Related fields are not grouped logically, causing confusion during data entry and making the table harder to navigate.",
                    recommendation="Reorganize fields by grouping related information: contact details together, address information together, and financial data together.",
                    impact="Improved user experience, faster data entry, reduced errors",
                    effort="low",
                    estimated_improvement="25% reduction in data entry time",
                    implementation_steps=[
                        "Identify logical field groupings",
                        "Reorder fields in table view",
                        "Update any dependent forms and interfaces",
                        "Train users on new layout"
                    ],
                    confidence_score=0.85
                ),
                AnalysisResult(
                    table_id="tblSample",
                    table_name="Sample Table",
                    category=AnalysisCategory.STRUCTURE,
                    priority="low",
                    issue_type="poor_quality_example",
                    description="Bad example",  # Too short
                    recommendation="Do something",  # Too vague
                    impact="Maybe better",
                    effort="unknown",  # Invalid effort level
                    estimated_improvement="Some improvement",
                    implementation_steps=[],  # Missing steps
                    confidence_score=0.3  # Low confidence
                )
            ]
        }
    }
    
    try:
        # Create QA service
        qa_service = QualityAssuranceService()
        
        # Validate batch results
        print("Running quality assurance validation...")
        validation_summary = qa_service.validate_batch_results(sample_results)
        
        print(f"\n--- VALIDATION SUMMARY ---")
        print(f"Overall Quality Score: {validation_summary['overall_quality_score']:.2f}")
        print(f"Valid Analyses: {validation_summary['statistics']['valid_analyses']}")
        print(f"Warning Analyses: {validation_summary['statistics']['warning_analyses']}")
        print(f"Invalid Analyses: {validation_summary['statistics']['invalid_analyses']}")
        
        print(f"\n--- QUALITY ISSUES ---")
        for issue in validation_summary['quality_issues']:
            print(f"Table: {issue['table_id']}")
            print(f"Category: {issue['category']}")
            print(f"Issue: {issue['issue']}")
            print(f"Preview: {issue['analysis_preview']}")
            print()
        
        print(f"--- RECOMMENDATIONS ---")
        for rec in validation_summary['recommendations']:
            print(f"- {rec}")
        
    except Exception as e:
        logger.error(f"Quality assurance example failed: {e}")


async def example_error_handling():
    """
    Example: Error handling and fallback strategies
    """
    print("\n" + "="*50)
    print("EXAMPLE 3: Error Handling and Fallback")
    print("="*50)
    
    # Create error handling service
    error_service = ErrorHandlingService()
    
    # Simulate an operation that fails
    async def failing_operation():
        raise Exception("Simulated API rate limit error: quota exceeded")
    
    # Create error context
    context = ErrorContext(
        operation="table_analysis",
        table_id="tblTest123",
        table_name="Test Table",
        category="structure",
        max_attempts=3
    )
    
    try:
        print("Executing operation with error handling...")
        
        # This will fail and trigger fallback
        result = await error_service.execute_with_fallback(
            operation=failing_operation,
            context=context,
            fallback_strategy="simplified"
        )
        
        print(f"\n--- FALLBACK RESULT ---")
        print(f"Fallback Used: {result.get('fallback_used', False)}")
        print(f"Fallback Type: {result.get('fallback_type', 'none')}")
        
        if 'error_info' in result:
            print(f"Original Error: {result['error_info']['original_error']}")
            print(f"Error Category: {result['error_info']['error_category']}")
            print(f"Severity: {result['error_info']['severity']}")
        
    except Exception as e:
        logger.error(f"Error handling example failed: {e}")
    
    # Show error summary
    error_summary = error_service.get_error_summary()
    print(f"\n--- ERROR SUMMARY ---")
    print(f"Status: {error_summary['status']}")
    print(f"Total Errors: {error_summary['total_errors']}")
    
    if error_summary['total_errors'] > 0:
        print(f"Category Breakdown: {error_summary['category_breakdown']}")
        print(f"Severity Breakdown: {error_summary['severity_breakdown']}")
        
        print(f"\n--- ERROR RECOMMENDATIONS ---")
        for rec in error_service.get_error_recommendations():
            print(f"- {rec}")


async def example_cost_estimation():
    """
    Example: Cost estimation for different scenarios
    """
    print("\n" + "="*50)
    print("EXAMPLE 4: Cost Estimation")
    print("="*50)
    
    analysis_service = TableAnalysisService()
    
    scenarios = [
        {
            "name": "Complete Analysis (35 tables, all categories)",
            "table_count": 35,
            "categories": list(AnalysisCategory)
        },
        {
            "name": "Essential Analysis (35 tables, 3 key categories)",
            "table_count": 35,
            "categories": [AnalysisCategory.STRUCTURE, AnalysisCategory.FIELD_TYPES, AnalysisCategory.DATA_QUALITY]
        },
        {
            "name": "Structure Only (35 tables)",
            "table_count": 35,
            "categories": [AnalysisCategory.STRUCTURE]
        },
        {
            "name": "Small Base (5 tables, complete)",
            "table_count": 5,
            "categories": list(AnalysisCategory)
        }
    ]
    
    print("Cost estimates for different analysis scenarios:\n")
    
    for scenario in scenarios:
        estimate = analysis_service.estimate_batch_cost(
            table_count=scenario["table_count"],
            categories=scenario["categories"]
        )
        
        print(f"--- {scenario['name']} ---")
        print(f"Tables: {estimate['table_count']}")
        print(f"Categories: {estimate['categories_count']}")
        print(f"Estimated Total Cost: ${estimate['estimated_total_cost']}")
        print(f"Cost per Table: ${estimate['cost_per_table']}")
        print(f"Estimated Time: {estimate['estimated_time_minutes']:.1f} minutes")
        print()


async def example_workflow_simulation():
    """
    Example: Simulate complete workflow (without actual API calls)
    """
    print("\n" + "="*50)
    print("EXAMPLE 5: Complete Workflow Simulation")
    print("="*50)
    
    # This is a simulation - in practice you'd use real MCP server URLs
    print("Note: This is a simulation using mock data")
    print("In production, use actual MCP server and Airtable credentials\n")
    
    # Sample workflow configuration
    config = WorkflowConfig(
        mcp_server_url="http://localhost:8092",  # Mock URL
        airtable_base_id="appMetadataBase",
        metadata_table_id="tblTableMetadata",
        batch_size=3,
        max_concurrent=2,
        categories=[AnalysisCategory.STRUCTURE, AnalysisCategory.FIELD_TYPES],
        auto_update_airtable=False,  # Disabled for simulation
        quality_threshold=0.7
    )
    
    print(f"Workflow Configuration:")
    print(f"  MCP Server: {config.mcp_server_url}")
    print(f"  Metadata Base: {config.airtable_base_id}")
    print(f"  Batch Size: {config.batch_size}")
    print(f"  Max Concurrent: {config.max_concurrent}")
    print(f"  Categories: {[cat.value for cat in config.categories]}")
    print(f"  Quality Threshold: {config.quality_threshold}")
    
    print(f"\nIn a real workflow, this would:")
    print(f"1. Discover tables using MCP server")
    print(f"2. Run batch analysis on all discovered tables")
    print(f"3. Apply quality validation and filtering")
    print(f"4. Update Airtable metadata with results")
    print(f"5. Generate comprehensive summary report")
    
    # Show what the workflow summary would look like
    mock_summary = {
        "workflow_id": "workflow_1641234567",
        "status": "completed",
        "duration_seconds": 1245.7,
        "tables_discovered": 35,
        "tables_analyzed": 33,
        "tables_failed": 2,
        "cost_summary": {
            "total_cost": 2.34,
            "analysis_count": 66,
            "average_cost_per_analysis": 0.035
        },
        "airtable_updates": {
            "updated_records": 33,
            "failed_updates": 0,
            "errors": []
        },
        "failed_tables": [
            {"table_id": "tblProblem1", "error": "Timeout after 3 attempts"},
            {"table_id": "tblProblem2", "error": "Invalid schema format"}
        ]
    }
    
    print(f"\n--- MOCK WORKFLOW SUMMARY ---")
    print(json.dumps(mock_summary, indent=2))


async def main():
    """
    Run all examples
    """
    print("LLM-Powered Table Analysis Workflow Examples")
    print("=" * 60)
    
    examples = [
        ("Single Table Analysis", example_single_table_analysis),
        ("Quality Assurance", example_quality_assurance), 
        ("Error Handling", example_error_handling),
        ("Cost Estimation", example_cost_estimation),
        ("Workflow Simulation", example_workflow_simulation)
    ]
    
    for name, example_func in examples:
        try:
            print(f"\nRunning: {name}")
            await example_func()
        except Exception as e:
            logger.error(f"Example {name} failed: {e}")
            continue
    
    print("\n" + "="*60)
    print("All examples completed!")
    print("\nTo use this system in production:")
    print("1. Set up proper environment variables (GEMINI_API_KEY, etc.)")
    print("2. Configure MCP server with Airtable credentials")
    print("3. Start the LLM orchestrator service")
    print("4. Use the API endpoints to trigger analyses")
    print("5. Monitor costs and quality metrics")


if __name__ == "__main__":
    # Run examples
    asyncio.run(main())
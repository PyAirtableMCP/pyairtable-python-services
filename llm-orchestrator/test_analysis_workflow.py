#!/usr/bin/env python3
"""
Comprehensive test suite for the LLM-powered table analysis workflow

This script tests all components of the analysis system to ensure reliability
and quality of the analysis recommendations.
"""

import asyncio
import pytest
import json
import logging
from typing import Dict, List, Any
from unittest.mock import Mock, AsyncMock, patch

# Import our services for testing
from src.services.table_analysis import (
    TableAnalysisService, 
    AnalysisCategory, 
    TableMetadata, 
    AnalysisResult,
    PromptTemplates
)
from src.services.quality_assurance import QualityAssuranceService, ValidationResult
from src.services.error_handling import ErrorHandlingService, ErrorContext, ErrorCategory
from src.services.workflow_orchestrator import WorkflowOrchestrator, WorkflowConfig

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestTableAnalysisService:
    """Test suite for TableAnalysisService"""
    
    @pytest.fixture
    def sample_table_metadata(self):
        """Sample table metadata for testing"""
        return TableMetadata(
            base_id="appTestBase123",
            table_id="tblTestTable456",
            table_name="Test Customer Table",
            fields=[
                {
                    "id": "fldName",
                    "name": "Customer Name",
                    "type": "singleLineText"
                },
                {
                    "id": "fldEmail",
                    "name": "Email Address",
                    "type": "email"
                },
                {
                    "id": "fldNotes",
                    "name": "Customer Notes",
                    "type": "multilineText"
                }
            ],
            record_count=500
        )
    
    @pytest.fixture
    def mock_gemini_response(self):
        """Mock Gemini API response"""
        return {
            "choices": [{
                "message": {
                    "content": json.dumps([
                        {
                            "issue_type": "field_organization",
                            "priority": "medium",
                            "description": "Fields are not logically grouped",
                            "recommendation": "Group related fields together",
                            "impact": "Improved user experience",
                            "effort": "low",
                            "estimated_improvement": "20% faster data entry",
                            "implementation_steps": [
                                "Identify field groups",
                                "Reorder fields",
                                "Update views"
                            ],
                            "confidence_score": 0.85
                        }
                    ])
                }
            }],
            "usage": {
                "prompt_tokens": 150,
                "completion_tokens": 200,
                "total_tokens": 350,
                "cost": 0.025
            },
            "model": "gemini-2.0-flash-exp",
            "created": 1641234567
        }
    
    async def test_prompt_template_generation(self, sample_table_metadata):
        """Test prompt template generation"""
        templates = PromptTemplates()
        
        # Test structure analysis prompt
        prompt = templates.get_structure_analysis_prompt(sample_table_metadata)
        
        assert "Test Customer Table" in prompt
        assert "appTestBase123" in prompt
        assert "FIELDS:" in prompt
        assert "ANALYSIS FOCUS:" in prompt
        assert "JSON format" in prompt
        
        logger.info("✓ Prompt template generation test passed")
    
    async def test_analysis_result_parsing(self, mock_gemini_response, sample_table_metadata):
        """Test parsing of LLM responses into AnalysisResult objects"""
        service = TableAnalysisService()
        
        response_text = mock_gemini_response["choices"][0]["message"]["content"]
        
        results = service._parse_analysis_response(
            response_text,
            sample_table_metadata,
            AnalysisCategory.STRUCTURE
        )
        
        assert len(results) == 1
        result = results[0]
        
        assert result.table_id == sample_table_metadata.table_id
        assert result.table_name == sample_table_metadata.table_name
        assert result.category == AnalysisCategory.STRUCTURE
        assert result.priority == "medium"
        assert result.confidence_score == 0.85
        assert len(result.implementation_steps) == 3
        
        logger.info("✓ Analysis result parsing test passed")
    
    async def test_cost_estimation(self):
        """Test cost estimation accuracy"""
        service = TableAnalysisService()
        
        estimate = service.estimate_batch_cost(
            table_count=10,
            categories=[AnalysisCategory.STRUCTURE, AnalysisCategory.FIELD_TYPES]
        )
        
        assert estimate["table_count"] == 10
        assert estimate["categories_count"] == 2
        assert estimate["estimated_total_cost"] > 0
        assert estimate["cost_per_table"] > 0
        assert estimate["estimated_time_minutes"] > 0
        
        logger.info("✓ Cost estimation test passed")
    
    async def test_rate_limiting(self):
        """Test rate limiting functionality"""
        service = TableAnalysisService()
        
        # Test rate limiting delay
        import time
        start_time = time.time()
        
        await service._rate_limit()
        await service._rate_limit()
        
        elapsed = time.time() - start_time
        assert elapsed >= service.min_request_interval
        
        logger.info("✓ Rate limiting test passed")


class TestQualityAssuranceService:
    """Test suite for QualityAssuranceService"""
    
    @pytest.fixture
    def high_quality_result(self):
        """High quality analysis result for testing"""
        return AnalysisResult(
            table_id="tblTest",
            table_name="Test Table",
            category=AnalysisCategory.STRUCTURE,
            priority="high",
            issue_type="field_organization",
            description="Customer contact fields are scattered throughout the table, making data entry inefficient and increasing the likelihood of errors during data collection.",
            recommendation="Reorganize the table by grouping all contact-related fields (name, email, phone) together at the beginning of the table, followed by address fields, and then business-related information.",
            impact="Will reduce data entry time by approximately 30% and decrease data entry errors by 50%",
            effort="low",
            estimated_improvement="30% faster data entry, 50% fewer errors",
            implementation_steps=[
                "Identify all contact-related fields",
                "Reorder fields in logical groups",
                "Update data entry forms",
                "Train team on new layout"
            ],
            confidence_score=0.92
        )
    
    @pytest.fixture
    def low_quality_result(self):
        """Low quality analysis result for testing"""
        return AnalysisResult(
            table_id="tblTest",
            table_name="Test Table",
            category=AnalysisCategory.STRUCTURE,
            priority="high",
            issue_type="bad_structure",
            description="Bad",  # Too short
            recommendation="Fix it",  # Too vague
            impact="Better",  # Vague
            effort="unknown",  # Invalid
            estimated_improvement="Some improvement",  # Not quantified
            implementation_steps=[],  # Missing
            confidence_score=0.2  # Too low
        )
    
    async def test_high_quality_validation(self, high_quality_result):
        """Test validation of high-quality results"""
        qa_service = QualityAssuranceService()
        
        quality_checks = qa_service.validate_analysis_result(high_quality_result)
        
        # Should pass all quality checks
        valid_checks = [c for c in quality_checks if c.result == ValidationResult.VALID]
        assert len(valid_checks) >= 4  # Most checks should pass
        
        # Calculate overall score
        overall_score = qa_service._calculate_result_quality_score(quality_checks)
        assert overall_score >= 0.8  # High quality should score well
        
        logger.info("✓ High quality validation test passed")
    
    async def test_low_quality_validation(self, low_quality_result):
        """Test validation of low-quality results"""
        qa_service = QualityAssuranceService()
        
        quality_checks = qa_service.validate_analysis_result(low_quality_result)
        
        # Should fail multiple quality checks
        invalid_checks = [c for c in quality_checks if c.result == ValidationResult.INVALID]
        assert len(invalid_checks) >= 2  # Should have multiple failures
        
        # Calculate overall score
        overall_score = qa_service._calculate_result_quality_score(quality_checks)
        assert overall_score < 0.5  # Low quality should score poorly
        
        logger.info("✓ Low quality validation test passed")
    
    async def test_batch_validation(self, high_quality_result, low_quality_result):
        """Test batch result validation"""
        qa_service = QualityAssuranceService()
        
        batch_results = {
            "tblTest1": {
                AnalysisCategory.STRUCTURE: [high_quality_result]
            },
            "tblTest2": {
                AnalysisCategory.STRUCTURE: [low_quality_result]
            }
        }
        
        validation_summary = qa_service.validate_batch_results(batch_results)
        
        assert validation_summary["statistics"]["total_analyses"] == 2
        assert validation_summary["statistics"]["valid_analyses"] >= 1
        assert validation_summary["statistics"]["invalid_analyses"] >= 1
        assert len(validation_summary["quality_issues"]) >= 1
        assert len(validation_summary["recommendations"]) >= 1
        
        logger.info("✓ Batch validation test passed")


class TestErrorHandlingService:
    """Test suite for ErrorHandlingService"""
    
    async def test_error_categorization(self):
        """Test error categorization"""
        error_service = ErrorHandlingService()
        
        test_cases = [
            (Exception("Connection timeout"), ErrorCategory.TIMEOUT),
            (Exception("Rate limit exceeded"), ErrorCategory.API_LIMIT),
            (Exception("Authentication failed"), ErrorCategory.AUTHENTICATION),
            (Exception("JSON decode error"), ErrorCategory.PARSING),
            (Exception("Network unreachable"), ErrorCategory.NETWORK),
            (Exception("Unknown error"), ErrorCategory.UNKNOWN)
        ]
        
        for error, expected_category in test_cases:
            category = error_service._categorize_error(error)
            assert category == expected_category
        
        logger.info("✓ Error categorization test passed")
    
    async def test_retry_logic(self):
        """Test retry logic and backoff"""
        error_service = ErrorHandlingService()
        
        # Test retry decisions
        assert error_service._should_retry(Exception("Timeout")) == True
        assert error_service._should_retry(Exception("Rate limit")) == True
        assert error_service._should_retry(Exception("Authentication failed")) == False
        
        # Test backoff calculation
        delays = [error_service._calculate_retry_delay(i) for i in range(1, 4)]
        
        # Should increase with each attempt
        assert delays[1] > delays[0]
        assert delays[2] > delays[1]
        
        # Should not exceed max delay
        for delay in delays:
            assert delay <= error_service.retry_config["max_delay"]
        
        logger.info("✓ Retry logic test passed")
    
    async def test_fallback_execution(self):
        """Test fallback strategy execution"""
        error_service = ErrorHandlingService()
        
        # Create test context
        context = ErrorContext(
            operation="test_operation",
            table_id="tblTest",
            table_name="Test Table",
            max_attempts=2
        )
        
        # Test failing operation
        async def failing_operation():
            raise Exception("Simulated failure")
        
        # Execute with fallback
        result = await error_service.execute_with_fallback(
            operation=failing_operation,
            context=context,
            fallback_strategy="simplified"
        )
        
        assert result["fallback_used"] == True
        assert result["fallback_type"] == "simplified_analysis"
        assert "analysis_results" in result
        
        logger.info("✓ Fallback execution test passed")
    
    async def test_circuit_breaker(self):
        """Test circuit breaker functionality"""
        error_service = ErrorHandlingService()
        
        operation = "test_circuit_breaker"
        
        # Simulate multiple failures to trigger circuit breaker
        for i in range(6):  # Threshold is 5
            error_service._update_circuit_breaker(operation, Exception("Test failure"))
        
        # Circuit should be open
        assert error_service._is_circuit_open(operation) == True
        
        # Reset circuit breaker
        error_service._reset_circuit_breaker(operation)
        assert error_service._is_circuit_open(operation) == False
        
        logger.info("✓ Circuit breaker test passed")


class TestWorkflowIntegration:
    """Integration tests for the complete workflow"""
    
    async def test_workflow_configuration(self):
        """Test workflow configuration validation"""
        config = WorkflowConfig(
            mcp_server_url="http://test:8092",
            airtable_base_id="appTest",
            metadata_table_id="tblTest",
            batch_size=3,
            max_concurrent=2,
            categories=[AnalysisCategory.STRUCTURE],
            quality_threshold=0.7
        )
        
        assert config.batch_size == 3
        assert config.max_concurrent == 2
        assert len(config.categories) == 1
        assert config.quality_threshold == 0.7
        
        logger.info("✓ Workflow configuration test passed")
    
    async def test_table_metadata_extraction(self):
        """Test table metadata extraction from schema"""
        # This would normally test the _extract_relationships method
        # with real Airtable field data
        
        sample_fields = [
            {
                "id": "fldLink",
                "name": "Linked Records",
                "type": "multipleRecordLinks",
                "options": {
                    "linkedTableId": "tblOther",
                    "isReversed": False
                }
            },
            {
                "id": "fldLookup",
                "name": "Lookup Field",
                "type": "lookup",
                "options": {
                    "recordLinkFieldId": "fldLink",
                    "fieldIdInLinkedTable": "fldName"
                }
            }
        ]
        
        # Mock orchestrator to test relationship extraction
        config = WorkflowConfig(
            mcp_server_url="http://test:8092",
            airtable_base_id="appTest",
            metadata_table_id="tblTest"
        )
        
        orchestrator = WorkflowOrchestrator(config)
        relationships = orchestrator._extract_relationships(sample_fields)
        
        assert len(relationships) == 2
        assert relationships[0]["type"] == "link"
        assert relationships[1]["type"] == "lookup"
        
        logger.info("✓ Table metadata extraction test passed")


async def run_comprehensive_tests():
    """Run all test suites"""
    print("Running Comprehensive LLM Analysis Workflow Tests")
    print("=" * 60)
    
    test_suites = [
        ("Table Analysis Service", TestTableAnalysisService),
        ("Quality Assurance Service", TestQualityAssuranceService),
        ("Error Handling Service", TestErrorHandlingService),
        ("Workflow Integration", TestWorkflowIntegration)
    ]
    
    total_tests = 0
    passed_tests = 0
    
    for suite_name, test_class in test_suites:
        print(f"\n--- Testing {suite_name} ---")
        
        # Get test methods
        test_methods = [
            method for method in dir(test_class) 
            if method.startswith('test_') and callable(getattr(test_class, method))
        ]
        
        suite_instance = test_class()
        
        for test_method in test_methods:
            total_tests += 1
            
            try:
                # Setup fixtures if needed
                if hasattr(suite_instance, 'sample_table_metadata'):
                    suite_instance.sample_table_metadata = suite_instance.sample_table_metadata()
                if hasattr(suite_instance, 'mock_gemini_response'):
                    suite_instance.mock_gemini_response = suite_instance.mock_gemini_response()
                if hasattr(suite_instance, 'high_quality_result'):
                    suite_instance.high_quality_result = suite_instance.high_quality_result()
                if hasattr(suite_instance, 'low_quality_result'):
                    suite_instance.low_quality_result = suite_instance.low_quality_result()
                
                # Run test method
                test_func = getattr(suite_instance, test_method)
                
                # Handle both sync and async test methods
                if asyncio.iscoroutinefunction(test_func):
                    if hasattr(suite_instance, 'sample_table_metadata') and hasattr(suite_instance, 'mock_gemini_response'):
                        await test_func(suite_instance.sample_table_metadata, suite_instance.mock_gemini_response)
                    elif hasattr(suite_instance, 'high_quality_result') and hasattr(suite_instance, 'low_quality_result'):
                        await test_func(suite_instance.high_quality_result, suite_instance.low_quality_result)  
                    elif hasattr(suite_instance, 'sample_table_metadata'):
                        await test_func(suite_instance.sample_table_metadata)
                    elif hasattr(suite_instance, 'high_quality_result'):
                        await test_func(suite_instance.high_quality_result)
                    elif hasattr(suite_instance, 'low_quality_result'):
                        await test_func(suite_instance.low_quality_result)
                    else:
                        await test_func()
                else:
                    test_func()
                
                passed_tests += 1
                
            except Exception as e:
                logger.error(f"✗ {test_method} failed: {e}")
                continue
    
    # Test Summary
    print(f"\n" + "=" * 60)
    print(f"TEST SUMMARY")
    print(f"=" * 60)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print(f"\n🎉 All tests passed! The LLM analysis workflow is ready for production.")
    else:
        print(f"\n⚠️  Some tests failed. Review the implementation before deployment.")
    
    return passed_tests == total_tests


async def main():
    """Main test runner"""
    success = await run_comprehensive_tests()
    
    if success:
        print(f"\n✅ System Validation Complete")
        print(f"The LLM-powered table analysis workflow is functioning correctly.")
        print(f"\nNext steps:")
        print(f"1. Set up production environment variables")
        print(f"2. Configure MCP server with real Airtable credentials")
        print(f"3. Deploy the LLM orchestrator service")
        print(f"4. Run initial analysis on test data")
        print(f"5. Monitor performance and costs")
    else:
        print(f"\n❌ System Validation Failed")
        print(f"Please review and fix the failing tests before deployment.")


if __name__ == "__main__":
    asyncio.run(main())
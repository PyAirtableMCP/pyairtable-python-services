"""
Comprehensive error handling and fallback strategies for LLM analysis
"""
import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Callable, Union
from enum import Enum
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Error categories for classification"""
    NETWORK = "network"
    API_LIMIT = "api_limit"
    AUTHENTICATION = "authentication"
    PARSING = "parsing"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Context information for error handling"""
    operation: str
    table_id: Optional[str] = None
    table_name: Optional[str] = None
    category: Optional[str] = None
    attempt_number: int = 1
    max_attempts: int = 3
    additional_info: Optional[Dict[str, Any]] = None


@dataclass
class ErrorRecord:
    """Record of an error occurrence"""
    timestamp: float
    error_type: str
    error_message: str
    category: ErrorCategory
    severity: ErrorSeverity
    context: ErrorContext
    resolution: Optional[str] = None
    resolved: bool = False


class FallbackStrategy:
    """Base class for fallback strategies"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    async def execute(self, context: ErrorContext, error: Exception) -> Any:
        """Execute the fallback strategy"""
        raise NotImplementedError


class SimplifiedAnalysisFallback(FallbackStrategy):
    """Fallback to simplified analysis prompts"""
    
    def __init__(self):
        super().__init__(
            "simplified_analysis",
            "Use simplified prompts when complex analysis fails"
        )
    
    async def execute(self, context: ErrorContext, error: Exception) -> Dict[str, Any]:
        """Execute simplified analysis"""
        logger.info(f"Executing simplified analysis fallback for {context.table_name}")
        
        # Return a basic analysis structure
        return {
            "fallback_used": True,
            "fallback_type": self.name,
            "analysis_results": {
                "structure": [{
                    "issue_type": "analysis_fallback",
                    "priority": "medium",
                    "description": f"Full analysis failed for table {context.table_name}. Manual review recommended.",
                    "recommendation": "Perform manual analysis of this table structure and configuration.",
                    "impact": "Unknown - requires manual assessment",
                    "effort": "medium",
                    "estimated_improvement": "To be determined",
                    "implementation_steps": ["Schedule manual review", "Assess table structure", "Implement improvements"],
                    "confidence_score": 0.3
                }]
            },
            "error_info": {
                "original_error": str(error),
                "error_category": self._categorize_error(error).value,
                "severity": self._assess_severity(error).value
            }
        }
    
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize the error"""
        error_str = str(error).lower()
        
        if "timeout" in error_str or "timed out" in error_str:
            return ErrorCategory.TIMEOUT
        elif "rate limit" in error_str or "quota" in error_str:
            return ErrorCategory.API_LIMIT
        elif "authentication" in error_str or "unauthorized" in error_str:
            return ErrorCategory.AUTHENTICATION
        elif "json" in error_str or "parse" in error_str:
            return ErrorCategory.PARSING
        elif "network" in error_str or "connection" in error_str:
            return ErrorCategory.NETWORK
        else:
            return ErrorCategory.UNKNOWN
    
    def _assess_severity(self, error: Exception) -> ErrorSeverity:
        """Assess error severity"""
        category = self._categorize_error(error)
        
        severity_map = {
            ErrorCategory.CRITICAL: ErrorSeverity.CRITICAL,
            ErrorCategory.API_LIMIT: ErrorSeverity.HIGH,
            ErrorCategory.AUTHENTICATION: ErrorSeverity.HIGH,
            ErrorCategory.TIMEOUT: ErrorSeverity.MEDIUM,
            ErrorCategory.NETWORK: ErrorSeverity.MEDIUM,
            ErrorCategory.PARSING: ErrorSeverity.LOW,
            ErrorCategory.VALIDATION: ErrorSeverity.LOW,
            ErrorCategory.UNKNOWN: ErrorSeverity.MEDIUM
        }
        
        return severity_map.get(category, ErrorSeverity.MEDIUM)


class CachedResultsFallback(FallbackStrategy):
    """Fallback to cached previous results"""
    
    def __init__(self, cache_store: Optional[Dict[str, Any]] = None):
        super().__init__(
            "cached_results",
            "Use cached results from previous successful analyses"
        )
        self.cache_store = cache_store or {}
    
    async def execute(self, context: ErrorContext, error: Exception) -> Dict[str, Any]:
        """Execute cached results fallback"""
        cache_key = f"{context.table_id}_{context.category}"
        
        if cache_key in self.cache_store:
            logger.info(f"Using cached results for {context.table_name}")
            cached_result = self.cache_store[cache_key]
            
            # Add metadata about cache usage
            cached_result["fallback_used"] = True
            cached_result["fallback_type"] = self.name
            cached_result["cache_info"] = {
                "cached_at": cached_result.get("timestamp", "unknown"),
                "reason": f"Current analysis failed: {str(error)[:100]}"
            }
            
            return cached_result
        else:
            # No cache available, fall back to simplified analysis
            simplified_fallback = SimplifiedAnalysisFallback()
            return await simplified_fallback.execute(context, error)


class PartialResultsFallback(FallbackStrategy):
    """Fallback that salvages partial results from failed analysis"""
    
    def __init__(self):
        super().__init__(
            "partial_results",
            "Salvage partial results when full analysis fails"
        )
    
    async def execute(self, context: ErrorContext, error: Exception) -> Dict[str, Any]:
        """Execute partial results fallback"""
        logger.info(f"Attempting to salvage partial results for {context.table_name}")
        
        # Check if we have any partial data in the context
        partial_data = context.additional_info or {}
        
        if "partial_response" in partial_data:
            try:
                # Try to extract whatever we can from partial response
                partial_response = partial_data["partial_response"]
                
                # Attempt to parse partial JSON
                json_start = partial_response.find('[')
                json_end = partial_response.rfind(']')
                
                if json_start != -1 and json_end != -1:
                    partial_json = partial_response[json_start:json_end + 1]
                    partial_results = json.loads(partial_json)
                    
                    return {
                        "fallback_used": True,
                        "fallback_type": self.name,
                        "analysis_results": {
                            context.category or "unknown": partial_results
                        },
                        "partial_info": {
                            "partial_response_length": len(partial_response),
                            "extracted_results_count": len(partial_results),
                            "warning": "Results are incomplete due to analysis failure"
                        }
                    }
            except (json.JSONDecodeError, KeyError, TypeError) as parse_error:
                logger.warning(f"Failed to parse partial results: {parse_error}")
        
        # If we can't salvage anything, fall back to simplified analysis
        simplified_fallback = SimplifiedAnalysisFallback()
        return await simplified_fallback.execute(context, error)


class ErrorHandlingService:
    """Comprehensive error handling service with fallback strategies"""
    
    def __init__(self):
        self.error_records: List[ErrorRecord] = []
        self.fallback_strategies: Dict[str, FallbackStrategy] = {}
        self.retry_config = {
            "max_attempts": 3,
            "base_delay": 1.0,
            "max_delay": 30.0,
            "backoff_multiplier": 2.0
        }
        
        # Initialize fallback strategies
        self._setup_fallback_strategies()
        
        # Error pattern tracking
        self.error_patterns = {}
        self.circuit_breakers = {}
    
    def _setup_fallback_strategies(self):
        """Setup available fallback strategies"""
        self.fallback_strategies["simplified"] = SimplifiedAnalysisFallback()
        self.fallback_strategies["cached"] = CachedResultsFallback()
        self.fallback_strategies["partial"] = PartialResultsFallback()
    
    async def execute_with_fallback(
        self,
        operation: Callable,
        context: ErrorContext,
        fallback_strategy: str = "simplified"
    ) -> Any:
        """
        Execute operation with comprehensive error handling and fallback
        
        Args:
            operation: The operation to execute
            context: Error context information
            fallback_strategy: Which fallback strategy to use
            
        Returns:
            Operation result or fallback result
        """
        last_error = None
        
        for attempt in range(1, context.max_attempts + 1):
            try:
                context.attempt_number = attempt
                
                # Check circuit breaker
                if self._is_circuit_open(context.operation):
                    logger.warning(f"Circuit breaker open for {context.operation}")
                    break
                
                # Execute operation
                result = await operation()
                
                # Success - reset circuit breaker and return
                self._reset_circuit_breaker(context.operation)
                return result
                
            except Exception as error:
                last_error = error
                
                # Record error
                error_record = self._record_error(error, context)
                
                # Check if we should retry
                if attempt < context.max_attempts and self._should_retry(error):
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(f"Attempt {attempt} failed for {context.operation}. Retrying in {delay}s: {str(error)}")
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Update circuit breaker
                    self._update_circuit_breaker(context.operation, error)
                    break
        
        # All attempts failed - use fallback strategy
        logger.error(f"All attempts failed for {context.operation}. Using fallback strategy: {fallback_strategy}")
        
        fallback = self.fallback_strategies.get(fallback_strategy)
        if fallback:
            try:
                return await fallback.execute(context, last_error)
            except Exception as fallback_error:
                logger.error(f"Fallback strategy {fallback_strategy} also failed: {fallback_error}")
                # Use the most basic fallback
                basic_fallback = SimplifiedAnalysisFallback()
                return await basic_fallback.execute(context, last_error)
        else:
            logger.error(f"Unknown fallback strategy: {fallback_strategy}")
            raise last_error
    
    def _record_error(self, error: Exception, context: ErrorContext) -> ErrorRecord:
        """Record error occurrence"""
        error_record = ErrorRecord(
            timestamp=time.time(),
            error_type=type(error).__name__,
            error_message=str(error),
            category=self._categorize_error(error),
            severity=self._assess_error_severity(error, context),
            context=context
        )
        
        self.error_records.append(error_record)
        
        # Update error patterns
        pattern_key = f"{error_record.category.value}_{error_record.error_type}"
        self.error_patterns[pattern_key] = self.error_patterns.get(pattern_key, 0) + 1
        
        return error_record
    
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize error type"""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        if "timeout" in error_str or "timeout" in error_type:
            return ErrorCategory.TIMEOUT
        elif "rate" in error_str or "quota" in error_str or "limit" in error_str:
            return ErrorCategory.API_LIMIT
        elif "auth" in error_str or "unauthorized" in error_str or "forbidden" in error_str:
            return ErrorCategory.AUTHENTICATION
        elif "json" in error_str or "parse" in error_str or "decode" in error_str:
            return ErrorCategory.PARSING
        elif "network" in error_str or "connection" in error_str or "http" in error_type:
            return ErrorCategory.NETWORK
        elif "memory" in error_str or "resource" in error_str:
            return ErrorCategory.RESOURCE
        else:
            return ErrorCategory.UNKNOWN
    
    def _assess_error_severity(self, error: Exception, context: ErrorContext) -> ErrorSeverity:
        """Assess error severity based on error type and context"""
        category = self._categorize_error(error)
        
        # Base severity by category
        base_severity = {
            ErrorCategory.AUTHENTICATION: ErrorSeverity.HIGH,
            ErrorCategory.API_LIMIT: ErrorSeverity.HIGH,
            ErrorCategory.NETWORK: ErrorSeverity.MEDIUM,
            ErrorCategory.TIMEOUT: ErrorSeverity.MEDIUM,
            ErrorCategory.RESOURCE: ErrorSeverity.HIGH,
            ErrorCategory.PARSING: ErrorSeverity.LOW,
            ErrorCategory.VALIDATION: ErrorSeverity.LOW,
            ErrorCategory.UNKNOWN: ErrorSeverity.MEDIUM
        }.get(category, ErrorSeverity.MEDIUM)
        
        # Adjust based on context
        if context.attempt_number >= context.max_attempts:
            # Final attempt failure is more severe
            if base_severity == ErrorSeverity.LOW:
                base_severity = ErrorSeverity.MEDIUM
            elif base_severity == ErrorSeverity.MEDIUM:
                base_severity = ErrorSeverity.HIGH
        
        return base_severity
    
    def _should_retry(self, error: Exception) -> bool:
        """Determine if error is retryable"""
        category = self._categorize_error(error)
        
        # Generally retryable errors
        retryable_categories = {
            ErrorCategory.NETWORK,
            ErrorCategory.TIMEOUT,
            ErrorCategory.API_LIMIT,
            ErrorCategory.UNKNOWN
        }
        
        # Non-retryable errors
        non_retryable_categories = {
            ErrorCategory.AUTHENTICATION,
            ErrorCategory.VALIDATION
        }
        
        if category in non_retryable_categories:
            return False
        elif category in retryable_categories:
            return True
        else:
            # For parsing and resource errors, retry only once
            return True
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff"""
        delay = self.retry_config["base_delay"] * (
            self.retry_config["backoff_multiplier"] ** (attempt - 1)
        )
        return min(delay, self.retry_config["max_delay"])
    
    def _is_circuit_open(self, operation: str) -> bool:
        """Check if circuit breaker is open for operation"""
        circuit = self.circuit_breakers.get(operation, {})
        
        if not circuit.get("is_open", False):
            return False
        
        # Check if circuit should be reset (half-open)
        if time.time() - circuit.get("opened_at", 0) > circuit.get("timeout", 60):
            self.circuit_breakers[operation]["is_open"] = False
            self.circuit_breakers[operation]["half_open"] = True
            return False
        
        return True
    
    def _update_circuit_breaker(self, operation: str, error: Exception):
        """Update circuit breaker state"""
        if operation not in self.circuit_breakers:
            self.circuit_breakers[operation] = {
                "failure_count": 0,
                "is_open": False,
                "opened_at": 0,
                "timeout": 60,
                "threshold": 5
            }
        
        circuit = self.circuit_breakers[operation]
        circuit["failure_count"] += 1
        
        # Open circuit if threshold exceeded
        if circuit["failure_count"] >= circuit["threshold"]:
            circuit["is_open"] = True
            circuit["opened_at"] = time.time()
            logger.warning(f"Circuit breaker opened for {operation} after {circuit['failure_count']} failures")
    
    def _reset_circuit_breaker(self, operation: str):
        """Reset circuit breaker on success"""
        if operation in self.circuit_breakers:
            self.circuit_breakers[operation]["failure_count"] = 0
            self.circuit_breakers[operation]["is_open"] = False
            self.circuit_breakers[operation]["half_open"] = False
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get comprehensive error summary"""
        if not self.error_records:
            return {"status": "no_errors", "total_errors": 0}
        
        # Group errors by category and severity
        category_counts = {}
        severity_counts = {}
        recent_errors = []
        
        current_time = time.time()
        hour_ago = current_time - 3600
        
        for record in self.error_records:
            # Count by category
            category_counts[record.category.value] = category_counts.get(record.category.value, 0) + 1
            
            # Count by severity
            severity_counts[record.severity.value] = severity_counts.get(record.severity.value, 0) + 1
            
            # Recent errors (last hour)
            if record.timestamp > hour_ago:
                recent_errors.append({
                    "timestamp": record.timestamp,
                    "error_type": record.error_type,
                    "category": record.category.value,
                    "severity": record.severity.value,
                    "operation": record.context.operation,
                    "table_name": record.context.table_name
                })
        
        return {
            "status": "errors_recorded",
            "total_errors": len(self.error_records),
            "category_breakdown": category_counts,
            "severity_breakdown": severity_counts,
            "recent_errors": recent_errors,
            "error_patterns": self.error_patterns,
            "circuit_breakers": {
                op: {
                    "is_open": cb.get("is_open", False),
                    "failure_count": cb.get("failure_count", 0)
                }
                for op, cb in self.circuit_breakers.items()
            }
        }
    
    def get_error_recommendations(self) -> List[str]:
        """Get recommendations based on error patterns"""
        recommendations = []
        
        if not self.error_records:
            return recommendations
        
        # Analyze error patterns
        category_counts = {}
        for record in self.error_records:
            category_counts[record.category.value] = category_counts.get(record.category.value, 0) + 1
        
        total_errors = len(self.error_records)
        
        # API limit recommendations
        if category_counts.get("api_limit", 0) > total_errors * 0.2:
            recommendations.append("High rate of API limit errors. Consider implementing more aggressive rate limiting.")
        
        # Network recommendations
        if category_counts.get("network", 0) > total_errors * 0.3:
            recommendations.append("Frequent network errors. Check network stability and implement connection pooling.")
        
        # Timeout recommendations
        if category_counts.get("timeout", 0) > total_errors * 0.25:
            recommendations.append("Many timeout errors. Consider increasing timeout values or reducing request complexity.")
        
        # Parsing recommendations
        if category_counts.get("parsing", 0) > total_errors * 0.15:
            recommendations.append("Parsing errors detected. Review prompt engineering and response format expectations.")
        
        # Circuit breaker recommendations
        open_circuits = sum(1 for cb in self.circuit_breakers.values() if cb.get("is_open", False))
        if open_circuits > 0:
            recommendations.append(f"{open_circuits} circuit breakers are open. Monitor service health and consider manual intervention.")
        
        return recommendations
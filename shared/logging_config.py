"""
Structured logging configuration for PyAirtable services with Loki integration.

This module provides structured logging that integrates with the LGTM stack,
specifically Loki for log aggregation and correlation with traces.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import structlog
from structlog.typing import EventDict, Processor

try:
    from opentelemetry import trace
    from opentelemetry.trace import format_trace_id, format_span_id
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


class LokiLogFormatter:
    """Custom formatter for Loki-compatible JSON logs"""
    
    def __init__(self, service_name: str, service_version: str = "1.0.0"):
        self.service_name = service_name
        self.service_version = service_version
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.deployment_environment = os.getenv("DEPLOYMENT_ENVIRONMENT", "local")
    
    def __call__(self, logger: logging.Logger, method_name: str, event_dict: EventDict) -> str:
        """Format log entry for Loki"""
        
        # Get current span context if available
        trace_id = None
        span_id = None
        
        if OTEL_AVAILABLE:
            current_span = trace.get_current_span()
            if current_span.is_recording():
                span_context = current_span.get_span_context()
                trace_id = format_trace_id(span_context.trace_id)
                span_id = format_span_id(span_context.span_id)
        
        # Create structured log entry
        log_entry = {
            # Timestamp
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": event_dict.get("level", "info").upper(),
            
            # Service metadata
            "service": {
                "name": self.service_name,
                "version": self.service_version,
            },
            
            # Environment metadata
            "environment": self.environment,
            "deployment_environment": self.deployment_environment,
            
            # Log content
            "message": event_dict.get("event", ""),
            
            # Context
            "logger": logger.name,
            "module": event_dict.get("module", ""),
            "function": event_dict.get("function", ""),
            "line": event_dict.get("line", ""),
            
            # OpenTelemetry integration
            "trace_id": trace_id,
            "span_id": span_id,
            
            # Additional context
            "labels": {
                "service": self.service_name,
                "environment": self.environment,
                "level": event_dict.get("level", "info"),
            }
        }
        
        # Add any extra fields from the event
        extra_fields = {}
        for key, value in event_dict.items():
            if key not in ["event", "level", "timestamp", "module", "function", "line"]:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry["context"] = extra_fields
        
        # Add performance metrics if available
        if "duration_ms" in event_dict:
            log_entry["performance"] = {
                "duration_ms": event_dict["duration_ms"],
                "performance_bucket": self._get_performance_bucket(event_dict["duration_ms"])
            }
        
        # Add business context if available
        business_context = {}
        for field in ["user_id", "tenant_id", "api_key_hash", "cost_center"]:
            if field in event_dict:
                business_context[field] = event_dict[field]
        
        if business_context:
            log_entry["business"] = business_context
        
        # Add error details if this is an error log
        if event_dict.get("level") == "error" and "exception" in event_dict:
            log_entry["error"] = {
                "type": event_dict.get("exception_type", ""),
                "message": str(event_dict.get("exception", "")),
                "traceback": event_dict.get("traceback", "")
            }
        
        return json.dumps(log_entry, ensure_ascii=False, separators=(',', ':'))
    
    def _get_performance_bucket(self, duration_ms: float) -> str:
        """Categorize performance for monitoring"""
        if duration_ms < 100:
            return "fast"
        elif duration_ms < 500:
            return "normal"
        elif duration_ms < 2000:
            return "slow"
        elif duration_ms < 10000:
            return "very_slow"
        else:
            return "timeout_risk"


def add_trace_context(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add OpenTelemetry trace context to log events"""
    if not OTEL_AVAILABLE:
        return event_dict
    
    current_span = trace.get_current_span()
    if current_span.is_recording():
        span_context = current_span.get_span_context()
        event_dict["trace_id"] = format_trace_id(span_context.trace_id)
        event_dict["span_id"] = format_span_id(span_context.span_id)
    
    return event_dict


def add_caller_info(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add caller information to log events"""
    frame = sys._getframe(6)  # Adjust frame level as needed
    event_dict["module"] = frame.f_globals.get("__name__", "")
    event_dict["function"] = frame.f_code.co_name
    event_dict["line"] = frame.f_lineno
    return event_dict


def setup_structured_logging(
    service_name: str,
    service_version: str = "1.0.0",
    log_level: str = None,
    enable_loki: bool = True
) -> structlog.BoundLogger:
    """
    Setup structured logging for PyAirtable services
    
    Args:
        service_name: Name of the service
        service_version: Version of the service
        log_level: Log level (DEBUG, INFO, WARNING, ERROR)
        enable_loki: Whether to enable Loki-compatible formatting
    
    Returns:
        Configured structlog logger
    """
    
    # Get log level from environment or parameter
    log_level = log_level or os.getenv("LOG_LEVEL", "INFO")
    
    # Configure processors
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        add_trace_context,
        add_caller_info,
    ]
    
    # Add timestamp processor
    processors.append(structlog.processors.TimeStamper(fmt="iso"))
    
    if enable_loki:
        # Use Loki-compatible JSON formatter
        processors.append(LokiLogFormatter(service_name, service_version))
    else:
        # Use console formatter for development
        if os.getenv("ENVIRONMENT") == "development":
            processors.append(structlog.dev.ConsoleRenderer(colors=True))
        else:
            processors.append(structlog.processors.JSONRenderer())
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        logger_factory=structlog.WriteLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Create and return logger
    logger = structlog.get_logger(service_name)
    
    logger.info(
        "Structured logging initialized",
        service=service_name,
        version=service_version,
        log_level=log_level,
        loki_enabled=enable_loki,
        otel_available=OTEL_AVAILABLE
    )
    
    return logger


def log_request(
    logger: structlog.BoundLogger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None
):
    """Log HTTP request with structured data"""
    
    performance_bucket = "fast"
    if duration_ms > 100:
        performance_bucket = "normal"
    if duration_ms > 500:
        performance_bucket = "slow"
    if duration_ms > 2000:
        performance_bucket = "very_slow"
    if duration_ms > 10000:
        performance_bucket = "timeout_risk"
    
    log_data = {
        "http_method": method,
        "http_path": path,
        "http_status_code": status_code,
        "duration_ms": duration_ms,
        "performance_bucket": performance_bucket,
    }
    
    if user_id:
        log_data["user_id"] = user_id
    if tenant_id:
        log_data["tenant_id"] = tenant_id
    
    if status_code >= 500:
        logger.error("HTTP request failed", **log_data)
    elif status_code >= 400:
        logger.warning("HTTP request error", **log_data)
    else:
        logger.info("HTTP request completed", **log_data)


def log_database_query(
    logger: structlog.BoundLogger,
    operation: str,
    table: str,
    duration_ms: float,
    rows_affected: int = 0,
    error: Optional[Exception] = None
):
    """Log database query with structured data"""
    
    log_data = {
        "db_operation": operation,
        "db_table": table,
        "duration_ms": duration_ms,
        "rows_affected": rows_affected,
    }
    
    if error:
        logger.error(
            "Database query failed",
            exception=error,
            exception_type=type(error).__name__,
            **log_data
        )
    else:
        logger.info("Database query completed", **log_data)


def log_llm_call(
    logger: structlog.BoundLogger,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    duration_ms: float,
    error: Optional[Exception] = None
):
    """Log LLM API call with cost tracking"""
    
    log_data = {
        "ai_provider": provider,
        "ai_model": model,
        "ai_input_tokens": input_tokens,
        "ai_output_tokens": output_tokens,
        "ai_cost_usd": cost_usd,
        "ai_total_tokens": input_tokens + output_tokens,
        "duration_ms": duration_ms,
    }
    
    if error:
        logger.error(
            "LLM API call failed",
            exception=error,
            exception_type=type(error).__name__,
            **log_data
        )
    else:
        logger.info("LLM API call completed", **log_data)


def log_workflow_execution(
    logger: structlog.BoundLogger,
    workflow_id: str,
    workflow_type: str,
    status: str,
    duration_ms: float,
    steps_completed: int = 0,
    error: Optional[Exception] = None
):
    """Log workflow execution with structured data"""
    
    log_data = {
        "workflow_id": workflow_id,
        "workflow_type": workflow_type,
        "workflow_status": status,
        "duration_ms": duration_ms,
        "steps_completed": steps_completed,
    }
    
    if error:
        logger.error(
            "Workflow execution failed",
            exception=error,
            exception_type=type(error).__name__,
            **log_data
        )
    elif status == "completed":
        logger.info("Workflow execution completed", **log_data)
    else:
        logger.info("Workflow execution status", **log_data)


# Context managers for structured logging

class LogContext:
    """Context manager for adding structured context to logs"""
    
    def __init__(self, **context):
        self.context = context
    
    def __enter__(self):
        structlog.contextvars.bind_contextvars(**self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        structlog.contextvars.clear_contextvars()


# Example usage functions
def get_logger_for_service(service_name: str) -> structlog.BoundLogger:
    """Get a configured logger for a service"""
    return setup_structured_logging(
        service_name=service_name,
        service_version=os.getenv("SERVICE_VERSION", "1.0.0"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        enable_loki=os.getenv("ENVIRONMENT") != "development"
    )
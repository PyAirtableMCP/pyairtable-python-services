"""
Structured logging implementation with correlation ID support
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar

from .middleware import get_correlation_id, get_trace_id, get_span_id

# Context variables for logging
_log_context: ContextVar[Dict[str, Any]] = ContextVar('log_context', default={})


class TelemetryLogFormatter(logging.Formatter):
    """
    Custom log formatter that outputs structured JSON with trace context
    """
    
    def __init__(
        self,
        service_name: str,
        service_tier: str = "application",
        environment: str = None,
        include_source: bool = True,
    ):
        super().__init__()
        self.service_name = service_name
        self.service_tier = service_tier
        self.environment = environment or os.getenv("ENVIRONMENT", "development")
        self.include_source = include_source
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON"""
        
        # Base log structure
        log_entry = {
            "@timestamp": datetime.utcnow().isoformat() + "Z",
            "service": {
                "name": self.service_name,
                "tier": self.service_tier
            },
            "log": {
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            },
            "platform": {
                "name": "pyairtable",
                "environment": self.environment
            }
        }
        
        # Add correlation and trace context
        correlation_id = get_correlation_id()
        if correlation_id:
            log_entry["correlation"] = {"id": correlation_id}
        
        trace_id = get_trace_id()
        if trace_id:
            log_entry["trace"] = {"id": trace_id}
            
            span_id = get_span_id()
            if span_id:
                log_entry["trace"]["span_id"] = span_id
        
        # Add source information
        if self.include_source:
            log_entry["source"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
                "module": record.module,
            }
        
        # Add extra fields from log record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 
                          'pathname', 'filename', 'module', 'lineno', 'funcName', 
                          'created', 'msecs', 'relativeCreated', 'thread', 
                          'threadName', 'processName', 'process', 'message',
                          'exc_info', 'exc_text', 'stack_info']:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry["extra"] = extra_fields
        
        # Add context variables
        context = _log_context.get()
        if context:
            log_entry.update(context)
        
        # Add exception information
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None
            }
        
        # Add process information
        log_entry["process"] = {
            "pid": os.getpid(),
            "thread": record.thread,
            "thread_name": record.threadName
        }
        
        # Add cost tracking attributes
        cost_center = self._get_cost_center(self.service_tier)
        log_entry["cost"] = {
            "center": cost_center,
            "weight": self._get_log_weight(record.levelname)
        }
        
        return json.dumps(log_entry, default=str, separators=(',', ':'))
    
    def _get_cost_center(self, service_tier: str) -> str:
        """Map service tier to cost center"""
        cost_mapping = {
            "gateway": "gateway",
            "ai-ml": "ai-compute",
            "platform": "platform",
            "automation": "automation",
            "frontend": "frontend",
            "database": "infrastructure",
            "cache": "infrastructure",
            "observability": "observability"
        }
        return cost_mapping.get(service_tier, "application")
    
    def _get_log_weight(self, level: str) -> int:
        """Assign weight based on log level for cost tracking"""
        weights = {
            "DEBUG": 1,
            "INFO": 2,
            "WARNING": 4,
            "ERROR": 8,
            "CRITICAL": 16
        }
        return weights.get(level, 2)


def configure_structured_logging(
    service_name: str,
    service_tier: str = "application",
    level: str = "INFO",
    environment: str = None,
    include_source: bool = None,
) -> logging.Logger:
    """
    Configure structured logging for the service
    
    Args:
        service_name: Name of the service
        service_tier: Tier of the service
        level: Logging level
        environment: Environment (development, staging, production)
        include_source: Whether to include source file information
    
    Returns:
        Configured logger
    """
    
    # Set defaults based on environment
    environment = environment or os.getenv("ENVIRONMENT", "development")
    if include_source is None:
        include_source = environment == "development"
    
    # Create custom formatter
    formatter = TelemetryLogFormatter(
        service_name=service_name,
        service_tier=service_tier,
        environment=environment,
        include_source=include_source
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add stdout handler with structured formatting
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Configure specific loggers to reduce noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    return root_logger


def get_correlation_logger(
    name: str = None,
    extra_context: Dict[str, Any] = None
) -> logging.Logger:
    """
    Get a logger with automatic correlation ID context
    
    Args:
        name: Logger name (defaults to calling module)
        extra_context: Additional context to include in all log messages
    
    Returns:
        Logger with correlation context
    """
    
    logger = logging.getLogger(name)
    
    # Create adapter with correlation context
    class CorrelationAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            # Add correlation context
            extra = kwargs.get('extra', {})
            
            # Add correlation ID
            correlation_id = get_correlation_id()
            if correlation_id:
                extra['correlation_id'] = correlation_id
            
            # Add trace context
            trace_id = get_trace_id()
            if trace_id:
                extra['trace_id'] = trace_id
                
                span_id = get_span_id()
                if span_id:
                    extra['span_id'] = span_id
            
            # Add extra context
            if extra_context:
                extra.update(extra_context)
            
            # Add context variables
            context = _log_context.get()
            if context:
                extra.update(context)
            
            kwargs['extra'] = extra
            return msg, kwargs
    
    return CorrelationAdapter(logger, {})


def add_log_context(**kwargs):
    """Add context variables to all subsequent log messages in this context"""
    current_context = _log_context.get()
    new_context = {**current_context, **kwargs}
    _log_context.set(new_context)


def clear_log_context():
    """Clear all log context variables"""
    _log_context.set({})


def log_http_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: int,
    user_id: str = None,
    tenant_id: str = None,
    **extra
):
    """Log HTTP request with structured data"""
    logger.info(
        f"{method} {path} {status_code} {duration_ms}ms",
        extra={
            "http": {
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms
            },
            "user_id": user_id,
            "tenant_id": tenant_id,
            **extra
        }
    )


def log_database_operation(
    logger: logging.Logger,
    operation: str,
    table: str,
    duration_ms: int,
    rows_affected: int = None,
    **extra
):
    """Log database operation with structured data"""
    logger.info(
        f"Database {operation} on {table} completed in {duration_ms}ms",
        extra={
            "db": {
                "operation": operation,
                "table": table,
                "duration_ms": duration_ms,
                "rows_affected": rows_affected
            },
            "component": "database",
            **extra
        }
    )


def log_workflow_event(
    logger: logging.Logger,
    workflow_id: str,
    execution_id: str,
    step_name: str,
    status: str,
    duration_ms: int = None,
    **extra
):
    """Log workflow event with structured data"""
    logger.info(
        f"Workflow {workflow_id} step {step_name} {status}",
        extra={
            "workflow": {
                "id": workflow_id,
                "execution_id": execution_id,
                "step": step_name,
                "status": status,
                "duration_ms": duration_ms
            },
            "component": "workflow",
            **extra
        }
    )


def log_ai_operation(
    logger: logging.Logger,
    provider: str,
    model: str,
    operation: str,
    input_tokens: int = None,
    output_tokens: int = None,
    cost_usd: float = None,
    duration_ms: int = None,
    **extra
):
    """Log AI/ML operation with cost tracking"""
    logger.info(
        f"AI operation {operation} using {provider}/{model}",
        extra={
            "ai": {
                "provider": provider,
                "model": model,
                "operation": operation,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
                "duration_ms": duration_ms
            },
            "component": "ai-ml",
            **extra
        }
    )


def log_security_event(
    logger: logging.Logger,
    event_type: str,
    severity: str,
    user_id: str = None,
    ip_address: str = None,
    details: Dict[str, Any] = None,
    **extra
):
    """Log security event with appropriate severity"""
    level = logging.ERROR if severity in ["high", "critical"] else logging.WARNING
    
    logger.log(
        level,
        f"Security event: {event_type}",
        extra={
            "security": {
                "event_type": event_type,
                "severity": severity,
                "user_id": user_id,
                "ip_address": ip_address,
                "details": details
            },
            "component": "security",
            **extra
        }
    )
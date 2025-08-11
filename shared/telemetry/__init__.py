"""
PyAirtable Platform - Python Telemetry Library
Comprehensive OpenTelemetry instrumentation for Python services
"""

from .tracer import (
    initialize_telemetry,
    get_tracer,
    trace_function,
    trace_async_function,
    TraceContext,
    add_business_attributes,
    add_database_attributes,
    add_http_attributes,
    add_workflow_attributes,
    add_cost_attributes,
)

from .middleware import (
    FastAPITelemetryMiddleware,
    FlaskTelemetryMiddleware,
    add_correlation_id,
    get_correlation_id,
    get_trace_id,
    get_span_id,
)

from .logging import (
    configure_structured_logging,
    get_correlation_logger,
    TelemetryLogFormatter,
)

from .metrics import (
    initialize_metrics,
    create_counter,
    create_histogram,
    create_gauge,
    record_request_metrics,
    record_database_metrics,
    record_business_metrics,
)

__all__ = [
    # Tracing
    "initialize_telemetry",
    "get_tracer",
    "trace_function",
    "trace_async_function",
    "TraceContext",
    "add_business_attributes",
    "add_database_attributes",
    "add_http_attributes",
    "add_workflow_attributes",
    "add_cost_attributes",
    
    # Middleware
    "FastAPITelemetryMiddleware",
    "FlaskTelemetryMiddleware",
    "add_correlation_id",
    "get_correlation_id",
    "get_trace_id",
    "get_span_id",
    
    # Logging
    "configure_structured_logging",
    "get_correlation_logger",
    "TelemetryLogFormatter",
    
    # Metrics
    "initialize_metrics",
    "create_counter",
    "create_histogram",
    "create_gauge",
    "record_request_metrics",
    "record_database_metrics",
    "record_business_metrics",
]
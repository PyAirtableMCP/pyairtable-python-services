"""
OpenTelemetry tracing implementation for Python services
"""

import os
import functools
from typing import Optional, Dict, Any, Callable
from contextlib import contextmanager
import time
import asyncio

from opentelemetry import trace, baggage
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.propagators.composite import CompositeHTTPPropagator

# Global tracer instance
_tracer: Optional[trace.Tracer] = None


def initialize_telemetry(
    service_name: str,
    service_version: str = "1.0.0",
    service_tier: str = "application",
    environment: str = None,
    otlp_endpoint: str = None,
    sampling_ratio: float = None,
    resource_attributes: Dict[str, str] = None,
) -> trace.Tracer:
    """
    Initialize OpenTelemetry tracing for the service
    
    Args:
        service_name: Name of the service
        service_version: Version of the service
        service_tier: Tier of the service (gateway, platform, ai-ml, etc.)
        environment: Environment (development, staging, production)
        otlp_endpoint: OTLP collector endpoint
        sampling_ratio: Sampling ratio (0.0 to 1.0)
        resource_attributes: Additional resource attributes
    
    Returns:
        Configured tracer instance
    """
    global _tracer
    
    # Set defaults from environment
    environment = environment or os.getenv("ENVIRONMENT", "development")
    otlp_endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318")
    
    # Set sampling ratio based on environment
    if sampling_ratio is None:
        if environment == "development":
            sampling_ratio = 1.0  # 100% sampling in development
        elif environment == "staging":
            sampling_ratio = 0.5  # 50% sampling in staging
        else:
            sampling_ratio = 0.1  # 10% sampling in production
    
    # Create resource with service information
    resource_attrs = {
        ResourceAttributes.SERVICE_NAME: service_name,
        ResourceAttributes.SERVICE_VERSION: service_version,
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: environment,
        "platform.name": "pyairtable",
        "service.tier": service_tier,
    }
    
    # Add custom resource attributes
    if resource_attributes:
        resource_attrs.update(resource_attributes)
    
    resource = Resource.create(resource_attrs)
    
    # Create tracer provider
    tracer_provider = TracerProvider(resource=resource)
    
    # Create OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=True,  # Use insecure connection for development
        timeout=10,
    )
    
    # Add batch span processor
    span_processor = BatchSpanProcessor(
        otlp_exporter,
        max_queue_size=2048,
        max_export_batch_size=512,
        export_timeout_millis=30000,
        schedule_delay_millis=1000,
    )
    tracer_provider.add_span_processor(span_processor)
    
    # Set global tracer provider
    trace.set_tracer_provider(tracer_provider)
    
    # Set up propagators
    propagator = CompositeHTTPPropagator([
        TraceContextTextMapPropagator(),
        W3CBaggagePropagator(),
    ])
    
    # Create tracer
    _tracer = trace.get_tracer(
        instrumenting_module_name="pyairtable",
        instrumenting_library_version="1.0.0",
    )
    
    print(f"OpenTelemetry tracing initialized for {service_name}")
    print(f"Environment: {environment}")
    print(f"OTLP Endpoint: {otlp_endpoint}")
    print(f"Sampling Ratio: {sampling_ratio}")
    
    return _tracer


def get_tracer() -> trace.Tracer:
    """Get the global tracer instance"""
    if _tracer is None:
        raise RuntimeError("Telemetry not initialized. Call initialize_telemetry() first.")
    return _tracer


@contextmanager
def TraceContext(
    name: str,
    attributes: Dict[str, Any] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
):
    """
    Context manager for creating spans
    
    Args:
        name: Span name
        attributes: Span attributes
        kind: Span kind
    
    Yields:
        Active span
    """
    tracer = get_tracer()
    
    with tracer.start_as_current_span(name, kind=kind) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise


def trace_function(
    name: str = None,
    attributes: Dict[str, Any] = None,
    capture_args: bool = False,
    capture_result: bool = False,
):
    """
    Decorator for tracing synchronous functions
    
    Args:
        name: Span name (defaults to function name)
        attributes: Additional span attributes
        capture_args: Whether to capture function arguments
        capture_result: Whether to capture function result
    """
    def decorator(func: Callable) -> Callable:
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            
            with tracer.start_as_current_span(span_name) as span:
                # Add function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                # Add custom attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                
                # Capture arguments if requested
                if capture_args:
                    try:
                        # Capture positional args
                        if args:
                            span.set_attribute("function.args", str(args))
                        # Capture keyword args
                        if kwargs:
                            span.set_attribute("function.kwargs", str(kwargs))
                    except Exception:
                        # Ignore serialization errors
                        pass
                
                try:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    span.set_attribute("function.duration_ms", int(duration * 1000))
                    
                    # Capture result if requested
                    if capture_result:
                        try:
                            span.set_attribute("function.result", str(result))
                        except Exception:
                            # Ignore serialization errors
                            pass
                    
                    return result
                    
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        return wrapper
    return decorator


def trace_async_function(
    name: str = None,
    attributes: Dict[str, Any] = None,
    capture_args: bool = False,
    capture_result: bool = False,
):
    """
    Decorator for tracing asynchronous functions
    
    Args:
        name: Span name (defaults to function name)
        attributes: Additional span attributes
        capture_args: Whether to capture function arguments
        capture_result: Whether to capture function result
    """
    def decorator(func: Callable) -> Callable:
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            
            with tracer.start_as_current_span(span_name) as span:
                # Add function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                # Add custom attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                
                # Capture arguments if requested
                if capture_args:
                    try:
                        # Capture positional args
                        if args:
                            span.set_attribute("function.args", str(args))
                        # Capture keyword args
                        if kwargs:
                            span.set_attribute("function.kwargs", str(kwargs))
                    except Exception:
                        # Ignore serialization errors
                        pass
                
                try:
                    start_time = time.time()
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    span.set_attribute("function.duration_ms", int(duration * 1000))
                    
                    # Capture result if requested
                    if capture_result:
                        try:
                            span.set_attribute("function.result", str(result))
                        except Exception:
                            # Ignore serialization errors
                            pass
                    
                    return result
                    
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        return wrapper
    return decorator


def add_business_attributes(
    span: trace.Span,
    user_id: str = None,
    tenant_id: str = None,
    correlation_id: str = None,
    cost_center: str = None,
):
    """Add business context attributes to a span"""
    if user_id:
        span.set_attribute("user.id", user_id)
    if tenant_id:
        span.set_attribute("tenant.id", tenant_id)
    if correlation_id:
        span.set_attribute("correlation.id", correlation_id)
    if cost_center:
        span.set_attribute("cost.center", cost_center)


def add_database_attributes(
    span: trace.Span,
    operation: str,
    table: str = None,
    duration_ms: int = None,
    rows_affected: int = None,
):
    """Add database operation attributes to a span"""
    span.set_attribute("db.operation", operation)
    if table:
        span.set_attribute("db.table", table)
    if duration_ms is not None:
        span.set_attribute("db.duration_ms", duration_ms)
    if rows_affected is not None:
        span.set_attribute("db.rows_affected", rows_affected)
    span.set_attribute("component", "database")


def add_http_attributes(
    span: trace.Span,
    method: str,
    url: str = None,
    status_code: int = None,
    duration_ms: int = None,
):
    """Add HTTP request attributes to a span"""
    span.set_attribute("http.method", method)
    if url:
        span.set_attribute("http.url", url)
    if status_code is not None:
        span.set_attribute("http.status_code", status_code)
    if duration_ms is not None:
        span.set_attribute("http.duration_ms", duration_ms)


def add_workflow_attributes(
    span: trace.Span,
    workflow_id: str,
    execution_id: str = None,
    step_name: str = None,
):
    """Add workflow execution attributes to a span"""
    span.set_attribute("workflow.id", workflow_id)
    if execution_id:
        span.set_attribute("workflow.execution_id", execution_id)
    if step_name:
        span.set_attribute("workflow.step", step_name)
    span.set_attribute("component", "workflow")


def add_cost_attributes(
    span: trace.Span,
    cost_center: str,
    weight: int = 1,
):
    """Add cost tracking attributes to a span"""
    span.set_attribute("cost.center", cost_center)
    span.set_attribute("cost.weight", weight)
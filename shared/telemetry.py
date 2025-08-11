"""
OpenTelemetry instrumentation for PyAirtable Python services.

This module provides comprehensive tracing, metrics, and logging instrumentation
with cost-aware sampling and business metrics tracking.
"""

import functools
import logging
import os
import time
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from opentelemetry import baggage, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.propagators.composite import CompositeHTTPPropagator
from opentelemetry.propagators.jaeger import JaegerPropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import Status, StatusCode


class TelemetryConfig:
    """Configuration for OpenTelemetry telemetry."""
    
    def __init__(
        self,
        service_name: str,
        service_version: str = "1.0.0",
        service_tier: str = "application",
        environment: str = None,
        otlp_endpoint: str = None,
        jaeger_endpoint: str = None,
        sampling_ratio: float = 0.1,
        enable_debug: bool = False,
        resource_attributes: Optional[Dict[str, str]] = None,
    ):
        self.service_name = service_name
        self.service_version = service_version or os.getenv("SERVICE_VERSION", "1.0.0")
        self.service_tier = service_tier or os.getenv("SERVICE_TIER", "application")
        self.environment = environment or os.getenv("ENVIRONMENT", "development")
        self.otlp_endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
        self.jaeger_endpoint = jaeger_endpoint or os.getenv("JAEGER_ENDPOINT", "http://jaeger-all-in-one:14268/api/traces")
        self.sampling_ratio = float(os.getenv("OTEL_SAMPLING_RATIO", str(sampling_ratio)))
        self.enable_debug = enable_debug or os.getenv("OTEL_DEBUG", "false").lower() == "true"
        self.resource_attributes = resource_attributes or {}


class PyAirtableTelemetry:
    """Main telemetry class for PyAirtable services."""
    
    def __init__(self, config: TelemetryConfig):
        self.config = config
        self.tracer_provider = None
        self.tracer = None
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
    def _setup_logging(self):
        """Setup structured logging."""
        logging.basicConfig(
            level=logging.DEBUG if self.config.enable_debug else logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
    def initialize(self) -> trace.Tracer:
        """Initialize OpenTelemetry tracing with comprehensive instrumentation."""
        
        # Create resource with service information
        resource_attrs = {
            "service.name": self.config.service_name,
            "service.version": self.config.service_version,
            "service.tier": self.config.service_tier,
            "deployment.environment": self.config.environment,
            "platform.name": "pyairtable",
            "platform.cluster": "pyairtable-platform",
        }
        resource_attrs.update(self.config.resource_attributes)
        
        resource = Resource.create(resource_attrs)
        
        # Configure sampling
        if self.config.environment == "production":
            sampler = ParentBased(TraceIdRatioBased(self.config.sampling_ratio))
        else:
            sampler = ParentBased(TraceIdRatioBased(1.0))  # Always sample in dev
            
        # Create tracer provider
        self.tracer_provider = TracerProvider(resource=resource, sampler=sampler)
        
        # Setup exporters
        self._setup_exporters()
        
        # Set global tracer provider
        trace.set_tracer_provider(self.tracer_provider)
        
        # Setup propagators for context propagation
        set_global_textmap(CompositeHTTPPropagator([
            B3MultiFormat(),
            JaegerPropagator(),
        ]))
        
        # Auto-instrument libraries
        self._setup_auto_instrumentation()
        
        # Get tracer
        self.tracer = trace.get_tracer(
            instrumenting_module_name=self.config.service_name,
            instrumenting_library_version=self.config.service_version,
        )
        
        self.logger.info(
            f"OpenTelemetry initialized for {self.config.service_name} "
            f"(env: {self.config.environment}, sampling: {self.config.sampling_ratio})"
        )
        
        return self.tracer
    
    def _setup_exporters(self):
        """Setup trace exporters."""
        processors = []
        
        # OTLP exporter (primary)
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=self.config.otlp_endpoint, insecure=True)
            processors.append(BatchSpanProcessor(otlp_exporter))
            self.logger.info(f"OTLP exporter configured: {self.config.otlp_endpoint}")
        except Exception as e:
            self.logger.warning(f"Failed to configure OTLP exporter: {e}")
        
        # Jaeger exporter (fallback)
        try:
            jaeger_exporter = JaegerExporter(
                agent_host_name="jaeger-all-in-one",
                agent_port=6831,
            )
            processors.append(BatchSpanProcessor(jaeger_exporter))
            self.logger.info("Jaeger exporter configured")
        except Exception as e:
            self.logger.warning(f"Failed to configure Jaeger exporter: {e}")
        
        # Add processors to tracer provider
        for processor in processors:
            self.tracer_provider.add_span_processor(processor)
    
    def _setup_auto_instrumentation(self):
        """Setup automatic instrumentation for common libraries."""
        try:
            # FastAPI instrumentation
            FastAPIInstrumentor().instrument()
            
            # HTTP client instrumentation
            HTTPXClientInstrumentor().instrument()
            
            # Database instrumentation
            SQLAlchemyInstrumentor().instrument()
            AsyncPGInstrumentor().instrument()
            
            # Redis instrumentation
            RedisInstrumentor().instrument()
            
            # Logging instrumentation
            LoggingInstrumentor().instrument()
            
            # System metrics (if available)
            try:
                SystemMetricsInstrumentor().instrument()
            except Exception as e:
                self.logger.debug(f"System metrics instrumentation not available: {e}")
                
            self.logger.info("Auto-instrumentation configured")
            
        except Exception as e:
            self.logger.error(f"Failed to setup auto-instrumentation: {e}")
    
    def shutdown(self):
        """Shutdown telemetry gracefully."""
        if self.tracer_provider:
            self.tracer_provider.shutdown()
            self.logger.info("Telemetry shutdown complete")


# Decorators and helper functions

def trace_function(
    name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True
):
    """Decorator to trace function calls."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = name or f"{func.__module__}.{func.__name__}"
            
            with tracer.start_as_current_span(span_name) as span:
                # Add custom attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                
                # Add function metadata
                span.set_attribute("code.function", func.__name__)
                span.set_attribute("code.module", func.__module__)
                
                try:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    # Record performance metrics
                    span.set_attribute("function.duration_ms", duration * 1000)
                    span.set_status(Status(StatusCode.OK))
                    
                    return result
                    
                except Exception as e:
                    if record_exception:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
                    
        return wrapper
    return decorator


async def trace_async_function(
    name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True
):
    """Decorator to trace async function calls."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = name or f"{func.__module__}.{func.__name__}"
            
            with tracer.start_as_current_span(span_name) as span:
                # Add custom attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                
                # Add function metadata
                span.set_attribute("code.function", func.__name__)
                span.set_attribute("code.module", func.__module__)
                
                try:
                    start_time = time.time()
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    # Record performance metrics
                    span.set_attribute("function.duration_ms", duration * 1000)
                    span.set_status(Status(StatusCode.OK))
                    
                    return result
                    
                except Exception as e:
                    if record_exception:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
                    
        return wrapper
    return decorator


def add_ai_attributes(
    span: trace.Span,
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0
):
    """Add AI/ML specific attributes to a span."""
    span.set_attribute("ai.provider", provider)
    span.set_attribute("ai.model", model)
    span.set_attribute("ai.input_tokens", input_tokens)
    span.set_attribute("ai.output_tokens", output_tokens)
    span.set_attribute("ai.cost_usd", cost_usd)
    span.set_attribute("ai.tier", "llm")


def add_database_attributes(
    span: trace.Span,
    operation: str,
    table: str,
    rows_affected: int = 0,
    query: Optional[str] = None
):
    """Add database operation attributes to a span."""
    span.set_attribute(SpanAttributes.DB_SYSTEM, "postgresql")
    span.set_attribute(SpanAttributes.DB_OPERATION, operation)
    span.set_attribute(SpanAttributes.DB_SQL_TABLE, table)
    span.set_attribute("db.rows_affected", rows_affected)
    
    # Only include query in development
    if query and os.getenv("ENVIRONMENT") != "production":
        span.set_attribute(SpanAttributes.DB_STATEMENT, query)


def add_workflow_attributes(
    span: trace.Span,
    workflow_id: str,
    workflow_type: str,
    status: str,
    duration: Optional[float] = None
):
    """Add workflow execution attributes to a span."""
    span.set_attribute("workflow.id", workflow_id)
    span.set_attribute("workflow.type", workflow_type)
    span.set_attribute("workflow.status", status)
    if duration:
        span.set_attribute("workflow.duration_ms", duration * 1000)


def add_business_attributes(
    span: trace.Span,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    api_key_hash: Optional[str] = None,
    cost_center: Optional[str] = None
):
    """Add business context attributes to a span."""
    if user_id:
        span.set_attribute("user.id", user_id)
    if tenant_id:
        span.set_attribute("tenant.id", tenant_id)
    if api_key_hash:
        span.set_attribute("api.key_hash", api_key_hash)
    if cost_center:
        span.set_attribute("cost.center", cost_center)


def get_performance_bucket(duration_ms: float) -> str:
    """Categorize request duration for monitoring."""
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


def extract_service_from_path(path: str) -> str:
    """Determine service type from request path."""
    path_lower = path.lower()
    
    if any(keyword in path_lower for keyword in ["/ai", "/llm", "/chat", "/generate"]):
        return "ai-ml"
    elif any(keyword in path_lower for keyword in ["/auth", "/login", "/register", "/token"]):
        return "auth"
    elif any(keyword in path_lower for keyword in ["/workflow", "/automation", "/file"]):
        return "automation"
    elif any(keyword in path_lower for keyword in ["/airtable", "/table", "/record"]):
        return "airtable"
    elif any(keyword in path_lower for keyword in ["/analytics", "/metrics", "/reports"]):
        return "analytics"
    else:
        return "platform"


def hash_api_key(api_key: str) -> str:
    """Create a privacy-safe hash of API key for tracking."""
    if len(api_key) < 8:
        return "short_key"
    return f"{api_key[:3]}***{api_key[-3:]}"


# Context managers

class TraceContext:
    """Context manager for creating traced operations."""
    
    def __init__(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL
    ):
        self.name = name
        self.attributes = attributes or {}
        self.kind = kind
        self.span = None
        self.tracer = trace.get_tracer(__name__)
    
    def __enter__(self):
        self.span = self.tracer.start_span(self.name, kind=self.kind)
        for key, value in self.attributes.items():
            self.span.set_attribute(key, value)
        return self.span
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.span.record_exception(exc_val)
            self.span.set_status(Status(StatusCode.ERROR, str(exc_val)))
        else:
            self.span.set_status(Status(StatusCode.OK))
        self.span.end()


# Factory function for easy initialization
def initialize_telemetry(
    service_name: str,
    service_version: str = "1.0.0",
    service_tier: str = "application",
    **kwargs
) -> trace.Tracer:
    """Initialize telemetry with sensible defaults."""
    config = TelemetryConfig(
        service_name=service_name,
        service_version=service_version,
        service_tier=service_tier,
        **kwargs
    )
    
    telemetry = PyAirtableTelemetry(config)
    return telemetry.initialize()
"""
HTTP middleware for automatic tracing instrumentation
"""

import time
import uuid
from typing import Optional, List, Dict, Any
from contextvars import ContextVar

from opentelemetry import trace, baggage, context as otel_context
from opentelemetry.trace import Status, StatusCode, SpanKind
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.propagators import extract

from .tracer import get_tracer

# Context variables for request correlation
_correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')
_trace_id: ContextVar[str] = ContextVar('trace_id', default='')
_span_id: ContextVar[str] = ContextVar('span_id', default='')


class FastAPITelemetryMiddleware:
    """
    FastAPI middleware for automatic OpenTelemetry tracing
    """
    
    def __init__(
        self,
        app,
        service_name: str,
        service_tier: str = "application",
        skip_paths: List[str] = None,
        capture_headers: List[str] = None,
        capture_body: bool = False,
        max_body_size: int = 1024,
    ):
        self.app = app
        self.service_name = service_name
        self.service_tier = service_tier
        self.skip_paths = skip_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
        self.capture_headers = capture_headers or [
            "user-agent",
            "content-type",
            "accept",
            "x-forwarded-for",
            "x-real-ip",
        ]
        self.capture_body = capture_body
        self.max_body_size = max_body_size
        self.tracer = get_tracer()
        self.propagator = TraceContextTextMapPropagator()
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Skip certain paths
        path = scope.get("path", "")
        if path in self.skip_paths:
            await self.app(scope, receive, send)
            return
        
        # Extract or generate correlation ID
        headers = dict(scope.get("headers", []))
        correlation_id = headers.get(b"x-correlation-id", b"").decode()
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Extract trace context from headers
        header_dict = {k.decode(): v.decode() for k, v in headers.items()}
        ctx = extract(header_dict)
        
        # Create span
        method = scope.get("method", "GET")
        path_info = scope.get("path", "/")
        span_name = f"{method} {path_info}"
        
        with self.tracer.start_as_current_span(
            span_name,
            context=ctx,
            kind=SpanKind.SERVER,
        ) as span:
            # Set correlation ID in context
            _correlation_id.set(correlation_id)
            _trace_id.set(span.get_span_context().trace_id.to_bytes(16, 'big').hex())
            _span_id.set(span.get_span_context().span_id.to_bytes(8, 'big').hex())
            
            # Add basic attributes
            span.set_attribute("http.method", method)
            span.set_attribute("http.url", str(scope.get("server", ["", ""])[0]) + path_info)
            span.set_attribute("http.scheme", scope.get("scheme", "http"))
            span.set_attribute("http.target", path_info)
            span.set_attribute("service.name", self.service_name)
            span.set_attribute("service.tier", self.service_tier)
            span.set_attribute("correlation.id", correlation_id)
            span.set_attribute("request.id", correlation_id)
            
            # Add client information
            if "client" in scope:
                client_host, client_port = scope["client"]
                span.set_attribute("net.peer.ip", client_host)
                span.set_attribute("net.peer.port", client_port)
            
            # Add captured headers
            for header_name in self.capture_headers:
                header_value = headers.get(header_name.encode(), b"").decode()
                if header_value:
                    span.set_attribute(f"http.request.header.{header_name}", header_value)
            
            # Add query parameters
            query_string = scope.get("query_string", b"").decode()
            if query_string:
                span.set_attribute("http.query", query_string)
            
            # Capture request body if configured
            body = b""
            if self.capture_body:
                async def receive_wrapper():
                    nonlocal body
                    message = await receive()
                    if message["type"] == "http.request" and "body" in message:
                        body += message["body"]
                    return message
                
                receive = receive_wrapper
            
            # Process request
            start_time = time.time()
            status_code = 500  # Default to error
            
            async def send_wrapper(message):
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                    
                    # Add response headers for tracing
                    headers = message.get("headers", [])
                    headers.extend([
                        (b"x-trace-id", _trace_id.get().encode()),
                        (b"x-span-id", _span_id.get().encode()),
                        (b"x-correlation-id", correlation_id.encode()),
                    ])
                    message["headers"] = headers
                
                await send(message)
            
            try:
                await self.app(scope, receive, send_wrapper)
                
                # Set successful status
                if status_code < 400:
                    span.set_status(Status(StatusCode.OK))
                else:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {status_code}"))
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
            
            finally:
                # Calculate duration and add final attributes
                duration = time.time() - start_time
                span.set_attribute("http.status_code", status_code)
                span.set_attribute("http.request.duration_ms", int(duration * 1000))
                
                # Capture request body if configured and within size limit
                if self.capture_body and body and len(body) <= self.max_body_size:
                    try:
                        span.set_attribute("http.request.body", body.decode())
                    except UnicodeDecodeError:
                        span.set_attribute("http.request.body", "<binary>")


class FlaskTelemetryMiddleware:
    """
    Flask middleware for automatic OpenTelemetry tracing
    """
    
    def __init__(
        self,
        app,
        service_name: str,
        service_tier: str = "application",
        skip_paths: List[str] = None,
        capture_headers: List[str] = None,
    ):
        self.app = app
        self.service_name = service_name
        self.service_tier = service_tier
        self.skip_paths = skip_paths or ["/health", "/metrics"]
        self.capture_headers = capture_headers or [
            "User-Agent",
            "Content-Type",
            "Accept",
            "X-Forwarded-For",
            "X-Real-IP",
        ]
        self.tracer = get_tracer()
        self.propagator = TraceContextTextMapPropagator()
        
        # Install Flask hooks
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        app.teardown_request(self._teardown_request)
    
    def _before_request(self):
        from flask import request, g
        
        # Skip certain paths
        if request.path in self.skip_paths:
            return
        
        # Extract or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Extract trace context
        ctx = extract(dict(request.headers))
        
        # Create span
        span_name = f"{request.method} {request.path}"
        span = self.tracer.start_span(
            span_name,
            context=ctx,
            kind=SpanKind.SERVER,
        )
        
        # Store in Flask g object
        g.telemetry_span = span
        g.correlation_id = correlation_id
        g.start_time = time.time()
        
        # Set context variables
        _correlation_id.set(correlation_id)
        _trace_id.set(span.get_span_context().trace_id.to_bytes(16, 'big').hex())
        _span_id.set(span.get_span_context().span_id.to_bytes(8, 'big').hex())
        
        # Add basic attributes
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", request.url)
        span.set_attribute("http.scheme", request.scheme)
        span.set_attribute("http.target", request.path)
        span.set_attribute("service.name", self.service_name)
        span.set_attribute("service.tier", self.service_tier)
        span.set_attribute("correlation.id", correlation_id)
        span.set_attribute("request.id", correlation_id)
        
        # Add client information
        span.set_attribute("net.peer.ip", request.remote_addr or "unknown")
        
        # Add captured headers
        for header_name in self.capture_headers:
            header_value = request.headers.get(header_name)
            if header_value:
                span.set_attribute(f"http.request.header.{header_name.lower()}", header_value)
        
        # Add query parameters
        if request.query_string:
            span.set_attribute("http.query", request.query_string.decode())
    
    def _after_request(self, response):
        from flask import g
        
        if not hasattr(g, 'telemetry_span'):
            return response
        
        # Add response headers for tracing
        response.headers["X-Trace-ID"] = _trace_id.get()
        response.headers["X-Span-ID"] = _span_id.get()
        response.headers["X-Correlation-ID"] = g.correlation_id
        
        # Add response attributes
        duration = time.time() - g.start_time
        g.telemetry_span.set_attribute("http.status_code", response.status_code)
        g.telemetry_span.set_attribute("http.request.duration_ms", int(duration * 1000))
        
        # Set span status
        if response.status_code < 400:
            g.telemetry_span.set_status(Status(StatusCode.OK))
        else:
            g.telemetry_span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
        
        return response
    
    def _teardown_request(self, exception):
        from flask import g
        
        if not hasattr(g, 'telemetry_span'):
            return
        
        # Record exception if present
        if exception:
            g.telemetry_span.record_exception(exception)
            g.telemetry_span.set_status(Status(StatusCode.ERROR, str(exception)))
        
        # End span
        g.telemetry_span.end()


# Utility functions for accessing correlation information
def add_correlation_id(correlation_id: str):
    """Set correlation ID in current context"""
    _correlation_id.set(correlation_id)


def get_correlation_id() -> str:
    """Get correlation ID from current context"""
    return _correlation_id.get()


def get_trace_id() -> str:
    """Get trace ID from current context"""
    return _trace_id.get()


def get_span_id() -> str:
    """Get span ID from current context"""
    return _span_id.get()


def add_span_attributes(attributes: Dict[str, Any]):
    """Add attributes to the current active span"""
    span = trace.get_current_span()
    if span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


def add_span_event(name: str, attributes: Dict[str, Any] = None):
    """Add an event to the current active span"""
    span = trace.get_current_span()
    if span.is_recording():
        span.add_event(name, attributes or {})


def record_exception(exception: Exception, attributes: Dict[str, Any] = None):
    """Record an exception in the current active span"""
    span = trace.get_current_span()
    if span.is_recording():
        span.record_exception(exception, attributes or {})
        span.set_status(Status(StatusCode.ERROR, str(exception)))
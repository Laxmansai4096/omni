"""
OpenTelemetry and Azure Application Insights Distributed Tracing & Telemetry Service
Enterprise Forward Deployed Engineering (FDE) standard for end-to-end AI observability.
"""

import logging
import os
import time
from typing import Dict, Any, Optional
from contextlib import contextmanager

from app.config import settings

logger = logging.getLogger("telemetry")
logger.setLevel(logging.INFO)

_tracer = None
_is_initialized = False

def init_telemetry():
    """Initializes Azure Monitor OpenTelemetry if connection string is configured."""
    global _tracer, _is_initialized
    if _is_initialized:
        return

    conn_str = settings.APPLICATIONINSIGHTS_CONNECTION_STRING
    if not conn_str:
        logger.info("[Telemetry] Application Insights connection string not configured. Running in local trace mode.")
        _is_initialized = True
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry import trace

        # Configure Azure Monitor OpenTelemetry
        configure_azure_monitor(
            connection_string=conn_str,
            service_name=settings.OTEL_SERVICE_NAME
        )
        _tracer = trace.get_tracer("omnidoc.ai.platform")
        _is_initialized = True
        logger.info("[Telemetry] Azure Application Insights OpenTelemetry initialized successfully.")
    except Exception as e:
        logger.warning(f"[Telemetry] Could not initialize Azure Monitor OpenTelemetry: {e}. Falling back to standard logging.")
        _is_initialized = True

def get_tracer():
    """Returns the active OpenTelemetry tracer or a mock tracer."""
    global _tracer
    if not _is_initialized:
        init_telemetry()
    if _tracer:
        return _tracer
    
    try:
        from opentelemetry import trace
        return trace.get_tracer("omnidoc.ai.platform")
    except Exception:
        return None

def inject_trace_context(carrier: Dict[str, str]) -> Dict[str, str]:
    """Injects current W3C trace context (traceparent) into a dictionary (e.g. Service Bus message properties)."""
    try:
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
        from opentelemetry import trace
        
        current_span = trace.get_current_span()
        if current_span and current_span.get_span_context().is_valid:
            TraceContextTextMapPropagator().inject(carrier)
        else:
            import uuid
            trace_id = uuid.uuid4().hex
            span_id = uuid.uuid4().hex[:16]
            carrier["traceparent"] = f"00-{trace_id}-{span_id}-01"
    except Exception:
        import uuid
        carrier["traceparent"] = f"00-{uuid.uuid4().hex}-{uuid.uuid4().hex[:16]}-01"
    return carrier

def extract_trace_context(carrier: Dict[str, str]):
    """Extracts W3C trace context from carrier dictionary to continue distributed trace across microservices."""
    try:
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
        return TraceContextTextMapPropagator().extract(carrier)
    except Exception:
        return None

@contextmanager
def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Context manager for tracing an operation span."""
    tracer = get_tracer()
    start_time = time.time()
    
    if tracer:
        with tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, str(v) if not isinstance(v, (int, float, bool)) else v)
            try:
                yield span
            finally:
                elapsed_ms = (time.time() - start_time) * 1000
                span.set_attribute("duration_ms", elapsed_ms)
    else:
        yield None

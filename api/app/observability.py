from threading import Lock

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import get_settings


_configure_lock = Lock()
_configured = False


def configure_observability() -> None:
    """配置observability，集中封装当前模块的输入校验、核心处理和返回值约定。"""
    # 先处理输入与边界条件，再执行核心逻辑，最后返回稳定且可验证的结果。
    global _configured
    settings = get_settings()
    if _configured or not settings.otel_exporter_otlp_endpoint:
        return

    with _configure_lock:
        if _configured:
            return
        resource = Resource.create(
            {
                "service.name": settings.otel_service_name,
                "deployment.environment.name": settings.app_env,
            }
        )
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _configured = True

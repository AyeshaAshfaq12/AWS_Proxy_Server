import structlog
import logging
from datetime import datetime

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False
)

def structured_log(message: str, **kwargs) -> None:
    """Log structured messages with context"""
    logger = structlog.get_logger()
    logger.info(message, **kwargs)

def filter_headers(headers: dict) -> dict:
    """Remove sensitive headers from request"""
    sensitive_headers = {
        'authorization', 'cookie', 'x-api-key', 
        'x-auth-token', 'proxy-authorization'
    }
    return {k: v for k, v in headers.items() if k.lower() not in sensitive_headers}

def log_request(method: str, path: str, status_code: int = None, **kwargs):
    """Log HTTP request details"""
    log_data = {
        "method": method,
        "path": path,
        "timestamp": datetime.utcnow().isoformat()
    }
    if status_code:
        log_data["status_code"] = status_code
    log_data.update(kwargs)
    structured_log("HTTP Request", **log_data)

def log_error(error_type: str, message: str, **kwargs):
    """Log error with context"""
    logger = structlog.get_logger()
    logger.error(
        error_type,
        message=message,
        timestamp=datetime.utcnow().isoformat(),
        **kwargs
    )

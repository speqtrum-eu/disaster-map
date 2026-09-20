"""
Logging Configuration for Disaster Map Project.

Provides structured, production-ready logging with:
- Multiple output formats (console, JSON)
- Performance metrics integration
- Context-aware logging
- Rotating file handlers
"""

import json
import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import asdict


# Configure root logger early
_root_logger = None


def setup_logging(
    level: int = logging.INFO,
    format_type: str = "auto",  # auto, console, json
    include_performance: bool = True,
    log_file: Optional[str] = None,
) -> None:
    """
    Configure application-wide logging.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Output format type
        include_performance: Include performance metrics in logs
        log_file: Optional file path for rotating file handler
        
    Example:
        >>> setup_logging(level=logging.DEBUG, format_type="json")
    """
    global _root_logger
    
    # Get root logger
    if _root_logger is None:
        _root_logger = logging.getLogger()
    
    # Clear existing handlers to avoid duplicates
    _root_logger.handlers.clear()
    
    # Set level
    _root_logger.setLevel(level)
    
    # Create formatter based on format type
    if format_type == "json":
        handler = JSONFormatter(include_performance=include_performance)
    elif format_type == "console" or format_type == "auto":
        handler = ConsoleFormatter(
            include_performance=include_performance,
            colorize=sys.stdout.isatty()
        )
    else:
        handler = logging.StreamHandler(sys.stdout)
    
    # Add handler with formatting
    formatter = handler.formatter if hasattr(handler, 'formatter') else None
    if formatter is None:
        formatter = _root_logger.handlers[0].formatter if _root_logger.handlers else None
    
    handler.setFormatter(formatter or logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    
    _root_logger.addHandler(handler)
    
    # Add rotating file handler if specified
    if log_file:
        try:
            from logging.handlers import RotatingFileHandler
            
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                encoding="utf-8"
            )
            
            if formatter:
                file_handler.setFormatter(formatter)
                
            _root_logger.addHandler(file_handler)
            logger = logging.getLogger(__name__)
            logger.info(f"Logging to file: {log_file}")
        except Exception as e:
            print(f"Warning: Could not setup file handler: {e}", file=sys.stderr)
    
    # Log configuration
    logger = logging.getLogger(__name__)
    logger.debug(f"Logging configured: level={level}, format={format_type}")


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def __init__(self, include_performance: bool = True):
        super().__init__()
        self.include_performance = include_performance
    
    def format(self, record: logging.LogRecord) -> str:
        # Create log entry dictionary
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add performance metrics if available and requested
        if self.include_performance:
            perf_data = getattr(record, 'performance_metrics', None)
            if perf_data:
                log_entry["performance"] = perf_data
        
        # Add exception info if present
        if record.exc_info:
            import traceback
            log_entry["exception"] = traceback.format_exception(*record.exc_info)
        
        # Return JSON string
        return json.dumps(log_entry, default=str)


class ConsoleFormatter(logging.Formatter):
    """Console formatter with optional colorization."""
    
    COLORS = {
        "DEBUG": "\033[94m",      # Blue
        "INFO": "\033[92m",       # Green
        "WARNING": "\033[93m",    # Yellow
        "ERROR": "\033[91m",      # Red
        "CRITICAL": "\033[95m",   # Magenta
        "RESET": "\033[0m",       # Reset
    }
    
    def __init__(self, include_performance: bool = True, colorize: bool = False):
        super().__init__()
        self.include_performance = include_performance
        self.colorize = colorize
    
    def format(self, record: logging.LogRecord) -> str:
        # Get color for level
        color = self.COLORS.get(record.levelname, "")
        reset = self.COLORS["RESET"] if self.colorize else ""
        
        # Build message with performance metrics
        message = super().format(record)
        
        if self.include_performance:
            perf_data = getattr(record, 'performance_metrics', None)
            if perf_data:
                message += f" | PERF:{perf_data}"
        
        return f"{color}{message}{reset}"


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing frame")
    """
    return logging.getLogger(name)


def log_performance(
    record: logging.LogRecord, 
    metrics: Dict[str, float]
) -> None:
    """
    Attach performance metrics to a log record.
    
    Args:
        record: Log record to attach metrics to
        metrics: Dictionary of metric names and values
        
    Example:
        >>> log_performance(record, {"fps": 30.5, "latency_ms": 12.3})
    """
    record.performance_metrics = metrics


def get_current_stats() -> Dict[str, Any]:
    """Get current logging configuration."""
    return {
        "level": _root_logger.level if _root_logger else None,
        "handlers": len(_root_logger.handlers) if _root_logger else 0,
    }

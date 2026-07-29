import logging
import sys
import json
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Emit structured logs to stdout so the host platform owns retention."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status_code", "latency_ms", "event"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)

def get_logger(name: str):
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        c_handler = logging.StreamHandler(sys.stdout)
        c_handler.setLevel(logging.INFO)
        formatter = JsonFormatter()
        c_handler.setFormatter(formatter)
        
        logger.addHandler(c_handler)
        logger.propagate = False
        
    return logger

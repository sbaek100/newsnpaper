import logging
import json
import re
from typing import Any

MASK_KEYS = {"password", "passwordhash", "token", "authorization", "cookie", "secret", "apikey", "clientsecret", "credential", "passwd", "pw", "api_key", "private_key", "auth"}

def mask_email(email: str) -> str:
    if not isinstance(email, str) or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if not local:
        return email
    return f"{local[0]}***@{domain}"

def mask_dict(d: Any) -> Any:
    if isinstance(d, dict):
        new_d = {}
        for k, v in d.items():
            k_lower = k.lower()
            if any(token in k_lower for token in MASK_KEYS):
                new_d[k] = "***"
            elif "email" in k_lower:
                new_d[k] = mask_email(str(v))
            else:
                new_d[k] = mask_dict(v)
        return new_d
    elif isinstance(d, list):
        return [mask_dict(item) for item in d]
    return d

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt)
        }
        
        # Merge extra fields if provided as a dict
        if isinstance(record.args, dict):
            masked_args = mask_dict(record.args)
            log_record.update(masked_args)
            record.args = None  # prevent default formatting issues

        return json.dumps(log_record, ensure_ascii=False)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = JSONFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    return logger

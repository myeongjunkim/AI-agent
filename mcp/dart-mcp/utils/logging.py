"""
Simplified logging for dart-mcp
"""

import logging
import json
from datetime import datetime
from pathlib import Path

def get_logger(name: str = "dart-mcp", level: str = "INFO") -> logging.Logger:
    """
    Get a logger instance for dart-mcp
    
    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        
        # Console handler with simple text formatting (matching kc-chat-api style)
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)7s %(name)s : %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
    
    return logger
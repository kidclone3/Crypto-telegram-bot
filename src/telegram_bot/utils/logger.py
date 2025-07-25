import logging
import os
from datetime import datetime
from functools import lru_cache

@lru_cache(maxsize=1)
def setup_logger(name: str, file_path: str = None) -> logging.Logger:
    """
    Set up a logger with both file and console handlers.
    
    Args:
        name (str): Name of the logger
        file_path (str, optional): Path to the log file. If None, will use default path.
        
    Returns:
        logging.Logger: Configured logger instance
    """
    if file_path is None:
        file_path = os.path.join(
            os.environ.get("LOG_FOLDER", "."),
            f"{name}_{datetime.now().strftime('%Y-%m-%d')}.log",
        )
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Create file handler
    file_handler = logging.FileHandler(file_path)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(filename)s line %(lineno)d: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Add stdout handler
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(formatter)
    stdout_handler.setLevel(logging.INFO)
    logger.addHandler(stdout_handler)
    
    return logger

# Create default logger instance
logger = setup_logger("telegram_bot") 
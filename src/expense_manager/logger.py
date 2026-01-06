import logging
import os
from datetime import datetime

# using the folder directly to not depend on config.yaml file, in case the file is corrupted
LOG_DIR = "logs"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(lineno)d] - %(message)s"

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.log")
log_file_path = os.path.join(LOG_DIR, log_filename)

def get_logger(name):
    """
    Creates and configure a logger with the given name.

    Args:
        name(str): Name of the logger, typically __name__ of the module.
    
    Returns:
        logging.LOgger: COnfigured logger instance.
    """
    
    logger = logging.getLogger(name)
    
    if not logger.hasHandlers():
        logger.setLevel(logging.INFO)
        
        #File transfer
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        
        #console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        
        #Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

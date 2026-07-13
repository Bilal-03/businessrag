import logging
import sys
import os

def get_logger(name: str):
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Console Handler
        c_handler = logging.StreamHandler(sys.stdout)
        c_handler.setLevel(logging.INFO)
        
        # File Handler
        log_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        f_handler = logging.FileHandler(os.path.join(log_dir, 'app.log'))
        f_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(formatter)
        f_handler.setFormatter(formatter)
        
        logger.addHandler(c_handler)
        logger.addHandler(f_handler)
        
    return logger

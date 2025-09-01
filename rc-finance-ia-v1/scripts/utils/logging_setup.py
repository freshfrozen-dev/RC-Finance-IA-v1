from loguru import logger
from datetime import datetime
import os

def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    today = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"finance_{today}.log")
    
    logger.remove() # Remove o handler padrão
    logger.add(log_file, rotation="1 day", retention="7 days", level="INFO",
               format="{time} {level} {message}")
    logger.add(lambda msg: print(msg), level="INFO") # Adiciona um sink para imprimir no console

    logger.info("Configuração de logging inicializada.")



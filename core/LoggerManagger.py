import logging
from datetime import datetime
import os
import glob
from config import LOGS_DIR

class LoggerManager:
    def __init__(self, log_dir: str, max_logs: int = 10):
        self.log_dir = log_dir
        self.max_logs = max_logs
        self.logger = logging.getLogger()
        self.log_file = None

        self._configurar_logger()

    def _configurar_logger(self):
        if not self.logger.hasHandlers():
            current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.log_file = os.path.join(self.log_dir, f"log-{current_time}.log")

            os.makedirs(self.log_dir, exist_ok=True)

            file_handler = logging.FileHandler(self.log_file)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)

            self.logger.addHandler(file_handler)
            self.logger.setLevel(logging.INFO)

            print(f"Log configurado en: {self.log_file}")
            self.logger.info("Logger configurado correctamente.")

            self._limpiar_logs_antiguos()
        else:
            print("Logger ya configurado.")

    def _limpiar_logs_antiguos(self):
        log_files = sorted(
            glob.glob(os.path.join(self.log_dir, "log-*.log")),
            key=os.path.getmtime,
            reverse=True
        )
        archivos_a_eliminar = log_files[self.max_logs:]
        for archivo in archivos_a_eliminar:
            try:
                os.remove(archivo)
                self.logger.info(f"Archivo de log eliminado: {archivo}")
            except Exception as e:
                self.logger.warning(f"No se pudo eliminar el log antiguo {archivo}: {e}")

    def info(self, mensaje: str):
        print(mensaje)
        self.logger.info(mensaje)

    def error(self, mensaje: str):
        print(mensaje)
        self.logger.error(mensaje)

    def warning(self, mensaje: str):
        print(mensaje)
        self.logger.warning(mensaje)


    def obtener_nombre_logger(self):
        for handler in self.logger.handlers:
            if isinstance(handler, logging.FileHandler):
                return handler.baseFilename
        return None

log = LoggerManager(LOGS_DIR, max_logs=10)
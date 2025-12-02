"""
Logger simple con archivo por día - formato: YYYY-MM-DD.log
"""
from datetime import datetime
from pathlib import Path


class DailyLogger:
    """Logger que crea un archivo nuevo cada día"""
    
    def __init__(self, log_dir="logs"):
        self.log_dir = Path(log_dir)
        self._ensure_log_dir()
        
        # Obtener archivo de log para HOY
        self.current_log_file = self._get_todays_log_file()
        
        # Escribir encabezado si es archivo nuevo
        self._write_header()
    
    def _ensure_log_dir(self):
        """Crear directorio de logs si no existe"""
        self.log_dir.mkdir(exist_ok=True)
    
    def _get_todays_log_file(self):
        """Obtener ruta del archivo de log para hoy"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"watchdog_{today}.log"
    
    def _check_new_day(self):
        """Verificar si es un nuevo día y cambiar archivo si es necesario"""
        expected_file = self._get_todays_log_file()
        
        if self.current_log_file != expected_file:
            # ¡Es un nuevo día!
            old_file = self.current_log_file
            self.current_log_file = expected_file
            
            # Escribir encabezado en nuevo archivo
            self._write_header()
            
            # Registrar cambio en el viejo (si existe)
            if old_file.exists():
                self._write_to_file(old_file, f"[LOGGER] Continuado en {self.current_log_file.name}")
            
            # Registrar inicio en el nuevo
            self._write(f"[LOGGER] Iniciando nuevo día - Archivo anterior: {old_file.name}")
    
    def _write_header(self):
        """Escribir encabezado en archivo nuevo"""
        if not self.current_log_file.exists():
            header = f"[LOGGER] Archivo de log creado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += "[LOGGER] Formato: [FECHA] NIVEL - Mensaje\n"
            header += "="*60 + "\n"
            
            with open(self.current_log_file, 'a', encoding='utf-8') as f:
                f.write(header)
    
    def _write_to_file(self, file_path, message):
        """Escribe mensaje en archivo específico"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}\n"
        
        try:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(log_line)
        except Exception:
            # Si falla, no hacemos nada (no queremos crashear el watchdog)
            pass
    
    def _write(self, message):
        """Escribe mensaje en archivo de log actual"""
        # Primero verificar si es nuevo día
        self._check_new_day()
        
        # Escribir en archivo actual
        self._write_to_file(self.current_log_file, message)
    
    def info(self, message):
        """Log de información normal"""
        self._write(f"INFO - {message}")
        print(f"[INFO] {message}")
    
    def warning(self, message):
        """Log de advertencia"""
        self._write(f"WARNING - {message}")
        print(f"[WARNING] {message}")
    
    def error(self, message):
        """Log de error"""
        self._write(f"ERROR - {message}")
        print(f"[ERROR] {message}")
    
    def status(self, status_line):
        """Escribe 1 línea en status.txt (para Team Viewer)"""
        status_file = Path.cwd() / "status.txt"
        try:
            with open(status_file, 'w', encoding='utf-8') as f:
                f.write(f"{datetime.now().strftime('%H:%M')} - {status_line}")
        except Exception:
            pass
    
    def get_current_log_file(self):
        """Obtener nombre del archivo de log actual"""
        return self.current_log_file.name


# Logger global
logger = DailyLogger()
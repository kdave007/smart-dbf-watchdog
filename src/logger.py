"""
Logger simple para el watchdog - 1 archivo por día, rotación automática
"""
import os
from datetime import datetime
from pathlib import Path


class SimpleLogger:
    """Logger que escribe en watchdog.log y lo rota diariamente"""
    
    def __init__(self, log_dir="logs"):
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / "watchdog.log"
        self._ensure_log_dir()
        
        # Verificar si necesitamos rotar (nuevo día)
        self._rotate_if_needed()
    
    def _ensure_log_dir(self):
        """Crear directorio de logs si no existe"""
        self.log_dir.mkdir(exist_ok=True)
    
    def _rotate_if_needed(self):
        """Renombrar watchdog.log si es de otro día"""
        if not self.log_file.exists():
            return
        
        # Obtener fecha de modificación del archivo
        mod_time = datetime.fromtimestamp(self.log_file.stat().st_mtime)
        
        # Si el archivo es de ayer o antes, rotarlo
        if mod_time.date() < datetime.now().date():
            # Renombrar a YYYY-MM-DD.log
            new_name = mod_time.strftime("%Y-%m-%d.log")
            backup_file = self.log_dir / new_name
            
            # Si ya existe un backup con ese nombre, agregar número
            counter = 1
            while backup_file.exists():
                new_name = mod_time.strftime(f"%Y-%m-%d-{counter}.log")
                backup_file = self.log_dir / new_name
                counter += 1
            
            self.log_file.rename(backup_file)
            self._write(f"[LOGGER] Log rotado a {new_name}")
    
    def _write(self, message):
        """Escribe mensaje en el archivo de log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}\n"
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_line)
        except Exception:
            # Si falla, no hacemos nada (no queremos crashear el watchdog)
            pass
    
    def info(self, message):
        """Log de información normal"""
        self._write(f"INFO - {message}")
        print(f"[INFO] {message}")  # También en consola para desarrollo
    
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
                f.write(status_line)
        except Exception:
            pass


# Logger global para usar fácilmente
logger = SimpleLogger()
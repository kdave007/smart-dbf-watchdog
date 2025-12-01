"""
Lock Manager para el Watchdog
Usa el mismo patrón que smart_dbf.lock para consistencia
"""

import os
import json
from datetime import datetime
from pathlib import Path


class LockManager:
    """Maneja el lock file para prevenir múltiples instancias del watchdog"""
    
    LOCK_TIMEOUT_MINUTES = 5  # Más corto que 40min (para watchdog)
    TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    def __init__(self):
        # Misma carpeta que tu app principal
        self.lock_path = Path.cwd() / "watchdog.lock"
        self.owns_lock = False
    
    def check_and_acquire(self) -> bool:
        """
        Verifica si hay otro watchdog corriendo.
        
        Returns:
            True: Podemos continuar (no hay otro o lock huérfano)
            False: Hay otro watchdog corriendo, debemos salir
        """
        # No existe lock = primer watchdog
        if not self.lock_path.exists():
            return True
        
        try:
            # Leer lock existente
            with open(self.lock_path, 'r') as f:
                lock_data = json.load(f)
            
            timestamp_str = lock_data.get('timestamp', '')
            lock_pid = lock_data.get('pid', 0)
            
            # Parsear timestamp
            lock_time = datetime.strptime(timestamp_str, self.TIMESTAMP_FORMAT)
            current_time = datetime.now()
            
            # Calcular edad del lock en minutos
            minutes_old = (current_time - lock_time).total_seconds() / 60
            
            # DECISIÓN:
            if minutes_old < self.LOCK_TIMEOUT_MINUTES:
                # Lock reciente (< 5 min) → hay otro watchdog activo
                print(f"[LOCK] Otro watchdog activo (PID {lock_pid}, hace {minutes_old:.1f} min)")
                return False
            else:
                # Lock viejo (> 5 min) → proceso anterior probablemente crasheó
                print(f"[LOCK] Lock huérfano detectado ({minutes_old:.1f} min), removiendo...")
                self._remove_orphaned_lock()
                return True
                
        except Exception as e:
            # Lock corrupto o ilegible
            print(f"[LOCK] Error leyendo lock: {e}, removiendo...")
            self.lock_path.unlink(missing_ok=True)
            return True
    
    def create_lock(self):
        """Crea nuestro lock file"""
        lock_data = {
            "timestamp": datetime.now().strftime(self.TIMESTAMP_FORMAT),
            "pid": os.getpid(),
            "type": "watchdog"
        }
        
        with open(self.lock_path, 'w') as f:
            json.dump(lock_data, f, indent=2)
        
        self.owns_lock = True
        print(f"[LOCK] Lock creado (PID {os.getpid()})")
    
    def _remove_orphaned_lock(self):
        """Remueve lock file huérfano (de proceso anterior que crasheó)"""
        try:
            if self.lock_path.exists():
                self.lock_path.unlink()
                print("[LOCK] Lock huérfano removido")
        except Exception as e:
            print(f"[LOCK] Error removiendo lock: {e}")
    
    def remove_lock(self):
        """Remueve nuestro lock (al salir normalmente)"""
        if self.owns_lock and self.lock_path.exists():
            try:
                self.lock_path.unlink()
                self.owns_lock = False
                print("[LOCK] Lock removido (salida normal)")
            except Exception as e:
                print(f"[LOCK] Error removiendo nuestro lock: {e}")
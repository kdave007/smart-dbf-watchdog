"""
Lock Manager para el Watchdog
Usa el mismo patrón que smart_dbf.lock para consistencia
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path


class LockManager:
    """Maneja el lock file para prevenir múltiples instancias del watchdog"""
    
    LOCK_TIMEOUT_MINUTES = 5  # Más corto que 40min (para watchdog)
    TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    def __init__(self):
        # Determinar directorio del exe/script para ubicar el lock
        if getattr(sys, 'frozen', False):
            # Running as exe
            script_dir = Path(sys.executable).parent
        else:
            # Running as script
            script_dir = Path(__file__).parent.parent  # src/ -> project root
        
        self.lock_path = script_dir / "watchdog.lock"
        self.owns_lock = False
        self._last_refresh = None
    
    def check_and_acquire(self) -> bool:
        """
        Verifica si hay otro watchdog corriendo y adquiere el lock atómicamente.
        
        Returns:
            True: Lock adquirido exitosamente
            False: Hay otro watchdog corriendo, debemos salir
        """
        # Si el lock existe, verificar si es válido
        if self.lock_path.exists():
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
                    # Lock viejo (> 5 min) → verificar si el proceso realmente existe
                    if self._is_process_running(lock_pid):
                        print(f"[LOCK] Lock viejo ({minutes_old:.1f} min) pero proceso {lock_pid} AÚN VIVO → rechazando")
                        return False
                    else:
                        print(f"[LOCK] Lock huérfano detectado ({minutes_old:.1f} min, PID {lock_pid} muerto), removiendo...")
                        self._remove_orphaned_lock()
                    
            except Exception as e:
                # Lock corrupto o ilegible
                print(f"[LOCK] Error leyendo lock: {e}, removiendo...")
                self.lock_path.unlink(missing_ok=True)
        
        # Crear el lock con modo exclusivo (falla si ya existe)
        # Esto previene race conditions entre múltiples procesos
        try:
            # 'x' = exclusive creation, falla si el archivo existe
            with open(self.lock_path, 'x') as f:
                lock_data = {
                    "timestamp": datetime.now().strftime(self.TIMESTAMP_FORMAT),
                    "pid": os.getpid(),
                    "type": "watchdog"
                }
                json.dump(lock_data, f, indent=2)
            
            self.owns_lock = True
            self._last_refresh = datetime.now()
            print(f"[LOCK] Lock creado (PID {os.getpid()})")
            return True
            
        except FileExistsError:
            # Otro proceso creó el lock justo antes que nosotros
            print(f"[LOCK] Otro watchdog se adelantó (race condition detectada)")
            return False
        except Exception as e:
            print(f"[LOCK] Error creando lock: {e}")
            return False
    
    def _is_process_running(self, pid: int) -> bool:
        """Verifica si un proceso con el PID dado está corriendo usando tasklist de Windows."""
        try:
            # Usar tasklist para verificar si el PID existe
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}', '/NH'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5
            )
            
            # Si el PID existe, tasklist lo mostrará en la salida
            # Si no existe, dirá "INFO: No tasks are running..."
            output = result.stdout.lower()
            
            # Verificar que el proceso existe Y que sea watchdog
            if str(pid) in output and 'watchdog' in output:
                return True
            
            return False
            
        except Exception:
            # Si no podemos verificar, asumir que está corriendo (conservador)
            return True
    
    def create_lock(self):
        """
        DEPRECATED: Usar check_and_acquire() que es atómico.
        Mantenido por compatibilidad pero no hace nada.
        """
        # Ya no se usa, check_and_acquire() crea el lock
        pass
    
    def refresh_lock(self) -> bool:
        """Actualiza el timestamp del lock para indicar que seguimos vivos."""
        if not self.owns_lock:
            return False
        if not self.lock_path.exists():
            return False

        try:
            lock_data = {
                "timestamp": datetime.now().strftime(self.TIMESTAMP_FORMAT),
                "pid": os.getpid(),
                "type": "watchdog"
            }
            with open(self.lock_path, 'w') as f:
                json.dump(lock_data, f, indent=2)

            self._last_refresh = datetime.now()
            return True
        except Exception:
            return False
    
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
                self._last_refresh = None
                print("[LOCK] Lock removido (salida normal)")
            except Exception as e:
                print(f"[LOCK] Error removiendo nuestro lock: {e}")
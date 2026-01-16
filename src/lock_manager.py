"""
Lock Manager para el Watchdog
Usa Windows Named Mutex para prevenir múltiples instancias de forma atómica
"""

import os
import sys
import json
import time
import subprocess
import ctypes
from datetime import datetime
from pathlib import Path
from .logger import logger

# Windows API constants
ERROR_ALREADY_EXISTS = 183

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
        self._mutex_handle = None
    
    def check_and_acquire(self, max_retries=3) -> bool:
        """
        Verifica si hay otro watchdog corriendo y adquiere el lock atómicamente usando Windows Mutex.
        
        Args:
            max_retries: Número de intentos para manejar race conditions
        
        Returns:
            True: Lock adquirido exitosamente
            False: Hay otro watchdog corriendo, debemos salir
        """
        # PASO 1: Intentar adquirir mutex de Windows (100% atómico, sin race conditions)
        mutex_name = "Global\\SmartDBFWatchdogMutex"
        
        try:
            # Crear o abrir el mutex
            self._mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, True, mutex_name)
            last_error = ctypes.windll.kernel32.GetLastError()
            
            if last_error == ERROR_ALREADY_EXISTS:
                # Otro watchdog ya tiene el mutex
                logger.warning(f"[LOCK] Otro watchdog activo (mutex ya existe)")
                if self._mutex_handle:
                    ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
                    self._mutex_handle = None
                return False
            
            logger.info(f"[LOCK] Mutex de Windows adquirido exitosamente (PID {os.getpid()})")
            
        except Exception as e:
            logger.error(f"[LOCK] Error creando mutex de Windows: {e}")
            return False
        
        # PASO 2: Crear archivo de lock para compatibilidad y debugging
        import random
        
        # Agregar un pequeño delay aleatorio para evitar race conditions en boot simultáneo
        initial_delay = random.uniform(0.1, 0.5)  # 100-500ms
        time.sleep(initial_delay)
        logger.info(f"[LOCK] Delay inicial: {initial_delay:.3f}s para evitar race condition")
        
        for attempt in range(max_retries):
            if attempt > 0:
                # Esperar un poco entre reintentos para evitar race conditions
                wait_ms = attempt * 100  # 100ms, 200ms, etc.
                time.sleep(wait_ms / 1000.0)
                logger.info(f"[LOCK] Reintento {attempt + 1}/{max_retries}...")
            
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
                        logger.warning(f"[LOCK] Otro watchdog activo (PID {lock_pid}, hace {minutes_old:.1f} min)")
                        return False
                    else:
                        # Lock viejo (> 5 min) → verificar si el proceso realmente existe
                        if self._is_process_running(lock_pid):
                            logger.warning(f"[LOCK] Lock viejo ({minutes_old:.1f} min) pero proceso {lock_pid} AÚN VIVO → rechazando")
                            return False
                        else:
                            logger.info(f"[LOCK] Lock huérfano detectado ({minutes_old:.1f} min, PID {lock_pid} muerto), removiendo...")
                            self._remove_orphaned_lock()
                    
                except Exception as e:
                    # Lock corrupto o ilegible
                    logger.error(f"[LOCK] Error leyendo lock: {e}, removiendo...")
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
                logger.info(f"[LOCK] Lock creado exitosamente (PID {os.getpid()})")
                
                # Verificar que realmente somos dueños del lock
                time.sleep(0.05)  # Esperar 50ms para que el sistema de archivos se sincronice
                try:
                    with open(self.lock_path, 'r') as f:
                        verify_data = json.load(f)
                    if verify_data.get('pid') != os.getpid():
                        logger.error(f"[LOCK] VERIFICACIÓN FALLÓ: Lock tiene PID {verify_data.get('pid')}, esperábamos {os.getpid()}")
                        self.owns_lock = False
                        return False
                    logger.info(f"[LOCK] Verificación OK - somos dueños del lock")
                except Exception as e:
                    logger.error(f"[LOCK] Error verificando lock: {e}")
                    self.owns_lock = False
                    return False
                
                return True
                
            except FileExistsError:
                # Otro proceso creó el lock justo antes que nosotros
                logger.warning(f"[LOCK] Race condition: otro watchdog creó el lock primero")
                # Continuar al siguiente intento
                continue
            except Exception as e:
                logger.error(f"[LOCK] Error creando lock: {e}")
                return False
        
        # Si llegamos aquí, todos los intentos fallaron
        logger.error(f"[LOCK] No se pudo adquirir lock después de {max_retries} intentos")
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
            
            # Verificar si el PID existe en la salida
            # No verificamos el nombre porque puede ser python.exe (script) o watchdog.exe (compilado)
            if 'info: no tasks' not in output and str(pid) in output:
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
            logger.warning("[LOCK] Intento de refresh sin poseer el lock")
            return False
        if not self.lock_path.exists():
            logger.error("[LOCK] Lock file desapareció - no se puede refrescar")
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
        except Exception as e:
            logger.error(f"[LOCK] Error refrescando lock: {e}")
            return False
    
    def _remove_orphaned_lock(self):
        """Remueve lock file huérfano (de proceso anterior que crasheó)"""
        try:
            if self.lock_path.exists():
                self.lock_path.unlink()
                logger.info("[LOCK] Lock huérfano removido")
        except Exception as e:
            logger.error(f"[LOCK] Error removiendo lock: {e}")
    
    def remove_lock(self):
        """Remueve nuestro lock (al salir normalmente)"""
        # Liberar mutex de Windows
        if self._mutex_handle:
            try:
                ctypes.windll.kernel32.ReleaseMutex(self._mutex_handle)
                ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
                self._mutex_handle = None
                logger.info("[LOCK] Mutex de Windows liberado")
            except Exception as e:
                logger.error(f"[LOCK] Error liberando mutex: {e}")
        
        # Remover archivo de lock
        if self.owns_lock and self.lock_path.exists():
            try:
                self.lock_path.unlink()
                self.owns_lock = False
                self._last_refresh = None
                logger.info("[LOCK] Lock removido (salida normal)")
            except Exception as e:
                logger.error(f"[LOCK] Error removiendo nuestro lock: {e}")
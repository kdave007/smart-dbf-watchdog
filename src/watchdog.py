"""
Watchdog SIMPLIFICADO - Solo verifica lock file
"""
import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from .logger import logger


class AppWatchdog:
    """
    Watchdog que solo verifica el lock file JSON de tu app
    NO verifica procesos de Windows
    """
    
    def __init__(self, app_name="app_principal.exe", lock_file="app.lock", 
                 timeout_minutes=50, lock_time_format="%Y-%m-%d %H:%M:%S"):
        """
        Args:
            app_name: Solo para logging y ejecutar
            lock_file: Archivo lock JSON que tu app crea
            timeout_minutes: Máximo tiempo antes de considerar colgada
            lock_time_format: Formato del timestamp en JSON
        """
        self.app_name = app_name
        self.lock_file = Path(lock_file)
        self.timeout_minutes = timeout_minutes
        self.lock_time_format = lock_time_format
        
        # Determinar directorio base (donde están los exes)
        if getattr(sys, 'frozen', False):
            # Running as exe
            self.base_dir = Path(sys.executable).parent
        else:
            # Running as script - usar project root
            self.base_dir = Path(__file__).parent.parent

        # Si lock_file es relativo, asumir que vive junto al watchdog/app (base_dir)
        if not self.lock_file.is_absolute():
            self.lock_file = (self.base_dir / self.lock_file).resolve()
        
        logger.info(f"🛡️ Watchdog simplificado:")
        logger.info(f"   App: {self.app_name}")
        logger.info(f"   Lock file: {self.lock_file}")
        logger.info(f"   Timeout: {self.timeout_minutes} min")
        logger.info(f"   Lógica: Solo verifica lock file, NO procesos")
    
    def _read_lock_file(self):
        """Lee y parsea el lock file JSON"""
        if not self.lock_file.exists():
            logger.info(f"📭 Lock file NO existe: {self.lock_file}")
            return None
        
        try:
            with open(self.lock_file, 'r') as f:
                data = json.load(f)
            
            logger.info(f"📖 Lock file leído: timestamp={data.get('timestamp')}, pid={data.get('pid')}")
            return data
            
        except OSError as e:
            if e.winerror == 233:
                logger.warning(f"⚠️  Broken pipe al leer lock file (proceso terminado inesperadamente)")
                return None
            logger.error(f"❌ Error OS leyendo lock file: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error leyendo lock file: {e}")
            return None
    
    def _get_lock_age_minutes(self):
        """Calcula edad del lock file en minutos"""
        data = self._read_lock_file()
        if not data:
            return None
        
        timestamp_str = data.get('timestamp')
        if not timestamp_str:
            logger.error("❌ Lock file no tiene timestamp")
            return None
        
        try:
            lock_time = datetime.strptime(timestamp_str, self.lock_time_format)
            current_time = datetime.now()
            age_seconds = (current_time - lock_time).total_seconds()
            age_minutes = age_seconds / 60
            
            logger.info(f"⏱️  Lock file edad: {age_minutes:.1f} minutos")
            return age_minutes
            
        except Exception as e:
            logger.error(f"❌ Error calculando edad: {e}")
            return None
    
    def check_app_status(self):
        """
        Verifica estado BASADO SOLO EN LOCK FILE
        
        Returns:
            "not_running" - No hay lock file
            "running_ok"  - Lock file existe y es reciente (< timeout)
            "hung"        - Lock file existe y es viejo (> timeout)
        """
        logger.info("🔍 Verificando estado (solo por lock file)...")
        
        # 1. ¿Existe lock file?
        if not self.lock_file.exists():
            logger.info("📭 NO hay lock file → 'not_running'")
            return "not_running"
        
        # 2. Calcular edad
        lock_age = self._get_lock_age_minutes()
        if lock_age is None:
            logger.info("❓ No se pudo calcular edad → 'running_ok' (asumir bien)")
            return "running_ok"
        
        # 3. Decidir basado en edad
        if lock_age > self.timeout_minutes:
            logger.info(f"⚠️  Lock viejo ({lock_age:.1f} min > {self.timeout_minutes} min) → 'hung'")
            return "hung"
        else:
            logger.info(f"✅ Lock reciente ({lock_age:.1f} min) → 'running_ok'")
            return "running_ok"
    
    def start_app(self):
        """Ejecuta la app"""
        try:
            logger.info(f"🚀 Ejecutando {self.app_name}...")
            
            # Ambos exes están en el mismo directorio (self.base_dir)
            app_path = Path(self.app_name)
            
            if app_path.is_absolute():
                # Ruta absoluta proporcionada
                app_dir = app_path.parent
                app_exe = str(app_path)
            else:
                # Ruta relativa: buscar en base_dir (donde está el watchdog)
                app_dir = self.base_dir
                app_exe = str(self.base_dir / app_path)
            
            logger.info(f"📂 Directorio de trabajo: {app_dir}")
            logger.info(f"📄 Ejecutable: {app_exe}")
            
            # Save current directory
            original_cwd = os.getcwd()
            
            try:
                # Change to the app directory before launching
                os.chdir(str(app_dir))
                logger.info(f"🔄 Changed working directory to: {os.getcwd()}")
                
                # Launch the app - it will inherit the current working directory
                subprocess.Popen(
                    [app_exe],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
            finally:
                # Always restore original directory
                os.chdir(original_cwd)
                logger.info(f"🔄 Restored working directory to: {os.getcwd()}")
            
            logger.info(f"✅ {self.app_name} iniciada")
            
            # Esperar 30 segundos para que cree el lock file
            logger.info("⏳ Esperando creación de lock file...")
            time.sleep(30)
            
            # Verificar que se creó el lock file
            if self.lock_file.exists():
                logger.info(f"✅ Lock file creado: {self.lock_file}")
            else:
                logger.warning(f"⚠️  Lock file NO creado después de 30 segundos")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error ejecutando {self.app_name}: {e}")
            return False
    
    def kill_app(self):
        """
        Mata la app usando el PID del lock file
        (Más preciso que por nombre)
        """
        logger.warning("⚠️  Intentando terminar app...")
        
        # Leer PID del lock file
        data = self._read_lock_file()
        pid = data.get('pid') if data else None
        
        if pid:
            logger.info(f"🎯 Terminando por PID: {pid}")
            
            # Intentar terminación elegante
            try:
                subprocess.run(
                    ['taskkill', '/PID', str(pid), '/T'],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=10
                )
                logger.info(f"📤 Terminación enviada a PID {pid}")
            except Exception as e:
                logger.warning(f"⚠️  Error terminando PID {pid}: {e}")
        else:
            logger.warning("⚠️  No hay PID en lock file, terminando por nombre")
        
        # También intentar por nombre por si acaso
        try:
            subprocess.run(
                ['taskkill', '/IM', self.app_name, '/T'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10
            )
            logger.info(f"📤 Terminación enviada por nombre: {self.app_name}")
        except Exception as e:
            logger.warning(f"⚠️  Error terminando por nombre: {e}")
        
        # Esperar y verificar
        logger.info("⏳ Esperando 30 segundos...")
        time.sleep(30)
        
        # Verificar si el lock file fue eliminado
        if self.lock_file.exists():
            logger.error("❌ Lock file aún existe - app probablemente sigue corriendo")
            
            # Forzar terminación
            try:
                subprocess.run(
                    ['taskkill', '/F', '/IM', self.app_name, '/T'],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=10
                )
                logger.info("💥 Terminación forzada enviada")
            except Exception as e:
                logger.error(f"💥 Error en terminación forzada: {e}")
                return False
        else:
            logger.info("✅ Lock file eliminado - app terminada")
        
        return True
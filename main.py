"""
Watchdog Principal - Con recuperación robusta de errores
"""
import os
import sys
import time
import atexit
import traceback
from datetime import datetime

from src.lock_manager import LockManager
from src.logger import logger
from src.schedule_manager import scheduler
from src.watchdog import AppWatchdog


# ============================================
# CONFIGURACIÓN
# ============================================
CONFIG = {
    #"app_name": "smart-dbf_local.exe",
     "app_name": "smart-dbf_v2.1_32b.exe",
    "lock_file": "smart_dbf.lock",
    "timeout_minutes": 70,
    "check_interval_minutes": 15,  # Cambia a 15 para producción
    "wait_after_action_minutes": 2,
    "time_ranges": [(0, 6), (9, 24)],  # 0-6hrs y 9-24hrs
}

# Calcular segundos
CONFIG["check_interval"] = CONFIG["check_interval_minutes"] * 60
CONFIG["wait_after_action"] = CONFIG["wait_after_action_minutes"] * 60


def interruptible_sleep(seconds):
    """
    Duerme en chunks de 10 segundos, verificando stop.txt cada vez.
    Retorna True si se detectó stop.txt, False si completó el sleep normal.
    """
    elapsed = 0
    chunk = 10  # Verificar cada 10 segundos
    
    # Obtener directorio del script/exe
    if getattr(sys, 'frozen', False):
        # Running as exe
        script_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        script_dir = os.path.dirname(os.path.abspath(__file__))
    
    stop_file = os.path.join(script_dir, "stop.txt")
    
    while elapsed < seconds:
        if os.path.exists(stop_file):
            return True  # Señal de stop detectada
        
        # Dormir el menor entre: tiempo restante o chunk
        sleep_time = min(chunk, seconds - elapsed)
        time.sleep(sleep_time)
        elapsed += sleep_time
    
    return False  # Sleep completado sin interrupción


def check_startup_stop_file():
    """
    Verifica stop.txt al inicio del watchdog.
    
    Returns:
        True si debe continuar, False si debe detenerse
    """
    # Determinar ruta del stop.txt
    if getattr(sys, 'frozen', False):
        script_dir = os.path.dirname(sys.executable)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    
    stop_file = os.path.join(script_dir, "stop.txt")
    
    if not os.path.exists(stop_file):
        return True  # No existe, continuar
    
    try:
        # Leer contenido del archivo
        with open(stop_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # Si contiene "FROZEN" (case-insensitive), detener y mantener archivo
        if content.upper() == "FROZEN":
            logger.info("🛑 stop.txt contiene 'FROZEN' - Deteniendo watchdog y manteniendo archivo")
            logger.status("🛑 Detenido por FROZEN en stop.txt")
            return False
        
        # Si está vacío o contiene cualquier otro texto, eliminar y continuar
        logger.info(f"🗑️ stop.txt encontrado (contenido: '{content[:20]}...') - Eliminando y continuando")
        os.remove(stop_file)
        logger.info("✅ stop.txt eliminado, watchdog continuará")
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ Error leyendo stop.txt: {e} - Continuando de todas formas")
        return True


def main():
    """Función principal - ROBUSTA contra errores"""
    
    try:
        # Mostrar banner
        logger.info("=" * 60)
        logger.info("🛡️  WATCHDOG 1.7")
        logger.info(f"📅 Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"📌 CWD: {os.getcwd()}")
        logger.info(f"📌 Frozen: {getattr(sys, 'frozen', False)}")
        logger.info(f"📌 sys.executable: {sys.executable}")
        logger.info(f"📌 __file__: {__file__}")
        logger.info("=" * 60)
        
        # Verificar stop.txt al inicio
        if not check_startup_stop_file():
            return 1
        
        # Mostrar configuración
        logger.info(f"⚙️  CONFIGURACIÓN:")
        logger.info(f"   📱 App: {CONFIG['app_name']}")
        logger.info(f"   🔒 Lock: {CONFIG['lock_file']}")
        logger.info(f"   ⏱️  Timeout: {CONFIG['timeout_minutes']} min")
        logger.info(f"   🔄 Revisión: cada {CONFIG['check_interval_minutes']} min")
        ranges_str = ", ".join([f"{start}:00-{end}:00" for start, end in CONFIG['time_ranges']])
        logger.info(f"   🕐 Horario: {ranges_str}")
        logger.info("=" * 60)
        
        # 1. INICIALIZAR WATCHDOG
        app_watchdog = AppWatchdog(
            app_name=CONFIG["app_name"],
            lock_file=CONFIG["lock_file"],
            timeout_minutes=CONFIG["timeout_minutes"],
            lock_time_format="%Y-%m-%d %H:%M:%S"
        )
        
        # 2. VERIFICAR QUE NO HAY OTRO WATCHDOG Y ADQUIRIR LOCK
        lock_manager = LockManager()

        logger.info(f"🔒 Watchdog lock file: {lock_manager.lock_path}")
        
        if not lock_manager.check_and_acquire():
            logger.error("❌ Ya hay otro watchdog corriendo. Saliendo.")
            logger.status("❌ ERROR: Otro watchdog activo")
            return 1
        
        # Lock ya fue creado por check_and_acquire()
        logger.info(f"🔒 Watchdog registrado (PID {os.getpid()})")
        
        # 3. CONFIGURAR CLEANUP (se ejecuta incluso si crashea)
        atexit.register(lambda: lock_manager.remove_lock())
        atexit.register(lambda: logger.info("👋 Watchdog finalizado"))
        atexit.register(lambda: logger.status("💤 Watchdog detenido"))
        
        # 4. REGISTRAR HANDLER PARA SEÑALES DE CRASH
        def handle_crash(signum=None, frame=None):
            """Maneja crashes inesperados"""
            logger.error("💥 CRASH DETECTADO - Limpiando...")
            lock_manager.remove_lock()
            logger.status("💥 Watchdog crasheó")
            sys.exit(1)
        
        # En Windows no hay señales UNIX, pero podemos registrar con atexit
        atexit.register(handle_crash)
        
        logger.status(f"✅ Activo | Robustez: ALTA | Revisión: {CONFIG['check_interval_minutes']}min")
        
    except Exception as e:
        # ERROR EN INICIALIZACIÓN - NO PODEMOS CONTINUAR
        logger.error(f"💥 ERROR CRÍTICO en inicialización: {e}")
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        logger.status(f"❌ ERROR INICIAL: {str(e)[:40]}...")
        
        # Registrar para diagnóstico
        try:
            with open("watchdog_crash_init.log", "a") as f:
                f.write(f"[{datetime.now()}] INIT CRASH: {str(e)}\n")
                f.write(traceback.format_exc() + "\n")
        except:
            pass
        
        return 1
    
    # 5. LOOP PRINCIPAL CON RECUPERACIÓN POR CICLO
    ciclo = 0
    ejecuciones = 0
    reinicios = 0
    errores_recientes = 0
    
    # Refrescar watchdog.lock antes de que expire (LOCK_TIMEOUT_MINUTES=5)
    last_lock_refresh = datetime.now()
    lock_refresh_interval_seconds = 10  # Refrescar cada 10 segundos
    
    logger.info("🔁 Iniciando loop principal con recuperación...")
    
    # Determinar ruta del stop.txt una vez
    if getattr(sys, 'frozen', False):
        script_dir = os.path.dirname(sys.executable)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    stop_file = os.path.join(script_dir, "stop.txt")
    
    while True:
        try:
            # Mantener vivo el watchdog.lock para evitar que otro scheduler lo tome como huérfano
            now = datetime.now()
            if (now - last_lock_refresh).total_seconds() >= lock_refresh_interval_seconds:
                lock_manager.refresh_lock()
                last_lock_refresh = now

            # Chequear archivo de stop para finalizar el watchdog
            if os.path.exists(stop_file):
                logger.info("[STOP] 🛑 stop.txt encontrado. Saliendo del watchdog...")
                try:
                    os.remove(stop_file)
                    logger.info("[STOP] 🗑️ stop.txt eliminado")
                except Exception as e:
                    logger.warning(f"[STOP] ⚠️ No se pudo eliminar stop.txt: {e}")
                logger.status("🛑 Detenido por stop.txt")
                break

            ciclo += 1
            hora_actual = datetime.now().strftime('%H:%M')
            
            logger.info(f"🔄 Ciclo #{ciclo} - {hora_actual}")
            
            # Verificar si estamos en horario
            current_hour = datetime.now().hour
            in_schedule = any(start <= current_hour < end for start, end in CONFIG["time_ranges"])
            
            if in_schedule:
                ranges_str = ", ".join([f"{start}:00-{end}:00" for start, end in CONFIG['time_ranges']])
                logger.info(f"✅ En horario ({ranges_str})")
                
                # Verificar estado de la app
                estado = app_watchdog.check_app_status()
                logger.info(f"📊 Estado: {estado}")
                
                if estado == "not_running":
                    logger.info(f"🚀 Ejecutando {CONFIG['app_name']}...")
                    logger.status(f"🚀 Ejecutando {CONFIG['app_name']}...")
                    
                    if app_watchdog.start_app():
                        ejecuciones += 1
                        logger.info(f"✅ App iniciada (total: {ejecuciones})")
                        logger.status("✅ App en ejecución")
                        if interruptible_sleep(CONFIG["wait_after_action"]):
                            logger.info("[STOP] stop.txt detectado durante espera")
                            try:
                                os.remove(stop_file)
                                logger.info("[STOP] 🗑️ stop.txt eliminado")
                            except Exception as e:
                                logger.warning(f"[STOP] ⚠️ No se pudo eliminar stop.txt: {e}")
                            logger.status("🛑 Detenido por stop.txt")
                            break
                    else:
                        logger.error("❌ Error al iniciar app")
                        logger.status("❌ Error al iniciar")
                        errores_recientes += 1
                
                elif estado == "hung":
                    logger.warning(f"⚠️ App colgada (> {CONFIG['timeout_minutes']}min)")
                    logger.status("⚠️ App colgada, reiniciando...")
                    
                    if app_watchdog.kill_app():
                        reinicios += 1
                        logger.info(f"♻️ App terminada (reinicios: {reinicios})")
                        if interruptible_sleep(10):
                            logger.info("[STOP] stop.txt detectado durante espera")
                            try:
                                os.remove(stop_file)
                                logger.info("[STOP] 🗑️ stop.txt eliminado")
                            except Exception as e:
                                logger.warning(f"[STOP] ⚠️ No se pudo eliminar stop.txt: {e}")
                            logger.status("🛑 Detenido por stop.txt")
                            break
                        
                        if app_watchdog.start_app():
                            ejecuciones += 1
                            logger.info("✅ App reiniciada")
                            logger.status("✅ App reiniciada")
                            if interruptible_sleep(CONFIG["wait_after_action"]):
                                logger.info("[STOP] stop.txt detectado durante espera")
                                try:
                                    os.remove(stop_file)
                                    logger.info("[STOP] 🗑️ stop.txt eliminado")
                                except Exception as e:
                                    logger.warning(f"[STOP] ⚠️ No se pudo eliminar stop.txt: {e}")
                                logger.status("🛑 Detenido por stop.txt")
                                break
                        else:
                            logger.error("❌ Error al reiniciar")
                            logger.status("❌ Error al reiniciar")
                            errores_recientes += 1
                    else:
                        logger.error("❌ No se pudo recuperar app")
                        logger.status("❌ App colgada sin recuperación")
                        errores_recientes += 1
                
                elif estado == "running_ok":
                    logger.info("👍 App ejecutándose normalmente")
                    logger.status("👍 App OK")
                    errores_recientes = 0
            else:
                logger.info(f"😴 Fuera de horario")
                current_hour = datetime.now().hour
                next_range = min([start for start, end in CONFIG['time_ranges'] if start > current_hour], default=CONFIG['time_ranges'][0][0])
                logger.status(f"💤 Durmiendo hasta {next_range}:00")
            
            minutos = CONFIG["check_interval_minutes"]
            logger.info(f"💤 Durmiendo {minutos} minutos...")
            if interruptible_sleep(CONFIG["check_interval"]):
                logger.info("[STOP] stop.txt detectado durante sleep")
                try:
                    os.remove(stop_file)
                    logger.info("[STOP] 🗑️ stop.txt eliminado")
                except Exception as e:
                    logger.warning(f"[STOP] ⚠️ No se pudo eliminar stop.txt: {e}")
                logger.status("🛑 Detenido por stop.txt")
                break
            
        except KeyboardInterrupt:
            logger.info("🛑 Detenido por usuario")
            logger.status("🛑 Detenido por usuario")
            break
            
        except OSError as e:
            if hasattr(e, 'winerror') and e.winerror == 233:
                logger.warning(f"⚠️  Broken pipe detectado en ciclo #{ciclo} (proceso terminado inesperadamente)")
                logger.info("🔄 Continuando con el siguiente ciclo...")
                errores_recientes = 0
            else:
                errores_recientes += 1
                logger.error(f"⚠️  Error OS en ciclo #{ciclo}: {e}")
                logger.error(f"📋 Traceback parcial: {traceback.format_exc()[:500]}...")
                logger.status(f"⚠️  Error temporal, continuando...")
            
        except Exception as e:
            errores_recientes += 1
            logger.error(f"⚠️  Error en ciclo #{ciclo}: {e}")
            logger.error(f"📋 Traceback parcial: {traceback.format_exc()[:500]}...")
            logger.status(f"⚠️  Error temporal, continuando...")
            
            try:
                with open("watchdog_errors.log", "a") as f:
                    f.write(f"[{datetime.now()}] CYCLE {ciclo} ERROR: {str(e)}\n")
                    f.write(traceback.format_exc() + "\n")
            except:
                pass
            
            if errores_recientes >= 3:
                wait_time = 300
                logger.warning(f"⚠️  Muchos errores seguidos ({errores_recientes}), esperando {wait_time//60} min...")
                if interruptible_sleep(wait_time):
                    logger.info("[STOP] stop.txt detectado durante espera de error")
                    try:
                        os.remove(stop_file)
                        logger.info("[STOP] 🗑️ stop.txt eliminado")
                    except Exception as e:
                        logger.warning(f"[STOP] ⚠️ No se pudo eliminar stop.txt: {e}")
                    logger.status("🛑 Detenido por stop.txt")
                    break
            else:
                if interruptible_sleep(CONFIG["check_interval"]):
                    logger.info("[STOP] stop.txt detectado durante espera de error")
                    try:
                        os.remove(stop_file)
                        logger.info("[STOP] 🗑️ stop.txt eliminado")
                    except Exception as e:
                        logger.warning(f"[STOP] ⚠️ No se pudo eliminar stop.txt: {e}")
                    logger.status("🛑 Detenido por stop.txt")
                    break
    
    logger.info("=" * 60)
    logger.info(f"📊 RESUMEN FINAL:")
    logger.info(f"   Ciclos completados: {ciclo}")
    logger.info(f"   Ejecuciones de app: {ejecuciones}")
    logger.info(f"   Reinicios por colgadas: {reinicios}")
    logger.info(f"   Errores capturados: {errores_recientes}")
    logger.info("=" * 60)
    logger.info("👋 Watchdog finalizado correctamente")
    
    return 0


if __name__ == "__main__":
    # Cambiar al directorio del script
    try:
        if getattr(sys, 'frozen', False):
            os.chdir(os.path.dirname(sys.executable))
        else:
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
    except Exception as e:
        print(f"❌ ERROR cambiando directorio: {e}")
        sys.exit(1)
    
    # Ejecutar con captura de errores final
    try:
        exit_code = main()
    except Exception as e:
        print(f"💥 ERROR NO CAPTURADO: {e}")
        print(traceback.format_exc())
        exit_code = 1
    
    sys.exit(exit_code)